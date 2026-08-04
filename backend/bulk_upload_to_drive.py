"""
Run once to upload all existing PDFs to the new Shared Drive.
Usage:
    cd backend
    python bulk_upload_to_drive.py
"""
import json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from google_drive_service import upload_pdf_to_drive_details, is_drive_configured

RAW_PDFS = Path("data/raw_pdfs")
POLICIES = Path("data/policies.json")


def main():
    if not is_drive_configured():
        print("❌ Drive not configured. Check .env file.")
        return

    policies = json.loads(POLICIES.read_text(encoding="utf-8"))
    uploaded = skipped = failed = 0

    for policy in policies:
        fname = policy.get("file", "")
        path = RAW_PDFS / fname

        if not path.exists():
            print(f"  ⚠️  Not found locally, skipping: {fname}")
            skipped += 1
            continue

        if policy.get("drive_file_id"):
            print(f"  ✓  Already on Drive, skipping: {fname}")
            skipped += 1
            continue

        try:
            print(f"  ↑  Uploading: {fname} ...", end=" ", flush=True)
            result = upload_pdf_to_drive_details(str(path), fname)
            policy["drive_file_id"] = result["id"]
            policy["drive_url"] = result["webViewLink"]
            print(f"✅ {result['webViewLink']}")
            uploaded += 1
        except Exception as e:
            print(f"❌ Failed: {e}")
            failed += 1

    POLICIES.write_text(json.dumps(policies, indent=2), encoding="utf-8")

    print(f"\n{'='*50}")
    print(f"✅ Uploaded: {uploaded} | ⚠️  Skipped: {skipped} | ❌ Failed: {failed}")
    print("policies.json updated with drive_file_id and drive_url")


if __name__ == "__main__":
    main()