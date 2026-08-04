import re
from fastapi import APIRouter
from pydantic import BaseModel
from services.vector_db import load_vector_store
from typing import Optional, Any
from services.claude import ask_claude
from services.document_builder import detect_document_type
from services.user_storage import (
    get_conversation,
    add_message_to_conversation,
    create_conversation
)

router = APIRouter()

POWER_TYPE_ALIASES = {
    "ess": "BESS",
    "bess": "BESS",
    "battery energy storage system": "BESS",
    "battery energy storage systems": "BESS",
    "energy storage system": "BESS",
    "energy storage systems": "BESS",
}

POWER_TYPE_KEYWORD_ALIASES = (
    (
        "BESS",
        (
            "ess",
            "bess",
            "battery energy storage system",
            "battery energy storage systems",
            "energy storage system",
            "energy storage systems",
        ),
    ),
)


def clean_text(text):
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sanitize_answer(text: str) -> str:
    if not text:
        return ""

    cleaned = clean_text(text)

    cleaned = (
        cleaned
        .replace("\u20b9",   "Rs. ")
        .replace("\u2014",   "-")
        .replace("\u2013",   "-")
        .replace("\u2018",   "'")
        .replace("\u2019",   "'")
        .replace("\u201c",   '"')
        .replace("\u201d",   '"')
    )

    patterns = [
        r"\b(?:as\s+per)\s+(?:Clause|Section|Article)\s*[\dA-Za-z\.\-\(\)]+",
        r"\b(?:Clause|Section|Article)\s*[\dA-Za-z\.\-\(\)]+",
        r"\b(?:para(?:graph)?|paragraph)\s*[\dA-Za-z\.\-\(\)]+",
    ]
    for pat in patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)

    forbidden_phrases = [
        r"\bas\s+per\s+the\s+policy\b",
        r"\bbased\s+on\s+the\s+document\b",
        r"\bthe\s+context\s+states\b",
    ]
    for fp in forbidden_phrases:
        cleaned = re.sub(fp, "", cleaned, flags=re.IGNORECASE)

    cleaned = cleaned.replace("```", "")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def _is_claude_error(response: Any) -> bool:
    if response is None:
        return True
    if not isinstance(response, str):
        return False
    return response.strip().lower().startswith("failed:")


def _claude_error_message(response: Any) -> str:
    if response is None:
        return "Claude failed to respond."
    if not isinstance(response, str):
        return "Claude failed to respond."
    cleaned = response.strip()
    if cleaned.lower().startswith("failed:"):
        cleaned = cleaned[len("failed:"):].strip()
    return cleaned or "Claude failed to respond."


class _DocLike:
    """
    Minimal Document-like wrapper. Guarantees `.metadata` (dict) and
    `.page_content` (str) attributes so downstream code never has to
    special-case dicts vs. real LangChain Document objects.
    """
    __slots__ = ("metadata", "page_content")

    def __init__(self, metadata: dict, page_content: str):
        self.metadata = metadata or {}
        self.page_content = page_content or ""


def _normalize_doc(value: Any) -> Optional["_DocLike"]:
    if value is None:
        return None

    metadata = getattr(value, "metadata", None)
    if metadata is not None:
        page_content = getattr(value, "page_content", "") or ""
        return _DocLike(metadata, page_content)

    if isinstance(value, dict):
        metadata = value.get("metadata")
        if metadata is None:
            metadata = {k: v for k, v in value.items() if k != "page_content"}
        page_content = value.get("page_content", "") or ""
        if not metadata:
            return None
        return _DocLike(metadata, page_content)

    return None


def _get_docs_for_selected_files(db, selected_files):
    if not selected_files:
        return []

    if not hasattr(db, "docstore"):
        return []

    store = db.docstore
    items = getattr(store, "_dict", None) or getattr(store, "docs", None)
    if items is None:
        return []

    selected_docs = []
    for value in items.values():
        doc = _normalize_doc(value)
        if doc is None:
            continue
        source_file = (doc.metadata.get("source_file") or "").strip().lower()
        if source_file in selected_files:
            selected_docs.append(doc)

    return selected_docs


