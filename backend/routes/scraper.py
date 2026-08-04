from typing import Optional
from fastapi import APIRouter, HTTPException, Body, Query, Header
from pydantic import BaseModel
import os
import shutil
from services.scraper import (
    run_scraper,
    load_queue,
    save_queue,
    save_policy_metadata,
    build_policy_filename,
    update_item_from_filename,
    clear_pending_scrape_artifacts,
    load_seen_urls,
    save_seen_urls,
    STAGING_DIR,
    RAW_PDFS_DIR,
    _unlink_pdf,
)
from services.rag_pipeline import process_pdf
from services.auth import verify_token
from google_drive_service import (
    find_duplicate_pdf_in_drive,
    is_drive_configured,
    upload_pdf_to_drive_details,
    download_pdf_from_drive,
)

router = APIRouter()


class ScrapeActionRequest(BaseModel):
    id: str
    token: Optional[str] = None
    force: Optional[bool] = False
    filename: Optional[str] = None


def resolve_token(token: Optional[str] = None, authorization: Optional[str] = None) -> str:
    if token:
        return token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    raise HTTPException(status_code=401, detail="Token is required")


def require_token(token: Optional[str] = None, authorization: Optional[str] = None):
    resolved = resolve_token(token, authorization)
    if not verify_token(resolved):
        raise HTTPException(status_code=401, detail="Invalid token")
    return resolved


