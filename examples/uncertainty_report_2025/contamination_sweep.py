# pylint: skip-file

from pathlib import Path
import math

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from popsborder.scenarios import run_scenarios_parallel, generate_scenarios
from popsborder.inputs import load_configuration
from popsborder.outputs import save_scenario_result_to_pandas


CONFIG = "always_pest"
# CONFIG = "sometimes_pest"


def line_plot(
    ax, df, x, y, hue=None, style=None, title=None, legend=None, show_points=False
):
    """Single line plot into a given Axes object."""
    # Count N per x
    counts = df.groupby([x, hue, style]).size().tolist()
    if len(set(counts)) > 1:
        n_records = f"{counts} ({sum(counts)})"
    else:
        n_records = f"{counts[0]} ({sum(counts)})"
    title = f"{title}\nN={n_records}"

    sns.lineplot(
        data=df,
        x=x,
        y=y,
        hue=hue,
        style=style,
        estimator="mean",
        errorbar="sd",
        marker="o",
        legend=legend,
        ax=ax,
    )

    # Overlay actual data points
    if show_points:
        x_vals = df[x].astype(float).values
        x_range = x_vals.max() - x_vals.min()
        jitter_fraction = 0.01
        jitter_amount = x_range * jitter_fraction
        x_jittered = x_vals + np.random.uniform(
            -jitter_amount, jitter_amount, size=len(df)
        )

        sns.scatterplot(
            data=df,
            x=x_jittered,
            y=df[y],
            hue=df[hue] if hue else None,
            style=df[style] if style else None,
            alpha=0.4,
            # avoid duplicating legend entries just to show the point style
            legend=False,
            ax=ax,
        )

    ax.set_title(title)
    ax.set_xlabel(x)
    ax.set_ylabel(y)


def plot(df, x, y, hue=None, style=None, ncols=2, show_points=False):
    """
    Create line plots for one or multiple y variables.

    If y is a list -> grid of subplots.
    If y is a string -> single plot.
    """
    legend = "auto"  # Legend used for the first plot.
    if isinstance(y, str):
        fig, ax = plt.subplots(figsize=(8, 6))
        line_plot(
            ax, df, x=x, y=y, hue=hue, style=style, title=f"{y} vs {x}", legend=legend
        )
        fig.tight_layout()
        fig.savefig(f"uncertainty_plot_{y}.png", dpi=75)
        plt.show()
    else:
        n = len(y)
        nrows = math.ceil(n / ncols)
        fig, axes = plt.subplots(
            nrows=nrows, ncols=ncols, figsize=(8 * ncols, 6 * nrows)
        )
        axes = axes.flatten()

        for i, y_col in enumerate(y):
            line_plot(
                axes[i],
                df,
                x=x,
                y=y_col,
                hue=hue,
                style=style,
                title=f"{y_col} vs {x}",
                legend=legend,
                show_points=show_points,
            )
            legend = False  # Legend only for the first one and not others.

        # Remove unused subplots if any
        for j in range(i + 1, len(axes)):
            fig.delaxes(axes[j])

        fig.tight_layout()
        fig.savefig(f"contamination_sweep_{CONFIG}.png", dpi=75)
        plt.show()


def main():

    config = load_configuration(f"base_config_contamination_sweep_{CONFIG}.yml")

    output_file = Path("contamination_sweep_{CONFIG}.csv")
    # Load the CSV file into a DataFrame
    # (Allows for re-running to display without computing or, with carefulness,
    # to compute additional combinations.)
    if output_file.exists():
        done = pd.read_csv(output_file)
    else:
        done = None

    # Parameter ranges to test
    values = {
        "inspection/effectiveness": [0.7, 0.8, 0.9],
        "contamination/contamination_rate/value": [
            0.001,
            0.005,
            0.01,
            0.02,
            0.03,
            0.04,
            0.05,
            0.06,
            0.07,
            0.08,
            0.1,
        ],
        "contamination/clustered/value": [0.3, 0.5, 0.7],
        "inspection/selection_strategy": ["random", "convenience"],
        "inspection/release_program": ["none", "dynamic_skip_lot"],
    }

    scenarios, found = generate_scenarios(values, done)

    print(f"found {found} computed scenarios...")
    print(f"created {len(scenarios)} new scenarios...")

    results = run_scenarios_parallel(
        config=config,
        scenario_table=scenarios,
        seed=42,
        num_submission_per_scenario=1,
        num_runs_per_submission=100,
        num_consignments=3650,
        max_workers=None,
        limit=None,
    )

    df = save_scenario_result_to_pandas(results)
    if done is not None:
        df = pd.concat([done, df])
    if results:
        df.to_csv(output_file, index=False)
    # exit()  # exit after computation

    plot(
        df,
        x="contamination/contamination_rate/value",
        y=[
            "relative_intercepted_contaminants",
            "total_intercepted_contaminants",
            "avg_items_inspected_detection",
            "relative_missed_contaminants",
            "total_missed_contaminants",
            "avg_items_inspected_completion",
        ],
        hue="inspection/selection_strategy",
        style="inspection/release_program",
        ncols=3,
        show_points=False,
    )


if __name__ == "__main__":
    main()
