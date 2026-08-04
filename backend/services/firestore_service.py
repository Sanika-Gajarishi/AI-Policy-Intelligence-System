import firebase_admin
from firebase_admin import credentials, firestore
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SERVICE_ACCOUNT_FILE = (
    BASE_DIR / "credentials" / "service-account.json"
)

if not firebase_admin._apps:
    if SERVICE_ACCOUNT_FILE.exists():
        # Local development - uses the JSON key file
        print("Using service account file:", SERVICE_ACCOUNT_FILE)

        cred = credentials.Certificate(str(SERVICE_ACCOUNT_FILE))

        firebase_admin.initialize_app(
            cred,
            {
                "projectId": cred.project_id
            }
        )

        print("Firebase initialized successfully (local)")
        print("Project ID:", cred.project_id)
        print("Service Account:", cred.service_account_email)
    else:
        # Cloud Run / production - no key file in the container,
        # uses the service account attached to the Cloud Run service automatically
        print("No service account file found, using Application Default Credentials")

        firebase_admin.initialize_app()

        print("Firebase initialized successfully (Cloud Run / ADC)")

db = firestore.client()

print("Firestore client created successfully")