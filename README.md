# CS Reporting Pipeline

A Streamlit app that automates post-campaign reporting. It integrates two internal tools — the **Habanero Report Generator** and the **Product Clicks Helper** — into a single pipeline that produces Excel exports and a ready-to-present PowerPoint report.

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [What It Does Not Do](#what-it-does-not-do)
3. [Requirements](#requirements)
4. [How to Run](#how-to-run)
5. [Step-by-Step Usage Guide](#step-by-step-usage-guide)
6. [Input File Structures](#input-file-structures)
7. [Supported Brands / Processors](#supported-brands--processors)
8. [Outputs](#outputs)
9. [Campaign Dashboard](#campaign-dashboard)
10. [PowerPoint Export](#powerpoint-export)
11. [Project Structure](#project-structure)

---

## What It Does

- Reads a **Weekly Data Pull** and a **Frequency File** (Habanero inputs) and generates a formatted Excel report with reach, impressions, and frequency data.
- Reads an **FT File** (click tag data) and processes it through a brand-specific or generic processor to produce a long-form click tag report.
- Combines both outputs into an **Internal Raw File for CS** (two-sheet Excel: `ft_data` + `dv360_data`).
- Displays a live **Campaign Dashboard** with five tabs: Campaign Summary, Demographics, Area Performance, Product Performance, and Creative Performance.
- Exports the full dashboard as a **PowerPoint presentation** — one slide per tab — using the layout and style of the standard campaign performance report.

---

## What It Does Not Do

- Does **not** pull data directly from DV360, Google Sheets, or any API. All inputs must be uploaded manually as Excel files.
- Does **not** support PDF export (PowerPoint only).
- Does **not** add creative images to the PowerPoint automatically. Creative images must be added to the PPT manually after export.
- Does **not** validate the internal structure of your Excel files beyond what is needed to process them. If column names are wrong, it will error.
- Does **not** support multiple campaigns in a single run. One pipeline run = one campaign period.
- The **USM categorization step** requires manual input from the user mid-flow. It cannot be automated.

---

## Requirements

### Python packages

```
streamlit
pandas
openpyxl
matplotlib
python-pptx
```

Install all at once:

```bash
pip install streamlit pandas openpyxl matplotlib python-pptx
```

### Python version

Python 3.10 or higher (uses `X | Y` union type syntax in processors).

---

## How to Run

```bash
streamlit run app.py
```

Open the URL shown in the terminal (usually `http://localhost:8501`).

---

## Step-by-Step Usage Guide

### 1. Habanero Inputs

| Field | Description |
|---|---|
| **Client Name** | Name of the client (e.g. `McCaffrey's`). Used in file names and the PPT title slide. |
| **Report Number** | Sequential report number (e.g. `8`). Used in the Habanero file name. |
| **Region** | `US` or `AU`. US applies a Day −1 date shift to align the reporting window. |
| **Weekly Data Pull** | Excel file exported from DV360 with weekly impression/click data. Must have a sheet named `Data`. |
| **Frequency File** | Excel file with frequency data. Must have a sheet named `Data`. |

### 2. Product Clicks Inputs

| Field | Description |
|---|---|
| **Brand / Processor** | Choose from `USM`, `Redner's`, `McCaffrey's`, or `Custom`. Determines which processing logic is applied to the FT file. |
| **Brand Name** | *(Custom only)* Free-text name for the brand. Used in the campaign name and report. |
| **Week Number** | Campaign week number (e.g. `64`). Used to build the campaign name. |
| **Campaign Type** | For McCaffrey's: `Weekly` or `Sale` (dropdown). For Custom: free text (e.g. `Regular Ad`). Not shown for USM or Redner's. |
| **FT File** | Excel file with click tag data. Sheet 1 = FT data. Sheet 2 = Click Tag Guide (optional but recommended). |

### 3. Campaign Targets

| Field | Description |
|---|---|
| **Target Impressions** | The impression goal for the campaign period. Used in the Campaign Summary KPI table. |
| **Target CTR (%)** | The CTR goal. Target Clicks is derived automatically (`Target Impressions × Target CTR`). |

### 4. Report Settings

| Field | Description |
|---|---|
| **Color Palette** | Choose a color scheme for the dashboard charts and PowerPoint. Options: Classic Red, Navy Blue, Forest Green, Slate Purple. |
| **Client Logo** | Optional PNG or JPG. If uploaded, it appears on the PowerPoint title slide. |

### 5. Generate Reports

Click **Generate Reports**. The pipeline runs in this order:

1. Habanero report is generated.
2. FT file is processed through the brand processor.
3. *(USM only)* A manual categorization step appears — assign a category to each product, then click **Confirm Categories**.
4. Results are shown: Habanero preview table, final click tag preview table, download buttons, and the Campaign Dashboard.

### 6. Fill in Insights

In each dashboard tab, there is a text box for writing insights. These are included in the PowerPoint export. Fill them in **before** generating the PPT.

### 7. Export to PowerPoint

Click **Generate PowerPoint** at the bottom of the page. Once built, a **Download PowerPoint** button will appear.

---

## Input File Structures

### Weekly Data Pull (Habanero)

Sheet name: `Data`

Required columns:

| Column | Description |
|---|---|
| `Date` | Date of the data row |
| `Impressions` | Number of impressions |
| `Clicks` | Number of clicks |
| `Click Rate (CTR)` | CTR value (decimal, e.g. `0.0027`) |
| `Line Item` | Used as the Demographics label in the dashboard |
| `Creative Size` | Ad creative dimensions (e.g. `300x250`) |
| `Device Type` | Device breakdown |
| `Insertion Order` | Used to extract the Store name (last segment after `_`) |

### Frequency File (Habanero)

Sheet name: `Data`

Required columns:

| Column | Description |
|---|---|
| `Date` | Must match dates in the Weekly Data Pull |
| `Unique Reach: Average Impression Frequency` | Raw frequency value |

### FT File (Product Clicks)

**Sheet 1 — FT Data**

Required columns:

| Column | Description |
|---|---|
| `Date` | Date of the row |
| `Placement` | Placement string. The processor parses brand/store/version from this. |
| `Ad Size` | Creative dimensions (e.g. `300x250`, `728x90`) |
| `Version` | *(Redner's)* Store version identifier |
| `Click Tag 1`, `Click Tag 2`, … | Click counts per click tag slot. Column names must start with `Click Tag `. |

**Sheet 2 — Click Tag Guide** *(optional but required for product-level reporting)*

Maps click tag slots to product names. Structure varies by brand:

| Brand | Required columns |
|---|---|
| **USM** | `Banner` (brand name: `United Supermarkets`, `Albertsons`, `Market Street`), `Sizes` (ad size), `Click Tag 1`, `Click Tag 2`, … |
| **Redner's** | `Banner` (`S96` or `Others`), `Sizes`, `Click Tag 1`, `Click Tag 2`, … |
| **McCaffrey's** | `Sizes`, `Click Tag 1`, `Click Tag 2`, … |
| **Custom** | `Sizes` (required), optionally `Banner`. `Click Tag 1`, `Click Tag 2`, … |

If no guide is provided, product-level data will not be available and the Product Performance tab/slide will be skipped.

---

## Supported Brands / Processors

### USM (United Supermarkets)

- Parses placement to extract **Brand** (`United Supermarkets`, `Albertsons`, `Market Street`) and **Promotion Code** (store ID).
- Joins click tags against the guide on `Brand + Ad Size + Click Tag`.
- Excludes `Opening Frame` and `End Frame` rows.
- Requires a **manual categorization step** — the user assigns each product to one of 13 canonical categories (Beverages, Meat, Produce, etc.) before the report is finalized.
- Output columns: `Date`, `Brand`, `Promotion Code`, `Products`, `Category`, `Ad Size`, `Click Tag`, `Clicks`.

### Redner's

- Parses placement to extract **Version** (e.g. `S1`, `S96`) and renames the existing `Version` column to **Store**.
- Maps version to a **Guide Version** (`S96` or `Others`) for guide lookup.
- Joins click tags against the guide on `Guide Version + Ad Size + Click Tag`.
- Keeps Opening Frame and End Frame rows (not excluded).
- Output columns: `Date`, `Week`, `Version`, `Store`, `Ad Size`, `Click Tag`, `Product Name`, `Clicks`.

### McCaffrey's

- Uses the generic processor as a base.
- Parses the first segment of `Placement` as **Store**.
- Excludes `Opening Frame` and `End Frame` rows.
- Requires **Week Number** and **Campaign Type** (`Weekly` or `Sale`).
- Output columns: `Date`, `Campaign`, `Store`, `Product`, `Ad Size`, `Clicks`.

### Custom

- Uses the generic processor.
- Requires a **Brand Name**, **Week Number**, and optionally a **Campaign Type**.
- Works with any FT file that has `Click Tag X` columns.
- If a guide sheet is provided with `Sizes` and `Click Tag X` columns, products will be mapped. Otherwise, the Product Performance tab will be skipped.
- Output: long-form click tag data with whatever columns the FT file contains.

---

## Outputs

### 1. Habanero Report (Excel)

File name: `({report_number}) {client} {date_range}.xlsx`

Single sheet (`Data`) with all original weekly data columns plus:
- `Reach` = `Impressions / Frequency`

Formatted columns:
- `Date` → `yyyy/mm/dd`
- `Click Rate (CTR)` → `0.00%`
- `Reach` → `#,##0`

### 2. Internal Raw File for CS (Excel)

File name: `{client}_Internal_Raw_File_for_CS.xlsx`

Two sheets:

**`ft_data`** — processed click tag data:

| Column | Description |
|---|---|
| `Date` | Row date |
| `Campaign` | Auto-generated campaign label (e.g. `W64 Weekly_Jan 29 - Feb 4`) |
| `Store` | Store name (if available) |
| `Product` | Product name (if guide was provided) |
| `Ad Size` | Creative size |
| `Clicks` | Click count |

**`dv360_data`** — processed DV360/Habanero data:

| Column | Description |
|---|---|
| `Date` | Row date (shifted −1 day for US region) |
| `Campaign` | Same campaign label as ft_data |
| `Store` | Extracted from `Insertion Order` |
| `Demographics` | From `Line Item` |
| `Creative Size` | Ad creative dimensions |
| `Device Type` | Device breakdown |
| `Impressions` | Impression count |
| `Clicks` | Click count |
| `Click Rate (CTR)` | CTR value |

### 3. PowerPoint Report

File name: `{client}_Campaign_Report.pptx`

Six slides:

| Slide | Content |
|---|---|
| **Title** | Client logo (if uploaded) on left, campaign name on right |
| **Campaign Summary** | KPI table (Target / Delivery / Over Delivery), campaign highlights, overview bar chart |
| **Demographics** | Insights, demographics table, grouped bar chart |
| **Area Level** | Combo chart (bars + lines), insights, area table |
| **Products** | Product table, pie chart, product insights |
| **Creatives** | Creative size table, insights, impressions/clicks chart |

---

## Campaign Dashboard

The live dashboard mirrors the PowerPoint layout. It appears after processing and has five tabs:

| Tab | Chart type | Data source |
|---|---|---|
| Campaign Summary | Dual-axis bar (log scale) | `dv360_data` |
| Demographics | Grouped bar, dual axis | `dv360_data` grouped by `Demographics` |
| Area Performance | Bar + dual line (Clicks + CTR) | `dv360_data` grouped by `Store` |
| Product Performance | Pie chart | `ft_data` grouped by `Product` |
| Creative Performance | Grouped bar, dual axis | `dv360_data` grouped by `Creative Size` |

Each tab has an insights text box. Text written there is carried into the PowerPoint.

The **Color Palette** selector (in Report Settings) updates the dashboard charts live — you can switch palettes to preview how the PPT will look before exporting.

---

## Project Structure

```
lam_reporting/
│
├── app.py                        # Main Streamlit app
│
├── habanero/
│   └── generator.py              # Habanero report builder
│
├── processors/
│   ├── base.py                   # Generic long-form converter + fallback processor
│   ├── usm.py                    # USM processor
│   ├── redners.py                # Redner's processor
│   └── mccaffreys.py             # McCaffrey's processor
│
├── reporting/
│   ├── ft_builder.py             # Builds ft_data from processed click tags
│   ├── dv360_builder.py          # Builds dv360_data from Habanero output
│   └── pptx_exporter.py          # PowerPoint report generator
│
├── dashboard/
│   ├── summary.py                # Campaign Summary tab
│   ├── demographics.py           # Demographics tab
│   ├── areas.py                  # Area Performance tab
│   ├── products.py               # Product Performance tab
│   └── creatives.py              # Creative Performance tab
│
└── charts/
    ├── summary_charts.py         # Overview bar chart
    ├── demographic_charts.py     # Grouped bar chart
    ├── area_charts.py            # Combo bar + line chart
    ├── product_charts.py         # Pie chart
    └── creative_charts.py        # Grouped bar chart
```
