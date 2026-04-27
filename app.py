import streamlit as st
import pandas as pd
from io import BytesIO

from habanero.generator import generate_habanero_report
from reporting.ft_builder import build_ft_data
from reporting.dv360_builder import build_dv360_data
from reporting.pptx_exporter import build_pptx

from dashboard.summary import show_summary
from dashboard.demographics import show_demographics
from dashboard.areas import show_area_performance
from dashboard.products import show_products
from dashboard.creatives import show_creatives

from processors import usm, redners, mccaffreys, bottlemart
from processors.base import generic_process


PROCESSORS = {
    "USM": usm,
    "Redner's": redners,
    "McCaffrey's": mccaffreys,
    "Bottlemart": bottlemart,
}

PALETTES = {
    "Classic Red": {
        "primary": "#8B1A1A",
        "secondary": "#f2a6a6",
        "accent": "#c49a00",
    },
    "Navy Blue": {
        "primary": "#1A3A6B",
        "secondary": "#a6bdf2",
        "accent": "#c49a00",
    },
    "Forest Green": {
        "primary": "#1A5C2A",
        "secondary": "#a6d4b0",
        "accent": "#c49a00",
    },
    "Slate Purple": {
        "primary": "#3D1A6B",
        "secondary": "#c2a6f2",
        "accent": "#c49a00",
    },
}


st.set_page_config(page_title="CS Reporting Pipeline", layout="wide")

