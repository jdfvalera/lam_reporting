import pandas as pd
from processors.base import build_campaign_label


def build_ft_data(df, week_number, campaign_type, client=None):

    df = df.copy()

    df["Date"] = pd.to_datetime(df["Date"])

    start = df["Date"].min()
    end = df["Date"].max()

    df["Date"] = df["Date"].dt.strftime("%Y/%m/%d")

    if start.month == end.month:
        date_range = f"{start.strftime('%b %-d')} - {end.strftime('%-d')}"
    else:
        date_range = f"{start.strftime('%b %-d')} - {end.strftime('%b %-d')}"

    campaign = build_campaign_label(date_range, campaign_type, week_number)

    if client == "USM":
        ft_data = pd.DataFrame({
            "Date": df["Date"],
            "Brand": df.get("Brand"),
            "Promotion Code": df.get("Promotion Code"),
            "Products": df.get("Products"),
            "Category": df.get("Category"),
            "Ad Size": df.get("Ad Size"),
            "Click Tag": df.get("Click Tag"),
            "Clicks": df["Clicks"],
        })
    elif client == "Redner's":
        ft_data = pd.DataFrame({
            "Date": df["Date"],
            "Week": df.get("Week"),
            "Version": df.get("Version"),
            "Store": df.get("Store"),
            "Ad Size": df.get("Ad Size"),
            "Click Tag": df.get("Click Tag"),
            "Product Name": df.get("Product"),
            "Clicks": df["Clicks"],
        })
    elif client == "Bottlemart":
        ft_data = pd.DataFrame({
            "Date": df["Date"],
            "Campaign": campaign,
            "Zone": df.get("Zone"),
            "Product": df.get("Product"),
            "Ad Size": df.get("Ad Size"),
            "Clicks": df["Clicks"],
        })
    else:
        ft_data = pd.DataFrame({
            "Date": df["Date"],
            "Campaign": campaign,
            "Store": df.get("Store"),
            "Product": df.get("Product"),
            "Ad Size": df.get("Ad Size"),
            "Clicks": df["Clicks"],
        })

    return ft_data, campaign