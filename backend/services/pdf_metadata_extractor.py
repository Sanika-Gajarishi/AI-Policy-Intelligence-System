import os
import re

import fitz  # PyMuPDF
import pdfplumber


STATE_KEYWORDS = {
    "Maharashtra": ["maharashtra", "mahagenco", "merc"],
    "Gujarat": ["gujarat", "gerc", "geda"],
    "Rajasthan": ["rajasthan", "rrecl", "rerc"],
    "Karnataka": ["karnataka", "kredl", "kerc", "bescom"],
    "Tamil Nadu": ["tamil nadu", "tamilnadu", "tangedco", "tnerc"],
    "Andhra Pradesh": ["andhra pradesh", "aperc", "apepdcl"],
    "Telangana": ["telangana", "tserc", "tsgenco"],
    "Madhya Pradesh": ["madhya pradesh", "mperc", "mppmcl"],
    "Uttar Pradesh": ["uttar pradesh", "uperc", "uppcl"],
    "Punjab": ["punjab", "pserc", "pspcl"],
    "Haryana": ["haryana", "herc", "dhbvn"],
    "Kerala": ["kerala", "kseb", "kserc"],
    "Central": [
        "central",
        "cerc",
        "mnre",
        "cea ",
        "ministry of power",
        "government of india",
        "goi",
        "national",
    ],
}

ENERGY_TYPE_KEYWORDS = {
    "Solar": ["solar", "photovoltaic", "pv ", "rooftop solar", "saur"],
    "Wind": ["wind", "wind energy", "wind power"],
    "BESS": ["ess", "bess", "battery storage", "energy storage", "battery energy"],
    "Green Hydrogen": ["green hydrogen", "hydrogen", "electrolyser"],
    "Integrated Renewable": ["integrated renewable", "hybrid", "re integration"],
    "Biomass": ["biomass", "biogas", "bioenergy"],
    "Hydro": ["hydro", "hydropower", "small hydro"],
    "Transmission": ["transmission", "inter-state transmission", "ists"],
    "Distribution": ["distribution", "discom", "feeder"],
    "Grid": ["grid", "smart grid", "grid integration"],
    "Clean Energy": ["clean energy", "clean power", "net zero", "decarbonisation"],
}

DOC_TYPE_KEYWORDS = {
    "Corrigendum": ["corrigendum", "corrigendum -", "corrigendum –", "corrigendum 1", "corrigendum 2"],
    "Government Resolution": ["government resolution", "शासन निर्णय", "शासन निर्णय :-"],
    "Order": ["tariff order", "final order", "order", "directions"],
    "Circular": ["circular", "office memorandum", "memorandum"],
    "Notification": ["notification", "notifications", "notified", "gazette notification"],
    "Guideline": ["guideline", "guidelines"],
    "Tender": ["request for selection", "rfs", "tender", "bid document", "competitive bidding"],
    "Policy": ["policy", "policies"],
    "Road Map": ["road map", "roadmap", "action plan", "framework"],
    "Act": ["electricity act", "energy act", "act "],
    "Gazette": ["official gazette", "gazette"],
    "Regulation": ["regulation", "regulations", "regulatory"],
}

STRICT_DOC_TYPE_KEYWORDS = {
    label: keywords
    for label, keywords in DOC_TYPE_KEYWORDS.items()
    if label != "Policy"
}

ENERGY_RELEVANCE_KEYWORDS = [
    "solar",
    "wind",
    "renewable",
    "electricity",
    "energy",
    "power",
    "tariff",
    "grid",
    "hydrogen",
    "bess",
    "storage",
    "transmission",
    "distribution",
    "photovoltaic",
    "biomass",
    "hydro",
    "cerc",
    "merc",
    "gerc",
    "mnre",
    "discom",
    "genco",
]

NEW_PUB_YEARS = {2023, 2024, 2025, 2026}
EXTRACT_PAGES = max(1, int(os.getenv("SCRAPER_PDF_EXTRACT_PAGES", "5")))