PDF_ANSWER_RULES = """
⚠ ABSOLUTE BAN — NEVER use any of these headings or labels, no matter what:
- Executive Summary
- Key Takeaways  
- Key Points
- Summary (as a section heading inside your answer)
- Additional Notes
- Overview (as a section heading)
- Details
- Information
- Key Highlights
- Important Notes
- Conclusion (as a generic closing header)
These are forbidden in EVERY answer type. Violating this will make the answer useless.

CRITICAL RULES:
1. PRIMARY SOURCE: Base factual claims on the "DOCUMENT EXCERPTS" block below. Paraphrase accurately; do not copy any sentence word-for-word; do not contradict the excerpts.
2. PLAIN LANGUAGE: Never mention legal numbering like clause/section/paragraph/article numbers. Explain ideas in normal words.
3. NO FABRICATION: Do not invent capacities, percentages, dates, deadlines, targets, penalties, or responsibilities that are not supported by the excerpts. If the excerpts do not give a specific number/date, say that clearly.
4. PROFESSIONAL FORMATTING: Use markdown formatting throughout your answer:
   - Use **bold** for key terms, figures, and important labels
   - Use bullet points (-) for lists of items, provisions, or features
   - Use numbered lists (1. 2. 3.) for sequential steps or ranked items
   - Use ### headings for major sections when the answer has multiple topics
   - Keep paragraphs short (3-4 sentences max); separate them with a blank line
   - Never write a wall of text — always break content into scannable sections
5. OUTSIDE THE PDF: If the excerpts do not fully answer the question, say what is missing briefly. Then you MAY add a clearly labeled subsection:

**General knowledge (not from this PDF):**
…concise, accurate information that directly answers the user's question. Do not present this as if it were from the PDF.
"""


def detect_question_type(question: str) -> str:
    q = question.lower().strip()

    # ── FIX: infographic intent is checked FIRST, not last. ────────────────
    # The frontend always sends questions prefixed with "Create an
    # infographic: ...". If the user's own question happened to contain an
    # earlier trigger word (e.g. "compare", "target", "policy"), the old
    # ordering matched "table"/"targets"/"specific" before ever reaching the
    # infographic check below — silently returning the wrong response shape
    # for the "Export Infographic" button. An explicit "infographic" mention
    # is an unambiguous, strong signal and should always win.
    infographic_keywords = [
        "infographic", "visual summary", "visual overview", "key stats",
        "key statistics", "at a glance", "snapshot",
        "create a visual", "show infographic", "give me a visual"
    ]
    if any(m in q for m in infographic_keywords):
        return "infographic"

    summary_markers = (
        "summary", "summarize", "summarise", "give summary", "provide summary",
        "tl;dr", "tldr", "brief overview", "overview of this", "overview of the",
        "in brief", "high-level overview", "timeline overview", "implementation timeline",
        "policy timeline", "timeline of", "give an overview", "provide an overview",
        "give overview", "provide overview",
    )
    if any(m in q for m in summary_markers):
        return "summary"

    comparison_keywords = [
        "compare", "comparison", "difference", "differences", "versus", " vs ",
        "vs.", "against", "compare with", "compare between", "distinguish",
        "better than", "pros and cons", "advantages", "disadvantages",
        "similarities", "similarity", "differ", "differs"
    ]
    explicit_table_keywords = [
        "tabulated list", "table of", "in table form", "tabular",
        "comparison table", "provide a table", "show in table",
    ]
    if any(k in q for k in comparison_keywords) or any(k in q for k in explicit_table_keywords):
        return "table"

    targets_keywords = [
        "target", "goal", "capacity", " gw", "gw ", "mw",
        "how many", "amount", "percentage", "number",
    ]
    if any(k in q for k in targets_keywords):
        return "targets"

    general_keywords = ["explain", "how does", "how do", "describe"]
    if any(k in q for k in general_keywords):
        return "general"

    coverage_keywords = [
        "what is under", "what comes under", "covered under",
        "what does this policy cover", "scope of policy", "coverage of policy",
        "what technologies are covered", "what sectors are covered",
        "what all is included", "what all is covered",
    ]
    if any(k in q for k in coverage_keywords):
        return "coverage"

    specific_keywords = [
        "what is", "when was", "where is", "who ", "which",
        "how much", "what are the", "policy", "scheme", "program",
    ]
    if any(k in q for k in specific_keywords):
        return "specific"

    return "general"


def _format_policy_lines(policies: Optional[list]) -> str:
    if not policies:
        return "(none specified)"
    lines = []
    for p in policies:
        if not isinstance(p, dict):
            continue
        fn = (p.get("file") or "").strip() or "unknown file"
        st = p.get("state") or "—"
        yr = p.get("year") if p.get("year") is not None else "—"
        pt = p.get("power_type") or p.get("powerType") or "—"
        lines.append(f"  - {fn} (state: {st}, year: {yr}, energy type: {pt})")
    return "\n".join(lines) if lines else "(none specified)"


