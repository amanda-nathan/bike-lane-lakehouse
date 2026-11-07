"""Charts for the README and eval write-up. Reads from Trino and evals/results.

    uv run --group docs python docs/charts.py
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bikelake import warehouse  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "img"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
BLUE = "#2a78d6"
GRAY = "#a9a8a2"
ORANGE = "#eb6834"

plt.rcParams.update(
    {
        "font.family": ["Helvetica Neue", "Arial"],
        "font.size": 10,
        "text.color": INK,
        "axes.labelcolor": INK_2,
        "axes.edgecolor": GRID,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "savefig.dpi": 200,
    }
)


def query(sql: str) -> list[list]:
    return warehouse.run(sql)["rows"]


def finish(ax, title: str, subtitle: str) -> None:
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", pad=22)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9, color=INK_2, va="bottom")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)


def lanes_by_borough() -> None:
    rows = query("""
        SELECT coalesce(borough, 'All NYC') AS area,
               cast(sum(cyclists_hurt_after) - sum(cyclists_hurt_before) AS double) / sum(cyclists_hurt_before),
               cast(sum(citywide_cyclists_hurt_after) - sum(citywide_cyclists_hurt_before) AS double) / sum(citywide_cyclists_hurt_before)
        FROM fct_nyc_new_lane_safety
        GROUP BY GROUPING SETS ((borough), ())
    """)
    order = ["All NYC", "Manhattan", "Queens", "Bronx", "Brooklyn"]  # Staten Island: 1 injury before
    rows = sorted([r for r in rows if r[0] in order], key=lambda r: order.index(r[0]))[::-1]
    areas = [r[0] for r in rows]
    near = [r[1] * 100 for r in rows]
    city = [r[2] * 100 for r in rows]

    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    y = range(len(areas))
    h = 0.34
    ax.barh([i + h / 2 + 0.02 for i in y], near, height=h, color=BLUE, label="Within 50 m of new protected lanes")
    ax.barh([i - h / 2 - 0.02 for i in y], city, height=h, color=GRAY, label="Citywide, same two-year windows")
    for i, (n, c) in enumerate(zip(near, city)):
        ax.text(max(n, 0) + 0.8, i + h / 2 + 0.02, f"{n:+.0f}%" if abs(n) >= 1 else f"{n:+.1f}%", va="center", fontsize=9, color=INK)
        ax.text(max(c, 0) + 0.8, i - h / 2 - 0.02, f"{c:+.1f}%", va="center", fontsize=9, color=INK_2)
    ax.set_yticks(list(y), areas)
    ax.axvline(0, color=INK_2, linewidth=0.8)
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_xlim(min(min(city), 0) - 2, max(near) + 8)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:+.0f}%" if v else "0")
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.1), ncol=2, frameon=False, fontsize=9)
    finish(ax, "Cyclists hurt, 2 years after vs. 2 years before a protected lane",
           "NYC lanes installed 2015 to Oct 2024. Not adjusted for more people riding. Staten Island left out (1 injury before).")
    fig.tight_layout()
    fig.savefig(OUT / "new_lanes_by_borough.png")
    plt.close(fig)


def washington_street() -> None:
    rows = query("""
        SELECT count_year, avg(bikes), count(*) FROM fct_boston_bike_counts_daily
        WHERE location_name = 'Washington Street north of Bexley Road' AND season = 'Summer'
        GROUP BY 1 ORDER BY 1
    """)
    years = [r[0] for r in rows]
    bikes = [r[1] for r in rows]

    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ax.plot(years, bikes, color=BLUE, linewidth=2, marker="o", markersize=5,
            markeredgecolor=SURFACE, markeredgewidth=1.5)
    for x, v in [(years[0], bikes[0]), (2018, bikes[years.index(2018)]), (years[-1], bikes[-1])]:
        ax.annotate(f"{v:.0f}", (x, v), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
    ax.set_xticks(years, [str(y) for y in years])
    ax.set_ylim(0, max(bikes) * 1.2)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_ylabel("Bikes per day")
    finish(ax, "Washington St north of Bexley Rd, Roslindale: summer bike counts",
           "Average of the summer count days, about 2 per year. No summer count in 2017.")
    fig.tight_layout()
    fig.savefig(OUT / "washington_street_summers.png")
    plt.close(fig)


def eval_results() -> None:
    """Share of answers with the right number and the required point, hard questions, by model and setup."""
    files = sorted((ROOT / "evals" / "results").glob("*_questions_hard_*.json"))
    latest = {}
    for f in files:
        data = json.loads(f.read_text())
        latest[data["model"]] = data
    models = [m for m in ("claude-opus-5-5", "claude-haiku-5-5") if m in latest]
    if not models:
        return
    arms = [("sql_only", "SQL only", GRAY), ("semantic_first", "Semantic layer first", BLUE)]
    labels = {"claude-opus-5-5": "Claude Opus 5.5", "claude-haiku-5-5": "Claude Haiku 5.5"}

    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    w = 0.28
    for j, (arm, label, color) in enumerate(arms):
        xs, means = [], []
        for i, model in enumerate(models):
            rows = [r for r in latest[model]["results"] if r["arm"] == arm]
            per_run = []
            for rep in sorted({r["repeat"] for r in rows}):
                run = [r for r in rows if r["repeat"] == rep]
                per_run.append(100 * sum(bool(r["correct"] and r["makes_point"]) for r in run) / len(run))
            x = i + (j - 0.5) * (w + 0.04)
            mean = sum(per_run) / len(per_run)
            ax.bar(x, mean, width=w, color=color, label=label if i == 0 else None)
            ax.scatter([x] * len(per_run), per_run, s=14, color=INK, zorder=3, linewidths=0)
            ax.text(x, max(per_run + [mean]) + 3, f"{mean:.0f}%", ha="center", fontsize=9)
            xs.append(x)
            means.append(mean)
    ax.set_xticks(range(len(models)), [labels[m] for m in models])
    ax.set_ylim(0, 112)
    ax.set_yticks([0, 25, 50, 75, 100], ["0", "25%", "50%", "75%", "100%"])
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2, frameon=False, fontsize=9)
    n = len({r["id"] for r in latest[models[0]]["results"]})
    finish(ax, "Hard questions answered fully right",
           f"Right number and the required caveat. {n} questions, 3 runs each (dots).")
    fig.tight_layout()
    fig.savefig(OUT / "eval_hard_questions.png")
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    lanes_by_borough()
    washington_street()
    eval_results()
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))
