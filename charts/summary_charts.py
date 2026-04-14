import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


def overview_chart(impressions, clicks, ctr, label, palette):
    primary = palette["primary"]
    secondary = palette["secondary"]
    accent = palette["accent"]

    fig, ax1 = plt.subplots(figsize=(7, 5))
    fig.patch.set_facecolor("white")
    ax1.set_facecolor("white")

    bar_width = 0.18
    x = 0

    ax1.bar(x - bar_width, impressions, width=bar_width, color=primary, label="Impressions")
    ax1.bar(x, clicks, width=bar_width, color=secondary, label="Clicks")

    ax1.set_yscale("log")
    min_val = max(1, min(clicks, impressions) * 0.5)
    max_val = max(impressions, clicks) * 2
    ax1.set_ylim(min_val, max_val)
    ax1.set_xlim(-0.5, 0.5)
    ax1.set_ylabel("Impressions and Clicks", color="#333333", fontsize=9)
    ax1.set_xticks([x])
    ax1.set_xticklabels([label], color="#333333", fontsize=9)
    ax1.tick_params(colors="#333333", labelsize=8)
    ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

    ax2 = ax1.twinx()
    ax2.bar(x + bar_width, ctr, width=bar_width, color=accent, label="CTR")
    ax2.set_ylabel("CTR", color="#333333", fontsize=9)
    ax2.set_ylim(0, ctr * 2.5 if ctr > 0 else 0.01)
    ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:.2%}"))
    ax2.tick_params(colors="#333333", labelsize=8)

    ax1.text(x - bar_width, impressions * 1.15, f"{impressions:,}",
             ha="center", va="bottom", fontsize=8, fontweight="bold", color="#333333")
    ax1.text(x, clicks * 1.2, f"{clicks:,}",
             ha="center", va="bottom", fontsize=8, color="#333333")
    ax2.text(x + bar_width, ctr * 1.1, f"{ctr:.2%}",
             ha="center", va="bottom", fontsize=8, color=accent, fontweight="bold")

    for spine in ax1.spines.values():
        spine.set_color("#cccccc")
    for spine in ax2.spines.values():
        spine.set_color("#cccccc")
    ax1.grid(axis="y", linestyle="--", alpha=0.3, color="#cccccc")

    ax1.set_title("Overall Campaign Performance", color="#333333", fontsize=11, loc="left", pad=8)

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    fig.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(0.6, 1.0),
               ncol=3, frameon=False, fontsize=8)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    return fig
