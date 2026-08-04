import json
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from services.claude import ask_claude
from services.vector_db import load_vector_store, get_docs_by_source_file
from services.document_builder import build_docx, build_pptx, build_pdf, parse_json_response

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


class DocumentRequest(BaseModel):
    question: str
    doc_type: str
    selected_policies: Optional[list] = None
    state: Optional[str] = None
    year: Optional[int] = None
    power_type: Optional[str] = None


# ── FIX #1: robust filename matching ─────────────────────────────────────────
def _clean_filename(name: str) -> str:
    """Normalize a filename/path for comparison: strip path, lowercase,
    collapse whitespace. Deliberately does NOT strip the extension, so
    'policy.pdf' and 'policy.docx' remain distinct — but handles both a bare
    filename and a full path/URL being passed by the frontend."""
    if not name:
        return ""
    name = name.strip().replace("\\", "/")
    name = name.split("/")[-1]  # drop any path prefix
    name = name.split("?")[0]   # drop any querystring if a URL was passed
    return name.strip().lower()


def _policy_file_set(selected_policies: Optional[list]) -> set[str]:
    if not selected_policies:
        return set()
    out = set()
    for policy in selected_policies:
        if not isinstance(policy, dict):
            continue
        raw = policy.get("file") or policy.get("filename") or policy.get("source_file") or ""
        cleaned = _clean_filename(raw)
        if cleaned:
            out.add(cleaned)
    return out


def _get_docs_for_selected_files(db, selected_files: set[str]):
    """
    Pull ALL chunks belonging to the explicitly selected policy file(s) only.
    This was previously called but never defined, which meant selecting a
    policy silently did nothing and the code fell through to a global
    similarity search — the root cause of PPTs being generated about the
    wrong document.

    Uses get_docs_by_source_file(), which scans db.docstore._dict directly —
    the same pattern vector_db.save_vector_store() already uses for dedup.
    This is correct for FAISS: similarity_search() ranks by relevance to a
    query, it was never designed to fetch "every chunk for file X" exactly.
    """
    matched = get_docs_by_source_file(db, selected_files)
    seen_content = set()
    deduped = []
    for doc in matched:
        content_hash = hash(doc.page_content)
        if content_hash not in seen_content:
            seen_content.add(content_hash)
            deduped.append(doc)
    return deduped


def _retrieve_documents(request: DocumentRequest):
    db = load_vector_store()
    if db is None:
        return None, "No vector store is available. Proceeding with general knowledge only."

    selected_files = _policy_file_set(request.selected_policies)

    # ── FIX #2: no silent fallback to global search when a policy is
    # explicitly selected. If we can't find its chunks, fail loudly instead
    # of quietly generating content about a different document. ──────────
    if selected_files:
        docs = _get_docs_for_selected_files(db, selected_files)
        if docs:
            return docs, None
        return [], (
            f"No indexed content found for the selected file(s): "
            f"{', '.join(sorted(selected_files))}. The document may not be "
            f"indexed yet, or its metadata.source_file doesn't match the "
            f"filename sent by the frontend."
        )

    docs = db.similarity_search(request.question, k=60)

    state_filter = _normalize_state(request.state)
    power_type_filter = _normalize_power_type(request.power_type)
    year_filter = _normalize_year(request.year)
    if state_filter or power_type_filter or year_filter:
        filtered_docs = []
        for doc in docs:
            meta = doc.metadata or {}
            if state_filter and meta.get("state") != state_filter:
                continue
            if power_type_filter:
                meta_power_type = _normalize_power_type(str(meta.get("power_type", "")))
                if not meta_power_type or meta_power_type.lower() != power_type_filter.lower():
                    continue
            if year_filter and int(meta.get("year", 0)) != year_filter:
                continue
            filtered_docs.append(doc)
        if filtered_docs:
            return filtered_docs, None

    return docs, None


# ── DYNAMIC PPT PROMPT (Claude decides theme, layout choice, count, order) ──
_PPT_LAYOUT_DOCS = """
- "cover"      hero slide: eyebrow, title, subtitle, 0-4 stats
- "stat_grid"  4-6 standout numbers with labels
- "chart"      ONE chart backed by real document data. chart_type must be one
               of: "bar", "pie", "doughnut", "line", "area". Use "pie" or
               "doughnut" for any technology/energy MIX (works for any
               combination of technologies present in the doc). Use "bar" or
               "line" for targets/capacity/growth over time. Only include if
               the document actually contains the numbers.
- "split"      two-column comparison, before/after, or vision+mission
- "cards"      2-9 icon+title+detail cards
- "list"       a titled slide of full-sentence bullets
- "timeline"   dated events + up to 3 highlight cards
- "closing"    key takeaways + footer
"""