def _metadata_from_docs(docs: list) -> dict[str, Any]:
    if not docs:
        return {"state": "Unknown", "energy_type": "Unknown", "year": "Unknown", "source_files": []}
    metas = [getattr(d, "metadata", None) or {} for d in docs]
    states = sorted({str(m.get("state")) for m in metas if m.get("state")})
    years = sorted({str(m.get("year")) for m in metas if m.get("year") not in (None, "", 0)})
    types = sorted({str(m.get("power_type")) for m in metas if m.get("power_type")})
    files: list[str] = []
    seen: set[str] = set()
    for m in metas:
        f = m.get("source_file")
        if f and f not in seen:
            seen.add(f)
            files.append(str(f))
    return {
        "state": ", ".join(states) if states else "See excerpts",
        "energy_type": ", ".join(types) if types else "See excerpts",
        "year": ", ".join(years) if years else "See excerpts",
        "source_files": files,
    }


def _sources_from_docs(docs: list, limit: int = 15) -> list:
    sources = []
    seen: set = set()
    for doc in docs[:limit]:
        meta = getattr(doc, "metadata", None) or {}
        source_file = meta.get("source_file")
        if not source_file:
            continue
        key = (source_file, meta.get("state", "Unknown"), meta.get("year", "Unknown"), meta.get("power_type", "Unknown"))
        if key in seen:
            continue
        seen.add(key)
        sources.append({
            "file": source_file,
            "state": meta.get("state", "Unknown"),
            "year": meta.get("year", "Unknown"),
            "power_type": meta.get("power_type", "Unknown"),
        })
    return sources


def _policy_header(metadata: dict, selected_policies: Optional[list]) -> str:
    files = metadata.get("source_files") or []
    files_str = ", ".join(files) if files else "See excerpts"
    sel = ""
    if selected_policies:
        sel = (
            "\nUser selected policies (dashboard; must stay relevant to these):\n"
            + _format_policy_lines(selected_policies)
        )
    return f"""SELECTED POLICY METADATA (from index; use excerpts as ground truth):
State: {metadata.get("state", "Unknown")}
Energy type: {metadata.get("energy_type", "Unknown")}
Year: {metadata.get("year", "Unknown")}
Source file(s): {files_str}
{sel}"""


