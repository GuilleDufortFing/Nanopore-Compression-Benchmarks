"""Split analysis helpers extracted from the article notebook."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .figures import maybe_export_figure
from .shared import latest_result_run


SIZE_SPLIT_REQUIRED_COLUMNS = {
    "filename",
    "total_bytes",
    "compressed_signal_bytes",
    "total_signal_table_bytes",
    "rows",
}
TIME_SPLIT_REQUIRED_COLUMNS = {
    "filename",
    "comp_total_s",
    "comp_proc_s",
    "comp_pct",
    "decomp_total_s",
    "decomp_proc_s",
    "decomp_pct",
    "comp_intervals",
    "decomp_intervals",
}


def _validate_split_frame(
    frame: pd.DataFrame,
    *,
    required_columns: set[str],
    source: str,
) -> pd.DataFrame:
    missing_columns = required_columns.difference(frame.columns)
    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(f"Split data from {source} is missing columns: {missing_text}")
    return frame.copy()


def _build_split_artifacts_from_frames(
    size_df: pd.DataFrame,
    time_df: pd.DataFrame,
    *,
    size_run_dir: Path | None,
    time_run_dir: Path | None,
) -> dict[str, object]:
    size_df = _validate_split_frame(
        size_df,
        required_columns=SIZE_SPLIT_REQUIRED_COLUMNS,
        source="size-split input",
    )
    time_df = _validate_split_frame(
        time_df,
        required_columns=TIME_SPLIT_REQUIRED_COLUMNS,
        source="time-split input",
    )

    merged_df = size_df.merge(
        time_df, on="filename", how="inner", suffixes=("_size", "_time")
    )
    if merged_df.empty:
        raise ValueError(
            "No overlapping filenames were found between size-split and time-split summaries."
        )

    merged_df["signal_table_overhead_bytes"] = (
        merged_df["total_signal_table_bytes"] - merged_df["compressed_signal_bytes"]
    )
    merged_df["remaining_file_bytes"] = (
        merged_df["total_bytes"] - merged_df["total_signal_table_bytes"]
    )
    if (merged_df["signal_table_overhead_bytes"] < 0).any():
        raise ValueError(
            "Derived signal table overhead is negative for at least one file."
        )
    if (merged_df["remaining_file_bytes"] < 0).any():
        raise ValueError(
            "Derived remaining file bytes are negative for at least one file."
        )

    merged_df["compressed_signal_pct"] = (
        100.0 * merged_df["compressed_signal_bytes"] / merged_df["total_bytes"]
    )
    merged_df["signal_table_overhead_pct"] = (
        100.0 * merged_df["signal_table_overhead_bytes"] / merged_df["total_bytes"]
    )
    merged_df["remaining_file_pct"] = (
        100.0 * merged_df["remaining_file_bytes"] / merged_df["total_bytes"]
    )
    merged_df["compression_other_pct"] = 100.0 - merged_df["comp_pct"]
    merged_df["decompression_other_pct"] = 100.0 - merged_df["decomp_pct"]

    total_bytes = merged_df["total_bytes"].sum()
    total_signal_table_bytes = merged_df["total_signal_table_bytes"].sum()
    overall_row = {
        "filename": "ALL_FILES",
        "file_count": int(len(merged_df)),
        "total_bytes": int(total_bytes),
        "compressed_signal_bytes": int(merged_df["compressed_signal_bytes"].sum()),
        "signal_table_overhead_bytes": int(
            merged_df["signal_table_overhead_bytes"].sum()
        ),
        "remaining_file_bytes": int(merged_df["remaining_file_bytes"].sum()),
        "compressed_signal_pct": 100.0
        * merged_df["compressed_signal_bytes"].sum()
        / total_bytes,
        "signal_table_overhead_pct": 100.0
        * merged_df["signal_table_overhead_bytes"].sum()
        / total_bytes,
        "remaining_file_pct": 100.0
        * merged_df["remaining_file_bytes"].sum()
        / total_bytes,
        "comp_total_s": merged_df["comp_total_s"].sum(),
        "comp_proc_s": merged_df["comp_proc_s"].sum(),
        "comp_pct": 100.0
        * merged_df["comp_proc_s"].sum()
        / merged_df["comp_total_s"].sum(),
        "compression_other_pct": 100.0
        - (100.0 * merged_df["comp_proc_s"].sum() / merged_df["comp_total_s"].sum()),
        "decomp_total_s": merged_df["decomp_total_s"].sum(),
        "decomp_proc_s": merged_df["decomp_proc_s"].sum(),
        "decomp_pct": 100.0
        * merged_df["decomp_proc_s"].sum()
        / merged_df["decomp_total_s"].sum(),
        "decompression_other_pct": 100.0
        - (
            100.0
            * merged_df["decomp_proc_s"].sum()
            / merged_df["decomp_total_s"].sum()
        ),
        "rows": int(merged_df["rows"].sum()),
        "comp_intervals": int(merged_df["comp_intervals"].sum()),
        "decomp_intervals": int(merged_df["decomp_intervals"].sum()),
        "size_run_dir": str(size_run_dir) if size_run_dir is not None else "",
        "time_run_dir": str(time_run_dir) if time_run_dir is not None else "",
        "total_signal_table_bytes": int(total_signal_table_bytes),
    }
    overall_df = pd.DataFrame([overall_row])

    return {
        "size_run_dir": size_run_dir,
        "time_run_dir": time_run_dir,
        "per_file_df": merged_df,
        "overall_df": overall_df,
    }


def load_split_summary_frame(
    results_root: Path, summary_name: str
) -> tuple[Path, pd.DataFrame]:
    run_dir = latest_result_run(results_root)
    summary_path = run_dir / "summaries" / summary_name
    if not summary_path.is_file():
        raise FileNotFoundError(f"Missing split summary file: {summary_path}")
    return run_dir, pd.read_csv(summary_path)


def build_split_artifacts_from_paths(
    size_summary_path: Path,
    time_summary_path: Path,
) -> dict[str, object]:
    size_summary_path = Path(size_summary_path).expanduser().resolve()
    time_summary_path = Path(time_summary_path).expanduser().resolve()
    if not size_summary_path.is_file():
        raise FileNotFoundError(f"Missing size-split summary file: {size_summary_path}")
    if not time_summary_path.is_file():
        raise FileNotFoundError(f"Missing time-split summary file: {time_summary_path}")

    return _build_split_artifacts_from_frames(
        pd.read_csv(size_summary_path),
        pd.read_csv(time_summary_path),
        size_run_dir=size_summary_path.parent.parent,
        time_run_dir=time_summary_path.parent.parent,
    )


def build_split_artifacts_from_frames(
    size_df: pd.DataFrame,
    time_df: pd.DataFrame,
    *,
    size_run_dir: Path | None = None,
    time_run_dir: Path | None = None,
) -> dict[str, object]:
    return _build_split_artifacts_from_frames(
        size_df,
        time_df,
        size_run_dir=Path(size_run_dir).expanduser().resolve()
        if size_run_dir is not None
        else None,
        time_run_dir=Path(time_run_dir).expanduser().resolve()
        if time_run_dir is not None
        else None,
    )


def build_split_artifacts(
    size_results_root: Path,
    time_results_root: Path,
) -> dict[str, object]:
    size_run_dir, size_df = load_split_summary_frame(
        size_results_root,
        "pod5_size_summaries.csv",
    )
    time_run_dir, time_df = load_split_summary_frame(
        time_results_root,
        "pod5_benchmarks.csv",
    )

    return _build_split_artifacts_from_frames(
        size_df,
        time_df,
        size_run_dir=size_run_dir,
        time_run_dir=time_run_dir,
    )


def split_pie_autopct(pct: float) -> str:
    return f"{pct:.1f}%" if pct >= 3.0 else ""


def plot_split_decomposition(
    overall_df: pd.DataFrame,
    *,
    export_enabled: bool = False,
    output_dir: Path | None = None,
    export_format: str = "png",
    include_titles: bool = True,
) -> None:
    row = overall_df.iloc[0]

    pie_specs = [
        {
            "title": "File size partition",
            "legend_title": "File size components",
            "segments": [
                ("Compressed signal", row["compressed_signal_pct"], "#5CB9E4"),
                ("Signal table overhead", row["signal_table_overhead_pct"], "#7BC67B"),
                ("Other file bytes", row["remaining_file_pct"], "#D9D9D9"),
            ],
        },
        {
            "title": "Compression time partition",
            "legend_title": "Compression time components",
            "segments": [
                ("Signal processing", row["comp_pct"], "#E8A425"),
                ("Other work", row["compression_other_pct"], "#F4D2A0"),
            ],
        },
        {
            "title": "Decompression time partition",
            "legend_title": "Decompression time components",
            "segments": [
                ("Signal processing", row["decomp_pct"], "#DC6E62"),
                ("Other work", row["decompression_other_pct"], "#F1B5A8"),
            ],
        },
    ]

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle("Article workload decomposition", fontsize=16, fontweight="bold")

    for ax, pie_spec in zip(axes, pie_specs):
        labels = [segment[0] for segment in pie_spec["segments"]]
        values = [segment[1] for segment in pie_spec["segments"]]
        colors = [segment[2] for segment in pie_spec["segments"]]
        wedges, _, _ = ax.pie(
            values,
            colors=colors,
            startangle=90,
            counterclock=False,
            autopct=split_pie_autopct,
            pctdistance=0.75,
            wedgeprops={"edgecolor": "white", "linewidth": 1.0},
            textprops={"fontsize": 15},
        )
        ax.set_title(pie_spec["title"], fontsize=14)
        legend_labels = [
            f"{label} ({value:.2f}%)" for label, value in zip(labels, values)
        ]
        ax.legend(
            wedges,
            legend_labels,
            title=pie_spec["legend_title"],
            loc="center left",
            bbox_to_anchor=(1.0, 0.5),
            frameon=False,
            fontsize=15,
            title_fontsize=16,
        )

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    if output_dir is not None:
        maybe_export_figure(
            fig,
            "splits",
            "workload_decomposition",
            export_enabled=export_enabled,
            output_dir=output_dir,
            export_format=export_format,
            include_titles=include_titles,
        )
    plt.show()
