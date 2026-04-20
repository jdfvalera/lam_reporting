import pandas as pd


def build_ft_data(df, week_number, campaign_type, client=None):

    df = df.copy()

    df["Date"] = pd.to_datetime(df["Date"])

    start = df["Date"].min()
    end = df["Date"].max()

    if start.month == end.month:
        date_range = f"{start.strftime('%b %-d')} - {end.strftime('%-d')}"
    else:
        date_range = f"{start.strftime('%b %-d')} - {end.strftime('%b %-d')}"

    if week_number is not None and campaign_type:
        campaign = f"W{week_number} {campaign_type}_{date_range}"
    elif week_number is not None:
        campaign = f"W{week_number}_{date_range}"
    else:
        campaign = date_range

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