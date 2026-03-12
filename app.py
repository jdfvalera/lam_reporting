import streamlit as st
import pandas as pd
from io import BytesIO

from habanero.generator import generate_habanero_report
from reporting.ft_builder import build_ft_data
from reporting.dv360_builder import build_dv360_data

from processors import usm, redners, mccaffreys
from processors.base import generic_process


PROCESSORS = {
    "USM": usm,
    "Redner's": redners,
    "McCaffrey's": mccaffreys,
}


st.set_page_config(page_title="CS Reporting Pipeline", layout="wide")

st.title("CS Reporting Pipeline")

st.divider()

# --------------------------------------------------
# HABANERO INPUTS
# --------------------------------------------------

st.subheader("Habanero Report")

client = st.text_input("Client Name")
report_number = st.text_input("Report Number")

region = st.selectbox(
    "Region",
    ["US", "AU"]
)

weekly_file = st.file_uploader(
    "Weekly Data Pull",
    type=["xlsx"]
)

frequency_file = st.file_uploader(
    "Frequency File",
    type=["xlsx"]
)

st.divider()

# --------------------------------------------------
# PRODUCT CLICKS INPUTS
# --------------------------------------------------

st.subheader("Product Clicks")

brand = st.text_input(
    "Brand / Client Processor (USM, Redner's, McCaffrey's or custom)"
)

week_number = st.number_input(
    "Week Number",
    min_value=1,
    max_value=999
)

campaign_type = st.text_input(
    "Campaign Type (Weekly, Sale etc)"
)

ft_file = st.file_uploader(
    "FT File",
    type=["xlsx"]
)

st.divider()

# --------------------------------------------------
# GENERATE PIPELINE
# --------------------------------------------------

if st.button("Generate Reports"):

    if not all([
        weekly_file,
        frequency_file,
        ft_file,
        client,
        report_number
    ]):
        st.error("Please upload all required files.")
        st.stop()

    # --------------------------------------------------
    # HABANERO PIPELINE
    # --------------------------------------------------

    habanero_df, habanero_buffer, habanero_filename = generate_habanero_report(
        weekly_file,
        frequency_file,
        client,
        report_number,
        region
    )

    st.success("Habanero report generated.")

    # --------------------------------------------------
    # PRODUCT CLICKS PIPELINE
    # --------------------------------------------------

    xls = pd.ExcelFile(ft_file)

    wide_df = pd.read_excel(xls, sheet_name=0)

    guide_df = None
    if len(xls.sheet_names) > 1:
        guide_df = pd.read_excel(xls, sheet_name=1)

    processor = PROCESSORS.get(brand)

    if processor:
        long_df = processor.process(wide_df, guide_df)
        final_clicks = processor.build_final_export(
            long_df,
            week_number=week_number,
            campaign_type=campaign_type
        )
    else:
        long_df = generic_process(wide_df, guide_df)
        final_clicks = long_df

    st.success("Product clicks report generated.")

    # --------------------------------------------------
    # FT DATA
    # --------------------------------------------------

    ft_data, campaign_name = build_ft_data(
        final_clicks,
        week_number,
        campaign_type
    )

    # --------------------------------------------------
    # DV360 DATA
    # --------------------------------------------------

    dv360_data = build_dv360_data(
        habanero_df,
        campaign_name,
        region
    )

    # --------------------------------------------------
    # CS EXPORT
    # --------------------------------------------------

    cs_buffer = BytesIO()

    with pd.ExcelWriter(cs_buffer, engine="openpyxl") as writer:

        ft_data.to_excel(
            writer,
            sheet_name="ft_data",
            index=False
        )

        dv360_data.to_excel(
            writer,
            sheet_name="dv360_data",
            index=False
        )

    # --------------------------------------------------
    # DOWNLOADS
    # --------------------------------------------------

    st.download_button(
        "Download Habanero Report",
        data=habanero_buffer.getvalue(),
        file_name=habanero_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.download_button(
        "Download Internal Raw File for CS",
        data=cs_buffer.getvalue(),
        file_name=f"{client}_Internal_Raw_File_for_CS.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )