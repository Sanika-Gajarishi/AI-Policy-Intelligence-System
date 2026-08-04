"""Post-AI filtering gates for ClimateHub scraper queue admission."""

import re

# --- Tunable config (edit lists here without changing gate logic) ---

ALLOWED_DOC_TYPES = {
    "Policy",
    "Act",
    "Notification",
    "Gazette",
    "Corrigendum",
    "Circular",
    "Government Resolution",
    "Guideline",
    "Order",
    "Roadmap",
    "Regulation",
    "Tender",
}

ALLOWED_TOPICS = {
    "Wind",
    "Solar",
    "Hydrogen",
    "Green Hydrogen",
    "BESS",
    "Biomass",
    "Clean Energy",
    "Transmission",
    "Grid",
    "Renewable Energy",
    "Integrated Energy",
    "Integrated Renewable",
    "Integrated Renewable Energy",
    "Hydro",
    "Ocean",
    "Geothermal",
    "Hybrid",
    "Wind Solar Hybrid",
    "Distribution",
}

REGULATOR_SITES = {"cerc", "merc", "gerc", "meda", "mnre", "cea"}

_GENERAL_TOPIC_ALLOWED_DOC_TYPES = {
    "Gazette",
    "Notification",
    "Order",
    "Government Resolution",
    "Regulation",
    "Act",
    "Corrigendum",
}

# Substring phrases (case-insensitive); annexure/addendum handled separately.
TITLE_DENYLIST_PHRASES = (
    "csr policy",
    "corporate social responsibility",
    "data privacy",
    "retention policy",
    "compliance management",
    "vigilance circular",
    "general commercial circular",
    "testing circular",
    "electric vehicle circular",
    "b and r circular",
    "b&r circular",
    "ce(mm)",
    "ce (stores)",
    "website polic",
)

_DOC_TYPE_KEYWORDS = tuple(doc_type.lower() for doc_type in ALLOWED_DOC_TYPES)

_BLANK_PLACEHOLDER_RE = re.compile(r"_{2,}|\.{4,}")
_TRUNCATED_ENDING_RE = re.compile(
    r"\b(will be|shall be|is to be|to be|has been|have been)\s*$",
    re.IGNORECASE,
)


def _normalize_doc_type(doc_type) -> str:
    if not doc_type:
        return ""
    return str(doc_type).strip()


def _normalize_topic(topic) -> str:
    if not topic:
        return ""
    return str(topic).strip()


def _normalize_site_id(site_id) -> str:
    if not site_id:
        return ""
    return str(site_id).strip().lower()


_TOPIC_STOPWORDS = frozenset({"of", "and", "the", "in", "for", "to", "a", "an"})

_MEDA_MARATHI_ENERGY_KEYWORDS = (
    "धोरण",
    "ऊर्जा",
    "सौर",
    "पवन",
    "हायड्रोजन",
    "अक्षय",
    "नवीकरणीय",
    "अपारंपरिक",
)

_MEDA_GENERAL_TOPIC_DOC_TYPES = frozenset({
    "Policy",
    "Act",
    "Regulation",
    "Notification",
})

_MEDA_POLICY_TITLE_KEYWORDS = (
    "धोरण",
    "policy",
)


def topic_matches(doc_topic: str, allowed_topics: set) -> bool:
    """Token-level match: shared non-stopword tokens between doc topic and allowed topics."""
    doc_topic_norm = _normalize_topic(doc_topic)
    if not doc_topic_norm:
        return False
    doc_words = set(doc_topic_norm.lower().split())
    for allowed in allowed_topics:
        allowed_words = set(str(allowed).lower().split())
        shared = (doc_words - _TOPIC_STOPWORDS) & (allowed_words - _TOPIC_STOPWORDS)
        if shared:
            return True
    return False


def _meda_marathi_energy_title_bypass(meta: dict) -> bool:
    site_id = _normalize_site_id(meta.get("site_id"))
    if site_id != "meda":
        return False
    topic = _normalize_topic(meta.get("topic"))
    if topic != "General":
        return False
    doc_type = _normalize_doc_type(meta.get("doc_type"))
    if doc_type not in _MEDA_GENERAL_TOPIC_DOC_TYPES:
        return False
    title = meta.get("title") or ""
    title_lower = title.lower()
    for keyword in _MEDA_POLICY_TITLE_KEYWORDS:
        if keyword in title or keyword in title_lower:
            return True
    return False


def _title_has_doc_type_keyword(title_lower: str) -> bool:
    return any(keyword in title_lower for keyword in _DOC_TYPE_KEYWORDS)


def _is_truncated_title_fragment(title: str) -> bool:
    stripped = (title or "").strip()
    if not stripped:
        return False

    title_lower = stripped.lower()
    if _title_has_doc_type_keyword(title_lower):
        return False

    if _BLANK_PLACEHOLDER_RE.search(stripped):
        return True

    if _TRUNCATED_ENDING_RE.search(stripped):
        return True

    return False


def _annexure_or_addendum_rejected(title: str) -> str | None:
    stripped = (title or "").strip()
    if not stripped:
        return None

    lower = stripped.lower()
    if lower == "annexure" or lower.startswith("annexure -"):
        return "annexure title"
    if lower == "addendum" or lower.startswith("addendum -"):
        return "addendum title"
    return None


def title_denylist_gate(meta: dict) -> tuple[bool, str]:
    """
    Gate 1 — reject off-topic or junk titles before queue admission.
    Returns (passes, reason). passes=True means the document may continue.
    """
    title = meta.get("title") or ""
    title_lower = title.lower()

    special = _annexure_or_addendum_rejected(title)
    if special:
        return False, special

    for phrase in TITLE_DENYLIST_PHRASES:
        if phrase in title_lower:
            return False, f"contains '{phrase}'"

    if _is_truncated_title_fragment(title):
        return False, "truncated title fragment"

    return True, ""


def type_topic_gate(meta: dict) -> tuple[bool, str]:
    """
    Gate 2 — reject documents whose doc_type/topic/site combo is out of scope.
    Returns (passes, reason). passes=True means the document may continue.
    """
    doc_type = _normalize_doc_type(meta.get("doc_type"))
    topic = _normalize_topic(meta.get("topic"))
    site_id = _normalize_site_id(meta.get("site_id"))

    if doc_type not in ALLOWED_DOC_TYPES:
        return False, "doc_type not allowed"

    if topic_matches(topic, ALLOWED_TOPICS):
        return True, ""

    if _meda_marathi_energy_title_bypass(meta):
        return True, "marathi_energy_keyword"

    if (
        topic == "General"
        and doc_type in _GENERAL_TOPIC_ALLOWED_DOC_TYPES
        and site_id in REGULATOR_SITES
    ):
        return True, ""

    return False, "topic/doc_type/site combination not allowed"
