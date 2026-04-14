import streamlit as st
from charts.product_charts import product_pie_chart


def show_products(ft_data, palette):

    # Support both "Product" (McCaffrey's/Redner's) and "Products" (USM)
    col = "Product" if "Product" in ft_data.columns else "Products"

    products = (
        ft_data.groupby(col)["Clicks"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )

    st.dataframe(products)

    fig = product_pie_chart(products, palette)
    st.pyplot(fig)

    st.text_area("Product Insights", key="product_insights")
