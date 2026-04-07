import os
import base64
import requests
from pathlib import Path

# ---------------------------------------------------------------------------
# Config — one entry per Airtable table to sync
# ---------------------------------------------------------------------------
TABLES = [
    {
        "base_id":      "app6kSWgnKx3E5ULh",
        "table_name":   "Assets",
        "attach_field": "Photos",
        "url_field":    "Permanent Photo URL",
    },
    {
        "base_id":      "appVinwKwEnt5HAIk",
        "table_name":   "Properties",
        "attach_field": "Photo",
        "url_field":    "Photo URL",
    },
    {
        "base_id":      "appkiOATCNN0jhzjG",
        "table_name":   "Projects",
        "attach_field": "Photo",
        "url_field":    "Photo URL",
    }    
]

AIRTABLE_PAT  = os.environ["AIRTABLE_PAT"]
GITHUB_TOKEN  = os.environ["GITHUB_TOKEN"]
GITHUB_REPO   = "Fiera-Real-Estate-UK/Asset-Images"
GITHUB_BRANCH = "main"
IMAGE_DIR     = "images"

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

GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/contents"


# ---------------------------------------------------------------------------
# Step 1: Fetch records that have a photo but no permanent URL yet
# ---------------------------------------------------------------------------
def get_records_needing_sync(base_id, table_name, attach_field, url_field):
    records = []
    offset  = None
    url     = f"https://api.airtable.com/v0/{base_id}/{table_name}"

    while True:
        params = {
            "filterByFormula": f"AND({{{attach_field}}}, {{{url_field}}} = '')",
            "fields[]": [attach_field, "Name"]
        }
        if offset:
            params["offset"] = offset

        response = requests.get(url, headers=airtable_headers, params=params)
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
        ext = ".jpg"
    return ext


# ---------------------------------------------------------------------------
# Step 4: Commit image to GitHub and return the permanent URL
# ---------------------------------------------------------------------------
def commit_to_github(record_id: str, image_bytes: bytes, extension: str) -> str:
    filename = f"{IMAGE_DIR}/{record_id}{extension}"
    api_path = f"{GITHUB_API}/{filename}"

    sha = None
    check = requests.get(api_path, headers=github_headers)
    if check.status_code == 200:
        sha = check.json()["sha"]

    payload = {
        "message": f"Add image for Airtable record {record_id}",
        "content": base64.b64encode(image_bytes).decode("utf-8"),
        "branch":  GITHUB_BRANCH
    }
    if sha:
        payload["sha"] = sha

    response = requests.put(api_path, headers=github_headers, json=payload)
    response.raise_for_status()

    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{filename}"


# ---------------------------------------------------------------------------
# Step 5: Write the permanent URL back to Airtable
# ---------------------------------------------------------------------------
def write_url_to_airtable(base_id, table_name, record_id, url_field, url):
    payload  = {"fields": {url_field: url}}
    response = requests.patch(
        f"https://api.airtable.com/v0/{base_id}/{table_name}/{record_id}",
        headers=airtable_headers,
        json=payload
    )
    response.raise_for_status()


# ---------------------------------------------------------------------------
# Main — loops over all configured tables
# ---------------------------------------------------------------------------
def main():
    for table in TABLES:
        base_id      = table["base_id"]
        table_name   = table["table_name"]
        attach_field = table["attach_field"]
        url_field    = table["url_field"]

        print(f"\n--- {table_name} ({base_id}) ---")
        records = get_records_needing_sync(base_id, table_name, attach_field, url_field)
        print(f"Found {len(records)} record(s) needing sync.")

        for record in records:
            record_id   = record["id"]
            attachments = record.get("fields", {}).get(attach_field, [])

            if not attachments:
                print(f"  Skipping {record_id} — no attachments found")
                continue

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
                write_url_to_airtable(base_id, table_name, record_id, url_field, permanent_url)
                print(f"  ✓ {permanent_url}")

            except Exception as e:
                print(f"  ✗ Failed for {record_id}: {e}")
                continue

    print("\nDone.")


if __name__ == "__main__":
    main()