def create_adaptive_prompt(
    question: str,
    context: str,
    metadata: dict,
    question_type: Optional[str] = None,
    selected_policies: Optional[list] = None,
) -> str:
    qt = question_type or detect_question_type(question)
    header = _policy_header(metadata, selected_policies)
    excerpts = f"""DOCUMENT EXCERPTS FROM THE SELECTED PDF(S):
---
{context}
---
"""

    if qt == "summary":
        source_files_str = ", ".join(metadata.get("source_files", [])) or "Unknown"
        return f"""You are an expert assistant for Indian renewable energy policy documents.

{header}

{excerpts}

{PDF_ANSWER_RULES}

USER QUESTION:
{question}

Write a comprehensive, professional summary using the structure below.
Use markdown formatting throughout: **bold** for key terms, bullet points for lists, ### for section headings.
Keep each section focused and scannable — no walls of text.

### Document Information

| Field | Value |
|-------|-------|
| State | {metadata.get("state", "Unknown")} |
| Energy Type | {metadata.get("energy_type", "Unknown")} |
| Year | {metadata.get("year", "Unknown")} |
| Source File | {source_files_str} |

### Summary

Write 2–4 paragraphs explaining the purpose, provisions, implementation mechanism, and expected impact. Separate each paragraph with a blank line.

### Key Highlights

**Main Provisions**

- List the main provisions as bullet points

**Incentives**

- List incentives as bullet points

**Regulatory Changes**

- List any regulatory changes as bullet points

**Key Stakeholders**

- List stakeholders as bullet points

### Important Insights

Write 4–6 insights. Each insight should be a short paragraph (2–3 sentences) followed by a blank line.

### Targets and Objectives

List each target or objective on its own bullet point. Include capacities, deadlines, and percentages exactly as stated in the excerpts. If no specific numbers appear, list the qualitative objectives instead.

### Recommendations

List 4–5 forward-looking recommendations or conclusions.

1. First recommendation
2. Second recommendation
(and so on)
"""

    if qt == "coverage":
        return f"""You are an expert assistant for renewable energy policies.

{header}

{excerpts}

{PDF_ANSWER_RULES}

USER QUESTION:
{question}

════════════════════════════════════════
OUTPUT FORMAT — MANDATORY. NO EXCEPTIONS.
════════════════════════════════════════

STEP 1 — Write ONE ### heading that directly names what is being covered.
STEP 2 — Write 1 sentence of context.
STEP 3 — Group covered items under **bold sub-headings**, each followed by bullet points.

Now answer the actual USER QUESTION above using exactly that structure.
"""

    if qt == "table":
        return f"""You are an expert assistant for Indian renewable energy policy documents.

{header}

{excerpts}

USER QUESTION:
{question}

════════════════════════════════════════════════════════════
YOUR ENTIRE RESPONSE MUST BE A SINGLE RAW JSON OBJECT.
NO text before it. NO text after it. NO markdown. NO backticks.
════════════════════════════════════════════════════════════

CORRECT response (pure JSON only):
{{"table_title":"Renewable Energy Targets Comparison","headers":["Category","Target","Deadline"],"rows":[["RE share of demand","50%","FY 2029-30"]],"notes":""}}

SCHEMA:
{{
  "table_title": "Short descriptive title",
  "headers": ["Column 1", "Column 2", "Column 3"],
  "rows": [["Value", "Value", "Value"]],
  "notes": ""
}}

RULES:
- Every row must have the same number of cells as the headers row.
- Max 60 characters per cell.
- Use only data from the DOCUMENT EXCERPTS above.
- Write "Not specified" for any value not in the excerpts.
- Do NOT fabricate figures.
"""

    if qt == "targets":
        return f"""You are an expert assistant for Indian renewable energy policy documents.

{header}

{excerpts}

{PDF_ANSWER_RULES}

USER QUESTION:
{question}

════════════════════════════════════════
OUTPUT FORMAT — MANDATORY. NO EXCEPTIONS.
════════════════════════════════════════

STEP 1 — Write ONE ### heading.
STEP 2 — Write 1 sentence of context (overall target and deadline if available).
STEP 3 — Group targets under **bold sub-headings** by category. Each target on its own bullet. Bold every number, capacity, and date.

Now answer the actual USER QUESTION above using exactly that structure.
If a number or date does not appear in the excerpts, write "Not specified in the document" for that item.
"""

    if qt == "specific":
        return f"""You are an expert assistant for Indian renewable energy policy documents.

{header}

{excerpts}

{PDF_ANSWER_RULES}

USER QUESTION:
{question}

════════════════════════════════════════
OUTPUT FORMAT — MANDATORY. NO EXCEPTIONS.
════════════════════════════════════════

STEP 1 — Write ONE ### heading that names exactly what is being asked.
STEP 2 — Write 1–2 sentences of direct factual answer.
STEP 3 — If there are multiple related facts or categories, use **bold sub-headings** + bullet points.

Now answer the actual USER QUESTION above using exactly that structure.
If the answer is not in the excerpts, state that plainly first, then add a clearly labelled general knowledge block.
"""

    # ------------------------------------------------------------------ #
    # INFOGRAPHIC PROMPT — DYNAMIC. Claude chooses theme + which layout    #
    # sections apply, in what order, how many — same philosophy as the    #
    # PPT prompt in export.py, and matches PolicyInfographic.jsx's        #
    # {theme, sections[]} rendering schema (header_stats / stat_grid /    #
    # chart / cards / columns / timeline / glance).                       #
    # ------------------------------------------------------------------ #
    if qt == "infographic":
        return f"""You are an elite infographic designer specializing in Indian renewable
energy policy. Design the best possible single-page infographic for THIS
specific document — not a template with values swapped in.

{header}

{excerpts}

{PDF_ANSWER_RULES}

USER QUESTION:
{question}

Identify what kind of document this actually is (it may cover one technology
or several — solar, wind, BESS, biomass, green hydrogen, hybrid, offshore,
whatever is ACTUALLY in the excerpts, never assume a single technology) and
what story it should tell a reader. Choose a visual theme (fonts, colors)
that fits this document's tone — vary this across documents, don't default
to the same palette every time.

Build 4-8 stacked sections chosen from ONLY these section types (choose which
ones apply, how many, and in what order for THIS document — never force a
section that doesn't fit, and never repeat the same sequence you'd use for a
different document unless it genuinely calls for the same story):

- "header_stats"  title/eyebrow + 3-4 headline stats + reference/notified/valid-until dates if available
- "stat_grid"     grid of standout numbers with labels
- "chart"         chart_type one of bar|pie|doughnut|line|area, backed by
                  real document numbers only. Use pie/doughnut for any
                  technology or energy mix present in the document (whatever
                  technologies actually appear — don't assume which ones).
                  Only include if the document has real quantitative data.
- "cards"         icon+title+detail cards (2-9 items) — technologies,
                  incentives, provisions, stakeholders, whatever fits
- "columns"       2-3 labeled columns of short list items (e.g. direct vs
                  indirect benefits, eligibility categories)
- "timeline"      dated events
- "glance"        compact label/value reference grid + footer note

Rules:
1. Only use information present in the excerpts — never invent data.
2. Only include a "chart" section if real quantitative data supports it.
3. Every section title must be unique. Full sentences in body text.
4. Two different documents should produce different section counts, order,
   and themes — not the same template with different words swapped in.

Return ONLY valid JSON, no markdown, no explanation, no backticks, matching:

{{
  "title": "Exact document title",
  "narrative_label": "short internal description of what this document is",
  "theme": {{
    "style_name": "one to three words, e.g. Modern Energy, Executive Boardroom",
    "title_font": "a font available in browsers, e.g. Merriweather, Georgia",
    "body_font": "a font available in browsers, e.g. Inter, Segoe UI",
    "primary_color": "hex no #",
    "secondary_color": "hex no # (deep background tone)",
    "accent_color": "hex no # (used for numbers/highlights)",
    "text_color": "hex no # (readable on secondary_color)",
    "muted_color": "hex no #"
  }},
  "sections": [
    {{ "type": "header_stats", "eyebrow": "...", "title": "...",
       "reference_number": "...", "notified_date": "...", "valid_until": "...",
       "stats": [{{"value":"...","label":"..."}}] }},
    {{ "type": "stat_grid", "eyebrow": "...", "title": "...",
       "stats": [{{"value":"...","label":"..."}}] }},
    {{ "type": "chart", "eyebrow": "...", "title": "...",
       "chart_type": "bar|pie|doughnut|line|area",
       "categories": ["..."], "series_name": "...", "values": [0] }},
    {{ "type": "cards", "eyebrow": "...", "title": "...",
       "items": [{{"icon":"...","title":"...","detail":"..."}}] }},
    {{ "type": "columns", "eyebrow": "...", "title": "...",
       "columns": [{{"title":"...","items":["..."]}}] }},
    {{ "type": "timeline", "eyebrow": "...", "title": "...",
       "events": [{{"date":"...","label":"..."}}] }},
    {{ "type": "glance", "title": "...",
       "stats": [{{"label":"...","value":"..."}}], "footer": "..." }}
  ]
}}
"""

    # ------------------------------------------------------------------ #
    # GENERAL PROMPT (default)                                             #
    # ------------------------------------------------------------------ #
    return f"""You are an expert assistant for Indian renewable energy policy documents.

{header}

{excerpts}

{PDF_ANSWER_RULES}

USER QUESTION:
{question}

════════════════════════════════════════
OUTPUT FORMAT — MANDATORY. NO EXCEPTIONS.
════════════════════════════════════════

STEP 1 — Write ONE ### heading that directly reflects the user's question intent.

BANNED headings (never use these):
- ### Overview / ### Summary / ### Key Takeaways / ### Executive Summary
- ### Key Points / ### Additional Notes / ### Details / ### Information

STEP 2 — Write 1–2 sentences of context immediately after the heading.

STEP 3 — Organise using **bold sub-headings** + bullet points. Bold every key term, figure, date, capacity, or place name.

STEP 4 — One brief closing sentence.

Now answer the actual USER QUESTION above using exactly that structure.
"""