def _extract_first_page_text(pdf_path: str) -> str:
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for i in range(min(EXTRACT_PAGES, len(doc))):
            page_text = doc[i].get_text()
            text += page_text
        doc.close()
        if text.strip():
            return text
    except Exception:
        pass

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:EXTRACT_PAGES]:
                page_text = page.extract_text() or ""
                text += page_text
        if text.strip():
            return text
    except Exception:
        pass

    return text


def _contains_keyword(text: str, keyword: str) -> bool:
    keyword = keyword.strip().lower()
    if not keyword:
        return False
    if re.search(r"\w", keyword[0]) and re.search(r"\w", keyword[-1]):
        return bool(re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text))
    return keyword in text


def _match_keywords(text: str, keyword_map: dict) -> str:
    for label, keywords in keyword_map.items():
        if any(_contains_keyword(text, kw) for kw in keywords):
            return label
    return "General"


def policy_confidence_score(text: str, title: str) -> int:
    combined = f"{title or ''} {text or ''}".lower()
    score = 0
    if "धोरण" in combined:
        score += 3
    if "प्रस्तावना" in combined:
        score += 3
    if _contains_keyword(combined, "policy"):
        score += 2
    if _contains_keyword(combined, "preamble"):
        score += 2
    if _contains_keyword(combined, "vision"):
        score += 1
    if "guiding strategies" in combined:
        score += 1
    return score


def is_real_policy(text: str, title: str) -> bool:
    return policy_confidence_score(text, title) >= 4


def _extract_header_text(text: str, fallback_title: str = "") -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    header = " ".join(lines[:12])
    return f"{fallback_title} {header}".lower()


def _requires_strict_policy_detection(fallback_state: str, source_url: str | None) -> bool:
    state = (fallback_state or "").strip().lower()
    url = (source_url or "").strip().lower()
    return (
        state == "maharashtra"
        or "mahaurja.maharashtra.gov.in" in url
        or "mnre.gov.in" in url
    )


def _detect_doc_type(
    text: str,
    fallback_title: str,
    fallback_category: str,
    strict_policy: bool = False,
) -> str:
    try:
        text_lower = text.lower()
        title_lower = fallback_title.lower()
    except Exception:
        text_lower = text
        title_lower = fallback_title

    header_text = _extract_header_text(text_lower, title_lower)
    if is_real_policy(text, fallback_title):
        return "Policy"
    # Corrigendum often appears at the very top — check explicitly first
    if "corrigendum" in header_text:
        return "Corrigendum"

    keyword_map = STRICT_DOC_TYPE_KEYWORDS if strict_policy else DOC_TYPE_KEYWORDS
    header_match = _match_keywords(header_text, keyword_map)
    if header_match != "General":
        return header_match

    full_match = _match_keywords(text_lower, keyword_map)
    if full_match != "General":
        return full_match

    if strict_policy and fallback_category == "Policy":
        return "General"
    return fallback_category


def _extract_year(text: str) -> int | None:
    patterns = [
        r"\b(20\d{2})\b",
        r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](20\d{2})",
    ]
    years = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            year = int(match.group(1) if len(match.groups()) == 1 else match.group(3))
            if 2000 <= year <= 2030:
                years.append(year)
    return min(years) if years else None


def _extract_month(text: str, year: int | None) -> str | None:
    months = [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ]
    if year:
        # Look for textual month followed by year, e.g. "May 2026"
        match = re.search(rf'({"|".join(months)})\s+{year}', text, re.IGNORECASE)
        if match:
            return match.group(1).capitalize()

        # Also look for numeric date patterns when year is present: dd-mm-YYYY or dd/mm/YYYY
        m = re.search(r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](20\d{2})", text)
        if m and int(m.group(3)) == int(year):
            month_num = int(m.group(2))
            if 1 <= month_num <= 12:
                return months[month_num - 1].capitalize()

    # Fallback: any month name anywhere
    for month in months:
        if month in text:
            return month.capitalize()
    return None