# --------------------------------------------------
# Session state
# --------------------------------------------------
for key, default in {
    "stage": "idle",
    "pc_df_pending": None,
    "pc_final_df": None,
    "habanero_df": None,
    "hab_buffer": None,
    "hab_filename": None,
    "saved_client": None,
    "saved_custom_brand_name": None,
    "saved_week_number": None,
    "saved_campaign_type": None,
    "saved_region": None,
    "saved_target_impressions": 0,
    "saved_target_ctr": 0.0,
    "ft_data": None,
    "dv360_data": None,
    "campaign_name": None,
    "saved_brand": None,
    "unmapped_df": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.title("CS Reporting Pipeline")
st.divider()

# --------------------------------------------------
# HABANERO INPUTS
# --------------------------------------------------
st.header("Habanero Inputs")

client = st.text_input("Client Name")
report_number = st.text_input("Report Number")
region = st.selectbox("Region", ["US", "AU"])
weekly_file = st.file_uploader("Weekly Data Pull", type=["xlsx"])
frequency_file = st.file_uploader("Frequency File", type=["xlsx"])

st.divider()

# --------------------------------------------------
# PRODUCT CLICKS INPUTS
# --------------------------------------------------
st.header("Product Clicks Inputs")

brand = st.selectbox("Brand / Processor", list(PROCESSORS.keys()) + ["Custom"])

custom_brand_name = None
week_number = None
campaign_type = None

if brand == "Custom":
    custom_brand_name = st.text_input("Brand Name")
    week_number = st.number_input("Week Number", min_value=1, max_value=999, step=1)
    campaign_type = st.text_input("Campaign Type (e.g. Regular Ad, Sale)")

elif brand in ("USM", "Redner's", "McCaffrey's", "Bottlemart"):
    week_number = st.number_input("Week Number", min_value=1, max_value=999, step=1)
    if brand == "McCaffrey's":
        campaign_type = st.selectbox("Campaign Type", ["Weekly", "Sale"])
    elif brand == "Bottlemart":
        campaign_type = st.selectbox("Campaign Type", ["Weekly", "Sale"])

ft_file = st.file_uploader("FT File", type=["xlsx"])

st.divider()

# --------------------------------------------------
# CAMPAIGN TARGETS
# --------------------------------------------------
st.header("Campaign Targets")

target_impressions = st.number_input("Target Impressions", min_value=0)
target_ctr = st.number_input("Target CTR (%)", min_value=0.0, step=0.01) / 100
target_clicks = int(target_impressions * target_ctr)

st.divider()

# --------------------------------------------------
# REPORT SETTINGS  (always visible — affects live dashboard + PPT)
# --------------------------------------------------
st.header("Report Settings")

palette_name = st.selectbox("Color Palette", list(PALETTES.keys()))
palette = PALETTES[palette_name]

logo_file = st.file_uploader(
    "Client Logo for PPT title slide (optional — PNG or JPG)",
    type=["png", "jpg", "jpeg"],
)

# --------------------------------------------------
# STAGE: idle — show Generate button
# --------------------------------------------------
if st.session_state.stage == "idle":

    col_a, col_b = st.columns([1, 1])

    with col_a:
        run_habanero_only = st.button("Generate Habanero Only", type="secondary")
    with col_b:
        run_full = st.button("Generate Reports", type="primary")

    if run_habanero_only:
        if not all([weekly_file, frequency_file, client, report_number]):
            st.error("Please upload the Weekly Data Pull and Frequency File, and fill in Client Name and Report Number.")
            st.stop()

        st.session_state.saved_client = client
        st.session_state.saved_region = region

        habanero_df, hab_buffer, hab_filename = generate_habanero_report(
            weekly_file, frequency_file, client, report_number, region
        )
        st.session_state.habanero_df = habanero_df
        st.session_state.hab_buffer = hab_buffer
        st.session_state.hab_filename = hab_filename
        st.session_state.stage = "habanero_only"
        st.rerun()

    if run_full:
        if not all([weekly_file, frequency_file, ft_file, client, report_number]):
            st.error("Please upload all required files.")
            st.stop()

        if brand == "Custom" and not custom_brand_name:
            st.error("Please enter a Brand Name for the Custom processor.")
            st.stop()

        st.session_state.saved_client = client
        st.session_state.saved_brand = brand
        st.session_state.saved_custom_brand_name = custom_brand_name
        st.session_state.saved_week_number = week_number
        st.session_state.saved_campaign_type = campaign_type
        st.session_state.saved_region = region
        st.session_state.saved_target_impressions = target_impressions
        st.session_state.saved_target_ctr = target_ctr
        # Clear cached computed data so done stage recalculates
        st.session_state.ft_data = None
        st.session_state.dv360_data = None
        st.session_state.campaign_name = None

        # HABANERO
        habanero_df, hab_buffer, hab_filename = generate_habanero_report(
            weekly_file, frequency_file, client, report_number, region
        )
        st.session_state.habanero_df = habanero_df
        st.session_state.hab_buffer = hab_buffer
        st.session_state.hab_filename = hab_filename
        st.success("Habanero report generated.")

        # PRODUCT CLICKS
        xls = pd.ExcelFile(ft_file)
        wide_df = pd.read_excel(xls, sheet_name=0)
        guide_df = pd.read_excel(xls, sheet_name=1) if len(xls.sheet_names) > 1 else None

        processor = PROCESSORS.get(brand)

        unmapped_df = pd.DataFrame()
        if processor:
            result = processor.process(wide_df, guide_df)
            if isinstance(result, tuple):
                long_df, unmapped_df = result
            else:
                long_df = result
        else:
            result = generic_process(wide_df, guide_df)
            if isinstance(result, tuple):
                long_df, unmapped_df = result
            else:
                long_df = result

        st.session_state.unmapped_df = unmapped_df

        if (
            brand == "USM"
            and hasattr(usm, "needs_manual_categorization")
            and usm.needs_manual_categorization(long_df)
        ):
            st.session_state.pc_df_pending = long_df
            st.session_state.stage = "categorize"
            st.rerun()

        if processor:
            final_clicks = processor.build_final_export(
                long_df, week_number=week_number, campaign_type=campaign_type
            )
        else:
            final_clicks = long_df

        st.session_state.pc_final_df = final_clicks
        st.session_state.stage = "done"
        st.rerun()

# --------------------------------------------------
# STAGE: habanero_only — download only
# --------------------------------------------------
if st.session_state.stage == "habanero_only":
    st.success("Habanero report generated.")
    st.dataframe(st.session_state.habanero_df, use_container_width=True)

    st.download_button(
        "Download Habanero Report",
        data=st.session_state.hab_buffer.getvalue(),
        file_name=st.session_state.hab_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.divider()
    if st.button("Start Over", key="habanero_only_start_over"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --------------------------------------------------
# STAGE: categorize (USM only)
# --------------------------------------------------
if st.session_state.stage == "categorize":

    df = st.session_state.pc_df_pending
    spec = usm.get_categorization_spec(df)
    category_map = {}

    st.markdown("### Categorize Products")

    for product, count in spec["products"]:
        category_map[product] = st.selectbox(
            f"{product} ({count})",
            options=spec["categories"],
            key=f"cat_{product}"
        )

    if st.button("Confirm Categories", type="primary"):
        df = usm.apply_category_map(df, category_map)
        final_clicks = usm.build_final_export(df)
        st.session_state.pc_final_df = final_clicks
        st.session_state.ft_data = None
        st.session_state.dv360_data = None
        st.session_state.campaign_name = None
        st.session_state.stage = "done"
        st.rerun()

# --------------------------------------------------
# STAGE: done — previews, exports, dashboard, PPT
# --------------------------------------------------
if st.session_state.stage == "done" and st.session_state.pc_final_df is not None:

    final_clicks = st.session_state.pc_final_df
    habanero_df  = st.session_state.habanero_df
    hab_buffer   = st.session_state.hab_buffer
    hab_filename = st.session_state.hab_filename
    saved_client              = st.session_state.saved_client
    saved_brand               = st.session_state.saved_brand
    saved_week_number         = st.session_state.saved_week_number
    saved_campaign_type       = st.session_state.saved_campaign_type
    saved_region              = st.session_state.saved_region
    saved_target_impressions  = st.session_state.saved_target_impressions
    saved_target_ctr          = st.session_state.saved_target_ctr
    saved_target_clicks       = int(saved_target_impressions * saved_target_ctr)

    # Compute ft_data once and cache; always rebuild dv360_data
    if st.session_state.ft_data is None:
        ft_data, campaign_name = build_ft_data(
            final_clicks, saved_week_number, saved_campaign_type, client=saved_brand
        )
        st.session_state.ft_data      = ft_data
        st.session_state.campaign_name = campaign_name
    else:
        ft_data       = st.session_state.ft_data
        campaign_name = st.session_state.campaign_name

    dv360_data = build_dv360_data(habanero_df, campaign_name, saved_region, client=saved_brand, week_number=saved_week_number)

    st.success("Product clicks processed.")

    unmapped_df = st.session_state.unmapped_df
    if unmapped_df is not None and not unmapped_df.empty:
        dropped_total = int(unmapped_df["Clicks"].sum())
        st.warning(f"{dropped_total:,} click(s) were dropped — click tags not found in the guide.")
        with st.expander("View unmapped click breakdown"):
            group_cols = [c for c in ["Version", "Brand", "Store", "Ad Size", "Click Tag"] if c in unmapped_df.columns]
            breakdown = (
                unmapped_df.groupby(group_cols, sort=False)["Clicks"]
                .sum()
                .reset_index()
                .sort_values("Clicks", ascending=False)
            )
            st.dataframe(breakdown, use_container_width=True, hide_index=True)

    st.subheader(f"Preview — {saved_client} ({campaign_name})")
    st.dataframe(habanero_df, use_container_width=True)

    st.markdown("### Preview — Final Click Tag Output")
    st.dataframe(final_clicks, use_container_width=True)

    st.markdown("### Preview — DV360 Data")
    if isinstance(dv360_data, dict):
        for sheet_name, sheet_df in dv360_data.items():
            st.markdown(f"**{sheet_name}**")
            st.dataframe(sheet_df, use_container_width=True, hide_index=True)
    else:
        st.dataframe(dv360_data, use_container_width=True, hide_index=True)

    # -----------------------------
    # INTERNAL CS EXPORT
    # -----------------------------
    cs_buffer = BytesIO()
    with pd.ExcelWriter(cs_buffer, engine="openpyxl") as writer:
        ft_data.to_excel(writer, sheet_name="ft_data", index=False)
        if isinstance(dv360_data, dict):
            for sheet_name, sheet_df in dv360_data.items():
                sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)
        else:
            dv360_data.to_excel(writer, sheet_name="dv360_data", index=False)

    st.download_button(
        "Download Habanero Report",
        data=hab_buffer.getvalue(),
        file_name=hab_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.download_button(
        "Download Internal Raw File for CS",
        data=cs_buffer.getvalue(),
        file_name=f"{saved_client}_Internal_Raw_File_for_CS.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.divider()
    st.header("Campaign Dashboard")

    tabs = st.tabs([
        "Campaign Summary",
        "Demographics",
        "Area Performance",
        "Product Performance",
        "Creative Performance",
    ])

    with tabs[0]:
        show_summary(dv360_data, saved_target_impressions, saved_target_clicks,
                     saved_target_ctr, palette)
    with tabs[1]:
        show_demographics(dv360_data, palette)
    with tabs[2]:
        show_area_performance(dv360_data, palette)
    with tabs[3]:
        show_products(ft_data, palette)
    with tabs[4]:
        show_creatives(dv360_data, palette)

    # -----------------------------
    # PPT EXPORT
    # -----------------------------
    st.divider()
    st.subheader("Export Report")

    if st.button("Generate PowerPoint", type="primary"):
        with st.spinner("Building presentation…"):
            pptx_buf = build_pptx(
                client=saved_client,
                campaign_name=campaign_name,
                habanero_df=habanero_df,
                ft_data=ft_data,
                dv360_data=dv360_data,
                target_impressions=saved_target_impressions,
                target_clicks=saved_target_clicks,
                target_ctr=saved_target_ctr,
                highlights=st.session_state.get("campaign_highlights", ""),
                demographic_insights=st.session_state.get("demographic_insights", ""),
                area_insights=st.session_state.get("area_insights", ""),
                product_insights=st.session_state.get("product_insights", ""),
                creative_insights=st.session_state.get("creative_insights", ""),
                palette=palette,
                logo_bytes=logo_file.getvalue() if logo_file else None,
            )
        st.download_button(
            "Download PowerPoint",
            data=pptx_buf.getvalue(),
            file_name=f"{saved_client}_Campaign_Report.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )

    st.divider()
    if st.button("Start Over"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
