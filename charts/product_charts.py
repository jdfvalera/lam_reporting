import matplotlib.pyplot as plt

_SLICE_COLORS = [
    "#8B1A1A", "#c49a00", "#4a90d9", "#5cb85c", "#e67e22",
    "#9b59b6", "#1abc9c", "#e74c3c", "#95a5a6", "#f39c12", "#2ecc71",
]


def product_pie_chart(products, palette):
    primary = palette["primary"]
    accent = palette["accent"]

    # Use primary as first slice color, then cycle through the rest
    colors = [primary, accent] + [c for c in _SLICE_COLORS if c not in (primary, accent)]

    labels = [
        (p[:22] + "…") if len(p) > 22 else p
        for p in products.index
    ]

    fig, ax = plt.subplots(figsize=(6, 5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    wedges, texts, autotexts = ax.pie(
        products.values,
        labels=labels,
        autopct="%1.1f%%",
        colors=colors[: len(products)],
        startangle=90,
        pctdistance=0.75,
    )
    
    for t in texts:
        t.set_fontsize(7)
    for at in autotexts:
        at.set_fontsize(7)
        at.set_color("white")

    ax.set_title("Product Clicks", color="#333333", fontsize=11, loc="left", pad=8)

    plt.tight_layout()
    return fig
