import streamlit as st
import pandas as pd
from io import BytesIO

from habanero.generator import generate_habanero_report
from reporting.ft_builder import build_ft_data
from reporting.dv360_builder import build_dv360_data

from dashboard.summary import show_summary
from dashboard.demographics import show_demographics
from dashboard.areas import show_area_performance
from dashboard.products import show_products
from dashboard.creatives import show_creatives

from processors import usm, redners, mccaffreys
from processors.base import generic_process


PROCESSORS = {
    "USM": usm,
    "Redner's": redners,
    "McCaffrey's": mccaffreys
}


st.set_page_config(
    page_title="CS Reporting Pipeline",
    layout="wide"
)

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
    "saved_week_number": None,
    "saved_campaign_type": None,
    "saved_region": None,
    "saved_target_impressions": 0,
    "saved_target_ctr": 0.0,
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

week_number = None
campaign_type = None

if brand in ("Redner's", "McCaffrey's", "USM"):
    week_number = st.number_input("Week Number", min_value=1, max_value=999, step=1)

if brand == "McCaffrey's":
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

# --------------------------------------------------
# STAGE: idle — show Generate button
# --------------------------------------------------
if st.session_state.stage == "idle":

    if st.button("Generate Reports"):

        if not all([weekly_file, frequency_file, ft_file, client, report_number]):
            st.error("Please upload all required files.")
            st.stop()

        # Persist inputs for use in later stages
        st.session_state.saved_client = client
        st.session_state.saved_week_number = week_number
        st.session_state.saved_campaign_type = campaign_type
        st.session_state.saved_region = region
        st.session_state.saved_target_impressions = target_impressions
        st.session_state.saved_target_ctr = target_ctr

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

        if processor:
            long_df = processor.process(wide_df, guide_df)
        else:
            long_df = generic_process(wide_df, guide_df)

        # USM categorization check
        if (
            brand == "USM"
            and hasattr(usm, "needs_manual_categorization")
            and usm.needs_manual_categorization(long_df)
        ):
            st.session_state.pc_df_pending = long_df
            st.session_state.stage = "categorize"
            st.rerun()

        # Non-USM: build final export immediately
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
        st.session_state.stage = "done"
        st.rerun()

# --------------------------------------------------
# STAGE: done — preview, exports, dashboard
# --------------------------------------------------
if st.session_state.stage == "done" and st.session_state.pc_final_df is not None:

    final_clicks = st.session_state.pc_final_df
    habanero_df = st.session_state.habanero_df
    hab_buffer = st.session_state.hab_buffer
    hab_filename = st.session_state.hab_filename
    saved_client = st.session_state.saved_client
    saved_week_number = st.session_state.saved_week_number
    saved_campaign_type = st.session_state.saved_campaign_type
    saved_region = st.session_state.saved_region
    saved_target_impressions = st.session_state.saved_target_impressions
    saved_target_ctr = st.session_state.saved_target_ctr
    saved_target_clicks = int(saved_target_impressions * saved_target_ctr)

    st.success("Product clicks processed.")

    # -----------------------------
    # FT DATA
    # -----------------------------
    ft_data, campaign_name = build_ft_data(
        final_clicks, saved_week_number, saved_campaign_type
    )

    st.subheader(f"Preview — {saved_client} ({campaign_name})")
    st.dataframe(habanero_df, use_container_width=True)

    st.markdown("### Preview — Final Click Tag Output")
    st.dataframe(final_clicks, use_container_width=True)

    # -----------------------------
    # DV360 DATA
    # -----------------------------
    dv360_data = build_dv360_data(habanero_df, campaign_name, saved_region)

    # -----------------------------
    # INTERNAL CS EXPORT
    # -----------------------------
    cs_buffer = BytesIO()
    with pd.ExcelWriter(cs_buffer, engine="openpyxl") as writer:
        ft_data.to_excel(writer, sheet_name="ft_data", index=False)
        dv360_data.to_excel(writer, sheet_name="dv360_data", index=False)

    # -----------------------------
    # DOWNLOADS
    # -----------------------------
    st.download_button(
        "Download Habanero Report",
        data=hab_buffer.getvalue(),
        file_name=hab_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.download_button(
        "Download Internal Raw File for CS",
        data=cs_buffer.getvalue(),
        file_name=f"{saved_client}_Internal_Raw_File_for_CS.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.divider()
    st.header("Campaign Dashboard")

    tabs = st.tabs([
        "Campaign Summary",
        "Demographics",
        "Area Performance",
        "Product Performance",
        "Creative Performance"
    ])

    with tabs[0]:
        show_summary(dv360_data, saved_target_impressions, saved_target_clicks, saved_target_ctr)

    with tabs[1]:
        show_demographics(dv360_data)

    with tabs[2]:
        show_area_performance(dv360_data)

    with tabs[3]:
        show_products(ft_data)

    with tabs[4]:
        show_creatives(dv360_data)

    st.divider()
    if st.button("Start Over"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
