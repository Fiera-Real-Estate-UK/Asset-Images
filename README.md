# Asset-Images

Permanent image storage for Fiera Real Estate UK project assets, integrated with Airtable and Power BI.

## Purpose

Airtable attachment URLs expire after a short period, making them unsuitable as a stable image source for Power BI. This repo solves that by acting as permanent public image storage. A sync script runs hourly via GitHub Actions, detects new images across configured Airtable tables, commits them here, and writes a permanent URL back to each Airtable record.

## Business context

Images are managed across two Airtable bases reflecting the structure of the two main business lines:

- **Equity** — deals are always single-property. Images are stored at the deal level in the **Assets** table (`app6kSWgnKx3E5ULh`). One image per record.
- **Debt** — deals can span multiple properties. Images are stored at the property level in the **Properties** table (`appVinwKwEnt5HAIk`), with one image per property record. This allows each property in a deal to carry its own image independently.

In both cases, only the first attachment per record is synced.

## How it works

```
Airtable record (attachment added)
→ GitHub Actions (hourly)
→ sync_images.py detects records where attachment exists but permanent URL is empty
→ Image downloaded using Airtable's expiring URL
→ Image committed to images/ using Airtable record ID as filename
→ Permanent URL written back to Airtable
→ Power BI reads stable URL
```

## Airtable configuration

| Base | Base ID | Table | Attachment Field | URL Field |
|---|---|---|---|---|
| Equity | app6kSWgnKx3E5ULh | Assets | Photos | Permanent Photo URL |
| Debt | appVinwKwEnt5HAIk | Properties | Photo | Photo URL |

To add a third table in future, add an entry to the `TABLES` list at the top of `sync_images.py` — no other changes needed.

## Repo structure

```
Asset-Images/
├── images/                  # All images, named by Airtable record ID (e.g. rec24BIUIrp0lI3V1.jpg)
├── sync_images.py           # Sync script
├── .github/
│   └── workflows/
│       └── sync.yml         # GitHub Actions workflow (runs hourly)
└── README.md
```

Filenames use the Airtable record ID, which is unique across all bases, so there is no collision risk between the two tables sharing the same `images/` directory.

## GitHub Actions

The workflow runs on two triggers:
- **Scheduled** — every hour (`0 * * * *`)
- **Manual** — via the Actions tab → "Run workflow" (useful for testing or forcing an immediate sync)

Logs for each run are available in the Actions tab. Each table is processed in sequence. Each record prints either a ✓ with the committed URL or a ✗ with the error reason.

## Secrets

One secret is required, set under **Settings → Secrets and variables → Actions**:

| Secret | Description |
|---|---|
| `AIRTABLE_PAT` | Airtable Personal Access Token with read/write access to both the Assets and Properties tables |

`GITHUB_TOKEN` is provided automatically by GitHub Actions — no setup needed.

> **Note:** Ensure the Airtable PAT has access to both bases (`app6kSWgnKx3E5ULh` and `appVinwKwEnt5HAIk`). If the Properties sync fails on first run, check the token's base permissions in Airtable's token settings.

## Migrating existing records

Any records that currently have a URL in their permanent URL field (e.g. a legacy SharePoint link) will be skipped — the script only processes records where that field is empty.

To migrate them:
1. Clear the relevant URL field on the Airtable records to be migrated
2. Trigger the workflow manually via the Actions tab
3. The script will process them on the next run

## Power BI

| Business Line | Field to use as image URL column |
|---|---|
| Equity | Permanent Photo URL (Assets table) |
| Debt | Photo URL (Properties table) |

These URLs are permanent, publicly accessible, and render correctly in PDF and PowerPoint exports.
