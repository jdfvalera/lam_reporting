import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np


def area_chart(area, palette):
    primary = palette["primary"]
    accent = palette["accent"]

    # Sort by impressions descending to match sample
    area = area.sort_values("Impressions", ascending=False)

    labels = area.index.tolist()
    impressions = area["Impressions"].tolist()
    clicks = area["Clicks"].tolist()
    ctrs = area["CTR"].tolist()

    x = np.arange(len(labels))
    bar_width = 0.5

    fig, ax1 = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("white")
    ax1.set_facecolor("white")

    # Impressions bars — log scale on left axis
    bars = ax1.bar(x, impressions, bar_width, color=primary, label="Impressions", zorder=2)

    # Clicks line — also on left axis (log scale makes both visible)
    ax1.plot(x, clicks, "o-", color="#aaaaaa", linewidth=1.5,
             markersize=5, label="Clicks", zorder=3)

    ax1.set_yscale("log")
    ax1.set_ylabel("Impressions and Clicks", color="#333333", fontsize=9)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=15, ha="right", fontsize=8)
    ax1.tick_params(colors="#333333", labelsize=8)
    ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

    # CTR line — right axis
    ax2 = ax1.twinx()
    ax2.plot(x, ctrs, "o-", color=accent, linewidth=2, markersize=7, label="CTR", zorder=3)
    ax2.set_ylabel("CTR", color="#333333", fontsize=9)
    ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:.2%}"))
    ax2.tick_params(colors="#333333", labelsize=8)

    # Value labels on impression bars
    for bar, val in zip(bars, impressions):
        ax1.text(bar.get_x() + bar.get_width() / 2, val * 1.1,
                 f"{int(val):,}", ha="center", va="bottom",
                 fontsize=6, fontweight="bold", color="white")

    # Clicks values below dots
    for xi, val in zip(x, clicks):
        ax1.text(xi, val * 0.65, f"{int(val):,}",
                 ha="center", va="top", fontsize=6, color="#555555")

    # CTR values above dots
    for xi, val in zip(x, ctrs):
        ax2.text(xi, val * 1.08, f"{val:.2%}",
                 ha="center", va="bottom", fontsize=6,
                 color=accent, fontweight="bold")

    for spine in ax1.spines.values():
        spine.set_color("#cccccc")
    for spine in ax2.spines.values():
        spine.set_color("#cccccc")
    ax1.grid(axis="y", linestyle="--", alpha=0.3, color="#cccccc")

    ax1.set_title("Metrics Breakdown per Area", color="#333333", fontsize=11, loc="left", pad=8)

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    fig.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(0.5, 1.0),
               ncol=3, frameon=False, fontsize=8)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    return fig
