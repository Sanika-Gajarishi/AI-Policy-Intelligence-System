# NOTE: For JS-rendered sites, Playwright must be installed:
# pip install playwright && playwright install chromium
# If Playwright is not installed, those sites fall back to requests.

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx
import aiofiles
import requests
from requests.exceptions import SSLError
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from services.pdf_metadata_extractor import extract_metadata_with_ai
from services.scrape_filters import title_denylist_gate, type_topic_gate

requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning
)

load_dotenv()

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    if os.getenv("DISABLE_PLAYWRIGHT", "").lower() in ("1", "true", "yes"):
        PLAYWRIGHT_AVAILABLE = False
import uuid
import json
import os
import random
import re
import io
import sys
import time

# Force UTF-8 stdout/stderr so Devanagari/Marathi text prints correctly on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
    "Referer": "https://www.google.com/",
}

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
QUEUE_FILE = DATA_DIR / "scrape_queue.json"
SEEN_URLS_FILE = DATA_DIR / "scraper_seen_urls.json"
SITES_FILE = DATA_DIR / "target_sites.json"
STAGING_DIR = DATA_DIR / "scraped_queue"
POLICY_FILE = DATA_DIR / "policies.json"
RAW_PDFS_DIR = DATA_DIR / "raw_pdfs"
SCRAPER_PAGE_TIMEOUT = int(os.getenv("SCRAPER_PAGE_TIMEOUT", "10"))
SCRAPER_PDF_TIMEOUT = int(os.getenv("SCRAPER_PDF_TIMEOUT", "15"))
SCRAPER_JS_TIMEOUT = int(os.getenv("SCRAPER_JS_TIMEOUT", "15000"))
SCRAPER_JS_SETTLE_MS = int(os.getenv("SCRAPER_JS_SETTLE_MS", "500"))
SCRAPER_PAGE_DELAY_MIN = float(os.getenv("SCRAPER_PAGE_DELAY_MIN", "0.1"))
SCRAPER_PAGE_DELAY_MAX = float(os.getenv("SCRAPER_PAGE_DELAY_MAX", "0.3"))
SCRAPER_PDF_DELAY_MIN = float(os.getenv("SCRAPER_PDF_DELAY_MIN", "0.1"))
SCRAPER_PDF_DELAY_MAX = float(os.getenv("SCRAPER_PDF_DELAY_MAX", "0.4"))
SCRAPER_FAST_MAX_PAGES = int(os.getenv("SCRAPER_FAST_MAX_PAGES", "5"))
SCRAPER_FAST_MAX_NEW = int(os.getenv("SCRAPER_FAST_MAX_NEW", "5"))

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STAGING_DIR, exist_ok=True)
os.makedirs(RAW_PDFS_DIR, exist_ok=True)

CATEGORY_KEYWORDS = {
    "Notification": ["notification", "notifications", "notice", "public notice", "notified"],
    "Corrigendum": ["corrigendum", "corrigendum -", "corrigendum –", "corrigendum 1"],
    "Government Resolution": ["government resolution", "शासन निर्णय", "शासन निर्णय :-"],
    "Circular": ["circular", "office memorandum", "memorandum", "sop", "procedure"],
    "Guideline": ["guideline", "guidelines"],
    "Tender": ["request for selection", "rfs", "tender", "bid document", "competitive bidding"],
    "Order": ["tariff order", "final order", "order", "suo motu"],
    "Policy": ["policy", "programme", "program", "plan"],
    "Road Map": ["road map", "roadmap", "trajectory", "target"],
    "Act": ["amendment act", "electricity act", "act", "bill"],
    "Gazette": ["official gazette", "gazette"],
    "Regulation": ["regulation", "regulations", "regulatory", "rpo"],
}

ENERGY_RELEVANT_KEYWORDS = [
    "solar", "wind", "hydro", "renewable", "clean energy", "green energy",
    "integrated energy", "integrated renewable", "bess", "battery storage",
    "energy storage", "pumped storage",
    "green hydrogen", "hydrogen",
    "green energy open access", "geoa", "distributed renewable",
    "grid", "transmission", "smart grid", "interstate transmission",
    "inter-state transmission", "gna", "connectivity",
    "distribution", "net metering", "rooftop", "roof-top", "prosumer",
    "electricity act", "electricity supply", "tariff", "renewable purchase",
    "rpo", "recs", "carbon", "emission", "energy efficiency",
    "energy conservation", "power purchase", "ppa", "wheeling",
    "open access", "captive", "cogeneration", "biomass", "biogas",
    "waste to energy", "geothermal", "tidal", "offshore wind",
    "onshore wind", "solar park", "ultra mega", "pm kusum",
    "kusum", "saur", "urja", "vidyut", "bijlee", "power policy",
    "energy policy", "power sector", "electricity sector",
    "generation capacity", "installed capacity", "mw", "gw",
    "power plant", "substation", "load dispatch",
    "smart meter", "demand side management", "dsm", "additional surcharge",
    "oa consumer", "oa consumers", "power purchase cost",
]

# ── KNOWN STATIC / PERMANENT DOCUMENTS ─────────────────────────────────────
# These are standing documents that live permanently on CEA/PGCIL/CERC pages.
# They were not published "today" — skip them always.
STATIC_DOCUMENT_PATTERNS = [
    "electricity act 2003",
    "electricity act, 2003",
    "major grid substations",
    "power sector at a glance",
    "ultra mega power project",
    "growth of electricity sector",
    "all india installed capacity",
    "executive summary",
    "monthly generation report",
    "annual report",
    "sop for connectivity portal",   # permanent SOP, not a new notification
    "holiday calendar",
    "holiday calender",
    "detailed advertisement",
    "non executive posts",
    "faqs and common errors",
    "existing regulations",
    "repealed regulations",
    "rti circulars",
    "tenders",
    "draft regulations",
    "notifications",
]

JUNK_TITLE_PATTERNS = [
    "mb, pdf", "kb, pdf", "mb,pdf", "kb,pdf",
    "(size:", "format: pdf",
    "click here", "download here",
    "rti act", "rti application", "fees payment", "rtgs", "neft",
    "name change", "citizen charter", "consumer rights",
    "help manual", "csr policy", "holiday calendar", "holiday calender",
    "advertisement", "recruitment", "vacancy", "tender notice",
    "safeguards monitoring",
    "re-statistics", "data protection", "website policy", "privacy policy",
    # GERC navigation category links — these are menu items, not documents
    "licensing regulations",
    "judgement/orders",
    "daily orders",
    "general regulations",
    "consumer regulations",
    "market development regulations",
    "codes & technical regulations",
    "repealed regulations",
    "orders on renewable energy",
    "re regulations",
    "tariff regulations",
    "procedural regulations",
    # Generic org header/footer patterns that appear as PDF titles
    "organization char",
    "block no.",
    "phone no:",
    "sector-11",
    "gandhinagar",
    "udhyog bhavan",
]


def _safe_print(message: str):
    try:
        print(message)
    except UnicodeEncodeError:
        # Last-resort fallback — should rarely trigger now that stdout is UTF-8
        print(message.encode("utf-8", errors="replace").decode("utf-8"))


def _polite_sleep(min_seconds: float, max_seconds: float):
    if max_seconds <= 0:
        return
    low = max(0, min_seconds)
    high = max(low, max_seconds)
    time.sleep(random.uniform(low, high))


def _unlink_pdf(path: Path, retries: int = 5, delay: float = 0.25) -> bool:
    """
    Windows can keep a just-downloaded PDF locked briefly. Treat missing files
    as already cleaned, and retry locked files before giving up.
    """
    for attempt in range(retries):
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return True
        except PermissionError:
            try:
                os.chmod(path, 0o666)
            except Exception:
                pass
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
                continue
            return False
        except OSError:
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
                continue
            return False
    return False


def is_static_permanent_doc(title: str) -> bool:
    """Return True if this looks like a permanent standing document, not a new publication."""
    lower = title.lower()
    for pattern in STATIC_DOCUMENT_PATTERNS:
        if pattern in lower:
            return True
    return False


def is_junk_title(title: str) -> bool:
    lower = (title or "").lower()
    return any(junk in lower for junk in JUNK_TITLE_PATTERNS)


