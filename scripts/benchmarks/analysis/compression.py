"""Compression analysis helpers extracted from the article notebook."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .figures import color_for_algorithm, maybe_export_figure
from .shared import (
    dataset_name_from_manifest,
    display_algorithm_name,
    load_run_manifest,
    normalize_requested_algorithms,
    resolve_available_algorithm,
    sort_algorithms,
    summary_stem_from_manifest,
)

COMPRESSION_REQUIRED_SUMMARY_COLUMNS = {
    "File",
    "total_chunks",
    "total_samples",
    "total_compressed_bytes",
    "bits_per_sample",
    "successful_chunk_count",
    "failed_chunk_count",
    "success_rate",
    "any_failed",
}
DEFAULT_COMPRESSION_PRD_REFERENCE_ALGORITHM = "PDZ"
DEFAULT_COMPRESSION_PRD_REPORT_ALGORITHMS = ["VBZ", "EX-ZD-ZSTD"]
DEFAULT_COMPRESSION_LATEX_MACRO_LABELS = {
    "PDZ": r"\algShort",
    "VBZ": "VBZ",
    "EX-ZD-ZSTD": r"\exzd",
}


def build_compression_run_entries(
    results_root: Path, dataset_run_ids: dict[str, str]
) -> list[dict[str, Path]]:
    return [
        {"label": dataset_name, "run_dir": Path(results_root) / run_id}
        for dataset_name, run_id in dataset_run_ids.items()
    ]


def available_summary_algorithms(run_dir: Path) -> list[str]:
    summaries_root = Path(run_dir) / "summaries"
    if not summaries_root.is_dir():
        raise FileNotFoundError(f"Missing summaries directory: {summaries_root}")
    return sort_algorithms(
        child.name for child in summaries_root.iterdir() if child.is_dir()
    )


def prepare_compression_runs(run_entries: list[dict]) -> list[dict]:
    prepared_runs = []
    for entry in run_entries:
        run_dir = Path(entry["run_dir"]).expanduser().resolve()
        manifest = load_run_manifest(run_dir)
        dataset_name = dataset_name_from_manifest(manifest)
        dataset_label = entry.get("label", dataset_name)
        prepared_runs.append(
            {
                "label": dataset_label,
                "dataset_name": dataset_name,
                "summary_stem": summary_stem_from_manifest(manifest),
                "run_dir": run_dir,
                "manifest": manifest,
                "available_algorithms": available_summary_algorithms(run_dir),
            }
        )

    duplicate_labels = [
        label
        for label, count in Counter(run["label"] for run in prepared_runs).items()
        if count > 1
    ]
    if duplicate_labels:
        duplicate_text = ", ".join(sorted(duplicate_labels))
        raise ValueError(
            "This notebook assumes one selected run per dataset label. Duplicate labels: "
            + duplicate_text
        )

    return prepared_runs


def selected_compression_algorithms(
    prepared_runs: list[dict], requested_algorithms: list[str] | None = None
) -> list[str]:
    if requested_algorithms is not None:
        return normalize_requested_algorithms(requested_algorithms)

    discovered = []
    for run in prepared_runs:
        discovered.extend(run["available_algorithms"])
    return sort_algorithms(discovered)


def load_compression_summary_frame(summary_path: Path) -> pd.DataFrame:
    frame = pd.read_csv(summary_path)
    missing_columns = COMPRESSION_REQUIRED_SUMMARY_COLUMNS.difference(frame.columns)
    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(
            f"Summary file {summary_path} is missing required columns: {missing_text}"
        )
    return frame


def aggregate_compression_summary_frame(
    frame: pd.DataFrame,
    *,
    dataset_label: str,
    dataset_name: str,
    algorithm: str,
    run_dir: Path,
    manifest: dict,
) -> dict:
    total_files = int(len(frame))
    total_chunks = int(frame["total_chunks"].sum())
    total_samples = int(frame["total_samples"].sum())
    total_compressed_bytes = int(frame["total_compressed_bytes"].sum())
    successful_chunk_count = int(frame["successful_chunk_count"].sum())
    failed_chunk_count = int(frame["failed_chunk_count"].sum())
    dataset_success_rate = (
        successful_chunk_count / total_chunks if total_chunks else float("nan")
    )
    weighted_bits_per_sample = (
        (8.0 * total_compressed_bytes) / total_samples
        if total_samples
        else float("nan")
    )
    any_failed = bool(
        pd.to_numeric(frame["any_failed"], errors="coerce").fillna(0).astype(int).any()
        or failed_chunk_count > 0
    )

    return {
        "dataset": dataset_label,
        "dataset_name": dataset_name,
        "algorithm": algorithm,
        "run_dir": str(run_dir),
        "run_timestamp": manifest.get("timestamp", ""),
        "file_count": total_files,
        "total_chunks": total_chunks,
        "total_samples": total_samples,
        "total_compressed_bytes": total_compressed_bytes,
        "bits_per_sample": weighted_bits_per_sample,
        "successful_chunk_count": successful_chunk_count,
        "failed_chunk_count": failed_chunk_count,
        "dataset_success_rate": dataset_success_rate,
        "any_failed": any_failed,
        "summary_status": "has_failures" if any_failed else "ok",
        "has_data": True,
    }


def build_missing_compression_row(
    run: dict, algorithm: str, summary_status: str = "missing_summary"
) -> dict:
    manifest_algorithms = sort_algorithms(run["manifest"].get("algorithms", []))
    return {
        "dataset": run["label"],
        "dataset_name": run["dataset_name"],
        "algorithm": display_algorithm_name(algorithm),
        "run_dir": str(run["run_dir"]),
        "run_timestamp": run["manifest"].get("timestamp", ""),
        "file_count": 0,
        "total_chunks": 0,
        "total_samples": 0,
        "total_compressed_bytes": 0,
        "bits_per_sample": pd.NA,
        "successful_chunk_count": 0,
        "failed_chunk_count": 0,
        "dataset_success_rate": pd.NA,
        "any_failed": False,
        "summary_status": summary_status,
        "has_data": False,
        "available_algorithms": ", ".join(run["available_algorithms"]),
        "manifest_algorithms": ", ".join(manifest_algorithms),
    }


def aggregate_compression_runs(
    prepared_runs: list[dict], algorithms: list[str]
) -> pd.DataFrame:
    aggregate_rows = []
    for run in prepared_runs:
        manifest_algorithms = sort_algorithms(run["manifest"].get("algorithms", []))
        summaries_root = run["run_dir"] / "summaries"
        available_algorithms = (
            {child.name for child in summaries_root.iterdir() if child.is_dir()}
            if summaries_root.is_dir()
            else set()
        )
        for algorithm in algorithms:
            resolved_algorithm = resolve_available_algorithm(
                algorithm, available_algorithms
            )
            summary_path = (
                summaries_root / resolved_algorithm / f"{run['summary_stem']}.csv"
            )
            if not summary_path.is_file():
                aggregate_rows.append(build_missing_compression_row(run, algorithm))
                continue

            frame = load_compression_summary_frame(summary_path)
            if frame.empty:
                aggregate_rows.append(
                    build_missing_compression_row(
                        run,
                        algorithm,
                        summary_status="empty_summary",
                    )
                )
                continue

            aggregate_row = aggregate_compression_summary_frame(
                frame=frame,
                dataset_label=run["label"],
                dataset_name=run["dataset_name"],
                algorithm=display_algorithm_name(algorithm),
                run_dir=run["run_dir"],
                manifest=run["manifest"],
            )
            aggregate_row["available_algorithms"] = ", ".join(
                run["available_algorithms"]
            )
            aggregate_row["manifest_algorithms"] = ", ".join(manifest_algorithms)
            aggregate_rows.append(aggregate_row)

    if not aggregate_rows:
        raise RuntimeError(
            "No aggregate rows were produced from the selected compression runs."
        )

    return pd.DataFrame(aggregate_rows)


def build_compression_artifacts(
    run_entries: list[dict],
    requested_algorithms: list[str] | None = None,
) -> tuple[list[dict], list[str], pd.DataFrame]:
    prepared_runs = prepare_compression_runs(run_entries)
    comparison_algorithms = selected_compression_algorithms(
        prepared_runs,
        requested_algorithms,
    )
    aggregate_df = aggregate_compression_runs(prepared_runs, comparison_algorithms)
    dataset_order = [run["label"] for run in prepared_runs]
    aggregate_df["dataset"] = pd.Categorical(
        aggregate_df["dataset"], categories=dataset_order, ordered=True
    )
    aggregate_df["algorithm"] = pd.Categorical(
        aggregate_df["algorithm"], categories=comparison_algorithms, ordered=True
    )
    aggregate_df = aggregate_df.sort_values(["dataset", "algorithm"]).reset_index(
        drop=True
    )
    return prepared_runs, comparison_algorithms, aggregate_df


def format_bps_row(row: pd.Series, digits: int = 4) -> pd.Series:
    vbz_value = row.get("VBZ")
    formatted_row = {}
    for algorithm, value in row.items():
        if pd.isna(value):
            formatted_row[algorithm] = ""
            continue

        formatted_value = f"{value:.{digits}f}"
        if algorithm == "VBZ" or pd.isna(vbz_value) or vbz_value == 0:
            formatted_row[algorithm] = formatted_value
            continue

        relative_percent = ((value - vbz_value) * 100.0) / vbz_value
        formatted_row[algorithm] = f"{formatted_value} ({relative_percent:+.2f}%)"

    return pd.Series(formatted_row)


def first_available_numeric_value(row: pd.Series):
    numeric_values = pd.to_numeric(row, errors="coerce").dropna()
    return numeric_values.iloc[0] if not numeric_values.empty else pd.NA


def format_integer_report_table(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.apply(
        lambda column: column.map(
            lambda value: "" if pd.isna(value) else f"{int(value):,}"
        )
    )


def plot_compression_comparison(
    aggregate_df: pd.DataFrame,
    dataset_order: list[str],
    comparison_algorithms: list[str],
    *,
    export_enabled: bool = False,
    output_dir: Path | None = None,
    export_format: str = "png",
    include_titles: bool = True,
) -> None:
    plot_df = aggregate_df.loc[aggregate_df["has_data"]].copy()
    if plot_df.empty:
        raise RuntimeError(
            "No dataset-level compression aggregates are available for plotting."
        )

    algorithms_in_plot = [
        algorithm
        for algorithm in comparison_algorithms
        if algorithm in plot_df["algorithm"].astype(str).tolist()
    ]
    bar_width = 0.8 / max(1, len(algorithms_in_plot))

    fig, ax = plt.subplots(figsize=(max(12, 1.8 * len(dataset_order) + 4), 6))

    for algorithm_index, algorithm in enumerate(algorithms_in_plot):
        algorithm_rows = (
            plot_df.loc[
                plot_df["algorithm"] == algorithm,
                ["dataset", "bits_per_sample", "summary_status"],
            ]
            .drop_duplicates(subset=["dataset"])
            .set_index("dataset")
            .reindex(dataset_order)
        )
        x_positions = [
            dataset_index - 0.4 + (bar_width / 2.0) + (algorithm_index * bar_width)
            for dataset_index in range(len(dataset_order))
        ]
        heights = pd.to_numeric(
            algorithm_rows["bits_per_sample"], errors="coerce"
        ).tolist()
        bars = ax.bar(
            x_positions,
            heights,
            width=bar_width,
            label=algorithm,
            color=color_for_algorithm(algorithm),
        )
        for bar, (_, row) in zip(bars, algorithm_rows.iterrows()):
            if (
                pd.notna(row["summary_status"])
                and row["summary_status"] == "has_failures"
            ):
                bar.set_edgecolor("black")
                bar.set_linewidth(1.0)
                bar.set_hatch("//")

    ax.set_xticks(list(range(len(dataset_order))))
    ax.set_xticklabels(dataset_order)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    ax.set_ylabel("Weighted bits per sample")
    ax.set_title("Compression comparison by dataset and algorithm")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.legend(title="Algorithm", bbox_to_anchor=(1.02, 1.0), loc="upper left")

    plt.tight_layout()
    if output_dir is not None:
        maybe_export_figure(
            fig,
            "compression",
            "compression_comparison",
            export_enabled=export_enabled,
            output_dir=output_dir,
            export_format=export_format,
            include_titles=include_titles,
        )
    plt.show()


def compute_compression_prd(candidate_value: float, reference_value: float) -> float:
    if pd.isna(candidate_value) or pd.isna(reference_value) or reference_value == 0:
        return float("nan")
    return (
        100.0
        * (float(candidate_value) - float(reference_value))
        / float(reference_value)
    )


def split_compression_dataset_groups(
    dataset_order: list[str],
) -> tuple[list[str], list[str]]:
    dna_datasets = [
        dataset for dataset in dataset_order if not str(dataset).endswith("-RNA")
    ]
    rna_datasets = [
        dataset for dataset in dataset_order if str(dataset).endswith("-RNA")
    ]
    return dna_datasets, rna_datasets


def build_compression_prd_frame(
    bps_matrix: pd.DataFrame,
    *,
    reference_algorithm: str = DEFAULT_COMPRESSION_PRD_REFERENCE_ALGORITHM,
    report_algorithms: list[str] | None = None,
) -> pd.DataFrame:
    report_algorithms = report_algorithms or DEFAULT_COMPRESSION_PRD_REPORT_ALGORITHMS
    required_algorithms = [reference_algorithm, *report_algorithms]
    missing_algorithms = [
        algorithm
        for algorithm in required_algorithms
        if algorithm not in bps_matrix.columns
    ]
    if missing_algorithms:
        missing_text = ", ".join(missing_algorithms)
        raise ValueError(
            f"Compression PRD report is missing required algorithms: {missing_text}"
        )

    prd_frame = bps_matrix.copy()
    for algorithm in report_algorithms:
        prd_frame[f"{algorithm}_prd_vs_{reference_algorithm}"] = prd_frame.apply(
            lambda row: compute_compression_prd(
                row.get(algorithm),
                row.get(reference_algorithm),
            ),
            axis=1,
        )
    return prd_frame


def format_compression_bps(value: float, digits: int = 3) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.{digits}f}"


def format_compression_value_with_prd(
    value: float,
    prd: float,
    digits: int = 3,
) -> str:
    if pd.isna(value):
        return ""
    if pd.isna(prd):
        return format_compression_bps(value, digits=digits)
    return f"{float(value):.{digits}f} ({float(prd):.{digits}f})"


def format_compression_prd_only(prd: float, digits: int = 3) -> str:
    if pd.isna(prd):
        return ""
    return f"({float(prd):.{digits}f})"


def build_compression_report_table(
    prd_frame: pd.DataFrame,
    dataset_order: list[str],
    *,
    reference_algorithm: str = DEFAULT_COMPRESSION_PRD_REFERENCE_ALGORITHM,
    report_algorithms: list[str] | None = None,
) -> pd.DataFrame:
    report_algorithms = report_algorithms or DEFAULT_COMPRESSION_PRD_REPORT_ALGORITHMS
    reference_column = f"{reference_algorithm} (bps)"
    report_column_labels = {
        algorithm: f"{algorithm} CR (PRD vs {reference_algorithm})"
        for algorithm in report_algorithms
    }

    rows = []
    dna_datasets, rna_datasets = split_compression_dataset_groups(dataset_order)
    for group_name, datasets in (("DNA", dna_datasets), ("RNA", rna_datasets)):
        if not datasets:
            continue

        for dataset in datasets:
            row = {
                "Dataset": dataset,
                reference_column: format_compression_bps(
                    prd_frame.loc[dataset, reference_algorithm]
                ),
            }
            for algorithm in report_algorithms:
                row[report_column_labels[algorithm]] = (
                    format_compression_value_with_prd(
                        prd_frame.loc[dataset, algorithm],
                        prd_frame.loc[
                            dataset, f"{algorithm}_prd_vs_{reference_algorithm}"
                        ],
                    )
                )
            rows.append(row)

        average_row = {
            "Dataset": f"{group_name} avg",
            reference_column: "",
        }
        for algorithm in report_algorithms:
            average_row[report_column_labels[algorithm]] = format_compression_prd_only(
                pd.to_numeric(
                    prd_frame.loc[
                        datasets, f"{algorithm}_prd_vs_{reference_algorithm}"
                    ],
                    errors="coerce",
                ).mean()
            )
        rows.append(average_row)

    return pd.DataFrame(rows)


def build_compression_latex_table(
    prd_frame: pd.DataFrame,
    dataset_order: list[str],
    *,
    reference_algorithm: str = DEFAULT_COMPRESSION_PRD_REFERENCE_ALGORITHM,
    report_algorithms: list[str] | None = None,
    latex_macro_labels: dict[str, str] | None = None,
    latex_label: str = "tab:cr",
) -> str:
    report_algorithms = report_algorithms or DEFAULT_COMPRESSION_PRD_REPORT_ALGORITHMS
    if not report_algorithms:
        raise ValueError(
            "At least one report algorithm is required for the LaTeX table."
        )

    latex_macro_labels = latex_macro_labels or DEFAULT_COMPRESSION_LATEX_MACRO_LABELS
    dna_datasets, rna_datasets = split_compression_dataset_groups(dataset_order)
    reference_label = latex_macro_labels.get(reference_algorithm, reference_algorithm)
    report_labels = [
        latex_macro_labels.get(algorithm, algorithm) for algorithm in report_algorithms
    ]
    column_spec = "|l|" + "|".join("r" for _ in range(1 + len(report_algorithms))) + "|"
    report_caption_labels = ", ".join(report_labels[:-1])
    if len(report_labels) > 1:
        report_caption_labels = (
            f"{report_caption_labels}, and {report_labels[-1]}"
            if report_caption_labels
            else report_labels[-1]
        )
    else:
        report_caption_labels = report_labels[0]
    header_labels = [f"{report_label} CR (PRD)" for report_label in report_labels]

    lines = [
        r"\begin{table}[]",
        r"\centering",
        f"\\caption{{Compression ratio for {reference_label}, {report_caption_labels}, with PRD relative to {reference_label}. DNA and RNA datasets are reported separately.}}",
        f"\\begin{{tabular}}{{{column_spec}}}",
        r"\hline",
        "Dataset"
        + f" & {reference_label}\\ (bps)"
        + "".join(f" & {label}" for label in header_labels)
        + r"\\",
        r"\hline",
    ]

    for group_name, datasets in (("DNA", dna_datasets), ("RNA", rna_datasets)):
        if not datasets:
            continue

        for dataset in datasets:
            reference_text = format_compression_bps(
                prd_frame.loc[dataset, reference_algorithm]
            )
            report_texts = [
                format_compression_value_with_prd(
                    prd_frame.loc[dataset, algorithm],
                    prd_frame.loc[dataset, f"{algorithm}_prd_vs_{reference_algorithm}"],
                )
                for algorithm in report_algorithms
            ]
            lines.append(
                f"{dataset} & {reference_text}"
                + "".join(f" & {report_text}" for report_text in report_texts)
                + r"\\"
            )
        lines.append(r"\hline")

        average_texts = [
            format_compression_prd_only(
                pd.to_numeric(
                    prd_frame.loc[
                        datasets, f"{algorithm}_prd_vs_{reference_algorithm}"
                    ],
                    errors="coerce",
                ).mean()
            )
            for algorithm in report_algorithms
        ]
        lines.append(f"{group_name} avg & " + " & ".join([""] + average_texts) + r"\\")
        lines.append(r"\hline")

    lines.extend(
        [
            r"\end{tabular}",
            f"\\label{{{latex_label}}}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines)


def build_subject_vs_baseline_compression_prd_frame(
    bps_matrix: pd.DataFrame,
    *,
    subject_algorithm: str,
    baseline_algorithms: list[str],
) -> pd.DataFrame:
    if not baseline_algorithms:
        raise ValueError(
            "At least one baseline algorithm is required for PRD reporting."
        )

    required_algorithms = [*baseline_algorithms, subject_algorithm]
    missing_algorithms = [
        algorithm
        for algorithm in required_algorithms
        if algorithm not in bps_matrix.columns
    ]
    if missing_algorithms:
        missing_text = ", ".join(missing_algorithms)
        raise ValueError(
            f"Compression PRD report is missing required algorithms: {missing_text}"
        )

    prd_frame = bps_matrix.copy()
    for baseline_algorithm in baseline_algorithms:
        prd_frame[f"{subject_algorithm}_prd_vs_{baseline_algorithm}"] = prd_frame.apply(
            lambda row: compute_compression_prd(
                row.get(subject_algorithm),
                row.get(baseline_algorithm),
            ),
            axis=1,
        )
    return prd_frame


def build_subject_last_compression_report_table(
    prd_frame: pd.DataFrame,
    dataset_order: list[str],
    *,
    subject_algorithm: str,
    baseline_algorithms: list[str],
) -> pd.DataFrame:
    if not baseline_algorithms:
        raise ValueError(
            "At least one baseline algorithm is required for report output."
        )

    subject_column = f"{subject_algorithm} (bps)"
    baseline_column_labels = {
        algorithm: f"{algorithm} CR ({subject_algorithm} vs {algorithm} PRD)"
        for algorithm in baseline_algorithms
    }

    rows = []
    dna_datasets, rna_datasets = split_compression_dataset_groups(dataset_order)
    for group_name, datasets in (("DNA", dna_datasets), ("RNA", rna_datasets)):
        if not datasets:
            continue

        for dataset in datasets:
            row = {"Dataset": dataset}
            for algorithm in baseline_algorithms:
                row[baseline_column_labels[algorithm]] = (
                    format_compression_value_with_prd(
                        prd_frame.loc[dataset, algorithm],
                        prd_frame.loc[
                            dataset, f"{subject_algorithm}_prd_vs_{algorithm}"
                        ],
                    )
                )
            row[subject_column] = format_compression_bps(
                prd_frame.loc[dataset, subject_algorithm]
            )
            rows.append(row)

        average_row = {"Dataset": f"{group_name} avg"}
        for algorithm in baseline_algorithms:
            average_row[baseline_column_labels[algorithm]] = (
                format_compression_prd_only(
                    pd.to_numeric(
                        prd_frame.loc[
                            datasets, f"{subject_algorithm}_prd_vs_{algorithm}"
                        ],
                        errors="coerce",
                    ).mean()
                )
            )
        average_row[subject_column] = ""
        rows.append(average_row)

    return pd.DataFrame(rows)


def build_subject_last_compression_latex_table(
    prd_frame: pd.DataFrame,
    dataset_order: list[str],
    *,
    subject_algorithm: str,
    baseline_algorithms: list[str],
    latex_macro_labels: dict[str, str] | None = None,
    latex_label: str = "tab:cr",
) -> str:
    if not baseline_algorithms:
        raise ValueError(
            "At least one baseline algorithm is required for the LaTeX table."
        )

    latex_macro_labels = latex_macro_labels or DEFAULT_COMPRESSION_LATEX_MACRO_LABELS
    dna_datasets, rna_datasets = split_compression_dataset_groups(dataset_order)

    subject_label = latex_macro_labels.get(subject_algorithm, subject_algorithm)
    baseline_labels = [
        latex_macro_labels.get(algorithm, algorithm)
        for algorithm in baseline_algorithms
    ]
    all_caption_labels = [*baseline_labels, subject_label]
    if len(all_caption_labels) > 1:
        caption_labels = ", ".join(all_caption_labels[:-1])
        caption_labels = (
            f"{caption_labels}, and {all_caption_labels[-1]}"
            if caption_labels
            else all_caption_labels[-1]
        )
    else:
        caption_labels = all_caption_labels[0]

    column_spec = (
        "|l|" + "|".join("r" for _ in range(1 + len(baseline_algorithms))) + "|"
    )
    header_labels = [
        f"{baseline_label} CR ({subject_label} vs {baseline_label} PRD)"
        for baseline_label in baseline_labels
    ]

    lines = [
        r"\begin{table}[]",
        r"\centering",
        f"\\caption{{Compression ratio for {caption_labels}, with PRD for {subject_label} relative to each baseline. DNA and RNA datasets are reported separately.}}",
        f"\\begin{{tabular}}{{{column_spec}}}",
        r"\hline",
        "Dataset"
        + "".join(f" & {label}" for label in header_labels)
        + f" & {subject_label}\\ (bps)"
        + r"\\",
        r"\hline",
    ]

    for group_name, datasets in (("DNA", dna_datasets), ("RNA", rna_datasets)):
        if not datasets:
            continue

        for dataset in datasets:
            baseline_texts = [
                format_compression_value_with_prd(
                    prd_frame.loc[dataset, algorithm],
                    prd_frame.loc[dataset, f"{subject_algorithm}_prd_vs_{algorithm}"],
                )
                for algorithm in baseline_algorithms
            ]
            subject_text = format_compression_bps(
                prd_frame.loc[dataset, subject_algorithm]
            )
            lines.append(
                f"{dataset} & " + " & ".join([*baseline_texts, subject_text]) + r"\\"
            )
        lines.append(r"\hline")

        average_texts = [
            format_compression_prd_only(
                pd.to_numeric(
                    prd_frame.loc[datasets, f"{subject_algorithm}_prd_vs_{algorithm}"],
                    errors="coerce",
                ).mean()
            )
            for algorithm in baseline_algorithms
        ]
        lines.append(f"{group_name} avg & " + " & ".join([*average_texts, ""]) + r"\\")
        lines.append(r"\hline")

    lines.extend(
        [
            r"\end{tabular}",
            f"\\label{{{latex_label}}}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines)