def _table_response_instructions() -> str:
    return """Return the answer as a structured table in this exact JSON format:
{
  "table_title": "Title of the table",
  "headers": ["Column 1", "Column 2", "Column 3"],
  "rows": [
    ["Row 1, Col 1", "Row 1, Col 2", "Row 1, Col 3"]
  ],
  "notes": "Any footnotes or additional context (optional)"
}
Rules:
- Return ONLY the JSON object, no markdown or extra explanation.
- Keep values concise and accurate.
"""


def _fallback_prompt_db_unavailable(question: str, table_mode: bool = False) -> str:
    prompt = f"""You are an expert on Indian renewable energy policy.

The policy document index is not available right now, so you have NO PDF excerpts.

USER QUESTION:
{question}

Answer accurately from general knowledge using professional markdown formatting:
- Use ### headings for sections
- Use bullet points for lists
- **Bold** key terms and figures
- Do not claim to have read a specific uploaded PDF
- If the question implies document-specific details you cannot see, say so briefly first
"""
    if table_mode:
        prompt += "\n" + _table_response_instructions()
    return prompt


def _fallback_prompt_no_chunks(question: str, selected_policies: Optional[list], table_mode: bool = False) -> str:
    policies_block = _format_policy_lines(selected_policies)
    prompt = f"""You are an expert on Indian renewable energy policy.

The user asked a question while these policy PDF(s) were selected in the dashboard, but no indexed text chunks were found for them.

SELECTED POLICIES:
{policies_block}

USER QUESTION:
{question}

Start with this exact line:
> **Note:** The full text of the selected PDF(s) is not available in this system; the following is general knowledge only, not a quote from the document.

Then answer the question using professional markdown formatting:
- ### headings for sections
- Bullet points for lists
- **Bold** key terms
- Stay relevant to the selected state, year, energy type, and filenames above
- Do not invent legal numbering, quotes, or figures from the unseen PDFs
"""
    if table_mode:
        prompt += "\n" + _table_response_instructions()
    return prompt