def _extract_day(text: str) -> int | None:
    match = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
        r"(?:january|february|march|april|may|june|july|august|"
        r"september|october|november|december)",
        text,
    )
    if match:
        return int(match.group(1))

    match = re.search(r"\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](20\d{2})", text)
    if match:
        return int(match.group(1))
    return None


def _extract_title(text: str, fallback_title: str) -> str:
    subject_match = re.search(
        r"\bsub(?:ject)?\s*[:\-]\s*(.{20,220}?)(?:\n|$)",
        text,
        re.IGNORECASE,
    )
    if subject_match:
        return subject_match.group(1).strip().title()

    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in text.split("\n")
        if len(line.strip()) > 8
    ]
    skip_words = [
        "e-mail", "email", "website", "www.", "http", "tel no", "phone",
        "page ", "address", "sardar patel vidyut bhavan",
        "block no", "sector-", "gandhinagar", "udhyog bhavan",
        "organization chart", "organisation chart", "org chart",
        "phone no", "fax no", "fax:", "pin code", "pincode",
        "gujarat energy development", "maharashtra energy development",
        "director@", "info@", "contact@",
    ]
    org_words = [
        "commission", "ministry", "government", "department", "nigam ltd",
        "authority", "corporation",
        "development agency", "energy agency", "regulatory commission",
        "electricity board", "power corporation",
    ]
    title_words = [
        "notification", "office memorandum", "circular", "request for selection",
        "rfs", "tender", "order", "policy", "regulation", "scheme",
        "guideline", "guidelines", "power purchase agreement",
    ]
    energy_words = [
        "solar", "wind", "renewable", "energy", "power", "hydrogen",
        "storage", "transmission", "distribution",
    ]

    POLICY_TITLE_PATTERNS = [
        r"renewable energy policy\s*20\d{2}",
        r"solar policy\s*20\d{2}",
        r"wind policy\s*20\d{2}",
        r"green hydrogen policy",
        r"hybrid policy",
        r"energy storage policy",
        r"अपारंपारिक ऊर्जा.*?20\d{2}",
        r"integrated renewable energy policy\s*20\d{2}",
        r"renewable policy\s*20\d{2}",
        r"renewable energy policy",
        r"integrated renewable energy policy",
        r"maharashtra renewable energy policy\s*20\d{2}",
]

    for pattern in POLICY_TITLE_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(0).title()


    candidates = []
    for index, line in enumerate(lines[:40]):
        lower = line.lower()
        if any(skip_word in lower for skip_word in skip_words):
            continue

        score = 0
        if any(word in lower for word in title_words):
            score += 6
        if any(word in lower for word in energy_words):
            score += 2
        if re.search(r"\b20\d{2}\b", lower):
            score += 1
        if any(word in lower for word in org_words):
            score -= 3
        if len(line) > 140:
            score -= 1
        score -= index * 0.1
        candidates.append((score, line))

    if candidates:
        best_score, best_line = max(candidates, key=lambda item: item[0])
        if best_score > 3 and len(best_line) > 12:
            return best_line.title()
    if fallback_title:
        cleaned =(
                 fallback_title
                 .replace("_", " ")
                 .replace("-", " ")
                 .replace(".pdf", "")
                .strip()
         )

    if len(cleaned) > 10:
        return cleaned.title()

    return fallback_title


def _extract_date_from_text(text: str) -> tuple:
    """Search for explicit 'dated' phrases or common date formats on the page.
    Returns (year, month, day) or (None, None, None).
    """
    # look for 'dated 15/05/2026', 'dtd. 15-05-2026', 'dated 15 May 2026', etc.
    patterns = [
        r"(?:dated|dtd\.?|date)\s*[:\-\s]?\s*(\d{1,2}[\/\-\. ]\d{1,2}[\/\-\. ]20\d{2})",
        r"(?:dated|dtd\.?|date)\s*[:\-\s]?\s*(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            g = m.group(1)
            # numeric date
            if re.search(r"\d{1,2}[\/\-\. ]\d{1,2}[\/\-\. ]20\d{2}", g):
                dm = re.search(r"(\d{1,2})[\/\-\. ](\d{1,2})[\/\-\. ](20\d{2})", g)
                if dm:
                    day = int(dm.group(1))
                    month = int(dm.group(2))
                    year = int(dm.group(3))
                    month_name = [
                        "January","February","March","April","May","June",
                        "July","August","September","October","November","December"
                    ][month - 1]
                    from datetime import datetime

                    try:
                        datetime(year, month, day)
                    except ValueError:
                        return None, None, None

                    return year, month_name, day
            # textual month
            tm = re.search(r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})", text, re.IGNORECASE)
            if tm:
                return int(tm.group(3)), tm.group(2).capitalize(), int(tm.group(1))

    return None, None, None


