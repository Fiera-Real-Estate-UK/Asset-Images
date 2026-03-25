# Asset-Images

Permanent image storage for Fiera Real Estate UK project assets, integrated with Airtable and Power BI.

## Purpose

Airtable attachment URLs expire after a short period, making them unsuitable as a stable image source for Power BI. This repo solves that by acting as permanent public image storage. A sync script runs hourly via GitHub Actions, detects new images in Airtable, commits them here, and writes a permanent URL back to the Airtable record.

## How it works

```
Airtable (Assets table) → GitHub Actions (hourly) → images/ committed to this repo → Permanent URL written back to Airtable → Power BI reads stable URL
```

1. A new record is added to the **Assets** table in Airtable with a photo attached
2. The hourly GitHub Action runs `sync_images.py`
3. The script finds records where **Photos** is populated but **Permanent Photo URL** is empty
4. It downloads the image using Airtable's (expiring) attachment URL
5. It commits the image to `images/` using the Airtable record ID as the filename (e.g. `rec24BIUIrp0lI3V1.jpg`)
6. It writes the permanent `raw.githubusercontent.com` URL back to the **Permanent Photo URL** field in Airtable
7. Power BI reads **Permanent Photo URL** — URLs never expire and work in PDF/PowerPoint exports

## Repo structure

```
Asset-Images/
├── images/                  # All project images, named by Airtable record ID
├── sync_images.py           # Sync script
├── .github/
│   └── workflows/
│       └── sync.yml         # GitHub Actions workflow (runs hourly)
└── README.md
```

## Airtable setup

| Detail | Value |
|---|---|
| Base ID | app6kSWgnKx3E5ULh |
| Table | Assets |
| Attachment field | Photos |
| URL field | Permanent Photo URL (Single line text) |

Only the first image per record is synced. If a record has multiple photos, only the first attachment is processed.

## GitHub Actions

The workflow runs on two triggers:
- **Scheduled** — every hour (`0 * * * *`)
- **Manual** — via the Actions tab → "Run workflow" (useful for testing or forcing an immediate sync)

Logs for each run are available in the Actions tab. Each processed record prints either a ✓ with the committed URL or a ✗ with the error reason.

## Secrets

One secret is required, set under **Settings → Secrets and variables → Actions**:

| Secret | Description |
|---|---|
| `AIRTABLE_PAT` | Airtable Personal Access Token with read/write access to the Assets table |

`GITHUB_TOKEN` is provided automatically by GitHub Actions — no setup needed.

## Migrating existing records from SharePoint

Any existing asset records that currently have a SharePoint URL in **Permanent Photo URL** will not be picked up automatically — the script only processes records where that field is empty.

To migrate them:
1. Clear the **Permanent Photo URL** field on the relevant Airtable records
2. Trigger the workflow manually via the Actions tab
3. The script will process them on the next run

## Power BI

Use the **Permanent Photo URL** field as your image URL column. These URLs are permanent, publicly accessible, and will render correctly in PDF and PowerPoint exports — unlike the previous SharePoint-based URLs which required authentication.
