"""Speed analysis helpers extracted from the article notebook."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from scipy import stats

from .figures import (
    color_for_algorithm,
    light_color_for_algorithm,
    marker_for_algorithm,
    maybe_export_figure,
)
from .shared import (
    build_file_index_table,
    dataset_name_from_manifest,
    discover_named_runs,
    display_algorithm_name,
    load_run_manifest,
    normalize_requested_algorithms,
    resolve_available_algorithm,
    sort_algorithms,
)


@dataclass(frozen=True)
class MetricSpec:
    mode: str
    mean_column: str
    std_column: str
    axis_label: str
    title_suffix: str


SPEED_METRIC_SPECS = {
    "compression": MetricSpec(
        mode="compression",
        mean_column="compression_speed_mb_sec",
        std_column="StdDev_Compression_speed",
        axis_label="Compression speed (MB/s)",
        title_suffix="Compression",
    ),
    "decompression": MetricSpec(
        mode="decompression",
        mean_column="decompression_speed_mb_sec",
        std_column="StdDev_Decompression_speed",
        axis_label="Decompression speed (MB/s)",
        title_suffix="Decompression",
    ),
}
SPEED_REQUIRED_SUMMARY_COLUMNS = {
    "File",
    "compressed_bytes",
    "bits_per_sample",
    "is_correct",
    "compression_speed_mb_sec",
    "decompression_speed_mb_sec",
    "StdDev_Compression_speed",
    "StdDev_Decompression_speed",
}
SPEED_FRAME_REQUIRED_COLUMNS = {"algorithm", *SPEED_REQUIRED_SUMMARY_COLUMNS}

TRADEOFF_ANNOTATION_LABELS = {
    "EX-ZD-ZSTD": "EX-ZD",
}


def configure_speed_runs(
    results_root: Path,
    machine_labels: dict[str, str] | None = None,
    denylist: list[str] | None = None,
) -> list[dict[str, Path | str]]:
    discovered_runs = discover_named_runs(results_root, denylist=denylist or [])
    available_runs = {
        entry["label"]: Path(entry["run_dir"]).resolve() for entry in discovered_runs
    }

    if not machine_labels:
        return [
            {
                "machine_name": entry["label"],
                "label": entry["label"],
                "run_dir": Path(entry["run_dir"]).resolve(),
            }
            for entry in discovered_runs
        ]

    missing_machines = [
        machine_name
        for machine_name in machine_labels
        if machine_name not in available_runs
    ]
    if missing_machines:
        missing_text = ", ".join(missing_machines)
        available_text = ", ".join(sorted(available_runs))
        raise ValueError(
            f"Unknown speed machine names: {missing_text}. Available runs: {available_text}"
        )

    display_names = list(machine_labels.values())
    duplicate_display_names = sorted(
        display_name
        for display_name in set(display_names)
        if display_names.count(display_name) > 1
    )
    if duplicate_display_names:
        duplicates_text = ", ".join(duplicate_display_names)
        raise ValueError(
            f"Speed machine display names must be unique. Duplicates: {duplicates_text}"
        )

    return [
        {
            "machine_name": machine_name,
            "label": display_label,
            "run_dir": available_runs[machine_name],
        }
        for machine_name, display_label in machine_labels.items()
    ]


def selected_speed_algorithms(
    runs: list[dict], requested_algorithms: list[str] | None = None
) -> list[str]:
    if requested_algorithms is not None:
        return normalize_requested_algorithms(requested_algorithms)

    discovered = []
    for entry in runs:
        manifest = load_run_manifest(Path(entry["run_dir"]).resolve())
        discovered.extend(manifest.get("algorithms", []))
    return normalize_requested_algorithms(discovered)


def summary_path_for_speed_algorithm(
    run_dir: Path, manifest: dict, algorithm: str
) -> tuple[Path, str]:
    dataset_name = dataset_name_from_manifest(manifest)
    available_algorithms = set(manifest.get("algorithms", []))
    resolved_algorithm = resolve_available_algorithm(algorithm, available_algorithms)
    summary_path = (
        Path(run_dir) / "summaries" / resolved_algorithm / f"{dataset_name}.csv"
    )
    if not summary_path.is_file():
        raise FileNotFoundError(
            f"Missing summary for algorithm '{algorithm}' (resolved id '{resolved_algorithm}'): {summary_path}"
        )
    return summary_path, resolved_algorithm


def normalize_speed_summary_frame(
    summary_df: pd.DataFrame,
    *,
    machine: str,
    run_dir: Path,
    run_id: str,
    dataset_name: str,
    algorithm: str,
    resolved_algorithm: str,
    summary_path: Path,
    metric_specs: dict[str, MetricSpec] | None = None,
) -> pd.DataFrame:
    metric_specs = metric_specs or SPEED_METRIC_SPECS
    missing_columns = SPEED_REQUIRED_SUMMARY_COLUMNS.difference(summary_df.columns)
    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(
            f"Summary file {summary_path} is missing columns: {missing_text}"
        )

    normalized_frames = []
    display_name = display_algorithm_name(algorithm)
    for mode, spec in metric_specs.items():
        frame = summary_df.copy()
        frame["machine"] = machine
        frame["run_label"] = machine
        frame["run_dir"] = str(run_dir)
        frame["run_id"] = run_id
        frame["dataset_name"] = dataset_name
        frame["algorithm"] = display_name
        frame["resolved_algorithm"] = resolved_algorithm
        frame["metric_mode"] = mode
        frame["speed_mean"] = pd.to_numeric(frame[spec.mean_column], errors="coerce")
        frame["speed_std"] = pd.to_numeric(frame[spec.std_column], errors="coerce")
        frame["source_summary_path"] = str(summary_path)
        normalized_frames.append(frame)

    return pd.concat(normalized_frames, ignore_index=True)


def load_speed_comparison_table(
    runs: list[dict],
    algorithms: list[str],
    metric_specs: dict[str, MetricSpec] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    metric_specs = metric_specs or SPEED_METRIC_SPECS
    frames = []
    metadata_rows = []
    machine_order = [entry["label"] for entry in runs]

    for entry in runs:
        machine = entry["label"]
        run_dir = Path(entry["run_dir"]).resolve()
        manifest = load_run_manifest(run_dir)
        available_algorithms = set(manifest.get("algorithms", []))
        dataset_name = dataset_name_from_manifest(manifest)
        run_id = run_dir.name

        for algorithm in algorithms:
            resolved_algorithm = resolve_available_algorithm(
                algorithm, available_algorithms
            )
            if resolved_algorithm not in available_algorithms:
                available_text = ", ".join(
                    display_algorithm_name(name)
                    for name in manifest.get("algorithms", [])
                )
                raise ValueError(
                    f"Algorithm '{algorithm}' is not present in machine '{machine}' ({run_dir}). "
                    f"Available algorithms: {available_text}"
                )

            summary_path, resolved_algorithm = summary_path_for_speed_algorithm(
                run_dir, manifest, algorithm
            )
            summary_df = pd.read_csv(summary_path)
            frames.append(
                normalize_speed_summary_frame(
                    summary_df,
                    machine=machine,
                    run_dir=run_dir,
                    run_id=run_id,
                    dataset_name=dataset_name,
                    algorithm=algorithm,
                    resolved_algorithm=resolved_algorithm,
                    summary_path=summary_path,
                    metric_specs=metric_specs,
                )
            )

        metadata_rows.append(
            {
                "machine": machine,
                "run_dir": str(run_dir),
                "run_id": run_id,
                "dataset_name": dataset_name,
                "available_algorithms": ", ".join(
                    display_algorithm_name(name)
                    for name in manifest.get("algorithms", [])
                ),
                "algorithm_token": manifest.get("algorithm_token", ""),
                "timestamp": manifest.get("timestamp"),
            }
        )

    if not frames:
        raise ValueError(
            "No speed summary tables were loaded. Check the notebook configuration."
        )

    comparison_df = pd.concat(frames, ignore_index=True)
    comparison_df["machine"] = pd.Categorical(
        comparison_df["machine"],
        categories=machine_order,
        ordered=True,
    )
    comparison_df["run_label"] = comparison_df["machine"]
    comparison_df = comparison_df.sort_values(
        ["machine", "metric_mode", "algorithm", "File"]
    ).reset_index(drop=True)

    metadata_df = pd.DataFrame(metadata_rows)
    metadata_df["machine"] = pd.Categorical(
        metadata_df["machine"],
        categories=machine_order,
        ordered=True,
    )
    metadata_df = metadata_df.sort_values("machine").reset_index(drop=True)
    return comparison_df, metadata_df


def _finalize_speed_artifacts(
    comparison_df: pd.DataFrame,
    *,
    algorithms: list[str],
    machine_order: list[str],
    metric_specs: dict[str, MetricSpec] | None = None,
    metadata_df: pd.DataFrame | None = None,
) -> dict[str, object]:
    metric_specs = metric_specs or SPEED_METRIC_SPECS
    metric_modes = list(metric_specs)

    comparison_df = comparison_df.copy()
    comparison_df["machine"] = pd.Categorical(
        comparison_df["machine"],
        categories=machine_order,
        ordered=True,
    )
    comparison_df["run_label"] = comparison_df["machine"]
    comparison_df = comparison_df.sort_values(
        ["machine", "metric_mode", "algorithm", "File"]
    ).reset_index(drop=True)

    if metadata_df is None:
        metadata_df = pd.DataFrame()
    else:
        metadata_df = metadata_df.copy()
        if not metadata_df.empty and "machine" in metadata_df.columns:
            metadata_df["machine"] = pd.Categorical(
                metadata_df["machine"],
                categories=machine_order,
                ordered=True,
            )
            metadata_df = metadata_df.sort_values("machine").reset_index(drop=True)

    coverage_df = summarize_speed_file_coverage(comparison_df)
    within_machine_intersection_df = compute_speed_intersection_report(
        comparison_df, algorithms
    )
    cross_machine_intersection_df = compute_speed_cross_machine_intersection_report(
        comparison_df
    )
    correctness_failures_df = validate_speed_correctness(comparison_df)
    file_index_df = build_file_index_table(
        comparison_df.loc[comparison_df["metric_mode"] == metric_modes[0]]
    )
    pairwise_tests = pd.concat(
        [
            pairwise_ttest_table(comparison_df, metric_mode, algorithms)
            for metric_mode in metric_modes
        ],
        ignore_index=True,
    )
    return {
        "algorithms": algorithms,
        "metric_modes": metric_modes,
        "machine_order": machine_order,
        "comparison_df": comparison_df,
        "metadata_df": metadata_df,
        "coverage_df": coverage_df,
        "within_machine_intersection_df": within_machine_intersection_df,
        "cross_machine_intersection_df": cross_machine_intersection_df,
        "correctness_failures_df": correctness_failures_df,
        "file_index_df": file_index_df,
        "pairwise_tests": pairwise_tests,
    }


def build_speed_artifacts_from_frames(
    summary_df: pd.DataFrame,
    *,
    machine: str,
    requested_algorithms: list[str] | None = None,
    metric_specs: dict[str, MetricSpec] | None = None,
    run_dir: Path | None = None,
    run_id: str | None = None,
    dataset_name: str | None = None,
) -> dict[str, object]:
    metric_specs = metric_specs or SPEED_METRIC_SPECS
    missing_columns = SPEED_FRAME_REQUIRED_COLUMNS.difference(summary_df.columns)
    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(
            f"In-memory speed summaries are missing columns: {missing_text}"
        )

    frame = summary_df.copy()
    frame["algorithm"] = frame["algorithm"].map(display_algorithm_name)
    available_algorithms = sort_algorithms(frame["algorithm"].dropna().tolist())
    algorithms = (
        normalize_requested_algorithms(requested_algorithms)
        if requested_algorithms is not None
        else available_algorithms
    )
    missing_algorithms = [
        algorithm for algorithm in algorithms if algorithm not in available_algorithms
    ]
    if missing_algorithms:
        missing_text = ", ".join(missing_algorithms)
        available_text = ", ".join(available_algorithms)
        raise ValueError(
            f"Requested algorithms are not present in the in-memory speed summaries: {missing_text}. "
            f"Available algorithms: {available_text}"
        )

    frame = frame.loc[frame["algorithm"].isin(algorithms)].copy()
    if frame.empty:
        raise ValueError("No speed rows remain after filtering algorithms.")

    resolved_run_dir = (
        Path(run_dir).expanduser().resolve() if run_dir is not None else None
    )
    resolved_run_id = run_id or (
        resolved_run_dir.name if resolved_run_dir is not None else ""
    )
    resolved_dataset_name = dataset_name or ""

    normalized_frames = []
    for mode, spec in metric_specs.items():
        normalized = frame.copy()
        normalized["machine"] = machine
        normalized["run_label"] = machine
        normalized["run_dir"] = str(resolved_run_dir) if resolved_run_dir is not None else ""
        normalized["run_id"] = resolved_run_id
        normalized["dataset_name"] = resolved_dataset_name
        normalized["resolved_algorithm"] = normalized["algorithm"]
        normalized["metric_mode"] = mode
        normalized["speed_mean"] = pd.to_numeric(
            normalized[spec.mean_column], errors="coerce"
        )
        normalized["speed_std"] = pd.to_numeric(
            normalized[spec.std_column], errors="coerce"
        )
        if "source_summary_path" not in normalized.columns:
            normalized["source_summary_path"] = ""
        normalized_frames.append(normalized)

    comparison_df = pd.concat(normalized_frames, ignore_index=True)
    metadata_df = pd.DataFrame(
        [
            {
                "machine": machine,
                "run_dir": str(resolved_run_dir) if resolved_run_dir is not None else "",
                "run_id": resolved_run_id,
                "dataset_name": resolved_dataset_name,
                "available_algorithms": ", ".join(available_algorithms),
                "algorithm_token": "",
                "timestamp": "",
            }
        ]
    )
    return _finalize_speed_artifacts(
        comparison_df,
        algorithms=algorithms,
        machine_order=[machine],
        metric_specs=metric_specs,
        metadata_df=metadata_df,
    )


def summarize_speed_file_coverage(comparison_df: pd.DataFrame) -> pd.DataFrame:
    return (
        comparison_df.groupby(
            ["machine", "algorithm", "metric_mode"], dropna=False, observed=True
        )["File"]
        .nunique()
        .rename("num_files")
        .reset_index()
        .sort_values(["metric_mode", "machine", "algorithm"])
        .reset_index(drop=True)
    )


def compute_speed_intersection_report(
    comparison_df: pd.DataFrame, algorithms: list[str]
) -> pd.DataFrame:
    rows = []
    grouped = comparison_df.groupby(
        ["machine", "metric_mode"], dropna=False, observed=True
    )
    for (machine, metric_mode), frame in grouped:
        file_sets = [
            set(frame.loc[frame["algorithm"] == algorithm, "File"])
            for algorithm in algorithms
            if algorithm in frame["algorithm"].tolist()
        ]
        if not file_sets:
            continue
        intersection = set.intersection(*file_sets)
        union = set.union(*file_sets)
        rows.append(
            {
                "machine": machine,
                "metric_mode": metric_mode,
                "common_files": len(intersection),
                "all_files": len(union),
                "dropped_files": len(union - intersection),
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values(["metric_mode", "machine"])
        .reset_index(drop=True)
    )


def compute_speed_cross_machine_intersection_report(
    comparison_df: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for metric_mode, metric_frame in comparison_df.groupby(
        "metric_mode", observed=True
    ):
        for algorithm, algorithm_frame in metric_frame.groupby(
            "algorithm", observed=True
        ):
            file_sets = [
                set(machine_frame["File"])
                for _, machine_frame in algorithm_frame.groupby(
                    "machine", observed=True
                )
            ]
            if not file_sets:
                continue
            intersection = set.intersection(*file_sets)
            union = set.union(*file_sets)
            rows.append(
                {
                    "metric_mode": metric_mode,
                    "algorithm": algorithm,
                    "common_files": len(intersection),
                    "all_files": len(union),
                    "dropped_files": len(union - intersection),
                }
            )

        combined_sets = [
            set(frame["File"])
            for _, frame in metric_frame.groupby(
                ["machine", "algorithm"], observed=True
            )
        ]
        if combined_sets:
            global_intersection = set.intersection(*combined_sets)
            global_union = set.union(*combined_sets)
            rows.append(
                {
                    "metric_mode": metric_mode,
                    "algorithm": "ALL_SELECTED",
                    "common_files": len(global_intersection),
                    "all_files": len(global_union),
                    "dropped_files": len(global_union - global_intersection),
                }
            )

    return (
        pd.DataFrame(rows)
        .sort_values(["metric_mode", "algorithm"])
        .reset_index(drop=True)
    )


def validate_speed_correctness(comparison_df: pd.DataFrame) -> pd.DataFrame:
    failures = comparison_df.loc[
        comparison_df["is_correct"] < 1.0,
        ["machine", "algorithm", "metric_mode", "File", "is_correct"],
    ]
    return failures.sort_values(
        ["machine", "algorithm", "metric_mode", "File"]
    ).reset_index(drop=True)


def pivot_metric_matrix(frame: pd.DataFrame, algorithms: list[str]) -> pd.DataFrame:
    return (
        frame.pivot_table(
            index="File", columns="algorithm", values="speed_mean", aggfunc="first"
        )
        .reindex(columns=algorithms)
        .dropna(how="any")
    )


def holm_adjust_pvalues(p_values: np.ndarray) -> np.ndarray:
    if len(p_values) == 0:
        return np.array([], dtype=float)

    p_values = np.asarray(p_values, dtype=float)
    order = np.argsort(p_values)
    adjusted_sorted = np.empty(len(p_values), dtype=float)
    running_max = 0.0
    total = len(p_values)

    for position, index in enumerate(order):
        scaled_value = (total - position) * p_values[index]
        running_max = max(running_max, scaled_value)
        adjusted_sorted[position] = min(running_max, 1.0)

    adjusted = np.empty(len(p_values), dtype=float)
    adjusted[order] = adjusted_sorted
    return adjusted


def pairwise_ttest_table(
    comparison_df: pd.DataFrame, metric_mode: str, algorithms: list[str]
) -> pd.DataFrame:
    rows = []
    metric_frame = comparison_df.loc[comparison_df["metric_mode"] == metric_mode].copy()

    for machine, frame in metric_frame.groupby("machine", observed=True):
        matrix = pivot_metric_matrix(frame, algorithms)
        if matrix.empty:
            continue

        for algorithm_a, algorithm_b in combinations(algorithms, 2):
            if not {algorithm_a, algorithm_b}.issubset(matrix.columns):
                continue
            aligned = matrix[[algorithm_a, algorithm_b]].dropna()
            if len(aligned) < 2:
                continue

            t_stat, p_value = stats.ttest_rel(
                aligned[algorithm_a], aligned[algorithm_b]
            )
            mean_a = aligned[algorithm_a].mean()
            mean_b = aligned[algorithm_b].mean()
            if mean_a > mean_b:
                faster_algorithm = algorithm_a
            elif mean_b > mean_a:
                faster_algorithm = algorithm_b
            else:
                faster_algorithm = "tie"

            rows.append(
                {
                    "machine": machine,
                    "metric_mode": metric_mode,
                    "algorithm_a": algorithm_a,
                    "algorithm_b": algorithm_b,
                    "paired_rows": len(aligned),
                    "mean_a": mean_a,
                    "mean_b": mean_b,
                    "t_stat": t_stat,
                    "p_value": p_value,
                    "faster_algorithm": faster_algorithm,
                    "speed_advantage_mb_sec": abs(mean_a - mean_b),
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "machine",
                "metric_mode",
                "algorithm_a",
                "algorithm_b",
                "paired_rows",
                "mean_a",
                "mean_b",
                "t_stat",
                "p_value",
                "p_value_holm",
                "significant_holm",
                "faster_algorithm",
                "speed_advantage_mb_sec",
            ]
        )

    result = (
        pd.DataFrame(rows)
        .sort_values(
            ["machine", "metric_mode", "p_value", "algorithm_a", "algorithm_b"]
        )
        .reset_index(drop=True)
    )
    result["p_value_holm"] = np.nan

    for (_, _), group in result.groupby(["machine", "metric_mode"], observed=True):
        adjusted = holm_adjust_pvalues(group["p_value"].to_numpy())
        result.loc[group.index, "p_value_holm"] = adjusted

    result["significant_holm"] = result["p_value_holm"] < 0.05
    return result


def summarize_machine_metric(
    comparison_df: pd.DataFrame, metric_mode: str
) -> pd.DataFrame:
    frame = comparison_df.loc[comparison_df["metric_mode"] == metric_mode].copy()
    if frame.empty:
        return pd.DataFrame()

    return (
        frame.groupby(["machine", "algorithm"], dropna=False, observed=True)
        .agg(
            Mean=("speed_mean", "mean"),
            Std=("speed_mean", "std"),
            Median=("speed_mean", "median"),
            IQR=(
                "speed_mean",
                lambda values: values.quantile(0.75) - values.quantile(0.25),
            ),
            Min=("speed_mean", "min"),
            Max=("speed_mean", "max"),
            Count=("speed_mean", "count"),
        )
        .reset_index()
        .sort_values(["machine", "algorithm"])
        .reset_index(drop=True)
    )


def build_tradeoff_summary(comparison_df: pd.DataFrame) -> pd.DataFrame:
    compression_frame = comparison_df.loc[
        comparison_df["metric_mode"] == "compression"
    ].copy()
    if compression_frame.empty:
        return pd.DataFrame()

    return (
        compression_frame.groupby(["machine", "algorithm"], dropna=False, observed=True)
        .agg(
            avg_bits_per_sample=("bits_per_sample", "mean"),
            avg_compression_speed=("compression_speed_mb_sec", "mean"),
            avg_decompression_speed=("decompression_speed_mb_sec", "mean"),
        )
        .reset_index()
        .sort_values(["machine", "avg_bits_per_sample", "algorithm"])
        .reset_index(drop=True)
    )


def plot_machine_metric_comparison(
    comparison_df: pd.DataFrame,
    machine: str,
    metric_mode: str,
    algorithms: list[str],
    *,
    export_enabled: bool = False,
    output_dir: Path | None = None,
    export_format: str = "png",
    include_titles: bool = True,
) -> pd.DataFrame:
    spec = SPEED_METRIC_SPECS[metric_mode]
    frame = comparison_df[
        (comparison_df["machine"] == machine)
        & (comparison_df["metric_mode"] == metric_mode)
    ].copy()
    if frame.empty:
        print(f"No data available for machine '{machine}' and metric '{metric_mode}'.")
        return pd.DataFrame()

    file_order = build_file_index_table(frame)["File"].tolist()
    positions = np.arange(len(file_order))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle(
        f"Machine {machine}: {spec.title_suffix} speed comparison",
        fontsize=16,
        fontweight="bold",
    )

    for algorithm in algorithms:
        algorithm_frame = (
            frame.loc[frame["algorithm"] == algorithm]
            .set_index("File")
            .reindex(file_order)
            .reset_index()
        )
        ax1.errorbar(
            positions,
            algorithm_frame["speed_mean"],
            yerr=algorithm_frame["speed_std"],
            fmt=f"{marker_for_algorithm(algorithm)}-",
            label=algorithm,
            alpha=0.8,
            capsize=3,
            markersize=5,
            color=color_for_algorithm(algorithm),
        )

    ax1.set_title("Speed comparison with standard deviation")
    ax1.set_xlabel("Test file number")
    ax1.set_ylabel(spec.axis_label)
    ax1.set_xticks(positions)
    ax1.set_xticklabels(range(1, len(file_order) + 1))
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    aggregate = (
        frame.groupby("algorithm", dropna=False, observed=True)["speed_mean"]
        .agg(Mean="mean", Std="std")
        .reindex(algorithms)
        .reset_index()
    )
    bars = ax2.bar(
        aggregate["algorithm"],
        aggregate["Mean"],
        yerr=aggregate["Std"].fillna(0.0),
        capsize=10,
        alpha=0.75,
        color=[color_for_algorithm(algorithm) for algorithm in aggregate["algorithm"]],
    )
    ax2.set_title("Average speed with error bars")
    ax2.set_ylabel("Average speed (MB/s)")
    ax2.grid(True, alpha=0.3)

    ymax = (
        (aggregate["Mean"] + aggregate["Std"].fillna(0.0)).max()
        if not aggregate.empty
        else 0.0
    )
    for bar, mean_value, std_value in zip(
        bars,
        aggregate["Mean"],
        aggregate["Std"].fillna(0.0),
    ):
        ax2.text(
            bar.get_x() + bar.get_width() / 2.0,
            mean_value + std_value + max(5.0, 0.02 * ymax),
            f"{mean_value:.1f}±{std_value:.1f}",
            ha="center",
            va="bottom",
            fontweight="bold",
        )

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    if output_dir is not None:
        maybe_export_figure(
            fig,
            "speed",
            f"{machine}_{metric_mode}_comparison",
            export_enabled=export_enabled,
            output_dir=output_dir,
            export_format=export_format,
            include_titles=include_titles,
        )
    plt.show()
    return aggregate


def plot_distribution_analysis(
    comparison_df: pd.DataFrame,
    machine: str,
    metric_mode: str,
    algorithms: list[str],
    *,
    export_enabled: bool = False,
    output_dir: Path | None = None,
    export_format: str = "png",
    include_titles: bool = True,
) -> None:
    spec = SPEED_METRIC_SPECS[metric_mode]
    frame = comparison_df[
        (comparison_df["machine"] == machine)
        & (comparison_df["metric_mode"] == metric_mode)
    ].copy()
    if frame.empty:
        print(f"No data available for machine '{machine}' and metric '{metric_mode}'.")
        return

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(
        f"Machine {machine}: {spec.title_suffix} distribution analysis",
        fontsize=16,
        fontweight="bold",
    )
    ax1, ax2, ax3, ax4 = axes.ravel()

    box_data = []
    for algorithm in algorithms:
        algorithm_frame = frame.loc[frame["algorithm"] == algorithm, "speed_mean"]
        box_data.append(algorithm_frame)
        ax1.hist(
            algorithm_frame,
            bins=10,
            alpha=0.6,
            label=algorithm,
            color=color_for_algorithm(algorithm),
            density=True,
        )
    ax1.set_xlabel(spec.axis_label)
    ax1.set_ylabel("Density")
    ax1.set_title("Speed distribution histograms")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    bp = ax2.boxplot(box_data, labels=algorithms, patch_artist=True)
    for patch, algorithm in zip(bp["boxes"], algorithms):
        patch.set_facecolor(light_color_for_algorithm(algorithm))
    ax2.set_ylabel(spec.axis_label)
    ax2.set_title("Box plot comparison")
    ax2.grid(True, alpha=0.3)

    vp = ax3.violinplot(
        box_data,
        positions=np.arange(1, len(algorithms) + 1),
        showmeans=True,
        showmedians=True,
    )
    for body, algorithm in zip(vp["bodies"], algorithms):
        body.set_facecolor(light_color_for_algorithm(algorithm))
        body.set_edgecolor(color_for_algorithm(algorithm))
        body.set_alpha(0.8)
    ax3.set_xticks(np.arange(1, len(algorithms) + 1))
    ax3.set_xticklabels(algorithms)
    ax3.set_ylabel(spec.axis_label)
    ax3.set_title("Violin plot distribution")
    ax3.grid(True, alpha=0.3)

    matrix = pivot_metric_matrix(frame, algorithms)
    if matrix.empty:
        ax4.text(
            0.5,
            0.5,
            "Not enough aligned files for correlation.",
            ha="center",
            va="center",
        )
        ax4.set_axis_off()
    else:
        correlation = matrix.corr().reindex(index=algorithms, columns=algorithms)
        plot_matrix = correlation.fillna(0.0)
        image = ax4.imshow(plot_matrix, cmap="coolwarm", vmin=-1.0, vmax=1.0)
        ax4.set_xticks(range(len(algorithms)))
        ax4.set_yticks(range(len(algorithms)))
        ax4.set_xticklabels(algorithms, rotation=45, ha="right")
        ax4.set_yticklabels(algorithms)
        ax4.set_title("Algorithm speed correlation")
        for row_index in range(len(algorithms)):
            for column_index in range(len(algorithms)):
                ax4.text(
                    column_index,
                    row_index,
                    f"{plot_matrix.iloc[row_index, column_index]:.2f}",
                    ha="center",
                    va="center",
                )
        fig.colorbar(image, ax=ax4, fraction=0.046, pad=0.04)
        ax4.grid(False)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    if output_dir is not None:
        maybe_export_figure(
            fig,
            "speed",
            f"{machine}_{metric_mode}_distribution",
            export_enabled=export_enabled,
            output_dir=output_dir,
            export_format=export_format,
            include_titles=include_titles,
        )
    plt.show()


def plot_cross_machine_comparison(
    comparison_df: pd.DataFrame,
    metric_mode: str,
    algorithms: list[str],
    machine_order: list[str],
    *,
    export_enabled: bool = False,
    output_dir: Path | None = None,
    export_format: str = "png",
    include_titles: bool = True,
) -> pd.DataFrame:
    spec = SPEED_METRIC_SPECS[metric_mode]
    summary_table = summarize_machine_metric(comparison_df, metric_mode)
    if summary_table.empty:
        print(f"No data available for metric '{metric_mode}'.")
        return pd.DataFrame()

    summary_table = (
        summary_table.set_index(["machine", "algorithm"])
        .reindex(
            pd.MultiIndex.from_product(
                [machine_order, algorithms], names=["machine", "algorithm"]
            )
        )
        .reset_index()
    )
    summary_table["Metric"] = metric_mode

    fig_width = max(9, 3 * len(machine_order) + 4)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(fig_width, 11))

    x = np.arange(len(machine_order))
    width = 0.8 / max(len(algorithms), 1)
    centered_offsets = (
        np.linspace(
            -(len(algorithms) - 1) / 2, (len(algorithms) - 1) / 2, len(algorithms)
        )
        * width
    )

    for offset, algorithm in zip(centered_offsets, algorithms):
        algorithm_summary = (
            summary_table.loc[summary_table["algorithm"] == algorithm]
            .set_index("machine")
            .reindex(machine_order)
            .reset_index()
        )
        bars = ax1.bar(
            x + offset,
            algorithm_summary["Mean"],
            width,
            yerr=algorithm_summary["Std"].fillna(0.0),
            label=algorithm,
            alpha=0.8,
            capsize=5,
            color=color_for_algorithm(algorithm),
        )
        for bar, mean_value, std_value in zip(
            bars,
            algorithm_summary["Mean"].fillna(0.0),
            algorithm_summary["Std"].fillna(0.0),
        ):
            ax1.text(
                bar.get_x() + bar.get_width() / 2.0,
                mean_value + std_value + 5,
                f"{mean_value:.0f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    ax1.set_title(f"Average {spec.title_suffix.lower()} speed by machine")
    ax1.set_ylabel("Average speed (MB/s)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(machine_order)
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    all_data = []
    all_labels = []
    for machine in machine_order:
        machine_frame = comparison_df[
            (comparison_df["machine"] == machine)
            & (comparison_df["metric_mode"] == metric_mode)
        ]
        for algorithm in algorithms:
            algorithm_values = machine_frame.loc[
                machine_frame["algorithm"] == algorithm, "speed_mean"
            ]
            all_data.append(algorithm_values)
            all_labels.append(f"{algorithm}\n{machine}")

    bp = ax2.boxplot(all_data, labels=all_labels, patch_artist=True)
    for patch, label in zip(bp["boxes"], all_labels):
        algorithm = label.split("\n", 1)[0]
        patch.set_facecolor(light_color_for_algorithm(algorithm))
    ax2.set_title(f"{spec.title_suffix} speed distribution by machine")
    ax2.set_ylabel("Speed (MB/s)")
    ax2.tick_params(axis="x", rotation=45)
    ax2.grid(True, alpha=0.3)

    legend_elements = [
        Rectangle(
            (0, 0),
            1,
            1,
            facecolor=light_color_for_algorithm(algorithm),
            label=algorithm,
        )
        for algorithm in algorithms
    ]
    ax2.legend(handles=legend_elements, loc="upper right")

    plt.tight_layout()
    if output_dir is not None:
        maybe_export_figure(
            fig,
            "speed",
            f"cross_machine_{metric_mode}",
            export_enabled=export_enabled,
            output_dir=output_dir,
            export_format=export_format,
            include_titles=include_titles,
        )
    plt.show()
    return summary_table


def plot_combined_speed_comparison(
    comparison_df: pd.DataFrame,
    algorithms: list[str],
    machine_order: list[str],
    *,
    export_enabled: bool = False,
    output_dir: Path | None = None,
    export_format: str = "png",
    include_titles: bool = True,
) -> None:
    """Two-panel bar chart: compression speed on top, decompression on bottom.

    Machine names appear once (on the bottom panel) and the algorithm legend
    appears once (as a figure-level legend).
    """

    def _reindex_summary(metric_mode: str) -> pd.DataFrame:
        tbl = summarize_machine_metric(comparison_df, metric_mode)
        if tbl.empty:
            return tbl
        return (
            tbl.set_index(["machine", "algorithm"])
            .reindex(
                pd.MultiIndex.from_product(
                    [machine_order, algorithms], names=["machine", "algorithm"]
                )
            )
            .reset_index()
        )

    comp_summary = _reindex_summary("compression")
    decomp_summary = _reindex_summary("decompression")

    if comp_summary.empty and decomp_summary.empty:
        print("No data available for combined speed comparison.")
        return

    # Narrow figure: width constrained so the y-label text fills most of it.
    fig_width = 7.0
    fig, (ax_comp, ax_decomp) = plt.subplots(
        2, 1, sharex=True, figsize=(fig_width, 3.5)
    )

    x = np.arange(len(machine_order))
    width = 0.8 / max(len(algorithms), 1)
    centered_offsets = (
        np.linspace(
            -(len(algorithms) - 1) / 2, (len(algorithms) - 1) / 2, len(algorithms)
        )
        * width
    )

    legend_handles: list = []

    def _draw_bars(ax: plt.Axes, summary: pd.DataFrame, collect_legend: bool) -> None:
        for offset, algorithm in zip(centered_offsets, algorithms):
            algorithm_summary = (
                summary.loc[summary["algorithm"] == algorithm]
                .set_index("machine")
                .reindex(machine_order)
                .reset_index()
            )
            bars = ax.bar(
                x + offset,
                algorithm_summary["Mean"],
                width,
                yerr=algorithm_summary["Std"].fillna(0.0),
                label=algorithm,
                alpha=0.8,
                capsize=3,
                color=color_for_algorithm(algorithm),
            )
            for bar, mean_value, std_value in zip(
                bars,
                algorithm_summary["Mean"].fillna(0.0),
                algorithm_summary["Std"].fillna(0.0),
            ):
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    mean_value + std_value + 5,
                    f"{mean_value:.0f}",
                    ha="center",
                    va="bottom",
                    fontsize=6,
                )
            if collect_legend:
                legend_handles.append(
                    Rectangle(
                        (0, 0),
                        1,
                        1,
                        facecolor=color_for_algorithm(algorithm),
                        alpha=0.8,
                        label=algorithm,
                    )
                )

    _draw_bars(ax_comp, comp_summary, collect_legend=True)
    _draw_bars(ax_decomp, decomp_summary, collect_legend=False)

    comp_spec = SPEED_METRIC_SPECS["compression"]
    decomp_spec = SPEED_METRIC_SPECS["decompression"]

    if include_titles:
        ax_comp.set_title(
            f"Average {comp_spec.title_suffix.lower()} speed by machine", fontsize=8
        )
        ax_decomp.set_title(
            f"Average {decomp_spec.title_suffix.lower()} speed by machine", fontsize=8
        )

    ax_comp.set_ylabel("Compression speed (MB/s)", fontsize=7)
    ax_decomp.set_ylabel("Decompression speed (MB/s)", fontsize=7)
    ax_comp.tick_params(axis="both", labelsize=6)
    ax_decomp.tick_params(axis="both", labelsize=6)
    ax_comp.grid(True, alpha=0.3)
    ax_decomp.grid(True, alpha=0.3)

    # Show machine names on top of the upper panel, hide them on the bottom.
    ax_comp.set_xticks(x)
    ax_comp.set_xticklabels(machine_order, fontsize=7)
    ax_comp.tick_params(
        axis="x", top=True, labeltop=True, bottom=False, labelbottom=False
    )
    ax_decomp.tick_params(
        axis="x", top=False, labeltop=False, bottom=False, labelbottom=False
    )

    ax_comp.text(
        0.01,
        0.97,
        "(a)",
        transform=ax_comp.transAxes,
        fontsize=7,
        fontweight="bold",
        va="top",
    )
    ax_decomp.text(
        0.01,
        0.97,
        "(b)",
        transform=ax_decomp.transAxes,
        fontsize=7,
        fontweight="bold",
        va="top",
    )

    ax_comp.legend(
        handles=legend_handles,
        loc="upper center",
        fontsize=7,
        frameon=True,
        framealpha=0.8,
    )

    plt.tight_layout(h_pad=0.5)
    if output_dir is not None:
        maybe_export_figure(
            fig,
            "speed",
            "cross_machine_combined",
            export_enabled=export_enabled,
            output_dir=output_dir,
            export_format=export_format,
            include_titles=include_titles,
        )
    plt.show()


def build_machine_rankings(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return pd.DataFrame()

    ranking_df = summary_df.copy()
    ranking_df["rank_within_machine"] = ranking_df.groupby("machine", observed=True)[
        "Mean"
    ].rank(
        ascending=False,
        method="dense",
    )
    return ranking_df.sort_values(
        ["machine", "rank_within_machine", "algorithm"]
    ).reset_index(drop=True)


def build_ratio_vs_vbz(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return pd.DataFrame()

    vbz_reference = summary_df.loc[
        summary_df["algorithm"] == "VBZ", ["machine", "Mean"]
    ].rename(columns={"Mean": "VBZ_Mean"})
    ratio_df = summary_df.merge(vbz_reference, on="machine", how="left")
    ratio_df["Speed_Ratio_vs_VBZ"] = ratio_df["Mean"] / ratio_df["VBZ_Mean"]
    return ratio_df.sort_values(
        ["machine", "Speed_Ratio_vs_VBZ"], ascending=[True, False]
    ).reset_index(drop=True)


def summarize_metric_winners(
    summary_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if summary_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    per_machine = (
        summary_df.sort_values(
            ["machine", "Mean", "algorithm"], ascending=[True, False, True]
        )
        .groupby("machine", observed=True)
        .head(1)
        .reset_index(drop=True)[["machine", "algorithm", "Mean", "Std"]]
        .rename(
            columns={
                "algorithm": "fastest_algorithm",
                "Mean": "mean_speed_mb_sec",
                "Std": "std_speed_mb_sec",
            }
        )
    )
    per_algorithm = (
        summary_df.sort_values(
            ["algorithm", "Mean", "machine"], ascending=[True, False, True]
        )
        .groupby("algorithm", observed=True)
        .head(1)
        .reset_index(drop=True)[["algorithm", "machine", "Mean", "Std"]]
        .rename(
            columns={
                "machine": "best_machine",
                "Mean": "mean_speed_mb_sec",
                "Std": "std_speed_mb_sec",
            }
        )
    )
    return per_machine, per_algorithm


def plot_tradeoff_bits_per_sample_vs_speed(
    comparison_df: pd.DataFrame,
    algorithms: list[str],
    machine_order: list[str],
    *,
    export_enabled: bool = False,
    output_dir: Path | None = None,
    export_format: str = "png",
    include_titles: bool = True,
) -> pd.DataFrame:
    tradeoff_df = build_tradeoff_summary(comparison_df)
    if tradeoff_df.empty:
        print("No data available for the bits-per-sample trade-off plot.")
        return tradeoff_df

    # Fixed 7-inch width for a two-column bioinformatics figure.
    # Use at most 4 columns so each panel has enough horizontal space for
    # annotations; reserve a small band for a figure-level legend.
    n_machines = len(machine_order)
    ncols = min(4, n_machines)
    nrows = int(np.ceil(n_machines / ncols))
    fig_height = 2 * nrows + 0.85
    fig, axes_grid = plt.subplots(
        nrows, ncols, figsize=(7.0, fig_height), sharey=True, squeeze=False
    )
    axes_flat = [ax for row in axes_grid for ax in row]

    if include_titles:
        fig.suptitle(
            "Bits per sample vs speed trade-off", fontsize=8, fontweight="bold"
        )

    for idx, (axis, machine) in enumerate(zip(axes_flat[:n_machines], machine_order)):
        machine_frame = tradeoff_df.loc[tradeoff_df["machine"] == machine].copy()
        if machine_frame.empty:
            axis.set_axis_off()
            continue

        machine_frame = machine_frame.sort_values(["avg_bits_per_sample", "algorithm"])
        speed_values = machine_frame[
            ["avg_compression_speed", "avg_decompression_speed"]
        ].to_numpy(dtype=float)
        y_min = float(np.nanmin(speed_values))
        y_max = float(np.nanmax(speed_values))
        y_span = y_max - y_min
        y_margin = max(40.0, y_span * 0.08) if y_span > 0 else 40.0
        x_min = machine_frame["avg_bits_per_sample"].min()
        x_max = machine_frame["avg_bits_per_sample"].max()
        x_padding = max(0.03, (x_max - x_min) * 0.12) if x_max > x_min else 0.08

        for _, row in machine_frame.iterrows():
            color = color_for_algorithm(row["algorithm"])
            x_value = row["avg_bits_per_sample"]
            compression_y = row["avg_compression_speed"]
            decompression_y = row["avg_decompression_speed"]

            axis.plot(
                [x_value, x_value],
                [compression_y, decompression_y],
                linestyle="--",
                linewidth=1.0,
                alpha=0.35,
                color=color,
            )
            axis.scatter(
                x_value,
                compression_y,
                marker="o",
                s=25,
                color=color,
                alpha=0.85,
            )
            axis.scatter(
                x_value,
                decompression_y,
                marker="x",
                s=30,
                color=color,
                alpha=0.95,
                linewidths=1.5,
            )
            axis.annotate(
                TRADEOFF_ANNOTATION_LABELS.get(row["algorithm"], row["algorithm"]),
                (x_value, compression_y),
                textcoords="offset points",
                xytext=(0, -6 if compression_y >= y_max - y_margin else 6),
                ha="center",
                va="top" if compression_y >= y_max - y_margin else "bottom",
                fontsize=6,
            )

        # Use an in-axes text label instead of set_title so the machine name
        # is preserved even when include_titles=False clears axis titles.
        axis.text(
            0.5,
            1.01,
            machine,
            transform=axis.transAxes,
            fontsize=7,
            ha="center",
            va="bottom",
        )
        axis.tick_params(axis="both", labelsize=6)
        axis.set_xlim(x_min - x_padding, x_max + x_padding)
        axis.grid(True, alpha=0.3)
        if idx % ncols == 0:
            axis.set_ylabel("Average speed (MB/s)", fontsize=7)

    # Hide unused grid cells and add shared axis adornments.
    for axis in axes_flat[n_machines:]:
        axis.set_axis_off()
    fig.supxlabel("Average bits per sample", fontsize=7, y=0.0625)

    marker_legend = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="black",
            linestyle="None",
            markersize=4,
            label="Compression",
        ),
        Line2D(
            [0],
            [0],
            marker="x",
            color="black",
            linestyle="None",
            markersize=4,
            label="Decompression",
        ),
    ]
    legend_anchor_y = 0.95 if include_titles else 0.99
    fig.legend(
        handles=marker_legend,
        loc="upper center",
        bbox_to_anchor=(0.5, legend_anchor_y),
        ncol=len(marker_legend),
        fontsize=7,
        frameon=False,
        handletextpad=0.5,
        columnspacing=1.2,
    )

    top_rect = 0.9 if include_titles else 0.93
    plt.tight_layout(rect=[0, 0.07, 1.0, top_rect])
    if output_dir is not None:
        maybe_export_figure(
            fig,
            "speed",
            "bits_per_sample_vs_speed_tradeoff",
            export_enabled=export_enabled,
            output_dir=output_dir,
            export_format=export_format,
            include_titles=include_titles,
        )
    plt.show()
    return tradeoff_df


def build_speed_artifacts(
    runs: list[dict],
    requested_algorithms: list[str] | None = None,
    metric_specs: dict[str, MetricSpec] | None = None,
) -> dict[str, object]:
    metric_specs = metric_specs or SPEED_METRIC_SPECS
    algorithms = selected_speed_algorithms(runs, requested_algorithms)
    comparison_df, metadata_df = load_speed_comparison_table(
        runs, algorithms, metric_specs
    )
    return _finalize_speed_artifacts(
        comparison_df,
        algorithms=algorithms,
        machine_order=[entry["label"] for entry in runs],
        metric_specs=metric_specs,
        metadata_df=metadata_df,
    )
