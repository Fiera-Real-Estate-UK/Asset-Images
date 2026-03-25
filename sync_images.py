import os
import base64
import requests
from pathlib import Path

# ---------------------------------------------------------------------------
# Config — matches your Airtable setup and GitHub repo
# ---------------------------------------------------------------------------
AIRTABLE_PAT   = os.environ["AIRTABLE_PAT"]
BASE_ID        = "app6kSWgnKx3E5ULh"
TABLE_NAME     = "Assets"
ATTACH_FIELD   = "Photos"
URL_FIELD      = "Permanent Photo URL"  # Must exist as a field in Airtable

GITHUB_TOKEN   = os.environ["GITHUB_TOKEN"]
GITHUB_REPO    = "Fiera-Real-Estate-UK/Asset-Images"
GITHUB_BRANCH  = "main"
IMAGE_DIR      = "images"  # Subdirectory in the repo where images are stored

# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------
airtable_headers = {
    "Authorization": f"Bearer {AIRTABLE_PAT}",
    "Content-Type": "application/json"
}

github_headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

AIRTABLE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"
GITHUB_API   = f"https://api.github.com/repos/{GITHUB_REPO}/contents"


# ---------------------------------------------------------------------------
# Step 1: Fetch records that have a photo but no permanent URL yet
# ---------------------------------------------------------------------------
def get_records_needing_sync():
    records = []
    offset = None

    while True:
        params = {
            # Only process records where Photos is populated and URL field is empty
            "filterByFormula": f"AND({{Photos}}, {{Permanent Photo URL}} = '')",
            "fields[]": [ATTACH_FIELD, "Name"]
        }
        if offset:
            params["offset"] = offset

        response = requests.get(AIRTABLE_URL, headers=airtable_headers, params=params)
        response.raise_for_status()
        data = response.json()

        records.extend(data.get("records", []))
        offset = data.get("offset")

        if not offset:
            break

    return records


# ---------------------------------------------------------------------------
# Step 2: Download image from Airtable's (expiring) attachment URL
# ---------------------------------------------------------------------------
def download_image(url: str) -> bytes:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content


# ---------------------------------------------------------------------------
# Step 3: Determine file extension from Airtable attachment metadata
# ---------------------------------------------------------------------------
def get_extension(attachment: dict) -> str:
    filename = attachment.get("filename", "image.jpg")
    ext = Path(filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        ext = ".jpg"  # Safe fallback
    return ext


# ---------------------------------------------------------------------------
# Step 4: Commit image to GitHub via the Contents API
# Returns the permanent raw.githubusercontent.com URL
# ---------------------------------------------------------------------------
def commit_to_github(record_id: str, image_bytes: bytes, extension: str) -> str:
    filename    = f"{IMAGE_DIR}/{record_id}{extension}"
    api_path    = f"{GITHUB_API}/{filename}"

    # Check if the file already exists — needed to get its SHA for updates
    sha = None
    check = requests.get(api_path, headers=github_headers)
    if check.status_code == 200:
        sha = check.json()["sha"]

    payload = {
        "message": f"Add image for Airtable record {record_id}",
        "content": base64.b64encode(image_bytes).decode("utf-8"),
        "branch": GITHUB_BRANCH
    }
    if sha:
        payload["sha"] = sha  # Required by GitHub API when updating an existing file

    response = requests.put(api_path, headers=github_headers, json=payload)
    response.raise_for_status()

    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{filename}"


# ---------------------------------------------------------------------------
# Step 5: Write the permanent URL back to the Airtable record
# ---------------------------------------------------------------------------
def write_url_to_airtable(record_id: str, url: str):
    payload = {"fields": {URL_FIELD: url}}
    response = requests.patch(
        f"{AIRTABLE_URL}/{record_id}",
        headers=airtable_headers,
        json=payload
    )
    response.raise_for_status()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Checking for records to sync...")
    records = get_records_needing_sync()
    print(f"Found {len(records)} record(s) needing sync.")

    for record in records:
        record_id   = record["id"]
        attachments = record.get("fields", {}).get(ATTACH_FIELD, [])

        if not attachments:
            print(f"  Skipping {record_id} — no attachments found")
            continue

        # Only processes the first image — extend here if multi-image support needed
        attachment = attachments[0]
        url        = attachment.get("url")

        if not url:
            print(f"  Skipping {record_id} — attachment has no URL")
            continue

        try:
            print(f"  Processing {record_id}...")
            extension     = get_extension(attachment)
            image_bytes   = download_image(url)
            permanent_url = commit_to_github(record_id, image_bytes, extension)
            write_url_to_airtable(record_id, permanent_url)
            print(f"  ✓ {permanent_url}")

        except Exception as e:
            # Log and continue — don't let one failure block the rest
            print(f"  ✗ Failed for {record_id}: {e}")
            continue

    print("Done.")


if __name__ == "__main__":
    main()
