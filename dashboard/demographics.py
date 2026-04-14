import streamlit as st
from charts.demographic_charts import demographic_chart


def show_demographics(df, palette):

    demo = (
        df.groupby("Demographics")
        .agg(Impressions=("Impressions", "sum"), Clicks=("Clicks", "sum"))
    )
    demo["CTR"] = demo["Clicks"] / demo["Impressions"]

    st.dataframe(demo)

    fig = demographic_chart(demo, palette)
    st.pyplot(fig)

    st.text_area("Demographic Insights", key="demographic_insights")
