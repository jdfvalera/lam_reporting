import pandas as pd
import re
from .base import default_clicktag_longform

# --------------------------------------------------
# Canonical USM categories
# --------------------------------------------------
USM_ALLOWED_CATEGORIES = [
    "Beverages",
    "Breakfast / Snacks",
    "Canned Goods",
    "Dairy / Eggs",
    "Frozen Food",
    "Meat",
    "Produce",
    "Soups and Broths",
    "Seafood",
    "Others - Home & Garden",
    "Others - Sauces and Condiments",
    "Others - Cleaning Products",
    "Others - Party & Celebration",
]

# Products to exclude entirely
EXCLUDED_PRODUCTS = {
    "Opening Frame",
    "End Frame",
}

# --------------------------------------------------
# Core processing
# --------------------------------------------------
def process(
    df: pd.DataFrame,
    guide_df: pd.DataFrame | None = None
) -> pd.DataFrame:

    # -------------------------------
    # FT → long-form click tags
    # -------------------------------
    long_df = default_clicktag_longform(df)

    # -------------------------------
    # Placement → Brand + Store
    # -------------------------------
    def parse_placement(placement):
        if not isinstance(placement, str):
            return "Unknown", None

        token = placement.split("_", 1)[0].strip().upper()

        # Split on "-"
        parts = [p.strip() for p in token.split("-", 1)]

        prefix = parts[0]          # USM / ALB / MS
        store = parts[1] if len(parts) > 1 else None

        if prefix == "USM":
            brand = "United Supermarkets"
        elif prefix == "ALB":
            brand = "Albertsons"
        elif prefix == "MS":
            brand = "Market Street"
        else:
            return "Unknown", None

        return brand, store

    brand_data = long_df["Placement"].apply(parse_placement)

    long_df["Brand"] = brand_data.apply(lambda x: x[0])
    long_df["Promotion Code"] = brand_data.apply(lambda x: x[1])

    # -------------------------------
    # Ad Size normalization
    # -------------------------------
    def clean_ad_size(val):
        if not isinstance(val, str):
            return None
        match = re.search(r"\d+\s*x\s*\d+", val)
        return match.group(0).replace(" ", "") if match else None

    long_df["Ad Size"] = long_df["Ad Size"].apply(clean_ad_size)

    # -------------------------------
    # If no guide, return base output
    # -------------------------------
    if guide_df is None:
        return long_df

    # -------------------------------
    # Normalize Click Tag Guide
    # -------------------------------
    guide = guide_df.rename(
        columns={
            "Banner": "Brand",
            "Sizes": "Ad Size",
        }
    )

    guide["Brand"] = guide["Brand"].astype(str).str.strip()
    guide["Ad Size"] = guide["Ad Size"].apply(clean_ad_size)

    click_cols = [
        c for c in guide.columns
        if c.lower().startswith("click tag ")
    ]

    if not click_cols:
        raise ValueError("Click Tag Guide missing Click Tag columns.")

    # -------------------------------
    # Unpivot guide
    # -------------------------------
    guide_long = guide.melt(
        id_vars=["Brand", "Ad Size"],
        value_vars=click_cols,
        var_name="Click Tag",
        value_name="Product",
    )

    guide_long["Click Tag"] = (
        guide_long["Click Tag"]
        .str.replace("Click Tag ", "", regex=False)
        .astype(int)
    )

    guide_long = guide_long.dropna(subset=["Product"])

    # -------------------------------
    # Final join (Brand only)
    # -------------------------------
    for col in ["Brand", "Ad Size"]:
        long_df[col] = long_df[col].astype(str).str.strip()
        guide_long[col] = guide_long[col].astype(str).str.strip()

    enriched = long_df.merge(
        guide_long,
        on=["Brand", "Ad Size", "Click Tag"],
        how="left",
    )

    # -------------------------------
    # Remove empty + non-analytic products
    # -------------------------------
    unmapped_df = enriched[enriched["Product"].isna()].copy()

    enriched = enriched.dropna(subset=["Product"])
    enriched["Product"] = enriched["Product"].astype(str).str.strip()
    enriched = enriched[enriched["Product"] != ""]
    enriched = enriched[
        ~enriched["Product"].isin(EXCLUDED_PRODUCTS)
    ]

    return enriched, unmapped_df


# --------------------------------------------------
# Categorization contract (USM only)
# --------------------------------------------------
def needs_manual_categorization(df: pd.DataFrame) -> bool:
    return "Product" in df.columns


def get_categorization_spec(df: pd.DataFrame):
    products = (
        df["Product"]
        .value_counts()
        .sort_index()
        .items()
    )

    return {
        "products": list(products),
        "categories": USM_ALLOWED_CATEGORIES,
    }


def apply_category_map(df: pd.DataFrame, category_map: dict) -> pd.DataFrame:
    df = df.copy()
    df["Category"] = df["Product"].map(category_map)
    return df


# --------------------------------------------------
# Final export
# --------------------------------------------------
def build_final_export(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    return pd.DataFrame({
        "Date": df["Date"],
        "Brand": df["Brand"],
        "Promotion Code": df["Promotion Code"],
        "Products": df["Product"],
        "Category": df.get("Category"),
        "Ad Size": df["Ad Size"],
        "Click Tag": df["Click Tag"],
        "Clicks": df["Clicks"],
    })