def is_energy_relevant(title: str, url: str) -> bool:
    title_stripped = title.strip()
    title_lower = title_stripped.lower()
    combined_lower = (title_stripped + " " + url).lower()

    if len(title_stripped) < 8:
        return False

    if re.search(r'\d+(\.\d+)?\s*(mb|kb),?\s*pdf', title_lower):
        return False

    if title_lower.strip() in ("view", "download", "click here", "read more", ""):
        return False

    if is_junk_title(title_lower):
        return False

    normalized = combined_lower.replace("-", " ").replace("_", " ")
    for keyword in ENERGY_RELEVANT_KEYWORDS:
        if keyword in normalized:
            return True

    return False


POWER_TYPE_KEYWORDS = {
    "Solar": ["solar"],
    "Wind": ["wind"],
    "Hydro": ["hydro"],
    "BESS": ["ess", "bess", "battery energy storage", "battery storage", "energy storage", "storage"],
    "Green Hydrogen": ["green hydrogen", "hydrogen"],
    "Integrated Renewable": [
        "integrated renewable",
        "integrated clean energy",
        "renewable energy and energy storage",
        "wind solar hybrid",
        "wind-solar hybrid",
        "hybrid renewable",
    ],
    "Biomass": ["biomass", "biogas", "waste to energy", "waste-to-energy"],
    "Clean Energy": [
        "clean energy",
        "green energy",
        "renewable energy",
        "renewable purchase obligation",
        "rpo",
    ],
    "Transmission": ["transmission"],
    "Distribution": ["distribution", "discom", "licensee"],
    "Grid": ["grid", "connectivity", "open access", "geoa"]
}


def _contains_keyword(text: str, keyword: str) -> bool:
    keyword = keyword.strip().lower()
    if not keyword:
        return False
    if re.search(r"\w", keyword[0]) and re.search(r"\w", keyword[-1]):
        return bool(re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text))
    return keyword in text


def detect_category(title: str, default: str) -> str:
    normalized = str(title or "").lower()
    for category in CATEGORY_KEYWORDS:
        if normalized.strip() == category.lower():
            return category
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if _contains_keyword(normalized, keyword):
                return category
    return default


def detect_year(title: str, url: str):
    combined = f"{title} {url}"
    match = re.search(r"(20\d{2})", combined)
    if match:
        return int(match.group(1))
    return datetime.now().year


def detect_power_type(title: str):
    normalized = title.lower()
    for power_type, keywords in POWER_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if _contains_keyword(normalized, keyword):
                return power_type
    return "General"


def _month_name(value):
    if not value:
        return None
    month_map = {
        "1": "January", "01": "January", "jan": "January", "january": "January",
        "2": "February", "02": "February", "feb": "February", "february": "February",
        "3": "March", "03": "March", "mar": "March", "march": "March",
        "4": "April", "04": "April", "apr": "April", "april": "April",
        "5": "May", "05": "May", "may": "May",
        "6": "June", "06": "June", "jun": "June", "june": "June",
        "7": "July", "07": "July", "jul": "July", "july": "July",
        "8": "August", "08": "August", "aug": "August", "august": "August",
        "9": "September", "09": "September", "sep": "September", "sept": "September", "september": "September",
        "10": "October", "oct": "October", "october": "October",
        "11": "November", "nov": "November", "november": "November",
        "12": "December", "dec": "December", "december": "December",
    }
    return month_map.get(str(value).strip().lower())


def _normalize_metadata(
    meta: dict,
    fallback_title: str,
    fallback_state: str,
    fallback_category: str,
    fallback_year=None,
    fallback_month=None,
    fallback_day=None,
) -> dict:
    normalized = meta if isinstance(meta, dict) else {}
    normalized["title"] = normalized.get("title") or fallback_title
    normalized["description"] = normalized.get("description") or normalized["title"]
    normalized["state"] = fallback_state or normalized.get("state") or "Unknown"
    normalized["doc_type"] = (
        normalized.get("doc_type")
        or detect_category(normalized["title"], fallback_category)
    )
    normalized["energy_type"] = (
        normalized.get("energy_type")
        or detect_power_type(normalized["title"])
    )
    normalized["year"] = normalized.get("year") or fallback_year
    normalized["month"] = _month_name(normalized.get("month")) or _month_name(fallback_month)
    normalized["day"] = normalized.get("day") or fallback_day

    if normalized.get("is_energy_relevant") is None:
        normalized["is_energy_relevant"] = is_energy_relevant(normalized["title"], "")

    if normalized.get("is_new_publication") is None:
        try:
            pub_year = int(normalized["year"]) if normalized.get("year") else None
        except (TypeError, ValueError):
            pub_year = None
        normalized["is_new_publication"] = bool(pub_year and pub_year >= datetime.now().year - 1)

    return normalized


def _extract_json_object(text: str) -> dict:
    cleaned = (text or "").strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


def _fallback_metadata(
    fallback_title: str,
    fallback_state: str,
    fallback_category: str,
    fallback_year=None,
    fallback_month=None,
    fallback_day=None,
) -> dict:
    has_publication_date = (
        fallback_year is not None
        and fallback_month is not None
        and fallback_day is not None
    )
    return {
        "title": fallback_title,
        "doc_type": detect_category(fallback_title, fallback_category),
        "energy_type": detect_power_type(fallback_title),
        "state": fallback_state,
        "year": fallback_year,
        "month": fallback_month,
        "day": fallback_day,
        "description": fallback_title,
        "is_energy_relevant": True,
        "is_new_publication": has_publication_date,
    }


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").lower().replace("www.", "")
    path = (parsed.path or "").rstrip("/")
    return f"{parsed.scheme.lower()}://{host}{path}"


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def fetch_page_async(url: str, client: httpx.AsyncClient) -> tuple:
    try:
        resp = await client.get(url, timeout=SCRAPER_PAGE_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        return resp.text, str(resp.url)
    except Exception as e:
        _safe_print(f"httpx async failed for {url}: {e}")
        return "", url


def extract_all_metadata_parallel(pdf_tasks: list, max_workers: int = 10) -> list:
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                extract_metadata_with_ai,
                str(task["staging_path"]),
                task["title"],
                task["site_state"],
                task["site_category"],
                task.get("html_year"),
                task.get("html_month"),
                task.get("html_day"),
                task.get("source_url"),
            ): task
            for task in pdf_tasks
        }
        for future in as_completed(futures):
            task = futures[future]
            try:
                meta = future.result()
                results.append((task, meta))
            except Exception as e:
                _safe_print(f"Metadata extraction failed for {task.get('source_url')}: {e}")
    return results


# Sites that bypass the AI year gate only for Regulation/Act (not Policy/Order).
_REGULATOR_STANDING_SITES = frozenset({"gerc", "merc", "cerc"})
_DEFAULT_STANDING_BYPASS_DOC_TYPES = frozenset({"Policy", "Act", "Regulation"})
_REGULATOR_STANDING_BYPASS_DOC_TYPES = frozenset({"Regulation", "Act"})

_FILENAME_DATE_PATTERNS = (
    (
        re.compile(r"dtd[.\-_]+(\d{2})[.\-](\d{2})[.\-](\d{4})", re.IGNORECASE),
        "dtd",
        lambda match: int(match.group(3)),
    ),
    (
        re.compile(r"_(\d{4})-(\d{2})-(\d{2})"),
        "iso",
        lambda match: int(match.group(1)),
    ),
    (
        re.compile(r"dated[_\-.](\d{2})[.\-](\d{2})[.\-](\d{4})", re.IGNORECASE),
        "dated",
        lambda match: int(match.group(3)),
    ),
    (
        re.compile(r"(\d{2})[.\-](\d{2})[.\-](\d{4})"),
        "ddmmyyyy",
        lambda match: int(match.group(3)),
    ),
)


def _normalize_doc_type(doc_type) -> str:
    if not doc_type:
        return ""
    return str(doc_type).strip()


