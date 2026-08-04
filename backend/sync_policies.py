import json
import os
import re

from google_drive_service import list_pdfs_from_drive

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

POLICY_FILE = os.path.join(
    BASE_DIR,
    "data",
    "policies.json"
)


def extract_metadata(filename):
    name = filename.replace(".pdf", "")
    parts = name.split("_")

    state = parts[0] if parts else "Unknown"

    # Find year
    year = 2025
    for p in reversed(parts):
        match = re.search(r"\d{4}", p)
        if match:
            year = int(match.group())
            break

    # Find category
    category = "General"
    categories = [
        "Policy",
        "Order",
        "Regulation",
        "Regulations",
        "Gazette",
        "Circular",
        "Notification",
        "Roadmap"
    ]

    for cat in categories:
        if cat.lower() in name.lower():
            category = cat
            break

    # Power type
    if len(parts) >= 4:
        power_type = "_".join(parts[1:-2])
    elif len(parts) >= 2:
        power_type = "_".join(parts[1:])
    else:
        power_type = "Unknown"

    return {
        "state": state,
        "year": year,
        "month": "",
        "power_type": power_type,
        "category": category
    }


# --------------------------------------------------------
# Load existing policies
# --------------------------------------------------------

if os.path.exists(POLICY_FILE):
    with open(POLICY_FILE, "r", encoding="utf-8") as f:
        policies = json.load(f)
else:
    policies = []

print(f"Loaded {len(policies)} existing policies")

# --------------------------------------------------------
# Build lookup by drive_id
# --------------------------------------------------------

existing_by_drive_id = {}

for p in policies:
    drive_id = (
        p.get("drive_id")
        or p.get("drive_file_id")
    )

    if drive_id:
        existing_by_drive_id[drive_id] = p

# --------------------------------------------------------
# Read Drive
# --------------------------------------------------------

drive_files = list_pdfs_from_drive()

print(f"Found {len(drive_files)} PDFs in Drive")

updated_policies = []

seen_drive_ids = set()

for file in drive_files:

    drive_id = file["id"]
    filename = file["name"]
    drive_link = file.get("webViewLink")

    seen_drive_ids.add(drive_id)

    # Existing file
    if drive_id in existing_by_drive_id:

        policy = existing_by_drive_id[drive_id]

        # Update filename if renamed
        policy["file"] = filename

        policy["drive_id"] = drive_id
        policy["drive_link"] = drive_link

        updated_policies.append(policy)

    else:

        print(f"Adding new file: {filename}")

        metadata = extract_metadata(filename)

        updated_policies.append(
            {
                "file": filename,
                "state": metadata["state"],
                "year": metadata["year"],
                "month": metadata["month"],
                "power_type": metadata["power_type"],
                "category": metadata["category"],
                "drive_id": drive_id,
                "drive_link": drive_link
            }
        )

# --------------------------------------------------------
# Save
# --------------------------------------------------------

with open(POLICY_FILE, "w", encoding="utf-8") as f:
    json.dump(
        updated_policies,
        f,
        indent=2,
        ensure_ascii=False
    )

print("policies.json synchronized successfully")