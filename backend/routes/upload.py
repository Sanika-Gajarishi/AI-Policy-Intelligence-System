import os
import json
from jose import jwt
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from google_drive_service import (
    is_drive_configured,
    upload_pdf_to_drive_details,
    file_exists_in_drive,
    download_pdf_from_drive
)

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "raw_pdfs")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 📄 Metadata file
POLICY_FILE = os.path.join(DATA_DIR, "policies.json")

# Slug must match build_policy_filename() / policies._parse_policy_from_filename
KNOWN_CATEGORY_SLUGS = frozenset({
    "Regulation", "Order", "Policy", "Road_Map", "Notification", "Circular", "General",
    "Act", "Gazette", "Electricity_Plan",
})

# 🔐 SECRET KEY (same as auth.py)
SECRET_KEY = "secret123"

# 📄 CATEGORY KEYWORDS for document type detection
CATEGORY_KEYWORDS = {
    "Regulation": ["regulation", "regulatory", "rpo"],
    "Order": ["order", "tariff order", "suo motu"],
    "Policy": ["policy", "scheme", "programme", "program", "plan"],
    "Road Map": ["road map", "roadmap", "trajectory", "target"],
    "Notification": ["notification", "notice", "public notice"],
    "Circular": ["circular", "guideline", "sop", "procedure"],
    "Act": ["act", "amendment act", "bill"],
    "Gazette": ["gazette", "official gazette"],
    "Electricity Plan": ["electricity plan", "power plan", "energy plan"],
}


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
    return slug if slug else "General"


def _parse_upload_filename(filename: str):
    """Returns (state, year_str, power_type, category_or_none). category set if 4+ part name."""
    base = filename.rsplit(".", 1)[0] if filename.lower().endswith(".pdf") else filename
    parts = [p.strip() for p in base.split("_") if p.strip()]
    if len(parts) < 3:
        return None

    try:
        int(parts[-1])
    except ValueError:
        return None

    if len(parts) >= 4 and parts[-2] in KNOWN_CATEGORY_SLUGS:
        state = parts[0]
        power_type = "_".join(parts[1:-2]) or "Unknown"
        cat = _slug_to_category_label(parts[-2])
        year_str = parts[-1]
        return state, year_str, power_type, cat

    state = parts[0]
    year_str = parts[-1]
    power_type = "_".join(parts[1:-1]) or "Unknown"
    return state, year_str, power_type, None


# 🔐 VERIFY TOKEN FUNCTION
def verify_token(token: str):
    try:
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return True
    except Exception:
        return False


# 💾 SAVE POLICY METADATA
def save_policy_metadata(file_name, state, year, month, power_type, category="General", drive_id=None, drive_link=None):
    if not os.path.exists(POLICY_FILE):
        with open(POLICY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)

    try:
        with open(POLICY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        data = []

    if not isinstance(data, list):
        data = []

    data = [policy for policy in data if policy.get("file") != file_name]

    entry = {
        "file": file_name,
        "state": state,
        "year": int(year),
        "month": month,
        "power_type": power_type,
        "category": category
    }
    if drive_id:
        entry["drive_id"] = drive_id
    if drive_link:
        entry["drive_link"] = drive_link
    data.append(entry)

    with open(POLICY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


@router.post("/upload")
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    state: Optional[str] = Form(None),
    year: Optional[str] = Form(None),
    month: str = Form("January"),
    power_type: Optional[str] = Form(None),
    category: Optional[str] = Form("General"),
    token: Optional[str] = Form(None)
):
    try:
        print(f"Upload request received: {file.filename}")

        if not file.filename:
            return {"error": "No file provided"}

        if not file.filename.lower().endswith(".pdf"):
            return {"error": "Only PDF files allowed"}

        parsed = _parse_upload_filename(file.filename)
        if not parsed:
            return {"error": "Invalid filename format. Use: State_EnergyType_Year.pdf or State_EnergyType_Category_Year.pdf"}

        extracted_state, extracted_year, extracted_type, category_from_name = parsed

        if category_from_name is not None:
            final_category = category_from_name
        else:
            hint = (category or "General").strip()
            if hint and hint != "General":
                final_category = hint
            else:
                title_hint = file.filename.replace(".pdf", "").replace("_", " ")
                final_category = detect_category(title_hint, "General")

        print(
            f"Extracted details: state={extracted_state}, year={extracted_year}, "
            f"type={extracted_type}, category={final_category}"
        )

        file_path = os.path.join(UPLOAD_DIR, file.filename)

        # ── Duplicate check ──────────────────────────────────────────────────
        if is_drive_configured() and file_exists_in_drive(file.filename):
            raise HTTPException(status_code=409, detail="PDF already exists in the system")
        if os.path.exists(file_path):
            raise HTTPException(status_code=409, detail="PDF already exists in the system")

        print(f"Saving file to: {file_path}")

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded PDF is empty")

        with open(file_path, "wb") as f:
            f.write(content)
        print(f"Saved {len(content)} bytes")

        # ── Google Drive upload ───────────────────────────────────────────────
        drive_id = None
        drive_link = None
        # FIX #2 & #3: temp_pdf declared here so it's always in scope below.
        # Default to the local file; overwritten if Drive download succeeds.
        temp_pdf = file_path

        try:
            if is_drive_configured():
                print("Google Drive configured — uploading file to Drive...")

                info = upload_pdf_to_drive_details(file_path, file.filename)
                print(f"Drive response: {info}")

                drive_id = info.get("id")
                drive_link = info.get("webViewLink")

                print("Downloading PDF from Google Drive for indexing...")
                # FIX #2: corrected indentation (no extra indent)
                # FIX #3: temp_pdf is now actually used below in background_tasks
                temp_pdf = download_pdf_from_drive(drive_id)

                print(f"Drive upload succeeded: {drive_id} -> {drive_link}")

                # FIX #5: remove local copy now that Drive + temp download exist
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Removed local copy: {file_path}")

            else:
                print("Google Drive not configured; skipping Drive upload")

        except Exception as e:
            print(f"DRIVE ERROR: {e}")
            # Fall back to local file for indexing if Drive failed
            temp_pdf = file_path

        # ── Save metadata ─────────────────────────────────────────────────────
        try:
            save_policy_metadata(
                file.filename,
                extracted_state,
                extracted_year,
                month or "January",
                extracted_type,
                final_category,
                drive_id=drive_id,
                drive_link=drive_link,
            )
            print("Metadata saved successfully")
        except Exception as e:
            print(f"METADATA SAVE FAILED: {e}")
            raise

        # ── FIX #1 & #4: schedule background indexing INSIDE the function,
        #    AFTER metadata is saved, using the correct temp_pdf path ──────────
        from services.rag_pipeline import process_pdf

        
        process_pdf(
            temp_pdf,          # path to PDF (Drive download or local fallback)
            extracted_state,
            extracted_year,
            month or "January",
            extracted_type,
            file.filename      # source_file= so FAISS stores the real filename
        )
        print("Background indexing started")

        # ── Build response ────────────────────────────────────────────────────
        resp = {
            "message": "PDF uploaded successfully. Processing started in background.",
            "file": file.filename,
        }
        if drive_id:
            resp["drive_id"] = drive_id
        if drive_link:
            resp["drive_link"] = drive_link

        return resp

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Upload error: {e}")
        return {"error": f"Upload failed: {str(e)}"}