def _standing_bypass_doc_types_for_site(site: dict) -> frozenset:
    custom = site.get("standing_bypass_doc_types")
    if custom:
        return frozenset(str(doc_type).strip() for doc_type in custom if str(doc_type).strip())
    site_id = str(site.get("id", "")).lower()
    if site_id in _REGULATOR_STANDING_SITES:
        return _REGULATOR_STANDING_BYPASS_DOC_TYPES
    return _DEFAULT_STANDING_BYPASS_DOC_TYPES


def _parse_doc_year(year_value) -> Optional[int]:
    if year_value is None:
        return None
    try:
        return int(year_value)
    except (TypeError, ValueError):
        return None


def _evaluate_standing_bypass(
    site: dict,
    doc_type: str,
    doc_year: Optional[int],
    year_filter: Optional[int],
) -> tuple[bool, bool, str]:
    """
    Returns (eligible, allowed, skip_reason).
    eligible: doc type qualifies for standing bypass consideration.
    allowed: may bypass the year gate.
    skip_reason: 'seeded_skip' when eligible but blocked by seeded mode.
    """
    if not site.get("allow_standing_policies"):
        return False, False, ""
    normalized = _normalize_doc_type(doc_type)
    if not normalized or normalized not in _standing_bypass_doc_types_for_site(site):
        return False, False, ""

    if not site.get("standing_policies_already_seeded", False):
        return True, True, ""

    if doc_year is None:
        return True, True, ""

    if year_filter is not None and doc_year == year_filter:
        return True, True, ""

    return True, False, "seeded_skip"


def _extract_reliable_date_from_filename(*texts) -> tuple[Optional[int], Optional[str], Optional[int], str]:
    combined = " ".join(str(text) for text in texts if text)
    if not combined:
        return None, None, None, ""
    current_year = datetime.now().year
    for pattern, label, extractor in _FILENAME_DATE_PATTERNS:
        match = pattern.search(combined)
        if not match:
            continue
        try:
            year = extractor(match)
        except (TypeError, ValueError):
            continue
        if 2000 <= year <= current_year + 2:
            if label == "iso":
                month_num = match.group(2)
                day = int(match.group(3))
            else:
                month_num = match.group(2)
                day = int(match.group(1))
            return year, _month_name(month_num), day, label
    return None, None, None, ""


def _date_matches_explicit_filters(
    doc_year,
    doc_month,
    doc_day,
    year_filter: Optional[int],
    month_filter: Optional[str],
    day_filter: Optional[int],
) -> bool:
    if year_filter is not None:
        try:
            if int(doc_year) != int(year_filter):
                return False
        except (TypeError, ValueError):
            return False
    if month_filter:
        normalized_doc_month = _month_name(doc_month)
        normalized_filter_month = _month_name(month_filter)
        if not normalized_doc_month or normalized_doc_month != normalized_filter_month:
            return False
    if day_filter is not None:
        try:
            if int(doc_day) != int(day_filter):
                return False
        except (TypeError, ValueError):
            return False
    return True


def _new_site_filter_stats() -> dict:
    return {
        "downloaded": 0,
        "passed_year": 0,
        "bypassed_standing": 0,
        "rejected_year": 0,
        "rejected_type_topic": 0,
        "rejected_denylist": 0,
        "added_to_queue": 0,
    }


def _process_pdf_tasks(
    pdf_tasks: list,
    site: dict,
    results: list,
    seen_urls: set,
    session_pdf_urls: set,
    today: datetime,
    year_filter: Optional[int] = None,
    month_filter: Optional[str] = None,
    day_filter: Optional[int] = None,
    site_stats: Optional[dict] = None,
    standing_policy_seen_this_run: Optional[set] = None,
) -> int:
    found_count = 0
    stats = site_stats if site_stats is not None else _new_site_filter_stats()
    standing_titles_seen = standing_policy_seen_this_run if standing_policy_seen_this_run is not None else set()
    MONTH_MAP = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
    }
    extracted_items = extract_all_metadata_parallel(pdf_tasks)
    for task, ai_meta in extracted_items:
        staging_path = task["staging_path"]
        title = task["title"]
        html_year = task["html_year"]
        html_month = task["html_month"]
        html_day = task["html_day"]
        absolute_pdf_url = task["source_url"]
        url_key = task["url_key"]
        file_id = task["file_id"]
        filename = task["filename"]

        if not isinstance(ai_meta, dict):
            _safe_print(f"  ✗ AI metadata extraction failed for {absolute_pdf_url}")
            _unlink_pdf(staging_path)
            continue

        ai_meta = _normalize_metadata(
            ai_meta,
            title,
            site.get("state", "Central"),
            site.get("default_category", "General"),
            html_year,
            html_month,
            html_day,
        )

        ai_meta["is_energy_relevant"] = True
        if not ai_meta.get("year"):
            extracted_year = html_year or _extract_year_from_text(title, absolute_pdf_url)
            if extracted_year:
                ai_meta["year"] = extracted_year
        if not ai_meta.get("month") and html_month:
            ai_meta["month"] = html_month
        if not ai_meta.get("day") and html_day:
            ai_meta["day"] = html_day

        doc_type = _normalize_doc_type(ai_meta.get("doc_type"))
        doc_year_int = _parse_doc_year(ai_meta.get("year"))
        _, standing_bypass, standing_skip = _evaluate_standing_bypass(
            site, doc_type, doc_year_int, year_filter
        )
        standing_bypass_used = False

        filename_year, filename_month, filename_day, filename_pattern = _extract_reliable_date_from_filename(
            filename, absolute_pdf_url, title
        )
        filename_gate_passed = False
        if (
            filename_year is not None
            and year_filter is not None
            and _date_matches_explicit_filters(
                filename_year,
                filename_month,
                filename_day,
                year_filter,
                month_filter,
                day_filter,
            )
        ):
            ai_meta["year"] = filename_year
            if filename_month:
                ai_meta["month"] = filename_month
            if filename_day:
                ai_meta["day"] = filename_day
            doc_year_int = filename_year
            filename_gate_passed = True
            if filename_pattern == "dtd":
                _safe_print(
                    f"  ○ Filename date gate (dtd pattern, date={filename_day}-{filename_month}-{filename_year}): {filename}"
                )
            else:
                _safe_print(
                    f"  ○ Filename date gate ({filename_pattern} pattern, "
                    f"date={filename_day}-{filename_month}-{filename_year}): {filename}"
                )

        if filename_gate_passed:
            passes = True
            stats["passed_year"] += 1
        else:
            passes, gate_reason = _ai_date_gate(
                ai_meta,
                year_filter,
                month_filter,
                day_filter,
                today,
                trust_official_site=True,
            )
            if not passes:
                if standing_bypass:
                    display_title = ai_meta.get("title", title)
                    _safe_print(f"  ○ Standing policy (year gate skipped): {display_title}")
                    stats["bypassed_standing"] += 1
                    standing_bypass_used = True
                elif standing_skip == "seeded_skip":
                    display_title = ai_meta.get("title", title)
                    _safe_print(
                        f"  ○ Standing policy (seeded mode, skipping year={doc_year_int}): "
                        f"{display_title}"
                    )
                    stats["rejected_year"] += 1
                    _unlink_pdf(staging_path)
                    continue
                else:
                    _safe_print(f"  ✗ AI gate ({gate_reason}): {ai_meta.get('title', title)[:50]}")
                    stats["rejected_year"] += 1
                    _unlink_pdf(staging_path)
                    continue
            else:
                stats["passed_year"] += 1

        filter_meta = {
            "title": ai_meta.get("title", title),
            "doc_type": ai_meta.get("doc_type"),
            "topic": ai_meta.get("energy_type"),
            "year": ai_meta.get("year"),
            "site_id": site.get("id"),
        }
        passes, _ = title_denylist_gate(filter_meta)
        if not passes:
            _safe_print(f"  ✗ Title denylist: {filter_meta['title']}")
            stats["rejected_denylist"] += 1
            _unlink_pdf(staging_path)
            continue

        passes, topic_gate_reason = type_topic_gate(filter_meta)
        if not passes:
            _safe_print(
                f"  ✗ Type/Topic gate (doc_type={filter_meta.get('doc_type')}, "
                f"topic={filter_meta.get('topic')}, site={filter_meta.get('site_id')}): "
                f"{filter_meta['title']}"
            )
            stats["rejected_type_topic"] += 1
            _unlink_pdf(staging_path)
            continue
        if topic_gate_reason == "marathi_energy_keyword":
            _safe_print(
                f"  ○ Marathi energy keyword match (topic gate bypassed): "
                f"{filter_meta['title']}"
            )

        if standing_bypass_used:
            display_title = ai_meta.get("title", title)
            normalized_standing_title = display_title.strip().lower()
            if normalized_standing_title in standing_titles_seen:
                _safe_print(
                    f"  ○ Standing policy already added this run, skip: {display_title}"
                )
                stats["rejected_year"] += 1
                _unlink_pdf(staging_path)
                continue
            standing_titles_seen.add(normalized_standing_title)

        pub_year = ai_meta.get("year")
        pub_month = ai_meta.get("month")
        pub_day = ai_meta.get("day")
        month_num = MONTH_MAP.get(str(pub_month).lower(), None) if pub_month else None
        if pub_year and month_num and pub_day:
            publication_date = f"{pub_year}-{month_num}-{str(pub_day).zfill(2)}"
        elif pub_year and month_num:
            publication_date = f"{pub_year}-{month_num}"
        elif pub_year:
            publication_date = str(pub_year)
        else:
            publication_date = None

        if not absolute_pdf_url or not absolute_pdf_url.startswith("http"):
            _safe_print(f"  ✗ Invalid URL: {absolute_pdf_url}")
            _unlink_pdf(staging_path)
            continue

        duplicate_info = find_existing_document(ai_meta.get("title", title), absolute_pdf_url)

        has_explicit_date_filter = (
            year_filter is not None
            or month_filter is not None
            or day_filter is not None
        )
        metadata_year = ai_meta.get("year")
        metadata_month = ai_meta.get("month")

        metadata = {
            "id": file_id,
            "title": ai_meta.get("title", title),
            "description": ai_meta.get("description", title),
            "source_id": site.get("id"),
            "source_name": site.get("name"),
            "source_url": absolute_pdf_url,
            "state": site.get("state", "Central"),
            "year": metadata_year if has_explicit_date_filter else (metadata_year or today.year),
            "month": metadata_month if has_explicit_date_filter else (metadata_month or today.strftime("%B")),
            "pub_date": f"{metadata_month or ''} {metadata_year or ''}".strip(),
            "day": pub_day,
            "html_year": html_year,
            "html_month": html_month,
            "html_day": html_day,
            "publication_date": publication_date,
            "power_type": ai_meta.get("energy_type") or detect_power_type(ai_meta.get("title", title)),
            "category": detect_category(
                ai_meta.get("doc_type") or ai_meta.get("title", title),
                site.get("default_category", "General"),
            ),
            "filename": filename,
            "status": "pending",
            "scraped_at": today.isoformat(),
            "scrape_session": today.strftime("%Y-%m-%d"),
            "scrape_year_filter": year_filter,
            "scrape_month_filter": month_filter,
            "scrape_day_filter": day_filter,
        }
        if duplicate_info:
            metadata["duplicate_of"] = duplicate_info
            metadata["already_in_system"] = True

        seen_urls.add(absolute_pdf_url)
        seen_urls.add(url_key)
        session_pdf_urls.add(url_key)
        results.append(metadata)
        found_count += 1
        stats["added_to_queue"] += 1
        duplicate_note = " existing" if duplicate_info else ""
        _safe_print(
            f"  ✓ Added{duplicate_note}: [{ai_meta.get('doc_type')}][{ai_meta.get('energy_type')}] "
            f"{ai_meta.get('title', title)[:60]}"
        )

    return found_count


