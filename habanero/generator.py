import pandas as pd
from io import BytesIO


def generate_habanero_report(
    weekly_file,
    frequency_file,
    client,
    report_number,
    region
):

    weekly = pd.read_excel(weekly_file, sheet_name="Data")
    weekly["Date"] = pd.to_datetime(weekly["Date"], errors="coerce", format="mixed")
    weekly = weekly.dropna(subset=["Date"])

    freq = pd.read_excel(frequency_file, sheet_name="Data")
    freq["Date"] = pd.to_datetime(freq["Date"], errors="coerce", format="mixed")
    freq = freq.dropna(subset=["Date"])

    freq = freq.rename(
        columns={
            "Unique Reach: Average Impression Frequency": "Frequency"
        }
    )

    freq["Frequency"] = pd.to_numeric(freq["Frequency"], errors="coerce")

    merged = weekly.merge(
        freq[["Date", "Frequency"]],
        on="Date",
        how="left"
    )

    merged["Impressions"] = pd.to_numeric(merged["Impressions"], errors="coerce")
    merged["Frequency"] = pd.to_numeric(merged["Frequency"], errors="coerce")
    merged["Reach"] = merged["Impressions"] / merged["Frequency"]

    raw_start = merged["Date"].min()
    raw_end = merged["Date"].max()

    if region == "US":
        start = raw_start - pd.Timedelta(days=1)
        end = raw_end - pd.Timedelta(days=1)
    else:
        start = raw_start
        end = raw_end

    if start.month == end.month:
        date_range = f"{start.strftime('%b %-d')} - {end.strftime('%-d')}"
    else:
        date_range = f"{start.strftime('%b %-d')} - {end.strftime('%b %-d')}"

    filename = f"({report_number}) {client} {date_range}.xlsx"

    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        merged.to_excel(writer, index=False, sheet_name="Data")
        ws = writer.book["Data"]

        date_col = merged.columns.get_loc("Date") + 1
        ctr_col = merged.columns.get_loc("Click Rate (CTR)") + 1
        reach_col = merged.columns.get_loc("Reach") + 1

        for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
            row[date_col - 1].number_format = "yyyy/mm/dd"
            row[ctr_col - 1].number_format = "0.00%"
            row[reach_col - 1].number_format = "#,##0"

    return merged, buffer, filename