@router.get("/scrape")
def scrape_endpoint(
    token: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    month: Optional[str] = Query(None),
    day: Optional[int] = Query(None),
    fast: bool = Query(True),
    authorization: Optional[str] = Header(None),
):
    require_token(token, authorization)
    try:
        result = run_scraper(
            state_filter=state,
            year_filter=year,
            month_filter=month,
            day_filter=day,
            fast_mode=fast,
        )
        new_documents = result.get("scraped", 0)
        message = result.get("message") or (
            "No new documents found for today" if new_documents == 0 else "Scrape complete"
        )
        return {
            "message": message,
            "new_documents": new_documents,
            "sites_checked": result.get("sites_checked", 0),
            "sites_with_results": result.get("sites_with_results", []),
            "errors": result.get("errors", 0),
            "fast_mode": result.get("fast_mode", fast),
            "nothing_found_message": result.get("nothing_found_message"),
            "session": result.get("session"),
            "filters": result.get("filters"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scrape failed: {e}")


@router.get("/scrape-queue")
def get_scrape_queue(
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    require_token(token, authorization)
    queue = load_queue()
    pending = [item for item in queue if item.get("status") == "pending"]
    pending.sort(key=lambda item: item.get("scraped_at", ""), reverse=True)
    return pending


@router.get("/scrape-queue/count")
def get_scrape_queue_count(
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    require_token(token, authorization)
    queue = load_queue()
    count = sum(1 for item in queue if item.get("status") == "pending")
    return {"count": count}


@router.post("/scrape-queue/clear")
def clear_scrape_queue(
    request: dict = Body(default={}),
    authorization: Optional[str] = Header(None),
):
    require_token(request.get("token"), authorization)
    result = clear_pending_scrape_artifacts()
    return {
        "message": "Pending scraped documents cleared",
        **result,
    }


@router.post("/accept-scraped")
def accept_scraped(
    request: ScrapeActionRequest = Body(...),
    authorization: Optional[str] = Header(None),
):
    require_token(request.token, authorization)
    queue = load_queue()
    item = next((it for it in queue if it.get("id") == request.id), None)

    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    if item.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Item is not pending")

    if request.filename:
        try:
            update_item_from_filename(item, request.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))



    

    # ── Duplicate check (queue-level) ────────────────────────────────────────
    duplicate_info = item.get("duplicate_of") if isinstance(item.get("duplicate_of"), dict) else None
    if duplicate_info and not request.force:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This document is already present in the system",
                "matched_by": duplicate_info.get("matched_by"),
                "existing_filename": duplicate_info.get("existing_filename"),
                "existing_status": duplicate_info.get("status"),
                "source_url": duplicate_info.get("source_url"),
                "title": duplicate_info.get("title"),
            },
        )

    # ── Fuzzy title duplicate check (local raw_pdfs) ─────────────────────────
    if not request.force:
        raw_pdfs_dir = RAW_PDFS_DIR
        existing_files = list(raw_pdfs_dir.glob("*.pdf")) if raw_pdfs_dir.exists() else []
        item_title = item.get("title", "").lower().replace(" ", "")
        for existing in existing_files:
            existing_clean = existing.stem.lower().replace("_", "")
            if len(item_title) > 15 and (
                item_title[:15] in existing_clean or existing_clean[:15] in item_title
            ):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "A very similar document already exists in the system",
                        "matched_by": "title",
                        "existing_filename": existing.name,
                    },
                )

    # ── Copy staging PDF to raw_pdfs ─────────────────────────────────────────
    staging_path = STAGING_DIR / item.get("filename")
    if not staging_path.exists():
        raise HTTPException(status_code=404, detail="Staging PDF not found")

    os.makedirs(RAW_PDFS_DIR, exist_ok=True)
    final_filename = build_policy_filename(item)
    target_path = RAW_PDFS_DIR / final_filename

    try:
        shutil.copy2(staging_path, target_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to copy staging PDF: {e}")

    # ── FIX #4: define item_month early so every branch below can use it ─────
    item_month = item.get("month") or "January"

    # ── Google Drive: duplicate check → upload → download temp copy ──────────
    drive_file = {}
    warnings = []
    # FIX #3: temp_pdf defaults to local copy; overwritten if Drive succeeds
    temp_pdf = str(target_path)

    if is_drive_configured():
        try:
            # Step 1 – duplicate check in Drive
            duplicate_drive_file = find_duplicate_pdf_in_drive(
                str(target_path), final_filename
            )
            if duplicate_drive_file:
                matched_by = ", ".join(
                    duplicate_drive_file.get("matched_by") or ["name/content"]
                )
                # Clean up the local copy we just created before raising
                if target_path.exists():
                    target_path.unlink()
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "PDF already exists in Google Drive",
                        "matched_by": matched_by,
                        "drive_file_id": duplicate_drive_file.get("id"),
                        "drive_file_name": duplicate_drive_file.get("name"),
                        "drive_url": duplicate_drive_file.get("webViewLink"),
                    },
                )

            # FIX #1 & #2: upload BEFORE trying to use drive_file["id"]
            # Step 2 – upload to Drive
            print(f"Uploading {final_filename} to Google Drive...")
            drive_file = upload_pdf_to_drive_details(str(target_path), final_filename)
            print(f"Drive upload succeeded: {drive_file.get('id')} -> {drive_file.get('webViewLink')}")

            # Step 3 – download a fresh temp copy for indexing
            print("Downloading temp copy from Drive for indexing...")
            temp_pdf = download_pdf_from_drive(drive_file["id"])
            print(f"Temp copy ready: {temp_pdf}")

            # FIX #5: remove the RAW_PDFS local copy — Drive is source of truth
            if target_path.exists():
                target_path.unlink()
                print(f"Removed local copy: {target_path}")

        except HTTPException:
            raise
        except Exception as e:
            error_text = str(e)
            if "Service Accounts do not have storage quota" in error_text:
                error_text = (
                    "Folder is in personal My Drive. Move it to a "
                    "Shared Drive and add the service account as Content Manager."
                )
            print(f"Warning: Drive upload failed for {final_filename}: {error_text}")
            warnings.append(
                f"Drive upload failed - PDF saved locally only. Error: {error_text}"
            )
    else:
        warnings.append("Drive not configured - PDF saved locally only.")

    # ── FIX #3: save_policy_metadata always runs (not only in else branch) ───
    save_policy_metadata(
        final_filename,
        item.get("state"),
        item.get("year"),
        item_month,
        item.get("power_type"),
        item.get("category", "General"),
        drive_file_id=drive_file.get("id"),
        drive_url=drive_file.get("webViewLink"),
    )

    # ── Index the PDF via RAG pipeline ───────────────────────────────────────
    try:
        process_pdf(
            temp_pdf,
            item.get("state"),
            item.get("year"),
            item_month,
            item.get("power_type"),
            final_filename,         # source_file= stores real name, not tmp*
        )
        print(f"Indexing complete for {final_filename}")
    except Exception as e:
        warnings.append(f"PDF accepted but indexing failed: {e}")
        print(f"Warning: PDF indexing failed for {final_filename}: {e}")
    finally:
        # FIX #5: always clean up the temp download after indexing attempt
        if temp_pdf and temp_pdf != str(target_path) and os.path.exists(temp_pdf):
            try:
                os.remove(temp_pdf)
                print(f"Removed temp PDF: {temp_pdf}")
            except Exception as e:
                print(f"Warning: could not remove temp PDF {temp_pdf}: {e}")

    # ── Update queue & seen URLs ──────────────────────────────────────────────
    item["status"] = "accepted"
    item["accepted_filename"] = final_filename
    item["drive_file_id"] = drive_file.get("id")
    item["drive_url"] = drive_file.get("webViewLink")
    save_queue(queue)

    source_url = item.get("source_url")
    if source_url:
        seen = load_seen_urls()
        seen.add(source_url)
        save_seen_urls(seen)

    # ── Remove staging file ───────────────────────────────────────────────────
    if not _unlink_pdf(staging_path):
        print(
            f"Warning: staging file is locked and will be cleaned on next startup: {staging_path}"
        )

    return {
        "message": "Document accepted" if warnings else "Document accepted and indexed",
        "title": item.get("title"),
        "filename": final_filename,
        "category": item.get("category"),
        "drive_file_id": drive_file.get("id"),
        "drive_url": drive_file.get("webViewLink"),
        "warnings": warnings,
    }


@router.post("/reject-scraped")
def reject_scraped(
    request: ScrapeActionRequest = Body(...),
    authorization: Optional[str] = Header(None),
):
    require_token(request.token, authorization)
    queue = load_queue()
    item = next((it for it in queue if it.get("id") == request.id), None)

    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    if item.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Item is not pending")

    staging_path = STAGING_DIR / item.get("filename")
    if staging_path.exists():
        if not _unlink_pdf(staging_path):
            print(
                f"Warning: rejected staging file is locked and will be cleaned on next startup: {staging_path}"
            )

    item["status"] = "rejected"

    source_url = item.get("source_url")
    if source_url:
        seen = load_seen_urls()
        seen.discard(source_url)
        save_seen_urls(seen)

    save_queue(queue)

    return {"message": "Document rejected"}