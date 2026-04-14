import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np


def demographic_chart(demo, palette):
    primary = palette["primary"]
    secondary = palette["secondary"]

    labels = demo.index.tolist()
    impressions = demo["Impressions"].tolist()
    clicks = demo["Clicks"].tolist()

    x = np.arange(len(labels))
    bar_width = 0.35

    fig, ax1 = plt.subplots(figsize=(7, 5))
    fig.patch.set_facecolor("white")
    ax1.set_facecolor("white")

    bars1 = ax1.bar(x - bar_width / 2, impressions, bar_width, color=primary, label="Impressions")

    ax2 = ax1.twinx()
    bars2 = ax2.bar(x + bar_width / 2, clicks, bar_width, color=secondary, label="Clicks")

    ax1.set_ylabel("Impressions", color="#333333", fontsize=9)
    ax2.set_ylabel("Clicks", color="#333333", fontsize=9)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=9)
    ax1.tick_params(colors="#333333", labelsize=8)
    ax2.tick_params(colors="#333333", labelsize=8)
    ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

    for bar, val in zip(bars1, impressions):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.01,
                 f"{int(val):,}", ha="center", va="bottom", fontsize=7,
                 fontweight="bold", color="#333333")

    for bar, val in zip(bars2, clicks):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.01,
                 f"{int(val):,}", ha="center", va="bottom", fontsize=7, color="#333333")

    for spine in ax1.spines.values():
        spine.set_color("#cccccc")
    for spine in ax2.spines.values():
        spine.set_color("#cccccc")
    ax1.grid(axis="y", linestyle="--", alpha=0.3, color="#cccccc")

    ax1.set_title("Impressions and Clicks", color="#333333", fontsize=11, loc="left", pad=8)

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    fig.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(0.5, 1.0),
               ncol=2, frameon=False, fontsize=8)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    return fig