def _site_base_url(site: dict) -> str:
    base = site.get("base_url")
    if base:
        return base.rstrip("/")
    scrape_urls = site.get("scrape_urls") or []
    if scrape_urls:
        parsed = urlparse(scrape_urls[0])
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    return ""


def _same_host(url: str, base_url: str) -> bool:
    if not url or not base_url:
        return False
    a = urlparse(url).netloc.lower().replace("www.", "")
    b = urlparse(base_url).netloc.lower().replace("www.", "")
    return bool(a and b and a == b)


def _build_seen_urls_for_run(seen_from_file: set, queue: list) -> set:
    seen = set()
    for item in queue:
        if item.get("status") != "pending":
            continue
        url = item.get("source_url")
        if url:
            seen.add(url)
            seen.add(_normalize_url(url))
    return seen


def find_existing_document(new_title: str, new_source_url: str) -> dict | None:
    normalized_new = _normalize_url(new_source_url)
    queue = load_queue()
    for item in queue:
        if item.get("status") == "rejected":
            continue
        existing_url = item.get("source_url")
        if existing_url and (
            existing_url == new_source_url
            or _normalize_url(existing_url) == normalized_new
        ):
            return {
                "matched_by": "source_url",
                "source_url": existing_url,
                "status": item.get("status"),
                "existing_filename": item.get("accepted_filename") or item.get("filename"),
                "title": item.get("title"),
            }

    policies_file = DATA_DIR / "policies.json"
    if policies_file.exists():
        with open(policies_file, encoding="utf-8") as f:
            policies = json.load(f)
        for policy in policies:
            file_name = policy.get("file", "")
            if not file_name or not (RAW_PDFS_DIR / file_name).exists():
                continue
            existing_title = file_name.replace(".pdf", "").replace("_", " ").lower()
            if new_title.lower()[:30] in existing_title or existing_title[:30] in new_title.lower():
                return {
                    "matched_by": "title",
                    "existing_filename": file_name,
                    "title": existing_title,
                    "category": policy.get("category"),
                    "power_type": policy.get("power_type"),
                    "state": policy.get("state"),
                    "year": policy.get("year"),
                }

    return None


def is_duplicate_document(new_title: str, new_source_url: str) -> bool:
    return find_existing_document(new_title, new_source_url) is not None


def load_seen_urls() -> set:
    if not SEEN_URLS_FILE.exists():
        return set()
    try:
        with open(SEEN_URLS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data if isinstance(data, list) else [])
    except Exception as e:
        print(f"Failed to load seen URLs: {e}")
        return set()


def save_seen_urls(seen: set):
    try:
        with open(SEEN_URLS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(seen)), f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to save seen URLs: {e}")


def load_queue() -> list:
    if not QUEUE_FILE.exists():
        return []
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Failed to load scrape queue: {e}")
        return []


def save_queue(queue: list):
    try:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to save scrape queue: {e}")


def clear_pending_scrape_artifacts() -> dict:
    """
    Remove unaccepted scraper test artifacts:
    - pending items from scrape_queue.json
    - temporary PDFs in data/scraped_queue

    Accepted policy PDFs in data/raw_pdfs are intentionally not touched.
    """
    queue = load_queue()
    pending_ids = {item.get("id") for item in queue if item.get("status") == "pending"}
    pending_filenames = {
        item.get("filename")
        for item in queue
        if item.get("status") == "pending" and item.get("filename")
    }

    deleted_files = 0
    failed_deletes = []
    for path in STAGING_DIR.glob("*.pdf"):
        if not pending_filenames or path.name in pending_filenames:
            if _unlink_pdf(path):
                deleted_files += 1
            else:
                failed_deletes.append(str(path))

    kept_queue = [item for item in queue if item.get("status") != "pending"]
    save_queue(kept_queue)

    return {
        "cleared_pending": len(pending_ids),
        "deleted_files": deleted_files,
        "failed_deletes": failed_deletes,
    }


