import os
import json
import hashlib
from pathlib import Path
import io
import tempfile
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive']

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

_service_account_file = Path(
    os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", BASE_DIR / "credentials" / "service-account.json")
)
SERVICE_ACCOUNT_FILE = (
    _service_account_file
    if _service_account_file.is_absolute()
    else BASE_DIR / _service_account_file
)
DEFAULT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()

_service = None


def is_drive_configured():
    # Support both file-based and JSON env variable credentials (for Render)
    has_credentials = SERVICE_ACCOUNT_FILE.exists() or bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
    return bool(DEFAULT_FOLDER_ID) and has_credentials


def get_drive_service():
    global _service
    if not is_drive_configured():
        missing = []
        if not DEFAULT_FOLDER_ID:
            missing.append("GOOGLE_DRIVE_FOLDER_ID")
        if not SERVICE_ACCOUNT_FILE.exists() and not os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
            missing.append("service account credentials")
        raise FileNotFoundError(
            f"Google Drive is not configured: missing {', '.join(missing)}"
        )
    if _service is None:
        # Try JSON env variable first (for Render deployment)
        sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        if sa_json:
            sa_info = json.loads(sa_json)
            credentials = service_account.Credentials.from_service_account_info(
                sa_info, scopes=SCOPES
            )
        else:
            credentials = service_account.Credentials.from_service_account_file(
                str(SERVICE_ACCOUNT_FILE), scopes=SCOPES
            )
        _service = build('drive', 'v3', credentials=credentials)
    return _service


def list_pdfs_from_drive(folder_id=None):
    """List all PDF files from Google Drive folder"""
    folder_id = folder_id or DEFAULT_FOLDER_ID
    if not folder_id:
        return []

    service = get_drive_service()
    safe_folder = folder_id.replace("'", "\\'")
    query = (
        f"'{safe_folder}' in parents and trashed = false "
        f"and mimeType = 'application/pdf'"
    )

    all_files = []
    page_token = None

    while True:
        result = service.files().list(
            q=query,
            spaces="drive",
            fields="nextPageToken, files(id, name, webViewLink, createdTime)",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()

        all_files.extend(result.get("files", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return all_files


def _drive_query_value(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace("'", "\\'")


def _file_md5(file_path):
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            md5.update(chunk)
    return md5.hexdigest()


def find_duplicate_pdf_in_drive(file_path, file_name, folder_id=None):
    folder_id = folder_id or DEFAULT_FOLDER_ID
    if not folder_id:
        raise ValueError("Google Drive folder ID is required")

    local_md5 = _file_md5(file_path)
    safe_folder = _drive_query_value(folder_id)
    safe_name = _drive_query_value(file_name)

    name_query = (
        f"'{safe_folder}' in parents and trashed = false "
        f"and mimeType = 'application/pdf' "
        f"and name = '{safe_name}'"
    )

    service = get_drive_service()
    result = service.files().list(
        q=name_query,
        spaces="drive",
        fields="files(id, name, md5Checksum, webViewLink)",
        pageSize=10,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    matches = result.get("files", [])
    if not matches:
        folder_query = (
            f"'{safe_folder}' in parents and trashed = false "
            f"and mimeType = 'application/pdf'"
        )
        page_token = None
        while True:
            result = service.files().list(
                q=folder_query,
                spaces="drive",
                fields="nextPageToken, files(id, name, md5Checksum, webViewLink)",
                pageSize=1000,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            matches = [
                f for f in result.get("files", [])
                if f.get("md5Checksum") == local_md5
            ]
            if matches:
                break
            page_token = result.get("nextPageToken")
            if not page_token:
                break

    if not matches:
        return None

    duplicate = matches[0]
    duplicate["matched_by"] = []
    if duplicate.get("name") == file_name:
        duplicate["matched_by"].append("name")
    if duplicate.get("md5Checksum") == local_md5:
        duplicate["matched_by"].append("content")
    duplicate["local_md5"] = local_md5
    return duplicate


def upload_pdf_to_drive_details(file_path, file_name, folder_id=None):
    folder_id = folder_id or DEFAULT_FOLDER_ID
    if not folder_id:
        raise ValueError("Google Drive folder ID is required")

    file_metadata = {
        'name': file_name,
        'parents': [folder_id],
    }

    media = MediaFileUpload(file_path, mimetype='application/pdf', resumable=True)

    file = get_drive_service().files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink',
        supportsAllDrives=True,
        supportsTeamDrives=True,
    ).execute()

    print(f"Uploaded to Drive: {file.get('id')} -> {file.get('webViewLink')}")
    return {
        "id": file.get("id"),
        "webViewLink": file.get("webViewLink"),
    }


def upload_pdf_to_drive(file_path, file_name, folder_id=None):
    return upload_pdf_to_drive_details(file_path, file_name, folder_id).get("id")


def delete_drive_file(file_id):
    if not file_id:
        return
    get_drive_service().files().delete(
        fileId=file_id, supportsAllDrives=True
    ).execute()

def file_exists_in_drive(filename):
    files = list_pdfs_from_drive()

    return any(
        f["name"].strip().lower() == filename.strip().lower()
        for f in files
    )


def download_pdf_from_drive(file_id):
    service = get_drive_service()

    request = service.files().get_media(fileId=file_id)

    fd, temp_path = tempfile.mkstemp(suffix=".pdf")

    with os.fdopen(fd, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

    return temp_path