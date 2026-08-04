from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import json
import os
import re
from datetime import datetime
from google_drive_service import list_pdfs_from_drive, is_drive_configured
from pathlib import Path
from google_drive_service import list_pdfs_from_drive, is_drive_configured, SERVICE_ACCOUNT_FILE

router = APIRouter()
import time

_drive_policies_cache = None
_drive_policies_cache_ts = 0.0
_DRIVE_CACHE_TTL = 0

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
POLICY_FILE = os.path.join(DATA_DIR, "policies.json")
UPLOAD_DIR = os.path.join(DATA_DIR, "raw_pdfs")

KNOWN_CATEGORY_SLUGS = frozenset({
    "Regulation", "Order", "Policy", "Road_Map", "Notification", "Circular", "General",
    "Government_Resolution", "Guideline", "Act", "Gazette", "Electricity_Plan",
})

# 📄 CATEGORY KEYWORDS for document type detection
CATEGORY_KEYWORDS = {
    "Regulation": ["regulation", "regulatory", "rpo"],
    "Order": ["order", "tariff order", "suo motu"],
    "Policy": ["policy", "programme", "program", "plan"],
    "Road Map": ["road map", "roadmap", "trajectory", "target"],
    "Notification": ["notification", "notice", "public notice"],
    "Government Resolution": ["government resolution", "शासन निर्णय", "शासन निर्णय :-"],
    "Circular": ["circular", "sop", "procedure"],
    "Guideline": ["guideline", "guidelines"],
    "Act": ["act", "amendment act", "bill"],
    "Gazette": ["gazette", "official gazette"],
    "Electricity Plan": ["electricity plan", "power plan", "energy plan"],
}

# Energy type naming convention (legacy stored values → canonical filter names)
POWER_TYPE_ALIASES = {
    "ESS": "BESS",
    "BESS": "BESS",
    "Battery Energy Storage System": "BESS",
    "Battery Energy Storage Systems": "BESS",
    "Energy Storage System": "BESS",
    "Energy Storage Systems": "BESS",
    "Hydro": "Green Hydrogen",
    "Hydrogen": "Green Hydrogen",
    "Integrated Clean Energy": "Integrated Renewable",
    "Integreated Clean Energy": "Integrated Renewable",
    "Integreated Renewable": "Integrated Renewable",
    "Integrated Renewable Energy": "Integrated Renewable",
    "Integreated Renewable Energy": "Integrated Renewable",
    "Renewable": "Integrated Renewable",
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
    (
        "Integrated Renewable",
        (
            "integrated renewable",
            "integreated renewable",
            "integrated renewable energy",
            "integreated renewable energy",
            "integrated clean energy",
            "integreated clean energy",
        ),
    ),
)

# Display labels for energy type filter dropdown (value → label)
POWER_TYPE_DISPLAY_LABELS = {
    "Solar": "Solar",
    "Wind": "Wind",
    "BESS": "ESS/BESS/Battery Energy Storage System",
    "Green Hydrogen": "Green Hydrogen",
    "Integrated Renewable": "Integrated Renewable",
    "Biomass": "Biomass",
    "Transmission": "Transmission",
    "Distribution": "Distribution",
    "Grid": "Grid",
    "Hybrid": "Hybrid",
    "Clean Energy": "Clean Energy",
    "General": "General",
    "Renewable Energy": "Renewable Energy",
}

ENERGY_TYPE_FILTER_OPTIONS = [
    {"value": "All", "label": "All"},
    {"value": "BESS", "label": POWER_TYPE_DISPLAY_LABELS["BESS"]},
    {"value": "Biomass", "label": POWER_TYPE_DISPLAY_LABELS["Biomass"]},
    {"value": "Clean Energy", "label": POWER_TYPE_DISPLAY_LABELS["Clean Energy"]},
    {"value": "General", "label": POWER_TYPE_DISPLAY_LABELS["General"]},
    {"value": "Green Hydrogen", "label": POWER_TYPE_DISPLAY_LABELS["Green Hydrogen"]},
    {"value": "Grid", "label": POWER_TYPE_DISPLAY_LABELS["Grid"]},
    {"value": "Hybrid", "label": POWER_TYPE_DISPLAY_LABELS["Hybrid"]},
    {"value": "Integrated Renewable", "label": POWER_TYPE_DISPLAY_LABELS["Integrated Renewable"]},
    {"value": "Renewable Energy", "label": POWER_TYPE_DISPLAY_LABELS["Renewable Energy"]},
    {"value": "Solar", "label": POWER_TYPE_DISPLAY_LABELS["Solar"]},
    {"value": "Transmission", "label": POWER_TYPE_DISPLAY_LABELS["Transmission"]},
    {"value": "Distribution", "label": POWER_TYPE_DISPLAY_LABELS["Distribution"]},
    {"value": "Wind", "label": POWER_TYPE_DISPLAY_LABELS["Wind"]},
]