def _build_ppt_prompt(context: str, question: str, selected_policies_desc: str) -> str:
    return f"""You are an elite presentation strategist and visual designer specializing in
Indian renewable energy policy. Your job is NOT to summarize the document —
it is to design the single best possible presentation for THIS specific
document, as a human consultant would.

DOCUMENT EXCERPTS:
{context}

USER REQUEST:
{question}

SELECTED POLICY FILE(S):
{selected_policies_desc}

============================================================
STEP 1 — READ THE DOCUMENT ON ITS OWN TERMS
============================================================
Do not assume this is a "policy" in the generic sense. It could be a state RE
policy covering one or many technologies (solar / wind / BESS / biomass /
green hydrogen / hybrid / offshore — whatever is ACTUALLY in the excerpts,
never assume a single technology), a regulatory/tariff order, an incentive or
subsidy scheme, a roadmap or strategy document, or a notification/gazette
amendment. Identify what this document actually is, what problem it solves,
what a reader most needs to walk away knowing, and what story best presents
that. Give this a short internal label describing THIS document specifically.

============================================================
STEP 2 — CHOOSE A VISUAL IDENTITY FOR THIS DECK
============================================================
Pick a theme that fits this document's tone. Make DIFFERENT choices for
different documents — never default to the same palette every time.
Return:
  "style_name":      one to three words (e.g. "Modern Energy",
                      "Executive Boardroom", "Consulting Minimal")
  "title_font":       a font available in PowerPoint (e.g. Cambria, Georgia,
                      Calibri Light, Bahnschrift, Segoe UI Semibold)
  "body_font":        a font available in PowerPoint
  "primary_color":    hex, no #
  "secondary_color":  hex, no # (deep background tone)
  "accent_color":     hex, no # (used for numbers/highlights)
  "text_color":       hex, no # (readable on secondary_color)
  "muted_color":      hex, no #

============================================================
STEP 3 — BUILD THE SLIDE SEQUENCE
============================================================
Choose 6-10 slides from these layout types ONLY (you decide which ones, how
many, and in what order — never repeat the same sequence for two different
documents unless they genuinely call for the same story):
{_PPT_LAYOUT_DOCS}

Rules:
1. Every slide's eyebrow, title, and subtitle must be unique within the deck.
2. Only use information present in the excerpts. Never invent statistics,
   dates, or names.
3. Only include a "chart" slide if there is real quantitative data to chart.
4. Do not force any layout that doesn't fit this document.
5. Full sentences everywhere except stat values/labels and card titles.

Return ONLY valid JSON, no markdown, no explanation, matching:

{{
  "title": "Exact document title",
  "narrative_label": "short internal description from Step 1",
  "theme": {{ "style_name": "", "title_font": "", "body_font": "",
             "primary_color": "", "secondary_color": "", "accent_color": "",
             "text_color": "", "muted_color": "" }},
  "slides": [
    {{
      "layout": "cover",
      "eyebrow": "...", "title": "...", "subtitle": "...",
      "stats": [{{"value":"...","label":"..."}}]
    }},
    {{
      "layout": "stat_grid",
      "eyebrow": "...", "title": "...", "subtitle": "...",
      "stats": [{{"value":"...","label":"..."}}]
    }},
    {{
      "layout": "chart",
      "eyebrow": "...", "title": "...", "subtitle": "...",
      "chart_type": "bar|pie|doughnut|line|area",
      "categories": ["..."],
      "series_name": "...",
      "values": [0],
      "callouts": [{{"title":"...","detail":"..."}}]
    }},
    {{
      "layout": "split",
      "eyebrow": "...", "title": "...",
      "left_label": "...", "left_text": "...",
      "right_label": "...", "right_text": "..."
    }},
    {{
      "layout": "cards",
      "eyebrow": "...", "title": "...", "subtitle": "...",
      "items": [{{"icon":"...","title":"...","detail":"..."}}]
    }},
    {{
      "layout": "list",
      "eyebrow": "...", "title": "...", "subtitle": "...",
      "bullets": ["..."]
    }},
    {{
      "layout": "timeline",
      "eyebrow": "...", "title": "...",
      "events": [{{"date":"...","label":"..."}}],
      "highlights": [{{"title":"...","detail":"..."}}]
    }},
    {{
      "layout": "closing",
      "title": "...", "takeaways": ["..."], "footer": "..."
    }}
  ]
}}
"""


