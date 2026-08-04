import os
import json
import shutil

from services.rag_pipeline import process_pdf
from services.vector_db import DB_PATH
from google_drive_service import download_pdf_from_drive  # <-- fixed import


def rebuild_vector_db():
    print("Rebuilding vector database...")

    if os.path.exists(DB_PATH):
        try:
            shutil.rmtree(DB_PATH)
            print("Old vector store removed.")
        except Exception as e:
            print(f"Could not remove old vector store: {e}")

    DATA_DIR = os.path.dirname(os.path.abspath(__file__))
    POLICY_FILE = os.path.join(DATA_DIR, "data", "policies.json")

    if not os.path.exists(POLICY_FILE):
        print("No policies.json found — nothing to rebuild.")
        return

    with open(POLICY_FILE, "r", encoding="utf-8") as f:
        policies = json.load(f)

    print(f"{len(policies)} policies found.")

    for policy in policies:
        filename = policy["file"]
        state = policy["state"]
        year = str(policy["year"])
        month = policy.get("month", "")
        power_type = policy["power_type"]

        temp_path = None
        try:
            drive_id = policy.get("drive_id") or policy.get("drive_file_id")
            if not drive_id:
                print(f"No drive_id found for {filename}")
                continue

            print(f"Downloading from Drive: {filename}")
            temp_path = download_pdf_from_drive(drive_id)  # returns its own temp path

            process_pdf(
                temp_path,
                state,
                year,
                month,
                power_type,
                source_file=filename
            )

            print(f"Indexed: {filename}")

        except Exception as e:
            print(f"Error processing {filename}: {e}")
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    print("Vector database rebuild completed.")


if __name__ == "__main__":
    rebuild_vector_db()