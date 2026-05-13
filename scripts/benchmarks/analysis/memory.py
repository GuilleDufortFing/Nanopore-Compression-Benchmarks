"""Memory analysis helpers extracted from the article notebook."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.lines import Line2D

from .figures import color_for_algorithm, maybe_export_figure
from .shared import (
    dataset_name_from_manifest,
    discover_named_runs,
    display_algorithm_name,
    load_run_manifest,
    sort_algorithms,
)


MEMORY_REQUIRED_PER_FILE_COLUMNS = {
    "relative_input_path",
    "algorithm",
    "repetition",
    "algorithm_to_uncompressed_peak_rss_kib",
    "uncompressed_to_algorithm_peak_rss_kib",
    "roundtrip_peak_rss_kib",
    "algorithm_to_uncompressed_elapsed_seconds",
    "uncompressed_to_algorithm_elapsed_seconds",
    "roundtrip_total_elapsed_seconds",
    "prepared_input_bytes",
    "uncompressed_output_bytes",
    "recompressed_output_bytes",
}
MEMORY_STAGE_LABELS = {
    "algorithm_to_uncompressed": "Decompression",
    "uncompressed_to_algorithm": "Compression",
}
MEMORY_STAGE_MARKERS = {
    "Compression": "o",
    "Decompression": "s",
}
MEMORY_STAGE_LINESTYLES = {
    "Compression": "--",
    "Decompression": "-",
}


def discover_memory_runs(results_root: Path) -> list[dict[str, object]]:
    discovered_runs = []
    for entry in discover_named_runs(results_root):
        run_dir = Path(entry["run_dir"]).resolve()
        manifest = load_run_manifest(run_dir)
        discovered_runs.append(
            {
                "run_id": run_dir.name,
                "run_dir": run_dir,
                "dataset": dataset_name_from_manifest(manifest),
                "manifest": manifest,
                "timestamp": manifest.get("timestamp", ""),
            }
        )

    latest_by_dataset = {}
    for run in sorted(discovered_runs, key=lambda item: (item["dataset"], item["run_id"])):
        latest_by_dataset[run["dataset"]] = run

    selected_runs = [latest_by_dataset[dataset] for dataset in sorted(latest_by_dataset)]
    if not selected_runs:
        raise FileNotFoundError(f"No memory runs found under {results_root}")
    return selected_runs


def load_memory_roundtrip_frame(run: dict[str, object]) -> pd.DataFrame:
    summary_path = Path(run["run_dir"]) / "summaries" / "roundtrip_per_file.csv"
    if not summary_path.is_file():
        raise FileNotFoundError(f"Missing memory summary file: {summary_path}")

    frame = pd.read_csv(summary_path)
    missing_columns = MEMORY_REQUIRED_PER_FILE_COLUMNS.difference(frame.columns)
    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(
            f"Memory summary file {summary_path} is missing columns: {missing_text}"
        )

    numeric_columns = [
        "repetition",
        "algorithm_to_uncompressed_peak_rss_kib",
        "uncompressed_to_algorithm_peak_rss_kib",
        "roundtrip_peak_rss_kib",
        "algorithm_to_uncompressed_elapsed_seconds",
        "uncompressed_to_algorithm_elapsed_seconds",
        "roundtrip_total_elapsed_seconds",
        "prepared_input_bytes",
        "uncompressed_output_bytes",
        "recompressed_output_bytes",
    ]
    frame[numeric_columns] = frame[numeric_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )
    if frame[numeric_columns].isna().any().any():
        bad_columns = [column for column in numeric_columns if frame[column].isna().any()]
        bad_text = ", ".join(bad_columns)
        raise ValueError(
            f"Memory summary file {summary_path} has non-numeric values in: {bad_text}"
        )

    frame["dataset"] = str(run["dataset"])
    frame["run_id"] = str(run["run_id"])
    frame["run_dir"] = str(run["run_dir"])
    frame["timestamp"] = str(run["timestamp"])
    frame["algorithm"] = frame["algorithm"].map(display_algorithm_name)
    frame["uncompressed_file_bytes"] = frame["uncompressed_output_bytes"]
    frame["uncompressed_file_size_mib"] = frame["uncompressed_file_bytes"] / (1024**2)
    frame["file_id"] = frame["dataset"] + "/" + frame["relative_input_path"].astype(str)
    return frame


def reshape_memory_points(roundtrip_df: pd.DataFrame) -> pd.DataFrame:
    stage_frames = []
    for stage_key, stage_label in MEMORY_STAGE_LABELS.items():
        peak_column = f"{stage_key}_peak_rss_kib"
        elapsed_column = f"{stage_key}_elapsed_seconds"
        stage_frame = roundtrip_df[
            [
                "dataset",
                "run_id",
                "run_dir",
                "timestamp",
                "file_id",
                "relative_input_path",
                "algorithm",
                "repetition",
                "uncompressed_file_bytes",
                "uncompressed_file_size_mib",
                peak_column,
                elapsed_column,
            ]
        ].copy()
        stage_frame = stage_frame.rename(
            columns={
                peak_column: "peak_rss_kib",
                elapsed_column: "elapsed_seconds",
            }
        )
        stage_frame["stage"] = stage_label
        stage_frames.append(stage_frame)

    memory_points_df = pd.concat(stage_frames, ignore_index=True)
    algorithm_order = sort_algorithms(memory_points_df["algorithm"].astype(str).tolist())
    memory_points_df["algorithm"] = pd.Categorical(
        memory_points_df["algorithm"],
        categories=algorithm_order,
        ordered=True,
    )
    memory_points_df["stage"] = pd.Categorical(
        memory_points_df["stage"],
        categories=list(MEMORY_STAGE_MARKERS),
        ordered=True,
    )
    memory_points_df["peak_rss_gib"] = memory_points_df["peak_rss_kib"] / (1024**2)
    memory_points_df["peak_rss_bytes"] = memory_points_df["peak_rss_kib"] * 1024.0
    memory_points_df["peak_rss_gb"] = memory_points_df["peak_rss_bytes"] / 1e9
    memory_points_df["uncompressed_file_size_gb"] = memory_points_df["uncompressed_file_bytes"] / 1e9
    memory_points_df["peak_rss_to_uncompressed_size_ratio"] = (
        memory_points_df["peak_rss_bytes"] / memory_points_df["uncompressed_file_bytes"]
    )
    return memory_points_df.sort_values(
        ["dataset", "relative_input_path", "algorithm", "stage"]
    ).reset_index(drop=True)


def build_memory_stage_summary(memory_points_df: pd.DataFrame) -> pd.DataFrame:
    return (
        memory_points_df.groupby(["algorithm", "stage"], observed=True)
        .agg(
            datasets=("dataset", "nunique"),
            files=("file_id", "nunique"),
            mean_uncompressed_file_size_mib=("uncompressed_file_size_mib", "mean"),
            median_uncompressed_file_size_mib=("uncompressed_file_size_mib", "median"),
            mean_peak_rss_gib=("peak_rss_gib", "mean"),
            median_peak_rss_gib=("peak_rss_gib", "median"),
            max_peak_rss_gib=("peak_rss_gib", "max"),
            mean_peak_rss_to_uncompressed_size_ratio=(
                "peak_rss_to_uncompressed_size_ratio",
                "mean",
            ),
            median_peak_rss_to_uncompressed_size_ratio=(
                "peak_rss_to_uncompressed_size_ratio",
                "median",
            ),
        )
        .reset_index()
    )


def build_memory_artifacts(
    results_root: Path,
    selected_runs: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    selected_runs = selected_runs or discover_memory_runs(results_root)
    loaded_runs = []
    for run in selected_runs:
        roundtrip_df = load_memory_roundtrip_frame(run)
        loaded_runs.append({**run, "roundtrip_df": roundtrip_df})

    roundtrip_df = pd.concat(
        [entry["roundtrip_df"] for entry in loaded_runs],
        ignore_index=True,
    )
    memory_points_df = reshape_memory_points(roundtrip_df)
    stage_summary_df = build_memory_stage_summary(memory_points_df)

    runs_df = pd.DataFrame(
        [
            {
                "dataset": entry["dataset"],
                "run_id": entry["run_id"],
                "timestamp": entry["timestamp"],
                "file_count": int(entry["roundtrip_df"]["file_id"].nunique()),
                "algorithm_count": int(
                    entry["roundtrip_df"]["algorithm"].astype(str).nunique()
                ),
                "algorithms": ", ".join(
                    sort_algorithms(
                        entry["roundtrip_df"]["algorithm"].astype(str).unique().tolist()
                    )
                ),
                "run_dir": str(entry["run_dir"]),
            }
            for entry in loaded_runs
        ]
    )

    return {
        "runs_df": runs_df,
        "roundtrip_df": roundtrip_df,
        "points_df": memory_points_df,
        "stage_summary_df": stage_summary_df,
    }


def plot_memory_peak_vs_file_size(
    memory_points_df: pd.DataFrame,
    *,
    export_enabled: bool = False,
    output_dir: Path | None = None,
    export_format: str = "png",
    include_titles: bool = True,
) -> None:
    plot_df = memory_points_df.copy()
    if plot_df.empty:
        raise RuntimeError("No memory benchmark points are available for plotting.")

    fig, ax = plt.subplots(figsize=(11.5, 7))
    sns.scatterplot(
        data=plot_df,
        x="uncompressed_file_size_gb",
        y="peak_rss_gb",
        hue="algorithm",
        style="stage",
        palette={
            algorithm: color_for_algorithm(algorithm)
            for algorithm in sort_algorithms(plot_df["algorithm"].astype(str).tolist())
        },
        markers=MEMORY_STAGE_MARKERS,
        s=90,
        alpha=0.85,
        edgecolor="white",
        linewidth=0.6,
        legend=False,
        ax=ax,
    )

    for algorithm in sort_algorithms(plot_df["algorithm"].astype(str).tolist()):
        for stage in MEMORY_STAGE_MARKERS:
            series_df = plot_df.loc[
                (plot_df["algorithm"].astype(str) == algorithm)
                & (plot_df["stage"].astype(str) == stage)
            ].sort_values("uncompressed_file_size_gb")
            if series_df.empty or len(series_df) < 2:
                continue
            x_log = np.log10(series_df["uncompressed_file_size_gb"].to_numpy())
            y_log = np.log10(series_df["peak_rss_gb"].to_numpy())
            slope, intercept = np.polyfit(x_log, y_log, 1)
            x_fit = np.linspace(x_log.min(), x_log.max(), 100)
            ax.plot(
                10**x_fit,
                10 ** (intercept + (slope * x_fit)),
                color=color_for_algorithm(algorithm),
                linestyle=MEMORY_STAGE_LINESTYLES[stage],
                linewidth=1.8,
                alpha=0.8,
            )

    ax.set_xscale("log")
    ax.set_yscale("log")
    _log_locator = mticker.LogLocator(base=10, subs=[1.0, 2.0, 5.0])
    _plain_formatter = mticker.FuncFormatter(lambda x, _: f"{x:g}")
    ax.xaxis.set_major_locator(_log_locator)
    ax.xaxis.set_major_formatter(_plain_formatter)
    ax.xaxis.set_minor_locator(mticker.NullLocator())
    ax.yaxis.set_major_locator(mticker.LogLocator(base=10, subs=[1.0, 2.0, 5.0]))
    ax.yaxis.set_major_formatter(_plain_formatter)
    ax.yaxis.set_minor_locator(mticker.NullLocator())
    ax.set_xlabel("Uncompressed file size (GB)")
    ax.set_ylabel("Peak RSS (GB)")
    ax.set_title("Peak memory usage vs uncompressed file size")
    ax.grid(which="both", linestyle="--", alpha=0.3)

    algorithm_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="",
            markerfacecolor=color_for_algorithm(algorithm),
            markeredgecolor="white",
            markeredgewidth=0.6,
            markersize=9,
            label=algorithm,
        )
        for algorithm in sort_algorithms(plot_df["algorithm"].astype(str).tolist())
    ]
    stage_handles = [
        Line2D(
            [0],
            [0],
            color="#444444",
            marker=MEMORY_STAGE_MARKERS[stage],
            linestyle=MEMORY_STAGE_LINESTYLES[stage],
            linewidth=1.8,
            markersize=8,
            label=stage,
        )
        for stage in MEMORY_STAGE_MARKERS
    ]
    first_legend = ax.legend(handles=algorithm_handles, title="Algorithm", loc="upper left")
    ax.add_artist(first_legend)
    ax.legend(handles=stage_handles, title="Stage", loc="lower right")

    plt.tight_layout()
    if output_dir is not None:
        maybe_export_figure(
            fig,
            "memory",
            "peak_rss_vs_file_size",
            export_enabled=export_enabled,
            output_dir=output_dir,
            export_format=export_format,
            include_titles=include_titles,
        )
    plt.show()