def normalize_power_type(power_type: str) -> str:
    """Map legacy power_type values to the current naming convention."""
    if not power_type:
        return "General"
    pt = str(power_type).strip()
    alias = POWER_TYPE_ALIASES.get(pt)
    if alias:
        return alias

    normalized = re.sub(r"[_-]+", " ", pt).lower().strip()
    for canonical, keywords in POWER_TYPE_KEYWORD_ALIASES:
        if any(
            re.search(rf"\b{re.escape(keyword)}\b", normalized)
            for keyword in keywords
        ):
            return canonical

    return pt


def detect_category(text: str, default: str = "General") -> str:
    """Detect document category from text using keyword matching."""
    lowered = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in lowered:
                return category
    return default


def _slug_to_category_label(slug: str) -> str:
    if slug == "Road_Map":
        return "Road Map"
    if slug == "Government_Resolution":
        return "Government Resolution"
    return slug if slug else "General"


def _parse_policy_from_filename(filename: str):
    """
    Parses raw_pdfs filenames.
    - 3-part old format: State_PowerType_Year.pdf
    - 4-part new format: State_PowerType_Category_Year.pdf
    - 5-part collision: State_PowerType_Category_Year_shortid.pdf
    """
    if not filename.lower().endswith(".pdf"):
        return None

    filename_without_ext = filename[:-4]
    parts = [p.strip() for p in filename_without_ext.split("_") if p.strip()]
    if len(parts) < 3:
        state = parts[0] if parts else "Unknown"
        power_type = parts[1] if len(parts) > 1 else "Unknown"
        year = datetime.now().year
        year_match = re.search(r"(19|20)\d{2}", filename_without_ext)
        if year_match:
            year = int(year_match.group(0))
        cat = detect_category(filename_without_ext.replace("_", " "), "General")
        return {
            "file": filename,
            "state": state,
            "year": year,
            "month": "January",
            "power_type": power_type,
            "category": cat,
        }

    # Find the rightmost part that is a 4-digit year (1900-2100)
    year_idx = -1
    for i in range(len(parts) - 1, -1, -1):
        try:
            year_val = int(parts[i])
            if 1900 <= year_val <= 2100:
                year_idx = i
                break
        except ValueError:
            continue

    if year_idx == -1:
        parsed = _parse_policy_from_filename_legacy(filename_without_ext, filename)
        return parsed

    year = int(parts[year_idx])
    state = parts[0] if parts else "Unknown"

    if year_idx > 0 and parts[year_idx - 1] in KNOWN_CATEGORY_SLUGS:
        category = _slug_to_category_label(parts[year_idx - 1])
        power_type = "_".join(parts[1:year_idx - 1]) if year_idx > 1 else "Unknown"
    else:
        category = "General"
        power_type = "_".join(parts[1:year_idx]) if year_idx > 1 else "Unknown"

    if category == "General":
        filename_text = filename_without_ext.replace("_", " ")
        category = detect_category(filename_text, "General")

    return {
        "file": filename,
        "state": state,
        "year": year,
        "month": "January",
        "power_type": power_type,
        "category": category,
    }


def _parse_policy_from_filename_legacy(filename_without_ext, filename):
    """Fallback when last segment is not a 4-digit year."""
    parts = [part.strip() for part in filename_without_ext.split("_")]
    state = "Unknown"
    power_type = "Unknown"
    year = datetime.now().year

    if len(parts) >= 3:
        state = parts[0] or "Unknown"
        power_type = "_".join(parts[1:-1]) or "Unknown"
        try:
            year = int(parts[-1])
        except ValueError:
            year_match = re.search(r"(19|20)\d{2}", filename_without_ext)
            if year_match:
                year = int(year_match.group(0))
    elif parts and parts[0]:
        state = parts[0]
        if len(parts) > 1 and parts[1]:
            power_type = parts[1]
        year_match = re.search(r"(19|20)\d{2}", filename_without_ext)
        if year_match:
            year = int(year_match.group(0))

    cat = detect_category(filename_without_ext.replace("_", " "), "General")
    return {
        "file": filename,
        "state": state,
        "year": year,
        "month": "January",
        "power_type": power_type,
        "category": cat,
    }

def _load_and_sync_policies():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    metadata_by_file = {}

    if os.path.exists(POLICY_FILE):
        with open(POLICY_FILE, "r", encoding="utf-8") as f:
            try:
                metadata = json.load(f)
            except json.JSONDecodeError:
                metadata = []

        if isinstance(metadata, list):
            for policy in metadata:
                file_name = policy.get("file")
                if file_name:
                    metadata_by_file[file_name] = policy

    discovered_by_file = {}

    # ==========================
    # LOCAL FILES
    # ==========================
    for file_name in os.listdir(UPLOAD_DIR):
        parsed = _parse_policy_from_filename(file_name)

        if parsed:
            discovered_by_file[file_name] = parsed

    # ==========================
    # GOOGLE DRIVE FILES
    # ==========================
    if is_drive_configured():
        try:
            drive_files = list_pdfs_from_drive()

            print(f"[POLICIES] Found {len(drive_files)} PDFs in Google Drive")

            for file in drive_files:
                file_name = file["name"]

                parsed = _parse_policy_from_filename(file_name)

                if parsed:
                    parsed["drive_id"] = file.get("id")
                    parsed["drive_link"] = file.get("webViewLink")

                    discovered_by_file[file_name] = parsed

        except Exception as e:
            print(f"[POLICIES] Drive sync failed: {e}")

    synced = []

    for file_name, discovered in discovered_by_file.items():

        existing = metadata_by_file.get(file_name, {})

        entry = {
            "file": file_name,
            "state": existing.get("state") or discovered["state"],
            "year": int(existing.get("year", discovered["year"])),
            "month": existing.get("month") or discovered["month"],
            "power_type": normalize_power_type(
                existing.get("power_type") or discovered["power_type"]
            ),
            "category": existing.get("category")
            or discovered.get("category")
            or "General",
        }

        if discovered.get("drive_id"):
            entry["drive_id"] = discovered["drive_id"]

        if discovered.get("drive_link"):
            entry["drive_link"] = discovered["drive_link"]

        synced.append(entry)

    synced.sort(key=lambda item: item["file"].lower())

    with open(POLICY_FILE, "w", encoding="utf-8") as f:
        json.dump(synced, f, indent=2)

    print(f"[POLICIES] Returning {len(synced)} policies")

    return synced