def _build_infographic_prompt(context: str, question: str, selected_policies_desc: str) -> str:
    return f"""You are an elite infographic designer specializing in Indian renewable
energy policy. Design the best possible single-page infographic for THIS
specific document — not a template with values swapped in.

DOCUMENT EXCERPTS:
{context}

USER REQUEST:
{question}

SELECTED POLICY FILE(S):
{selected_policies_desc}

Follow the same reasoning as a presentation designer: identify what kind of
document this is, what story it should tell, and choose a fitting visual
theme (fonts, colors) — vary this across documents, don't default to the
same palette every time.

Build 4-8 stacked sections chosen from ONLY these section types (choose which
ones apply, how many, and in what order for THIS document):
- "header_stats"     title/eyebrow + 3-4 headline stats
- "stat_grid"        grid of standout numbers with labels
- "chart"            chart_type one of bar|pie|doughnut|line|area, backed by
                      real document numbers only. Use pie/doughnut for any
                      technology or energy mix present in the document
                      (whatever technologies actually appear — don't assume).
- "cards"            icon+title+detail cards (2-9 items)
- "columns"          2-3 labeled columns of short list items
- "timeline"         dated events
- "glance"           compact label/value reference grid + footer note

Rules:
1. Only use information present in the excerpts — never invent data.
2. Only include a "chart" section if real quantitative data supports it.
3. Every section title must be unique. Full sentences in body text.
4. Two different documents should produce different section counts, order,
   and themes — not the same template with different words.

Return ONLY valid JSON, no markdown, no explanation, matching:

{{
  "title": "Exact document title",
  "narrative_label": "short internal description",
  "theme": {{ "style_name": "", "title_font": "", "body_font": "",
             "primary_color": "", "secondary_color": "", "accent_color": "",
             "text_color": "", "muted_color": "" }},
  "sections": [
    {{ "type": "header_stats", "eyebrow": "...", "title": "...",
       "reference_number": "...", "notified_date": "...", "valid_until": "...",
       "stats": [{{"value":"...","label":"..."}}] }},
    {{ "type": "stat_grid", "title": "...", "stats": [{{"value":"...","label":"..."}}] }},
    {{ "type": "chart", "title": "...", "chart_type": "bar|pie|doughnut|line|area",
       "categories": ["..."], "series_name": "...", "values": [0] }},
    {{ "type": "cards", "title": "...", "items": [{{"icon":"...","title":"...","detail":"..."}}] }},
    {{ "type": "columns", "title": "...",
       "columns": [{{"title":"...","items":["..."]}}] }},
    {{ "type": "timeline", "title": "...", "events": [{{"date":"...","label":"..."}}] }},
    {{ "type": "glance", "title": "...", "stats": [{{"label":"...","value":"..."}}],
       "footer": "..." }}
  ]
}}
"""


def _build_document_prompt(request: DocumentRequest, context: str) -> str:
    selected_block = ""
    if request.selected_policies:
        lines = []
        for policy in request.selected_policies:
            if not isinstance(policy, dict):
                continue
            lines.append(
                f"- {policy.get('file', 'unknown')} "
                f"(state={policy.get('state','?')}, year={policy.get('year','?')}, type={policy.get('power_type','?')})"
            )
        selected_block = "\nSELECTED POLICIES:\n" + "\n".join(lines)

    doc_type = request.doc_type.strip().lower()
    if doc_type == "word":
        format_hint = (
            "Create a professional Word-style document structure with headings, summary paragraphs, "
            "bullet lists, and a conclusion. Return only valid JSON.\n\n"
            'Schema:\n{"title": "...", "subtitle": "...", "sections": [{"heading": "...", "summary": "...", "bullets": ["..."]}], "key_stats": ["..."], "conclusion": "..."}'
        )
    else:
        format_hint = (
            "Create a professional report structure with headings, plain paragraphs, bullet lists, and a conclusion. "
            "Return only valid JSON.\n\n"
            'Schema:\n{"title": "...", "subtitle": "...", "sections": [{"heading": "...", "summary": "...", "bullets": ["..."]}], "key_stats": ["..."], "conclusion": "..."}'
        )

    return f"""You are an expert writer on Indian renewable energy policy. Generate a structured document based on the user request and the policy excerpts below.

DOCUMENT EXCERPTS:
{context}

USER REQUEST:
{request.question}
{selected_block}

{format_hint}
"""


