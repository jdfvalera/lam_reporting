# CS Reporting Pipeline

An automated post-campaign reporting pipeline. Drop your DV360 export files into a watched inbox folder and the agent processes them automatically — generating Habanero reports, Internal Raw Files for CS, and (for Foodtown) monthly aggregations.

The legacy Streamlit UI (`app.py`) remains available for manual use.

---

## Table of Contents

1. [How the Agent Works](#how-the-agent-works)
2. [Setup](#setup)
3. [Running the Agent](#running-the-agent)
4. [Inbox Folder Structure](#inbox-folder-structure)
5. [Folder Naming Convention](#folder-naming-convention)
6. [Foodtown Multi-Week Flow](#foodtown-multi-week-flow)
7. [File Detection (No Renaming Required)](#file-detection-no-renaming-required)
8. [Outputs](#outputs)
9. [USM Auto-Categorization](#usm-auto-categorization)
10. [Supported Brands](#supported-brands)
11. [Troubleshooting](#troubleshooting)
12. [Project Structure](#project-structure)
13. [Legacy Streamlit UI](#legacy-streamlit-ui)

---

## How the Agent Works

The agent watches the `inbox/` folder continuously. When it detects the right combination of files, it runs automatically:

**Stage 1 — Habanero only** (triggers as soon as weekly + frequency files arrive):
- Generates the Habanero Excel report and writes it into the same campaign folder.

**Stage 2 — Full pipeline** (triggers when the FT/GS file also arrives):
- Re-generates Habanero, processes click tag data, and writes the Internal Raw File for CS.

Both outputs land directly in the campaign folder alongside the source files. No separate output directory.

---

## Setup

**1. Install dependencies:**
```bash
pip install -r requirements.txt
```

**2. Create your `.env` file:**
```bash
cp .env.example .env
```
Open `.env` and add your Anthropic API key (required only for USM auto-categorization):
```
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Running the Agent

The agent is configured as a macOS LaunchAgent and **starts automatically on login**.

**Check if it's running:**
```bash
launchctl list | grep lam-reporting
```
A result like `71874  0  com.vmg.lam-reporting-agent` means it's healthy.

**Watch live logs:**
```bash
tail -f ~/Documents/VMG/lam_reporting/agent.log
```

**Stop / start manually:**
```bash
launchctl unload ~/Library/LaunchAgents/com.vmg.lam-reporting-agent.plist
launchctl load  ~/Library/LaunchAgents/com.vmg.lam-reporting-agent.plist
```

---

## Inbox Folder Structure

```
inbox/
  {Brand}/
    {CampaignFolder}/
      *Weekly*.xlsx        ← DV360 Weekly Data Pull
      *Frequency*.xlsx     ← DV360 Frequency File
      *FTData*.xlsx        ← FT Click Tag file  (triggers Stage 2)
      *GS_Product*.xlsx    ← GS file (Redner's only, replaces FT)
```

Pre-created brand folders are ready to use:

```
inbox/
  USM/
  Redners/
  McCaffreys/
  Bottlemart/
  Wrays/
  Repco/
  Detwilers/
  Foodtown/        ← see Foodtown section below
```

---

## Folder Naming Convention

Create a subfolder inside the brand folder for each campaign. The folder name controls the Habanero filename and campaign label in the CS file.

**Format:** `{report}_{CampaignType}`

| Folder name | Habanero label | Campaign column in CS |
|---|---|---|
| `29` | `(29)` | `May 7 - 13` |
| `29_W30` | `(29)` | `W30_May 7 - 13` |
| `29_W30_Weekly` | `(29)` | `W30_Weekly_May 7 - 13` |
| `25_Sale` | `(25)` | `Sale_May 6 - 12` |
| `FY26 Period 3` | `(FY26 Period 3)` | `FY26 Period 3_May 6 - 12` |

**Rules:**
- If the folder name starts with a number (e.g. `29_W30`), the leading number is used as the report number in the Habanero filename.
- Everything after the first `_` becomes the campaign type (e.g. `W30_Weekly`).
- If the campaign type starts with `W{N}` (e.g. `W30`), the week number is extracted automatically — no `config.json` needed for most brands.
- Non-numeric folder names (e.g. `FY26 Period 3`) use the full name as both label and campaign type.

**Redner's only** — requires a week number since it's used in the output. If the folder is named `29_W78`, week 78 is extracted automatically. Otherwise create a `config.json`:
```json
{ "week": 78 }
```

**Optional `config.json`** (place inside the campaign folder to override any field):
```json
{
  "client":        "My Client Name",
  "week":          8,
  "report":        8,
  "campaign_type": "Weekly"
}
```

---

## Foodtown Multi-Week Flow

Foodtown campaigns span one month (4 weeks, 2 bi-weekly periods). Use this folder structure:

```
inbox/Foodtown/
  Month 1/
    W1/   ← weekly + frequency → W1 Habanero generated here
    W2/   ← weekly + frequency + FT file → W2 Habanero + Biweekly1 CS generated here
    W3/   ← weekly + frequency → W3 Habanero
    W4/   ← weekly + frequency + FT file → W4 Habanero + Biweekly2 CS + Monthly CS
  Month 2/
    W5/   W6/   W7/   W8/    ← same pattern
```

**Trigger rules:**
- Any `W{odd}/` folder with weekly + frequency → Habanero for that week
- Any `W{even}/` folder with weekly + frequency → Habanero for that week
- `W{even}/` with all of: W{odd} Habanero done + W{even} Habanero done + FT file → Biweekly CS
- Both biweekly CS files done → Monthly CS written to the month folder

**State is saved** in `.foodtown_state.json` inside each month folder. Restarting the agent never re-runs completed steps.

**Outputs per month:**
| File | Location |
|---|---|
| `(W1) Foodtown May 1-7.xlsx` | `W1/` |
| `(W2) Foodtown May 8-14.xlsx` | `W2/` |
| `Foodtown_Biweekly1_Internal_Raw_File_for_CS.xlsx` | `W2/` |
| `(W3) Foodtown May 15-21.xlsx` | `W3/` |
| `(W4) Foodtown May 22-28.xlsx` | `W4/` |
| `Foodtown_Biweekly2_Internal_Raw_File_for_CS.xlsx` | `W4/` |
| `Foodtown_Monthly_Internal_Raw_File_for_CS.xlsx` | `Month 1/` |

---

## File Detection (No Renaming Required)

The agent detects file roles by filename pattern — you can drop raw DV360 exports without renaming:

| Role | Detected when filename contains |
|---|---|
| Weekly Data Pull | `weekly` |
| Frequency File | `frequency` or `freq` |
| FT file | `ftdata`, `ft_data`, `ft `, `ft.` or ` ft` |
| GS file | `gs_product`, `product_clicks`, or `gs.xlsx` |

Generated output files (those starting with `(` or ending with `_Internal_Raw_File_for_CS.xlsx`) are automatically excluded from detection so they never interfere with processing.

---

## Outputs

All output files are written into the same campaign folder as the source files.

### Habanero Report
**Filename:** `({label}) {Client} {date_range}.xlsx`
**Sheet:** `Data` — all original weekly columns plus `Reach = Impressions / Frequency`

### Internal Raw File for CS
**Filename:** `{Client}_Internal_Raw_File_for_CS.xlsx`

**Sheet `ft_data`** — processed click tag data:

| Column | Notes |
|---|---|
| `Date` | |
| `Campaign` | Auto-built from folder name + date range |
| `Store` | Parsed from Placement (brand-specific) |
| `Product` | Populated when guide sheet is present |
| `Ad Size` | Normalized (e.g. `300x250`) |
| `Clicks` | |

Schema varies by brand (USM adds Brand/Category/Promotion Code; Wray's omits Store; Redner's adds Week/Version/Click Tag).

**Sheet `dv360_data`** — DV360 impression data:

| Column | Notes |
|---|---|
| `Date` | Shifted −1 day for US region |
| `Campaign` | Same label as ft_data |
| `Store` | Parsed from Insertion Order |
| `Demographics` | From Line Item |
| `Creative Size` | |
| `Device Type` | |
| `Impressions` | |
| `Clicks` | |
| `Click Rate (CTR)` | Formatted as `x.xx%` |

---

## USM Auto-Categorization

USM products are automatically assigned to one of 13 canonical categories using keyword matching:

`Beverages` · `Breakfast / Snacks` · `Canned Goods` · `Dairy / Eggs` · `Frozen Food` · `Meat` · `Produce` · `Soups and Broths` · `Seafood` · `Others - Home & Garden` · `Others - Sauces and Condiments` · `Others - Cleaning Products` · `Others - Party & Celebration`

**How it works:**
1. Every product seen is saved to `usm_category_learned.json` with its assigned category.
2. On the next run, products already in that file are categorized instantly (no matching needed).
3. New products are matched by keyword rules. If no keyword matches, they default to `Others - Party & Celebration` and a warning is logged.

**To correct a wrong category:** open `usm_category_learned.json`, find the product, change the category string, save. The corrected mapping is used on the next run.

---

## Supported Brands

| Brand folder | Processor | Region | Notes |
|---|---|---|---|
| `USM` | USM | US | Auto-categorization, 3-brand network |
| `Redners` | Redner's | US | GS-only (no FT file needed) |
| `McCaffreys` | McCaffrey's | US | |
| `Bottlemart` | Bottlemart | AU | |
| `Wrays` | Wray's | US | No Store column in ft_data |
| `Repco` | Repco | AU | |
| `Detwilers` | Detwiler's | US | |
| `Foodtown` | Foodtown | US | Multi-week/monthly flow |

---

## Troubleshooting

**Agent not triggering:**
```bash
tail -f ~/Documents/VMG/lam_reporting/agent.log
```
Look for errors. Common causes: wrong folder depth, unrecognized brand folder name, missing files.

**Re-trigger a campaign after renaming a folder:**
The agent detects folder renames automatically. For other cases (e.g. adding a file after the agent was stopped), restart the agent:
```bash
launchctl unload ~/Library/LaunchAgents/com.vmg.lam-reporting-agent.plist
launchctl load  ~/Library/LaunchAgents/com.vmg.lam-reporting-agent.plist
```

**Foodtown step not advancing:**
Check `.foodtown_state.json` in the month folder. A step marked `true` will not re-run. Delete the state file to reset the entire month.

**USM products defaulting to wrong category:**
Edit `usm_category_learned.json` directly — find the product name key and update its category value.

---

## Project Structure

```
lam_reporting/
│
├── run_agent.py                  # Agent entry point (auto-started by LaunchAgent)
│
├── agent/
│   ├── watcher.py                # Watchdog file-system monitor
│   ├── orchestrator.py           # Standard brand pipeline runner
│   ├── foodtown_orchestrator.py  # Foodtown multi-week state machine
│   ├── folder_parser.py          # Folder name → campaign metadata
│   └── categorizer.py            # USM keyword-based auto-categorizer
│
├── habanero/
│   └── generator.py              # Habanero report builder
│
├── processors/
│   ├── base.py                   # Generic long-form converter
│   ├── usm.py                    # USM (United Supermarkets)
│   ├── redners.py                # Redner's (FT + GS modes)
│   ├── mccaffreys.py             # McCaffrey's
│   ├── bottlemart.py             # Bottlemart (AU)
│   ├── wrays.py                  # Wray's
│   ├── repco.py                  # Repco (AU)
│   ├── detwilers.py              # Detwiler's
│   └── foodtown.py               # Foodtown
│
├── reporting/
│   ├── ft_builder.py             # Builds ft_data sheet
│   ├── dv360_builder.py          # Builds dv360_data sheet
│   └── pptx_exporter.py          # PowerPoint generator (legacy UI)
│
├── dashboard/                    # Streamlit dashboard tabs (legacy UI)
├── charts/                       # Matplotlib chart generators (legacy UI)
│
├── inbox/                        # Drop files here
│   └── {Brand}/{Campaign}/
│
├── usm_category_learned.json     # Persisted USM product→category mappings
├── agent.log                     # Live agent log
├── .env                          # ANTHROPIC_API_KEY (not committed)
├── .env.example                  # Env template
├── requirements.txt              # Python dependencies
│
└── app.py                        # Legacy Streamlit UI
```

---

## Legacy Streamlit UI

The original Streamlit app is still available for manual one-off runs:

```bash
streamlit run app.py
```

It supports the full pipeline interactively, including the USM manual categorization step and PowerPoint export. It is no longer the primary tool — the agent handles all regular campaign processing.