@router.get("/policies")
def get_policies(state: str = None, year: int = None, power_type: str = None, category: str = None):
    data = _load_and_sync_policies()

    filtered = []

    for policy in data:
        if state and state != "All":
            policy_state = policy.get("state", "")
            if state == "Central":
                if not policy_state.startswith("Central"):
                    continue
            elif policy_state != state:
                continue
        if year and policy["year"] != year:
            continue
        if power_type and power_type != "All":
            filter_pt = normalize_power_type(power_type).lower()
            policy_pt = normalize_power_type(policy.get("power_type", "")).lower()
            if not (
                policy_pt == filter_pt or
                filter_pt in policy_pt or
                policy_pt in filter_pt
            ):
                continue
        if category and category != "All" and policy.get("category") != category:
            continue

        filtered.append(policy)

    return filtered


@router.get("/raw-policies")
def get_raw_policies():
    """Get all PDF files from raw_pdfs directory with metadata extracted from filenames"""
    policies = []
    for policy in _load_and_sync_policies():
        policy_with_path = dict(policy)
        policy_with_path["file_path"] = os.path.join(UPLOAD_DIR, policy["file"])
        policies.append(policy_with_path)
    return policies


@router.get("/drive-policies")
def get_drive_policies():
    """Get all PDF files from Google Drive folder (cached for 5 min)."""
    global _drive_policies_cache, _drive_policies_cache_ts

    if not is_drive_configured():
        return []

    now = time.time()
    if _drive_policies_cache is not None and (now - _drive_policies_cache_ts) < _DRIVE_CACHE_TTL:
        return _drive_policies_cache

    try:
        files = list_pdfs_from_drive()
        policies = []
        for f in files:
            parsed = _parse_policy_from_filename(f["name"])
            if parsed:
                parsed["drive_id"] = f["id"]
                parsed["webViewLink"] = f.get("webViewLink", "")
                policies.append(parsed)
        _drive_policies_cache = policies
        _drive_policies_cache_ts = now
        return policies
    except Exception as e:
        print(f"[drive-policies] Error: {e}")
        if _drive_policies_cache is not None:
            return _drive_policies_cache  # return stale cache rather than empty list
        return []

@router.get("/download/{filename}")
def download_policy(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/pdf'
    )

@router.get("/debug-drive")
def debug_drive():
    import os
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    sa_file_env = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    
    # Check secret file paths
    secret_paths = [
        "/etc/secrets/service-account.json",
        "/etc/secrets/credentials/service-account.json", 
    ]
    secret_files_found = {p: os.path.exists(p) for p in secret_paths}
    
    return {
        "is_configured": is_drive_configured(),
        "folder_id_set": bool(folder_id),
        "folder_id_preview": folder_id[:10] if folder_id else "NOT SET",
        "json_env_set": bool(sa_json),
        "json_preview": sa_json[:50] if sa_json else "NOT SET",
        "service_account_file_env": sa_file_env,
        "service_account_file_exists": os.path.exists(sa_file_env) if sa_file_env else False,
        "secret_files": secret_files_found,
        "all_google_keys": [k for k in os.environ.keys() if "GOOGLE" in k.upper()],
    }

@router.get("/debug-env")
def debug_env():
    import os
    keys = list(os.environ.keys())
    google_keys = [k for k in keys if "GOOGLE" in k.upper()]
    return {
        "google_related_keys": google_keys,
        "total_env_vars": len(keys)
    }

@router.get("/debug-file")
def debug_file():
    import os
    paths_to_check = [
        "/etc/secrets/service-account.json",
        "credentials/service-account.json",
        "/app/credentials/service-account.json",
        os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "NOT SET"),
    ]
    return {
        "env_value": os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "NOT SET"),
        "paths_checked": {p: os.path.exists(p) for p in paths_to_check}
    }

@router.get("/debug-drive-files")
def debug_drive_files():
    try:
        files = list_pdfs_from_drive()

        return {
            "count": len(files),
            "files": files[:20]
        }

    except Exception as e:
        return {
            "error": str(e)
        }