def _fallback_prompt_short_context(
    question: str,
    selected_policies: Optional[list],
    partial_excerpts: Optional[str] = None,
    table_mode: bool = False,
) -> str:
    policies_block = _format_policy_lines(selected_policies)
    partial = ""
    if partial_excerpts and partial_excerpts.strip():
        partial = f"""
PARTIAL DOCUMENT EXCERPTS (retrieval returned little text — ground factual claims here first):
---
{partial_excerpts.strip()}
---
"""
    prompt = f"""You are an expert on Indian renewable energy policy.

Very little text was retrieved from the document index for this question.
{partial}
SELECTED POLICIES (if any):
{policies_block}

USER QUESTION:
{question}

If the excerpts above do not answer the question, begin with:
> **Note:** Insufficient text was retrieved from the selected document(s).

Then provide a careful answer using professional markdown formatting.
"""
    if table_mode:
        prompt += "\n" + _table_response_instructions()
    return prompt


class QueryRequest(BaseModel):
    question: str
    state: Optional[str] = None
    year: Optional[int] = None
    power_type: Optional[str] = None
    selected_policies: Optional[list] = None
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None


def _normalize_state(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    clean = value.strip()
    if clean == "" or clean.lower() == "all":
        return None
    return clean


def _normalize_power_type(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    clean = value.strip()
    if clean == "" or clean.lower() == "all":
        return None
    normalized = re.sub(r"[_-]+", " ", clean).lower().strip()
    if normalized in POWER_TYPE_ALIASES:
        return POWER_TYPE_ALIASES[normalized]
    for canonical, keywords in POWER_TYPE_KEYWORD_ALIASES:
        if any(re.search(rf"\b{re.escape(keyword)}\b", normalized) for keyword in keywords):
            return canonical
    return clean


def _normalize_year(value: Optional[int]) -> Optional[int]:
    if value is None or value <= 0:
        return None
    return value


@router.post("/ask")
def ask_question(request: QueryRequest):
    qtype = detect_question_type(request.question)
    db = load_vector_store()

    # ── CONVERSATION HISTORY SETUP ────────────────────────────────────────
    conversation_id = request.conversation_id
    conversation_history = []
    conversation = None

    print("USER ID RECEIVED:", request.user_id)
    if not conversation_id:
        conversation_id = create_conversation(
            user_id=request.user_id,
            title=request.question[:50]
        )

    if conversation_id:
        conversation = get_conversation(conversation_id)
        if conversation:
            conversation_history = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in conversation.get("messages", [])
            ]
            print(f"[Conversation] Loaded {len(conversation_history)} messages from conversation {conversation_id}")
        else:
            print(f"[Conversation] Conversation {conversation_id} not found, creating new one")
            conversation_id = create_conversation(
                user_id=request.user_id,
                title=request.question[:50]
            )
            conversation_history = []

    # ── 1. DB UNAVAILABLE FALLBACK ────────────────────────────────────────
    if db is None:
        prompt = _fallback_prompt_db_unavailable(request.question, table_mode=(qtype == "table"))
        try:
            response = ask_claude(prompt, conversation_history)
        except Exception as e:
            print("[LLM ERROR]", e)
            return {"error": "Claude is temporarily unavailable. Please try again."}

        print("[LLM] Knowledge fallback (vector DB unavailable)...")
        if _is_claude_error(response):
            return {"error": _claude_error_message(response)}

        answer = sanitize_answer(response)
        if conversation_id:
            add_message_to_conversation(conversation_id, "user", request.question)
            add_message_to_conversation(conversation_id, "assistant", answer)

        if qtype == "table":
            return {"answer": response, "table": None, "sources": [], "conversation_id": conversation_id}
        return {"answer": answer, "sources": [], "conversation_id": conversation_id}

    selected = request.selected_policies

    if selected and len(selected) > 0:
        # ── FIX: use k=60 for infographic so we get enough chunks from the right PDF ──
        k_val = 60 if qtype == "infographic" else 30
        docs = db.similarity_search(request.question, k=k_val)

        selected_files = {
            (policy.get("file") or "").strip().lower()
            for policy in selected
            if policy.get("file")
        }
        print(f"User selected {len(selected_files)} policies: {selected_files}")

        filtered_docs = []
        for doc in docs:
            meta = doc.metadata or {}
            source_file = (meta.get("source_file") or "").strip().lower()
            if source_file and source_file in selected_files:
                filtered_docs.append(doc)

        seen_content = set()
        final_docs = []
        for doc in filtered_docs:
            content_hash = hash(doc.page_content)
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                final_docs.append(doc)

        if len(final_docs) < 5:
            k = min(getattr(db.index, "ntotal", 120), 120)
            print(f"Only {len(final_docs)} chunks found, doing wider search with k={k}...")
            wider_docs = db.similarity_search(request.question, k=k)
            wider_filtered = []
            for doc in wider_docs:
                meta = doc.metadata or {}
                source_file = (meta.get("source_file") or "").strip().lower()
                if source_file and source_file in selected_files:
                    wider_filtered.append(doc)
            wider_seen = set()
            wider_final = []
            for doc in wider_filtered:
                h = hash(doc.page_content)
                if h not in wider_seen:
                    wider_seen.add(h)
                    wider_final.append(doc)
            final_docs = wider_final
            print(f"Wider search found {len(final_docs)} total chunks")

        if not final_docs:
            selected_docs = _get_docs_for_selected_files(db, selected_files)
            if selected_docs:
                print(f"Selected policy docs found in index ({len(selected_docs)}) but were not returned by similarity search; using them directly.")
                final_docs = selected_docs[:20]
            else:
                # ── 2. NO CHUNKS FALLBACK ─────────────────────────────────
                print(f"No chunks matched selected policy {selected_files} — LLM fallback (policy-aware)")
                prompt = _fallback_prompt_no_chunks(request.question, selected, table_mode=(qtype == "table"))
                try:
                    response = ask_claude(prompt, conversation_history)
                except Exception as e:
                    print("[LLM ERROR]", e)
                    return {"error": "Claude is temporarily unavailable. Please try again."}

                cleaned = sanitize_answer(response) if response else "Could not get a response."
                result = {
                    "answer": cleaned,
                    "sources": [],
                    "warning": "No text from the selected PDF(s) was found in the search index. Answer uses general knowledge only; upload or re-index may be required.",
                    "conversation_id": conversation_id,
                }
                if qtype == "table":
                    result["answer"] = response
                if conversation_id:
                    add_message_to_conversation(conversation_id, "user", request.question)
                    add_message_to_conversation(conversation_id, "assistant", cleaned)
                return result

        if final_docs:
            print(f"Found {len(final_docs)} relevant chunks from selected policy files: {selected_files}")
    else:
        state_filter = _normalize_state(request.state)
        power_type_filter = _normalize_power_type(request.power_type)
        year_filter = _normalize_year(request.year)
        has_filters = any([state_filter, power_type_filter, year_filter])

        docs = db.similarity_search(request.question, k=30)
        filtered_docs = []

        for doc in docs:
            meta = doc.metadata
            if state_filter and meta.get("state") != state_filter:
                continue
            if year_filter and int(meta.get("year", 0)) != year_filter:
                continue
            if power_type_filter:
                meta_power_type = _normalize_power_type(str(meta.get("power_type", "")))
                if not meta_power_type:
                    continue
                meta_power_type_lower = meta_power_type.lower()
                power_type_filter_lower = power_type_filter.lower()
                if not (
                    meta_power_type_lower == power_type_filter_lower or
                    power_type_filter_lower in meta_power_type_lower or
                    meta_power_type_lower in power_type_filter_lower
                ):
                    continue
            filtered_docs.append(doc)

        if has_filters and not filtered_docs:
            return {"error": "No relevant policy found for the selected state/year/energy type."}

        final_docs = filtered_docs if has_filters else docs

    # ── FIX: infographic gets 20 chunks (same as summary) not just 8 ────
    if qtype in ("summary", "infographic"):
        context = "\n".join([doc.page_content for doc in final_docs[:20]])
    else:
        context = "\n".join([doc.page_content for doc in final_docs[:8]])

    meta_for_prompt = _metadata_from_docs(final_docs)

    # ── 3. SHORT CONTEXT FALLBACK ─────────────────────────────────────────
    if not context.strip() or len(context.strip()) < 300:
        prompt = _fallback_prompt_short_context(
            request.question,
            selected,
            partial_excerpts=context.strip() or None,
            table_mode=(qtype == "table"),
        )
        print("[LLM] Fallback (retrieved context too short)...")
        try:
            response = ask_claude(prompt, conversation_history)
        except Exception as e:
            print("[LLM ERROR]", e)
            return {"error": "Claude is temporarily unavailable. Please try again."}

        if _is_claude_error(response):
            return {"error": _claude_error_message(response)}

        cleaned = sanitize_answer(response)
        result = {
            "answer": cleaned,
            "sources": _sources_from_docs(final_docs),
            "warning": "Retrieved text from the document(s) was very short; the answer may lean on general knowledge.",
            "conversation_id": conversation_id,
        }
        if qtype == "table":
            result["answer"] = response
        if conversation_id:
            add_message_to_conversation(conversation_id, "user", request.question)
            add_message_to_conversation(conversation_id, "assistant", cleaned)
        return result

    prompt = create_adaptive_prompt(
        request.question,
        context,
        meta_for_prompt,
        question_type=qtype,
        selected_policies=selected,
    )

    # ── 4. MAIN ADAPTIVE RAG CALL ─────────────────────────────────────────
    print("[LLM] Sending adaptive RAG prompt...")
    try:
        response = ask_claude(prompt, conversation_history)
    except Exception as e:
        print("[LLM ERROR]", e)
        return {"error": "Claude is currently overloaded. Please try again in a few seconds."}

    try:
        print("[LLM] Response:", response[:500] if response else "(empty)")
    except Exception:
        print("[LLM] Response received (print truncated).")

    if _is_claude_error(response):
        return {"error": _claude_error_message(response)}

    # ── INFOGRAPHIC ───────────────────────────────────────────────────────
    if qtype == "infographic":
        import json
        import re as _re
        raw = _re.sub(r"```json|```", "", response).strip()
        try:
            parsed = json.loads(raw)
            if conversation_id:
                add_message_to_conversation(conversation_id, "user", request.question)
                add_message_to_conversation(conversation_id, "assistant", response)
            return {
                "answer": response,
                "infographic_data": parsed,
                "sources": _sources_from_docs(final_docs),
                "conversation_id": conversation_id,
            }
        except Exception:
            if conversation_id:
                add_message_to_conversation(conversation_id, "user", request.question)
                add_message_to_conversation(conversation_id, "assistant", response)
            return {
                "answer": response,
                "sources": _sources_from_docs(final_docs),
                "conversation_id": conversation_id,
            }

    # ── TABLE ─────────────────────────────────────────────────────────────
    if qtype == "table":
        try:
            import json
            cleaned_response = response.strip()
            if "```" in cleaned_response:
                cleaned_response = cleaned_response.split("```")[1]
                if cleaned_response.startswith("json"):
                    cleaned_response = cleaned_response[4:]
                cleaned_response = cleaned_response.strip()
            table_data = json.loads(cleaned_response)
            if isinstance(table_data, dict) and "headers" in table_data and "rows" in table_data:
                print("[LLM] Parsed as table/comparison response")
                if conversation_id:
                    add_message_to_conversation(conversation_id, "user", request.question)
                    add_message_to_conversation(conversation_id, "assistant", response)
                return {
                    "answer": response,
                    "table": table_data,
                    "sources": _sources_from_docs(final_docs),
                    "conversation_id": conversation_id,
                }
        except (json.JSONDecodeError, KeyError, ValueError):
            print("[LLM] Failed to parse comparison as table JSON, returning sanitized plain text")

        answer = sanitize_answer(response)
        if conversation_id:
            add_message_to_conversation(conversation_id, "user", request.question)
            add_message_to_conversation(conversation_id, "assistant", answer)
        return {
            "answer": answer,
            "sources": _sources_from_docs(final_docs),
            "conversation_id": conversation_id,
        }

    # ── 5. FINAL RESPONSE ─────────────────────────────────────────────────
    answer = sanitize_answer(response)
    if conversation_id:
        add_message_to_conversation(conversation_id, "user", request.question)
        add_message_to_conversation(conversation_id, "assistant", answer)
    return {"answer": answer, "sources": _sources_from_docs(final_docs), "conversation_id": conversation_id}