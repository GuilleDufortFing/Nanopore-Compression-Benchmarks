import argparse
import csv
import os
import platform
import shlex
import statistics
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common.cli import add_executable_argument, add_results_root_argument  # noqa: E402
from common.executables import resolve_named_executable  # noqa: E402
from common.inputs import iter_input_files  # noqa: E402
from common.runs import (  # noqa: E402
    build_run_id,
    create_run_directories,
    ensure_directory,
    write_run_manifest,
)


SUPPORTED_ALGORITHMS = ("VBZ", "PDZ")
LINUX_TIME_BINARY = Path("/usr/bin/time")
TIME_FORMAT = "elapsed_seconds=%e\nmax_rss_kib=%M"
ROUNDTRIP_POLICY = (
    "unmeasured input->algorithm setup, followed by measured algorithm->uncompressed "
    "and uncompressed->algorithm stages"
)
RAW_FIELDNAMES = [
    "relative_input_path",
    "input_file_name",
    "algorithm",
    "repetition",
    "stage",
    "stage_order",
    "source_format",
    "target_format",
    "input_bytes",
    "output_bytes",
    "peak_rss_kib",
    "elapsed_seconds",
]
STAGE_SUMMARY_FIELDNAMES = [
    "algorithm",
    "stage",
    "observations",
    "file_count",
    "mean_peak_rss_kib",
    "median_peak_rss_kib",
    "min_peak_rss_kib",
    "max_peak_rss_kib",
    "mean_elapsed_seconds",
    "median_elapsed_seconds",
    "min_elapsed_seconds",
    "max_elapsed_seconds",
    "mean_input_bytes",
    "mean_output_bytes",
]
ROUNDTRIP_PER_FILE_FIELDNAMES = [
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
]
ROUNDTRIP_SUMMARY_FIELDNAMES = [
    "algorithm",
    "observations",
    "file_count",
    "mean_roundtrip_peak_rss_kib",
    "median_roundtrip_peak_rss_kib",
    "min_roundtrip_peak_rss_kib",
    "max_roundtrip_peak_rss_kib",
    "mean_roundtrip_total_elapsed_seconds",
    "median_roundtrip_total_elapsed_seconds",
    "min_roundtrip_total_elapsed_seconds",
    "max_roundtrip_total_elapsed_seconds",
]


class BenchmarkExecutionError(RuntimeError):
    pass


def build_argument_parser():
    supported_text = " ".join(SUPPORTED_ALGORITHMS)
    return argparse.ArgumentParser(
        description=(
            "Run a Linux-only POD5 memory benchmark using the standalone copy executable. "
            "For each POD5 file and algorithm, the script performs an unmeasured "
            "input->algorithm setup pass, then measures peak RSS for the two measured "
            "round-trip stages: algorithm->uncompressed and uncompressed->algorithm."
        ),
        epilog=(
            "Supported algorithms:\n"
            f"  {supported_text}\n\n"
            "Examples:\n"
            "  python scripts/benchmarks/run_memory_benchmark.py data/pod5/ExamplePod5\n"
            "  python scripts/benchmarks/run_memory_benchmark.py data/pod5/DS1 VBZ PDZ --repetitions 3\n"
            "  python scripts/benchmarks/run_memory_benchmark.py data/pod5/DS1 PDZ --keep-intermediates"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )


def normalize_algorithm_selection(algorithm_tokens):
    if not algorithm_tokens:
        return list(SUPPORTED_ALGORITHMS)

    normalized_tokens = []
    for token in algorithm_tokens:
        parts = [part.strip() for part in token.split(",")]
        normalized_tokens.extend(part for part in parts if part)

    invalid = [token for token in normalized_tokens if token not in SUPPORTED_ALGORITHMS]
    if invalid:
        supported = ", ".join(SUPPORTED_ALGORITHMS)
        invalid_text = ", ".join(invalid)
        raise ValueError(
            f"Unsupported memory benchmark algorithms: {invalid_text}. Supported values: {supported}"
        )

    selected = []
    seen = set()
    for algorithm in SUPPORTED_ALGORITHMS:
        if algorithm in normalized_tokens and algorithm not in seen:
            selected.append(algorithm)
            seen.add(algorithm)

    if not selected:
        raise ValueError("No algorithms were selected")

    return selected


def build_algorithm_token(algorithms):
    return "-".join(algorithms)


def ensure_linux_memory_probe():
    if platform.system().lower() != "linux":
        raise ValueError(
            "run_memory_benchmark.py currently supports Linux only because it relies on '/usr/bin/time' "
            "to capture peak resident set size."
        )

    if not LINUX_TIME_BINARY.is_file():
        raise FileNotFoundError(
            "Expected GNU time at '/usr/bin/time' for peak RSS measurement, but it was not found."
        )


def discover_pod5_inputs(input_dir):
    input_root = Path(input_dir).resolve()
    pod5_files = list(
        iter_input_files(
            input_root,
            include_file=lambda file_path: file_path.suffix.lower() == ".pod5",
        )
    )
    if not pod5_files:
        raise ValueError(f"No POD5 files were found under '{input_root}'.")
    return input_root, pod5_files


def write_memory_run_manifest(
    run_root,
    *,
    input_dir,
    algorithms,
    repetitions,
    executable,
    pod5_files,
    keep_intermediates,
):
    return write_run_manifest(
        run_root,
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "benchmark_type": "memory",
            "platform_scope": "linux",
            "input_dir": str(Path(input_dir).resolve()),
            "algorithms": list(algorithms),
            "algorithm_token": build_algorithm_token(algorithms),
            "repetitions": repetitions,
            "measurement_metric": "peak_rss_kib",
            "measurement_tool": str(LINUX_TIME_BINARY),
            "roundtrip_policy": ROUNDTRIP_POLICY,
            "keep_intermediates": keep_intermediates,
            "pod5_file_count": len(pod5_files),
            "executable": str(Path(executable).resolve()),
        },
    )