def _selected_policies_desc(request: DocumentRequest) -> str:
    if not request.selected_policies:
        return "None specified — use best judgment based on excerpts and question."
    lines = []
    for p in request.selected_policies:
        if isinstance(p, dict):
            lines.append(f"- {p.get('file','unknown')} (state={p.get('state','?')}, year={p.get('year','?')}, type={p.get('power_type','?')})")
    return "\n".join(lines) or "None specified."


@router.post("/generate-doc")
def generate_document(request: DocumentRequest):
    if not request.question or not request.doc_type:
        raise HTTPException(status_code=400, detail="Question and doc_type are required.")

    docs, warning = _retrieve_documents(request)

    # If a policy was explicitly selected but nothing matched, fail clearly
    # instead of silently proceeding with unrelated content.
    if request.selected_policies and not docs:
        raise HTTPException(status_code=400, detail=warning or "No content found for the selected policy.")

    context = ""
    if docs:
        context = "\n".join([doc.page_content for doc in docs[:30]])

    doc_type = request.doc_type.strip().lower()
    selected_desc = _selected_policies_desc(request)

    if doc_type in ("ppt", "pptx"):
        if not context.strip():
            raise HTTPException(status_code=400, detail="No document context found. Please select a policy.")
        prompt = _build_ppt_prompt(context, request.question, selected_desc)
    elif doc_type == "infographic":
        if not context.strip():
            raise HTTPException(status_code=400, detail="No document context available for infographic.")
        prompt = _build_infographic_prompt(context, request.question, selected_desc)
    elif not context.strip():
        raise HTTPException(status_code=400, detail="No document context found. Please select a policy.")
    else:
        prompt = _build_document_prompt(request, context)

    print("\n========== EXPORT DEBUG ==========")
    print("Question:", request.question)
    print("Document Type:", request.doc_type)
    print("Selected files:", _policy_file_set(request.selected_policies))
    print("Context Length:", len(context))
    print("==================================\n")

    raw_response = ask_claude(prompt)

    if not raw_response or raw_response.strip().lower().startswith("failed:"):
        raise HTTPException(
            status_code=500,
            detail=(raw_response.strip() if raw_response else "Claude failed to respond.")
        )

    try:
        content = parse_json_response(raw_response)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse Claude JSON response: {exc}")

    if doc_type in ("ppt", "pptx"):
        path = build_pptx(content)
        return FileResponse(
            path,
            filename="policy_presentation.pptx",
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )

    if doc_type == "word":
        path = build_docx(content)
        return FileResponse(
            path,
            filename="policy_document.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    if doc_type == "report":
        path = build_pdf(content)
        return FileResponse(path, filename="policy_report.pdf", media_type="application/pdf")

    if doc_type == "infographic":
        return {"infographic_data": content}

    raise HTTPException(status_code=400, detail="Unsupported doc_type. Use ppt, word, report, or infographic.")

# Add this function to backend/services/vector_db.py (anywhere below load_vector_store
# is fine). It reuses the exact same db.docstore._dict scanning pattern your
# save_vector_store() already uses for dedup, so it's consistent with how this
# FAISS wrapper actually works — much more reliable than similarity_search()
# for "give me every chunk belonging to file X," which similarity_search was
# never designed to do (it ranks by relevance to a query, not exact match).

def get_docs_by_source_file(db, filenames: set[str]):
    """
    Return every chunk (as LangChain Document objects) whose metadata.source_file
    matches one of the given filenames (already lowercased, no path).
    Returns [] if none match or the docstore can't be inspected.
    """
    if db is None or not filenames:
        return []

    try:
        docs_dict = db.docstore._dict
    except Exception as e:
        print(f"[vector_db] Could not access docstore for filtered lookup: {e}")
        return []

    matched = []
    for _doc_id, document in docs_dict.items():
        meta = getattr(document, "metadata", {}) or {}
        source_file = str(meta.get("source_file", "")).strip().lower()
        # also compare against just the basename in case one side has a path
        basename = source_file.split("/")[-1].split("\\")[-1]
        if source_file in filenames or basename in filenames:
            matched.append(document)

    return matched