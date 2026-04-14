import streamlit as st
from charts.product_charts import product_pie_chart


def show_products(ft_data, palette):

    st.subheader("Summary – Products.")

    col = (
        "Product" if "Product" in ft_data.columns
        else "Products" if "Products" in ft_data.columns
        else None
    )

    if col is None:
        st.info("No product data available — the FT file did not include a Click Tag Guide with product mappings.")
        st.text_area(
            "Product Insights",
            label_visibility="collapsed",
            height=120,
            key="product_insights",
            placeholder="Write product insights here…",
        )
        return

    products = (
        ft_data.groupby(col)["Clicks"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )

    left, right = st.columns([1, 1.3])

    with left:
        styled = products.to_frame().style.format({"Clicks": "{:,.0f}"}).set_table_styles([
            {"selector": "th", "props": [
                ("background-color", palette["primary"]),
                ("color", "white"),
                ("font-weight", "bold"),
            ]},
            {"selector": "td", "props": [("text-align", "center")]},
        ])
        st.dataframe(styled, use_container_width=True)

    with right:
        fig = product_pie_chart(products, palette)
        st.pyplot(fig, use_container_width=True)

    st.markdown(
        f"""<div style="
            border: 1.5px dashed {palette['primary']};
            border-radius: 6px;
            padding: 12px 14px;
            margin-top: 8px;
            margin-bottom: 8px;
        ">
        <b style="color:{palette['primary']};">Product Click Performance</b>
        </div>""",
        unsafe_allow_html=True,
    )
    st.text_area(
        "Product Insights",
        label_visibility="collapsed",
        height=120,
        key="product_insights",
        placeholder="Write product insights here…",
    )