def parse_time_metrics(metrics_path):
    raw_metrics = Path(metrics_path).read_text(encoding="utf-8")
    values = {}
    for line in raw_metrics.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

    if "elapsed_seconds" not in values or "max_rss_kib" not in values:
        raise ValueError(
            f"Could not parse memory metrics from '{metrics_path}'. Raw contents: {raw_metrics!r}"
        )

    return {
        "elapsed_seconds": float(values["elapsed_seconds"]),
        "max_rss_kib": int(float(values["max_rss_kib"])),
    }


def run_copy_command(
    executable,
    input_path,
    output_path,
    compression_mode,
    *,
    measure_memory,
    metrics_path=None,
):
    base_command = [
        str(Path(executable).resolve()),
        str(Path(input_path).resolve()),
        str(Path(output_path).resolve()),
        f"--{compression_mode}",
    ]
    command = list(base_command)

    if measure_memory:
        if metrics_path is None:
            raise ValueError("metrics_path is required when measure_memory=True")
        command = [
            str(LINUX_TIME_BINARY),
            "-f",
            TIME_FORMAT,
            "-o",
            str(Path(metrics_path).resolve()),
            *base_command,
        ]

    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        stdout_text = completed.stdout.strip() or "<empty>"
        stderr_text = completed.stderr.strip() or "<empty>"
        raise BenchmarkExecutionError(
            "Copy command failed.\n"
            f"Command: {shlex.join(command)}\n"
            f"Exit code: {completed.returncode}\n"
            f"stdout:\n{stdout_text}\n"
            f"stderr:\n{stderr_text}"
        )

    if not Path(output_path).is_file():
        raise BenchmarkExecutionError(
            f"Copy command succeeded but did not create the expected output file '{output_path}'."
        )

    result = {
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if measure_memory:
        result.update(parse_time_metrics(metrics_path))

    return result


def build_stage_row(
    relative_input_path,
    *,
    algorithm,
    repetition,
    stage,
    stage_order,
    source_format,
    target_format,
    input_path,
    output_path,
    metrics,
):
    return {
        "relative_input_path": relative_input_path.as_posix(),
        "input_file_name": relative_input_path.name,
        "algorithm": algorithm,
        "repetition": repetition,
        "stage": stage,
        "stage_order": stage_order,
        "source_format": source_format,
        "target_format": target_format,
        "input_bytes": Path(input_path).stat().st_size,
        "output_bytes": Path(output_path).stat().st_size,
        "peak_rss_kib": metrics["max_rss_kib"],
        "elapsed_seconds": metrics["elapsed_seconds"],
    }


def build_workspace_dir(raw_root, relative_input_path, algorithm, repetition):
    return (
        Path(raw_root)
        / "intermediates"
        / algorithm
        / f"repeat_{repetition:03d}"
        / relative_input_path.with_suffix("")
    )


def run_roundtrip_measurement(
    executable,
    input_root,
    input_file,
    *,
    algorithm,
    repetition,
    raw_root,
    keep_intermediates,
):
    relative_input_path = Path(input_file).resolve().relative_to(Path(input_root).resolve())

    if keep_intermediates:
        workspace_dir = build_workspace_dir(raw_root, relative_input_path, algorithm, repetition)
        ensure_directory(workspace_dir)
        return execute_roundtrip_in_workspace(
            executable,
            input_file,
            relative_input_path,
            algorithm,
            repetition,
            workspace_dir,
        )

    with tempfile.TemporaryDirectory(
        prefix=f"{algorithm.lower()}_{repetition:03d}_",
        dir=str(raw_root),
    ) as temp_dir:
        return execute_roundtrip_in_workspace(
            executable,
            input_file,
            relative_input_path,
            algorithm,
            repetition,
            Path(temp_dir),
        )


def execute_roundtrip_in_workspace(
    executable,
    input_file,
    relative_input_path,
    algorithm,
    repetition,
    workspace_dir,
):
    ensure_directory(workspace_dir)

    input_stem = Path(input_file).stem
    prepared_path = Path(workspace_dir) / f"{input_stem}_{algorithm.lower()}_prepared.pod5"
    uncompressed_path = Path(workspace_dir) / f"{input_stem}_uncompressed.pod5"
    recompressed_path = Path(workspace_dir) / f"{input_stem}_{algorithm.lower()}_roundtrip.pod5"
    algorithm_to_uncompressed_metrics = Path(workspace_dir) / "algorithm_to_uncompressed.time"
    uncompressed_to_algorithm_metrics = Path(workspace_dir) / "uncompressed_to_algorithm.time"

    run_copy_command(
        executable,
        input_file,
        prepared_path,
        algorithm,
        measure_memory=False,
    )

    algorithm_to_uncompressed = run_copy_command(
        executable,
        prepared_path,
        uncompressed_path,
        "uncompressed",
        measure_memory=True,
        metrics_path=algorithm_to_uncompressed_metrics,
    )
    uncompressed_to_algorithm = run_copy_command(
        executable,
        uncompressed_path,
        recompressed_path,
        algorithm,
        measure_memory=True,
        metrics_path=uncompressed_to_algorithm_metrics,
    )

    return [
        build_stage_row(
            relative_input_path,
            algorithm=algorithm,
            repetition=repetition,
            stage="algorithm_to_uncompressed",
            stage_order=1,
            source_format=algorithm,
            target_format="uncompressed",
            input_path=prepared_path,
            output_path=uncompressed_path,
            metrics=algorithm_to_uncompressed,
        ),
        build_stage_row(
            relative_input_path,
            algorithm=algorithm,
            repetition=repetition,
            stage="uncompressed_to_algorithm",
            stage_order=2,
            source_format="uncompressed",
            target_format=algorithm,
            input_path=uncompressed_path,
            output_path=recompressed_path,
            metrics=uncompressed_to_algorithm,
        ),
    ]


def write_csv_rows(output_path, fieldnames, rows):
    with Path(output_path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return Path(output_path)


def build_stage_summary(rows):
    grouped_rows = {}
    for row in rows:
        grouped_rows.setdefault((row["algorithm"], row["stage"]), []).append(row)

    summary_rows = []
    for (algorithm, stage), group_rows in sorted(grouped_rows.items()):
        peaks = [row["peak_rss_kib"] for row in group_rows]
        elapsed = [row["elapsed_seconds"] for row in group_rows]
        input_sizes = [row["input_bytes"] for row in group_rows]
        output_sizes = [row["output_bytes"] for row in group_rows]

        summary_rows.append(
            {
                "algorithm": algorithm,
                "stage": stage,
                "observations": len(group_rows),
                "file_count": len({row["relative_input_path"] for row in group_rows}),
                "mean_peak_rss_kib": statistics.fmean(peaks),
                "median_peak_rss_kib": statistics.median(peaks),
                "min_peak_rss_kib": min(peaks),
                "max_peak_rss_kib": max(peaks),
                "mean_elapsed_seconds": statistics.fmean(elapsed),
                "median_elapsed_seconds": statistics.median(elapsed),
                "min_elapsed_seconds": min(elapsed),
                "max_elapsed_seconds": max(elapsed),
                "mean_input_bytes": statistics.fmean(input_sizes),
                "mean_output_bytes": statistics.fmean(output_sizes),
            }
        )

    return summary_rows


def build_roundtrip_per_file_summary(rows):
    grouped_rows = {}
    for row in rows:
        key = (row["relative_input_path"], row["algorithm"], row["repetition"])
        grouped_rows.setdefault(key, []).append(row)

    summary_rows = []
    for (relative_input_path, algorithm, repetition), group_rows in sorted(grouped_rows.items()):
        stage_rows = {row["stage"]: row for row in group_rows}
        algorithm_to_uncompressed = stage_rows["algorithm_to_uncompressed"]
        uncompressed_to_algorithm = stage_rows["uncompressed_to_algorithm"]

        summary_rows.append(
            {
                "relative_input_path": relative_input_path,
                "algorithm": algorithm,
                "repetition": repetition,
                "algorithm_to_uncompressed_peak_rss_kib": algorithm_to_uncompressed["peak_rss_kib"],
                "uncompressed_to_algorithm_peak_rss_kib": uncompressed_to_algorithm["peak_rss_kib"],
                "roundtrip_peak_rss_kib": max(
                    algorithm_to_uncompressed["peak_rss_kib"],
                    uncompressed_to_algorithm["peak_rss_kib"],
                ),
                "algorithm_to_uncompressed_elapsed_seconds": algorithm_to_uncompressed["elapsed_seconds"],
                "uncompressed_to_algorithm_elapsed_seconds": uncompressed_to_algorithm["elapsed_seconds"],
                "roundtrip_total_elapsed_seconds": (
                    algorithm_to_uncompressed["elapsed_seconds"]
                    + uncompressed_to_algorithm["elapsed_seconds"]
                ),
                "prepared_input_bytes": algorithm_to_uncompressed["input_bytes"],
                "uncompressed_output_bytes": algorithm_to_uncompressed["output_bytes"],
                "recompressed_output_bytes": uncompressed_to_algorithm["output_bytes"],
            }
        )

    return summary_rows


def build_roundtrip_summary(roundtrip_per_file_rows):
    grouped_rows = {}
    for row in roundtrip_per_file_rows:
        grouped_rows.setdefault(row["algorithm"], []).append(row)

    summary_rows = []
    for algorithm, group_rows in sorted(grouped_rows.items()):
        peaks = [row["roundtrip_peak_rss_kib"] for row in group_rows]
        elapsed = [row["roundtrip_total_elapsed_seconds"] for row in group_rows]

        summary_rows.append(
            {
                "algorithm": algorithm,
                "observations": len(group_rows),
                "file_count": len({row["relative_input_path"] for row in group_rows}),
                "mean_roundtrip_peak_rss_kib": statistics.fmean(peaks),
                "median_roundtrip_peak_rss_kib": statistics.median(peaks),
                "min_roundtrip_peak_rss_kib": min(peaks),
                "max_roundtrip_peak_rss_kib": max(peaks),
                "mean_roundtrip_total_elapsed_seconds": statistics.fmean(elapsed),
                "median_roundtrip_total_elapsed_seconds": statistics.median(elapsed),
                "min_roundtrip_total_elapsed_seconds": min(elapsed),
                "max_roundtrip_total_elapsed_seconds": max(elapsed),
            }
        )

    return summary_rows


def run_pipeline(
    input_dir,
    algorithm_tokens,
    *,
    repetitions=1,
    results_root=None,
    executable=None,
    keep_intermediates=False,
):
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")

    ensure_linux_memory_probe()
    selected_algorithms = normalize_algorithm_selection(algorithm_tokens)
    input_root, pod5_files = discover_pod5_inputs(input_dir)
    benchmark_executable = resolve_named_executable("copy", executable)
    run_id = build_run_id(input_root, build_algorithm_token(selected_algorithms))
    run_root, raw_root, summaries_root = create_run_directories(
        results_root,
        run_id,
        benchmark_type="memory",
    )
    manifest_path = write_memory_run_manifest(
        run_root,
        input_dir=input_root,
        algorithms=selected_algorithms,
        repetitions=repetitions,
        executable=benchmark_executable,
        pod5_files=pod5_files,
        keep_intermediates=keep_intermediates,
    )

    raw_rows = []
    for algorithm in selected_algorithms:
        for repetition in range(1, repetitions + 1):
            for input_file in pod5_files:
                relative_input_path = input_file.relative_to(input_root).as_posix()
                print(
                    f"Benchmarking {relative_input_path} with {algorithm} "
                    f"(repetition {repetition}/{repetitions})"
                )
                raw_rows.extend(
                    run_roundtrip_measurement(
                        benchmark_executable,
                        input_root,
                        input_file,
                        algorithm=algorithm,
                        repetition=repetition,
                        raw_root=raw_root,
                        keep_intermediates=keep_intermediates,
                    )
                )

    raw_rows = sorted(
        raw_rows,
        key=lambda row: (
            row["relative_input_path"],
            row["algorithm"],
            row["repetition"],
            row["stage_order"],
        ),
    )
    stage_summary_rows = build_stage_summary(raw_rows)
    roundtrip_per_file_rows = build_roundtrip_per_file_summary(raw_rows)
    roundtrip_summary_rows = build_roundtrip_summary(roundtrip_per_file_rows)

    raw_csv_path = write_csv_rows(raw_root / "memory_measurements.csv", RAW_FIELDNAMES, raw_rows)
    stage_summary_path = write_csv_rows(
        summaries_root / "stage_summary.csv",
        STAGE_SUMMARY_FIELDNAMES,
        stage_summary_rows,
    )
    roundtrip_per_file_path = write_csv_rows(
        summaries_root / "roundtrip_per_file.csv",
        ROUNDTRIP_PER_FILE_FIELDNAMES,
        roundtrip_per_file_rows,
    )
    roundtrip_summary_path = write_csv_rows(
        summaries_root / "roundtrip_summary.csv",
        ROUNDTRIP_SUMMARY_FIELDNAMES,
        roundtrip_summary_rows,
    )

    return {
        "run_id": run_id,
        "run_root": run_root,
        "raw_root": raw_root,
        "summaries_root": summaries_root,
        "manifest_path": manifest_path,
        "raw_csv_path": raw_csv_path,
        "stage_summary_path": stage_summary_path,
        "roundtrip_per_file_path": roundtrip_per_file_path,
        "roundtrip_summary_path": roundtrip_summary_path,
        "algorithms": selected_algorithms,
        "pod5_file_count": len(pod5_files),
    }


def main(argv=None):
    parser = build_argument_parser()
    parser.add_argument(
        "input_dir",
        nargs="?",
        help="Directory containing POD5 input files",
    )
    parser.add_argument(
        "algorithms",
        nargs="*",
        help="Optional subset of algorithms to benchmark (default: VBZ PDZ)",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="Number of repetitions per file and algorithm (default: 1)",
    )
    parser.add_argument(
        "--keep-intermediates",
        action="store_true",
        help="Keep the prepared, uncompressed, and round-tripped POD5 intermediates under raw/intermediates/.",
    )
    add_results_root_argument(parser)
    add_executable_argument(
        parser,
        help_text="Override the copy executable path",
    )

    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        parser.print_help(sys.stderr)
        return 1

    args = parser.parse_args(argv)

    if args.input_dir is None:
        parser.print_help(sys.stderr)
        return 1

    if not os.path.isdir(args.input_dir):
        parser.error(f"Input directory does not exist: '{args.input_dir}'")

    try:
        pipeline_result = run_pipeline(
            args.input_dir,
            args.algorithms,
            repetitions=args.repetitions,
            results_root=args.results_root,
            executable=args.executable,
            keep_intermediates=args.keep_intermediates,
        )
    except (BenchmarkExecutionError, FileNotFoundError, ValueError) as error:
        parser.error(str(error))

    print(f"Run ID: {pipeline_result['run_id']}")
    print(f"Run root: {pipeline_result['run_root']}")
    print(f"Raw measurements: {pipeline_result['raw_csv_path']}")
    print(f"Stage summary: {pipeline_result['stage_summary_path']}")
    print(f"Round-trip per-file summary: {pipeline_result['roundtrip_per_file_path']}")
    print(f"Round-trip summary: {pipeline_result['roundtrip_summary_path']}")
    print(f"Manifest: {pipeline_result['manifest_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())