def extract_metadata_with_ai(
    pdf_path: str,
    fallback_title: str,
    fallback_state: str,
    fallback_category: str = "General",
    fallback_year=None,
    fallback_month=None,
    fallback_day=None,
    source_url: str | None = None,
) -> dict:
    try:
        text = _extract_first_page_text(pdf_path)
        try:
            text_lower = text.lower()
            title_lower = fallback_title.lower()
        except Exception:
            text_lower = text
            title_lower = fallback_title

        matched_state = _match_keywords(text_lower, STATE_KEYWORDS)
        state = matched_state if matched_state != "General" else fallback_state
        header_text = _extract_header_text(text_lower, title_lower)
        energy = _match_keywords(header_text, ENERGY_TYPE_KEYWORDS)
        if energy == "General":
            energy = _match_keywords(text_lower, ENERGY_TYPE_KEYWORDS)
        doc_type = _detect_doc_type(
            text,
            fallback_title,
            fallback_category,
            strict_policy=_requires_strict_policy_detection(fallback_state, source_url),
        )
        # Prefer explicit 'dated' phrases inside the document for the true doc date
        d_year, d_month, d_day = _extract_date_from_text(text_lower)
        if d_year:
            year, month, day = d_year, d_month, d_day
        else:
            year = _extract_year(text_lower) or fallback_year
            month = _extract_month(text_lower, year) or fallback_month
            day = _extract_day(text_lower) or fallback_day
        title = _extract_title(text, fallback_title)
        relevant = any(keyword in text_lower for keyword in ENERGY_RELEVANCE_KEYWORDS)
        is_new = year in NEW_PUB_YEARS if year else False

        sentences = re.split(r"(?<=[.!?])\s+", text_lower[:1000])
        description = " ".join(
            sentence.strip().capitalize()
            for sentence in sentences[1:3]
            if len(sentence.strip()) > 30
        )

        try:
            print(f"[OfflineExtractor] {title} | {state} | {energy} | {year}")
        except UnicodeEncodeError:
            safe_title = title.encode("utf-8", errors="replace").decode("utf-8")
            print(f"[OfflineExtractor] {safe_title} | {state} | {energy} | {year}")

        # Site-specific overrides: some sites (e.g. GERC) host Orders that are
        # sometimes mis-classified; prefer Order for known hosts when text
        # contains petition/order markers.
        if source_url:
            src = source_url.lower()
            if "gercin.org" in src or "gerc" in src:
                if doc_type == "General" or any(k in text_lower for k in ("petition", "petitioner", "petition no", "final order", "order")):
                    doc_type = "Order"

        return {
            "title": title,
            "doc_type": doc_type,
            "energy_type": energy,
            "state": state,
            "year": year,
            "month": month,
            "day": day,
            "description": description or f"{doc_type} related to {energy} energy.",
            "is_energy_relevant": relevant,
            "is_new_publication": is_new,
        }

    except Exception as e:
        print(f"[OfflineExtractor] Failed: {e}. Using pure fallback.")
        return {
            "title": fallback_title,
            "doc_type": fallback_category,
            "energy_type": "General",
            "state": fallback_state,
            "year": fallback_year,
            "month": fallback_month,
            "day": fallback_day,
            "description": "",
            "is_energy_relevant": True,
            "is_new_publication": True,
        }