def load_sites() -> list:
    if not SITES_FILE.exists():
        print("Target sites file not found: data/target_sites.json")
        return []
    try:
        with open(SITES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Failed to load target sites: {e}")
        return []


def save_sites(sites: list):
    try:
        with open(SITES_FILE, "w", encoding="utf-8") as f:
            json.dump(sites, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        print(f"Failed to save target sites: {e}")


def _mark_standing_policies_seeded(site_id: str):
    if not site_id:
        return
    sites = load_sites()
    updated = False
    for site in sites:
        if site.get("id") != site_id or not site.get("allow_standing_policies"):
            continue
        if site.get("standing_policies_already_seeded", False):
            continue
        site["standing_policies_already_seeded"] = True
        updated = True
    if updated:
        save_sites(sites)


def category_to_filename_slug(category: str) -> str:
    raw = str(category or "General").strip()
    slug = re.sub(r"[^\w\s-]", "", raw).strip().replace(" ", "_")
    return slug or "General"


def build_policy_filename(item: dict) -> str:
    def clean(value: str) -> str:
        cleaned = re.sub(r"[^\w\s-]", "", str(value or "")).strip().replace(" ", "_")
        return cleaned or "Unknown"

    state = clean(item.get("state", "Unknown"))
    power_type = clean(item.get("power_type", "General"))
    category = clean(item.get("category", "General"))
    year = item.get("year", datetime.now().year)
    base = f"{state}_{power_type}_{category}_{year}.pdf"
    target = RAW_PDFS_DIR / base
    if not target.exists():
        return base

    short_id = str(item.get("id", uuid.uuid4()))[:8]
    return f"{state}_{power_type}_{category}_{year}_{short_id}.pdf"

def update_item_from_filename(item: dict, filename: str):
    """
    Update scraper metadata from a corrected filename.

    Expected format:
    State_EnergyType_DocumentType_Year.pdf
    """

    if not filename:
        return

    # Remove .pdf
    name, _ = os.path.splitext(filename.strip())

    # Split into parts
    parts = name.split("_")

    # Expected:
    # Maharashtra_Solar_Order_2025
    if len(parts) != 4:
        raise ValueError(
            "Filename must follow: State_EnergyType_DocumentType_Year.pdf"
        )

    state = parts[0]
    year = parts[-1]
    category = parts[-2]
    power_type = "_".join(parts[1:-2]).replace("_", " ")

    # Update metadata
    item["state"] = state
    item["power_type"] = power_type
    item["category"] = category
    item["year"] = int(year)


def save_policy_metadata(
    file_name,
    state,
    year,
    month,
    power_type,
    category="General",
    drive_file_id=None,
    drive_url=None,
):
    if not POLICY_FILE.exists():
        with open(POLICY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

    try:
        with open(POLICY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = []

    if not isinstance(data, list):
        data = []

    try:
        policy_year = int(year)
    except (TypeError, ValueError):
        policy_year = datetime.now().year

    data = [policy for policy in data if policy.get("file") != file_name]
    data.append({
        "file": file_name,
        "state": state or "Unknown",
        "year": policy_year,
        "month": month or "January",
        "power_type": power_type or "General",
        "category": category or "General",
        "drive_file_id": drive_file_id,
        "drive_url": drive_url,
    })

    try:
        with open(POLICY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Failed to save policy metadata: {e}")


def fetch_page_html(url: str, browser_page=None, session=None, use_playwright=True, async_client=None):
    if browser_page is not None:
        try:
            browser_page.goto(url, wait_until="domcontentloaded", timeout=SCRAPER_JS_TIMEOUT)
            browser_page.wait_for_timeout(SCRAPER_JS_SETTLE_MS)
            return browser_page.content(), browser_page.url
        except Exception as e:
            _safe_print(f"Playwright page failed for {url}: {e}, falling back to non-JS fetch")

    if use_playwright and PLAYWRIGHT_AVAILABLE:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_extra_http_headers(BROWSER_HEADERS)
                page.goto(url, wait_until="domcontentloaded", timeout=SCRAPER_JS_TIMEOUT)
                page.wait_for_timeout(SCRAPER_JS_SETTLE_MS)
                html = page.content()
                final_url = page.url
                browser.close()
                return html, final_url
        except Exception as e:
            _safe_print(f"Playwright failed for {url}: {e}, falling back to non-JS fetch")

    if async_client is not None:
        try:
            return _run_async(fetch_page_async(url, async_client))
        except Exception as e:
            _safe_print(f"httpx async failed for {url}: {e}")

    try:
        http = session or requests
        resp = http.get(url, timeout=SCRAPER_PAGE_TIMEOUT, headers=BROWSER_HEADERS)
        resp.raise_for_status()
        return resp.text, resp.url
    except SSLError as e:
        _safe_print(f"SSL verification failed for {url}: {e}. Retrying without verification.")
        try:
            http = session or requests
            resp = http.get(url, timeout=SCRAPER_PAGE_TIMEOUT, headers=BROWSER_HEADERS, verify=False)
            resp.raise_for_status()
            return resp.text, resp.url
        except Exception as retry_error:
            _safe_print(f"requests failed for {url}: {retry_error}")
            return "", url
    except Exception as e:
        _safe_print(f"requests failed for {url}: {e}")
        return "", url


def _resolve_document_url(href: str, page_url: str, base_url: str) -> str:
    """Build absolute document URL, fixing common gov-site path duplication."""
    href = (href or "").strip()
    if not href:
        return href
    if href.startswith(("http://", "https://")):
        return href

    normalized_href = href.lstrip("/")
    root = (base_url or page_url).rstrip("/")
    if normalized_href.lower().startswith("site/"):
        absolute = f"{root}/{normalized_href}"
    else:
        absolute = urljoin(page_url, href)

    parsed = urlparse(absolute)
    path = parsed.path
    if re.search(r"/Site/\d+/Site/", path, re.IGNORECASE):
        path = re.sub(r"/Site/\d+/Site/", "/Site/", path, flags=re.IGNORECASE)
    if re.search(r"/Site/Site/", path, re.IGNORECASE):
        path = re.sub(r"/Site/Site/", "/Site/", path, flags=re.IGNORECASE)
    if path != parsed.path:
        absolute = parsed._replace(path=path).geturl()
    return absolute


def _title_from_url(url: str) -> str:
    path = urlparse(url or "").path
    stem = os.path.splitext(os.path.basename(path))[0]
    if not stem:
        return ""
    title = re.sub(r"[_-]+", " ", stem)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _extract_year_from_text(*texts) -> Optional[int]:
    for text in texts:
        if not text:
            continue
        match = re.search(r"(20\d{2})", str(text))
        if match:
            try:
                return int(match.group(1))
            except (TypeError, ValueError):
                continue
    return None


def _is_likely_pdf_link(href: str, anchor_text: str = "") -> bool:
    raw_href = (href or "").strip()
    clean_href = raw_href.split("?")[0].split("#")[0].lower()
    href_lower = raw_href.lower()
    text_lower = (anchor_text or "").lower()
    document_text_keywords = [
        "download",
        "pdf",
        "order",
        "notification",
        "circular",
        "regulation",
        "tender",
        "rfs",
    ]
    document_href_keywords = [
        "download",
        "viewfile",
        "getfile",
        "fetch",
        "attachment",
    ]
    return (
        clean_href.endswith(".pdf")
        or ".pdf?" in href_lower
        or "pdf" in urlparse(raw_href).path.lower()
        or any(keyword in text_lower for keyword in document_text_keywords)
        or any(keyword in href_lower for keyword in document_href_keywords)
    )


def _is_download_href(href: str) -> bool:
    clean_href = (href or "").strip().split("?")[0].split("#")[0].lower()
    return clean_href.endswith((
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".zip",
        ".rar",
        ".jpg",
        ".jpeg",
        ".png",
    ))


def _looks_like_document_page(href: str, text: str) -> bool:
    combined = f"{href or ''} {text or ''}".lower()
    return any(
        keyword in combined
        for keyword in [
            "act",
            "acts",
            "amendment",
            "approval",
            "commission",
            "consultation",
            "determination",
            "directive",
            "draft",
            "gazette",
            "gazettes",
            "guideline",
            "guidelines",
            "petition",
            "proceeding",
            "public notice",
            "public-notice",
            "rule",
            "rules",
            "order",
            "orders",
            "regulation",
            "regulations",
            "notification",
            "notifications",
            "circular",
            "circulars",
            "policy",
            "policies",
            "scheme",
            "schemes",
            "renewable",
            "solar",
            "wind",
            "tariff",
            "myt",
            "document",
            "documents",
            "download",
            "downloads",
        ]
    )


def _should_inspect_pdf_with_ai(title: str, url: str, site: dict) -> bool:
    """
    Keep the cheap title/URL filter, but do not throw away official document
    links just because the anchor text omits the energy technology.
    """
    if is_static_permanent_doc(title) or is_junk_title(title):
        return False

    if is_energy_relevant(title, url):
        return True

    category = detect_category(title, site.get("default_category", "General"))
    if category != "General":
        return True

    source_text = " ".join(
        str(site.get(key, ""))
        for key in ("name", "full_name", "default_category")
    )
    source_lower = source_text.lower()
    if any(keyword in source_lower for keyword in ("electricity", "energy", "power", "renewable", "transmission")):
        return True

    return is_energy_relevant(source_text, site.get("base_url", ""))


def _discover_pages_from_html(
    soup: BeautifulSoup,
    page_url: str,
    base_url: str,
    queued_pages: set,
    max_pages: int,
) -> list:
    discovered = []
    for anchor in soup.find_all("a", href=True):
        if len(queued_pages) >= max_pages:
            break

        href = anchor["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        if _is_download_href(href):
            continue

        absolute_url = urljoin(page_url, href).split("#")[0]
        parsed = urlparse(absolute_url)
        if parsed.scheme not in ("http", "https"):
            continue
        if not _same_host(absolute_url, base_url or page_url):
            continue

        normalized = _normalize_url(absolute_url)
        if normalized in queued_pages:
            continue

        text = anchor.get_text(" ", strip=True)
        if not _looks_like_document_page(href, text):
            continue

        queued_pages.add(normalized)
        discovered.append(absolute_url)

    return discovered

def _extract_title_from_link(link, absolute_url: str) -> str:
    BAD_TITLES = {
        "",
        "view",
        "download",
        "click here",
        "pdf",
        "read more",
    }

    # 1. Anchor text
    title = link.get_text(" ", strip=True)
    title = re.sub(r"\s+", " ", title).strip()

    if (
            title
            and title.lower() not in BAD_TITLES
            and not re.fullmatch(
                r"^(view|download|click here|read more)(\s+pdf)?$",
                title,
                flags=re.I,
        )
    ):
        return title
    
        

    # 2. Table row extraction (works for MNRE/CERC/MERC)
    td = link.find_parent("td")
    if td:
        row = td.find_parent("tr")

        if row:
            texts = []

            for cell in row.find_all("td"):
                txt = cell.get_text(" ", strip=True)

                txt = re.sub(
                    r"\b(view|download|click here)\b",
                    "",
                    txt,
                    flags=re.I,
                )

                txt = re.sub(r"\s+", " ", txt).strip()

                if (
                        txt
                        and len(txt) > 10
                         and not re.fullmatch(
                            r"(view|download|click here|read more)(\s+pdf)?",
                            txt,
                            flags=re.I,
                    )
                ):
                    texts.append(txt)

            if texts:
                return max(texts, key=len)

    # 3. Parent containers (MEDA/Mahadiscom)
    parent = link.parent

    for _ in range(5):
        if parent is None:
            break

        txt = parent.get_text(" ", strip=True)

        txt = re.sub(
            r"\b(view|download|click here)\b",
            "",
            txt,
            flags=re.I,
        )

        txt = re.sub(r"\s+", " ", txt).strip()

        if  (
            txt
            and len(txt) > 10
            and not re.fullmatch(
                r"(view|download|click here|read more)(\s+pdf)?",
                txt,
                flags=re.I,
            )
        ):
            return txt

        parent = parent.parent

    # 4. Filename fallback
    path = urlparse(absolute_url).path
    filename = os.path.basename(path)

    if filename:
        filename = os.path.splitext(filename)[0]
        filename = re.sub(r"[_\-]+", " ", filename)
        filename = re.sub(r"\s+", " ", filename).strip()

        if filename.lower() not in BAD_TITLES:
            return filename

    # 5. Last fallback
    return absolute_url



def _extract_date_from_context(anchor, page_url: str) -> tuple:
    """
    Looks at the HTML surrounding a PDF anchor for a publication date.
    Returns (year, month, day) — any can be None.
    """
    DATE_PATTERNS = [
        r'(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](20\d{2})',
        r'(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2})(?!\d)',
        r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|'
        r'September|October|November|December)\s+(20\d{2})',
        r'(January|February|March|April|May|June|July|August|'
        r'September|October|November|December)\s+(\d{1,2}),?\s+(20\d{2})',
        r'/(20\d{2})/(\d{2})/',
    ]

    MONTH_NAMES = {
        '01':'January','02':'February','03':'March','04':'April',
        '05':'May','06':'June','07':'July','08':'August',
        '09':'September','10':'October','11':'November','12':'December',
        '1':'January','2':'February','3':'March','4':'April',
        '5':'May','6':'June','7':'July','8':'August',
        '9':'September','10':'October','11':'November','12':'December',
    }

    texts_to_check = []
    href = anchor.get('href', '')
    texts_to_check.append(href)
    texts_to_check.append(page_url)

    parent = anchor.parent
    for _ in range(5):
        if parent is None:
            break
        tag = getattr(parent, 'name', '')
        if tag == 'td':
            row = parent.parent
            if getattr(row, 'name', '') == 'tr':
                texts_to_check.append(row.get_text(' ', strip=True))
            for sibling in parent.find_previous_siblings('td') + parent.find_next_siblings('td'):
                texts_to_check.append(sibling.get_text(' ', strip=True))
        if tag in ('tr', 'li', 'div', 'p'):
            texts_to_check.append(parent.get_text(' ', strip=True))
            break
        texts_to_check.append(parent.get_text(' ', strip=True)[:200])
        parent = parent.parent

    def _validate_date(year, month, day):
        try:
            if year is None:
                return None, None, None
            year = int(year)
            current_year = datetime.now().year
            if year < 2000 or year > current_year + 2:
                return None, None, None

            if month is None:
                return None, None, None
            if isinstance(month, str):
                normalized_month = month.strip().lower()
                if normalized_month.isdigit():
                    month_num = int(normalized_month)
                else:
                    month_num = None
                    for key, value in MONTH_NAMES.items():
                        if value.lower() == normalized_month:
                            month_num = int(key)
                            break
                if month_num is None or month_num < 1 or month_num > 12:
                    return None, None, None
                month = MONTH_NAMES.get(str(month_num), month)
            elif isinstance(month, int):
                if month < 1 or month > 12:
                    return None, None, None
                month = MONTH_NAMES.get(str(month), month)

            if day is None:
                return year, month, None
            day = int(day)
            if day < 1 or day > 31:
                return None, None, None
            return year, month, day
        except (TypeError, ValueError):
            return None, None, None

    for text in texts_to_check:
        if not text:
            continue

        # Skip text that looks like petition references: "123 of 2019"
        text = re.sub(r'\b\d{3,4}\s+of\s+20\d{2}\b', '', text, flags=re.IGNORECASE)

        m = re.search(DATE_PATTERNS[0], text)
        if m:
            day, month_num, year = m.group(1), m.group(2), m.group(3)
            month = MONTH_NAMES.get(month_num.zfill(2), month_num)
            validated = _validate_date(year, month, day)
            if validated != (None, None, None):
                return validated

        m = re.search(DATE_PATTERNS[1], text, re.IGNORECASE)
        if m:
            day, month_num, year_suffix = m.group(1), m.group(2), m.group(3)
            month = MONTH_NAMES.get(month_num.zfill(2), month_num)
            validated = _validate_date(f"20{year_suffix}", month, day)
            if validated != (None, None, None):
                return validated

        m = re.search(DATE_PATTERNS[2], text, re.IGNORECASE)
        if m:
            validated = _validate_date(m.group(3), m.group(2).capitalize(), m.group(1))
            if validated != (None, None, None):
                return validated

        m = re.search(DATE_PATTERNS[3], text, re.IGNORECASE)
        if m:
            validated = _validate_date(m.group(3), m.group(1).capitalize(), m.group(2))
            if validated != (None, None, None):
                return validated

        m = re.search(DATE_PATTERNS[4], text)
        if m:
            year, month_num = int(m.group(1)), m.group(2)
            month = MONTH_NAMES.get(month_num, month_num)
            validated = _validate_date(year, month, None)
            if validated != (None, None, None):
                return validated

    return None, None, None


def _is_recently_published(html_year, html_month, html_day,
                            year_filter, month_filter, day_filter,
                            today: datetime) -> tuple:
    """
    Decide from HTML-context date whether this PDF is worth downloading.
    Returns (should_download: bool, reason: str).

    Logic:
    - If user gave explicit filters, apply them strictly.
    - If no filters given (default "show today's docs"):
        * If we found a date in HTML context: accept if it is
          within the last 30 days.
        * If no HTML date found: download anyway and let AI decide.
    """
    if year_filter or month_filter or day_filter:
        # Reject only when HTML context contains a date that contradicts the filter.
        # Missing HTML dates are common on MEDA/Mahadiscom pages — let AI verify from PDF.
        if year_filter and html_year:
            try:
                if int(html_year) != int(year_filter):
                    return False, f"year {html_year} != wanted {year_filter}"
            except (TypeError, ValueError):
                return False, f"invalid html year {html_year}"
        if month_filter and html_month:
            if not _date_matches_explicit_filters(None, html_month, None, None, month_filter, None):
                return False, f"month {html_month} != wanted {month_filter}"
        if day_filter and html_day:
            try:
                if int(html_day) != int(day_filter):
                    return False, f"day {html_day} != wanted {day_filter}"
            except (TypeError, ValueError):
                return False, f"invalid html day {html_day}"
        return True, "passes explicit filter (or pending AI verification)"

    if html_year is None:
        return True, "no html date, will check after AI"

    if not html_month or not html_day:
        return True, "partial html date, will check after AI"

    try:
        MONTH_MAP = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
        }
        month_num = MONTH_MAP.get(str(html_month).lower(), None) if html_month else today.month
        day_num = int(html_day) if html_day else today.day
        doc_date = datetime(int(html_year), month_num, day_num)
        oldest_allowed = (today - timedelta(days=30)).date()
        if oldest_allowed <= doc_date.date() <= today.date():
            return True, f"recent html date {doc_date.date()}"
        return False, f"html date {doc_date.date()} too old (want >= {oldest_allowed})"
    except (ValueError, TypeError):
        # Date parsing failed — let it through, AI will check
        return True, "html date parse failed, will check after AI"


def _ai_date_gate(ai_meta: dict, year_filter, month_filter, day_filter,
                  today: datetime, trust_official_site: bool = False) -> tuple:
    """
    After AI extraction, decide if this doc passes the date gate.
    Returns (passes: bool, reason: str).
    """
    title_lower = (ai_meta.get("title") or "").lower()
    ALWAYS_RELEVANT_TITLE_KEYWORDS = [
        "solar", "wind", "renewable", "energy policy", "power policy",
        "tariff order", "bess", "hydrogen", "integrated renewable",
        "electricity", "open access", "rooftop", "net metering",
    ]
    title_is_energy = any(kw in title_lower for kw in ALWAYS_RELEVANT_TITLE_KEYWORDS)

    # Only reject permanent docs when no explicit year filter given
    if not year_filter and not month_filter and not day_filter:
        if not ai_meta.get("is_new_publication", True):
            return False, "AI: not a new publication (permanent/standing document)"

    # Never reject clearly energy-titled documents on relevance grounds.
    if not trust_official_site and not title_is_energy and not ai_meta.get("is_energy_relevant", True):
        return False, "AI: not energy relevant"

    pub_year = ai_meta.get("year")
    pub_month = ai_meta.get("month")
    pub_day = ai_meta.get("day")

    try:
        pub_year = int(pub_year) if pub_year else None
    except (TypeError, ValueError):
        pub_year = None

    if pub_year is None:
        pub_year = _extract_year_from_text(
            ai_meta.get("title"),
            ai_meta.get("description"),
        )

    # Explicit user filters: require AI-detected fields to exist and match
    if year_filter or month_filter or day_filter:
        if year_filter:
            if pub_year is None:
                return False, "AI: no year for explicit filter"
            try:
                if int(pub_year) != int(year_filter):
                    return False, f"AI year {pub_year} != filter {year_filter}"
            except (TypeError, ValueError):
                return False, f"AI: invalid year {pub_year}"
        if month_filter:
            if not pub_month:
                return False, "AI: no month for explicit filter"
            if not _date_matches_explicit_filters(None, pub_month, None, None, month_filter, None):
                return False, f"AI month {pub_month} != filter {month_filter}"
        if day_filter:
            if pub_day is None:
                return False, "AI: no day for explicit filter"
            try:
                if int(pub_day) != int(day_filter):
                    return False, f"AI day {pub_day} != filter {day_filter}"
            except (TypeError, ValueError):
                return False, f"AI: invalid day {pub_day}"
        return True, "passes explicit filter"

    if pub_year is None:
        return False, "AI: could not determine publication year"

    MONTH_MAP = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12,
    }
    if pub_year == today.year:
        return True, f"AI: current year publication pub_year={pub_year}"

    pub_month_num = MONTH_MAP.get(str(pub_month).strip().lower()) if pub_month else None
    if pub_year == today.year - 1 and pub_month_num in (10, 11, 12):
        return True, f"AI: late last-year publication {pub_month} {pub_year}"

    return False, f"AI: old document, pub_year={pub_year}, pub_month={pub_month}"


def scrape_site(
    site: dict,
    seen_urls: set,
    year_filter: Optional[int] = None,
    month_filter: Optional[str] = None,
    day_filter: Optional[int] = None,
    fast_mode: bool = True,
) -> list:
    results = []
    site_id = site.get("id")
    base_url = _site_base_url(site)
    max_new = int(site.get("max_new_per_run", 25))
    max_pages = int(site.get("max_pages_per_run", 50))
    if fast_mode:
        max_new = min(max_new, SCRAPER_FAST_MAX_NEW)
        max_pages = min(max_pages, SCRAPER_FAST_MAX_PAGES)
    deep_crawl = bool(site.get("deep_crawl", False))
    today = datetime.now()
    site_stats = _new_site_filter_stats()

    _safe_print(f"\n{'='*60}")
    _safe_print(f"Scraping site {site_id}: {site.get('name')} ...")
    _safe_print(f"Limits: max_pages={max_pages}, max_new={max_new}, fast={fast_mode}")
    _safe_print(f"{'='*60}")

    seed_urls = list(site.get("scrape_urls") or [])
    pages_to_scrape = list(dict.fromkeys(seed_urls))
    queued_pages = {_normalize_url(url) for url in pages_to_scrape}

    session_pdf_urls = set()
    standing_policy_seen_this_run: set = set()
    MONTH_MAP = {
        "january":"01","february":"02","march":"03","april":"04",
        "may":"05","june":"06","july":"07","august":"08",
        "september":"09","october":"10","november":"11","december":"12",
    }

    playwright_runner = None
    browser = None
    browser_page = None
    http_session = requests.Session()
    http_session.headers.update(BROWSER_HEADERS)
    async_client = None
    use_playwright = bool(site.get("needs_js", False)) and PLAYWRIGHT_AVAILABLE

    if use_playwright:
        try:
            playwright_runner = sync_playwright().start()
            browser = playwright_runner.chromium.launch(headless=True)
            browser_page = browser.new_page()
            browser_page.set_extra_http_headers(BROWSER_HEADERS)
            _safe_print("  Using persistent Playwright browser for this site")
        except Exception as e:
            _safe_print(f"  Playwright startup failed, falling back to async httpx: {e}")
            browser_page = None
            use_playwright = False

    if not use_playwright:
        async_client = httpx.AsyncClient(
            headers=BROWSER_HEADERS,
            verify=False,
            http2=True,
            timeout=SCRAPER_PAGE_TIMEOUT,
        )
        _safe_print("  Using async httpx fetch for this site")

    try:
        for page_url in pages_to_scrape:
            if len(results) >= max_new:
                break

            _safe_print(f"  Fetching: {page_url} (playwright={use_playwright})")
            html, final_page_url = fetch_page_html(
                page_url,
                browser_page=browser_page if use_playwright else None,
                session=http_session,
                use_playwright=use_playwright,
                async_client=async_client,
            )
            _polite_sleep(SCRAPER_PAGE_DELAY_MIN, SCRAPER_PAGE_DELAY_MAX)
            if not html:
                _safe_print(f"  ✗ Failed to fetch {page_url}")
                continue

            soup = BeautifulSoup(html, "lxml")
            found_count = 0

            if deep_crawl and len(pages_to_scrape) < max_pages:
                discovered_pages = _discover_pages_from_html(
                    soup, final_page_url, base_url, queued_pages, max_pages
                )
                if discovered_pages:
                    pages_to_scrape.extend(discovered_pages)
                    _safe_print(f"  → Queued {len(discovered_pages)} linked document pages")

            pdf_tasks = []
            for anchor in soup.find_all("a", href=True):
                if len(results) >= max_new:
                    break

                href = anchor["href"].strip()
                if not href:
                    continue
                anchor_text = anchor.get_text(" ", strip=True)
                if not _is_likely_pdf_link(href, anchor_text):
                    continue

                absolute_pdf_url = _resolve_document_url(href, final_page_url, base_url)
                if "about-logo" in absolute_pdf_url.lower():
                    continue

                url_key = _normalize_url(absolute_pdf_url)
                if absolute_pdf_url in seen_urls or url_key in seen_urls:
                    continue
                if url_key in session_pdf_urls:
                    continue
                session_pdf_urls.add(url_key)

                title = _extract_title_from_link(anchor, absolute_pdf_url)
                title = re.sub(r"\s+", " ", title).strip()

                # ── PRE-FILTER 1: Known static/permanent docs ──────────
                if is_static_permanent_doc(title):
                    _safe_print(f"  ✗ Static doc, skip: {title[:60]}")
                    continue

                # ── PRE-FILTER 2: HTML context date check ──────────────
                html_year, html_month, html_day = _extract_date_from_context(anchor, final_page_url)

                should_dl, reason = _is_recently_published(
                    html_year, html_month, html_day,
                    year_filter, month_filter, day_filter, today
                )
                if not should_dl:
                    _safe_print(f"  ✗ HTML date gate ({reason}): {title[:50]}")
                    continue

                # ── PRE-FILTER 3: likely official energy document ──────
                # Some Maharashtra/Central pages use generic anchor text.
                # Let AI inspect official documents before deciding.
                if not _should_inspect_pdf_with_ai(title, absolute_pdf_url, site):
                    _safe_print(f"  ✗ Not a likely energy document: {title[:60]}")
                    continue

                _safe_print(f"  ↓ Downloading: {title[:60]}")
                file_id = str(uuid.uuid4())
                filename = f"{file_id}.pdf"
                staging_path = STAGING_DIR / filename

                try:
                    try:
                        pdf_resp = http_session.get(
                            absolute_pdf_url, timeout=SCRAPER_PDF_TIMEOUT,
                            stream=True
                        )
                    except SSLError as e:
                        _safe_print(
                            f"  ! SSL verification failed for PDF, retrying without verification: {e}"
                        )
                        pdf_resp = http_session.get(
                            absolute_pdf_url, timeout=SCRAPER_PDF_TIMEOUT,
                            stream=True, verify=False
                        )

                    with pdf_resp:
                        pdf_resp.raise_for_status()
                        with open(staging_path, "wb") as out_file:
                            for chunk in pdf_resp.iter_content(chunk_size=8192):
                                if chunk:
                                    out_file.write(chunk)
                except Exception as e:
                    _safe_print(f"  ✗ Download failed {absolute_pdf_url}: {e}")
                    continue
                _polite_sleep(SCRAPER_PDF_DELAY_MIN, SCRAPER_PDF_DELAY_MAX)

                site_stats["downloaded"] += 1
                pdf_tasks.append({
                    "staging_path": staging_path,
                    "title": title,
                    "site_state": site.get("state", "Central"),
                    "site_category": site.get("default_category", "General"),
                    "html_year": html_year,
                    "html_month": html_month,
                    "html_day": html_day,
                    "source_url": absolute_pdf_url,
                    "url_key": url_key,
                    "file_id": file_id,
                    "filename": filename,
                })

            if pdf_tasks:
                processed = _process_pdf_tasks(
                    pdf_tasks,
                    site,
                    results,
                    seen_urls,
                    session_pdf_urls,
                    today,
                    year_filter=year_filter,
                    month_filter=month_filter,
                    day_filter=day_filter,
                    site_stats=site_stats,
                    standing_policy_seen_this_run=standing_policy_seen_this_run,
                )
                if processed:
                    _safe_print(f"  → Processed {processed} downloaded PDFs on {page_url}")
                if len(results) >= max_new:
                    break
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if playwright_runner is not None:
            try:
                playwright_runner.stop()
            except Exception:
                pass
        http_session.close()

    _safe_print(
        f"Site {site_id}: {site_stats['downloaded']} downloaded, "
        f"{site_stats['passed_year']} passed year gate, "
        f"{site_stats['bypassed_standing']} bypassed (standing), "
        f"{site_stats['rejected_year']} rejected (year), "
        f"{site_stats['rejected_type_topic']} rejected (type/topic), "
        f"{site_stats['rejected_denylist']} rejected (denylist), "
        f"{site_stats['added_to_queue']} added to queue"
    )

    return results


def run_scraper(
    state_filter: Optional[str] = None,
    year_filter: Optional[int] = None,
    month_filter: Optional[str] = None,
    day_filter: Optional[int] = None,
    fast_mode: bool = True,
) -> dict:
    sites = load_sites()
    queue = load_queue()
    seen_urls = _build_seen_urls_for_run(load_seen_urls(), queue)

    normalized_state = state_filter.strip().lower() if state_filter else None
    if normalized_state in ("", "all", "all states"):
        normalized_state = None

    total_new = 0
    sites_checked = 0
    error_count = 0
    sites_with_results = []
    current_session = datetime.now().strftime("%Y-%m-%d")

    _safe_print(f"\n{'#'*60}")
    _safe_print(f"SCRAPER RUN: {current_session}")
    _safe_print(
        f"Filters: state={state_filter or 'ALL'}, year={year_filter if year_filter is not None else 'ANY'}, "
        f"month={month_filter if month_filter else 'ANY'}, day={day_filter if day_filter is not None else 'ANY'}, "
        f"fast={fast_mode}"
    )
    _safe_print(f"{'#'*60}\n")

    if not sites:
        return {"scraped": 0, "sites_checked": 0, "errors": 1, "session": current_session}

    for site in sites:
        if not site.get("enabled", False):
            continue
        if normalized_state and site.get("state", "").strip().lower() != normalized_state:
            continue
        try:
            site_results = scrape_site(
                site, seen_urls,
                year_filter=year_filter,
                month_filter=month_filter,
                day_filter=day_filter,
                fast_mode=fast_mode,
            )
            if site.get("allow_standing_policies") and not site.get(
                "standing_policies_already_seeded", False
            ):
                _mark_standing_policies_seeded(site.get("id"))
                site["standing_policies_already_seeded"] = True
            if site_results:
                queue.extend(site_results)
                total_new += len(site_results)
                sites_with_results.append(site.get("name") or site.get("id"))
                save_queue(queue)
                _safe_print(f"Saved {len(site_results)} new docs from {site.get('id')} to queue")
            sites_checked += 1
        except Exception as e:
            error_count += 1
            _safe_print(f"Error scraping {site.get('id')}: {e}")

    save_queue(queue)

    _safe_print(f"\n{'#'*60}")
    _safe_print(f"DONE: {total_new} new docs found across {sites_checked} sites, {error_count} errors")
    _safe_print(f"{'#'*60}\n")

    result = {
        "message": (
            f"Found {total_new} new documents"
            if total_new > 0
            else "No new documents found for today. Try scraping with a wider date range."
        ),
        "scraped": total_new,
        "sites_checked": sites_checked,
        "sites_with_results": sites_with_results,
        "errors": error_count,
        "session": current_session,
        "fast_mode": fast_mode,
        "filters": {
            "year": year_filter,
            "month": month_filter,
            "day": day_filter,
        },
    }
    if total_new == 0:
        today_for_message = datetime.now()
        result["nothing_found_message"] = (
            f"No new documents published today "
            f"({today_for_message.strftime('%B')} {today_for_message.day}, {today_for_message.year})"
        )
    return result
