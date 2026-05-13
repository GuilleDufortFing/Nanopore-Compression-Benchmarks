import argparse
import os
import sys
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common.algorithms import (  # noqa: E402
    SUPPORTED_ALGORITHMS,
    build_algorithm_token,
    build_algorithms_help,
    get_raw_algorithm_name,
    normalize_algorithm_selection,
)
from common.cli import add_executable_argument, add_results_root_argument  # noqa: E402
from common.execution import run_algorithm_executable_on_files  # noqa: E402
from common.executables import resolve_named_executable  # noqa: E402
from common.runs import (  # noqa: E402
    build_run_id,
    create_run_directories,
    write_run_manifest,
)
from common.summaries import walk_and_process_compression  # noqa: E402


def build_argument_parser():
    algorithms_help = build_algorithms_help()
    all_algorithms = " ".join(SUPPORTED_ALGORITHMS)

    return argparse.ArgumentParser(
        description=(
            "Run the compression benchmark pipeline for one input directory, "
            "writing timestamped raw outputs and compression-focused summaries "
            "for an explicit list of one or more algorithms."
        ),
        epilog=(
            "Supported algorithms:\n"
            f"{algorithms_help}\n\n"
            "Examples:\n"
            "  python scripts/benchmarks/run_compression_benchmark.py "
            "data/benchmark_bin/ExampleBin "
            "EX-ZD-ZSTD\n"
            "  python scripts/benchmarks/run_compression_benchmark.py "
            "data/benchmark_bin/ExampleBin "
                "EX-ZD-ZSTD PDZ\n"
            "  python scripts/benchmarks/run_compression_benchmark.py "
            "data/benchmark_bin/ExampleBin "
            f"{all_algorithms}"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )


def write_compression_run_manifest(
    run_root,
    input_dir,
    display_algorithms,
    executable,
):
    return write_run_manifest(
        run_root,
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "input_dir": str(Path(input_dir).resolve()),
            "algorithms": display_algorithms,
            "algorithm_token": build_algorithm_token(display_algorithms),
            "executable": str(Path(executable).resolve()),
        },
    )


def build_algorithm_raw_dir(raw_root, algorithm, input_dir):
    return raw_root / algorithm / Path(input_dir).resolve().name


def build_algorithm_summary_dir(summaries_root, algorithm):
    return summaries_root / algorithm


def run_pipeline(input_dir, algorithm_tokens, results_root=None, executable=None):
    selected_algorithms, _ = normalize_algorithm_selection(algorithm_tokens)
    display_algorithm_token = build_algorithm_token(selected_algorithms)
    benchmark_executable = resolve_named_executable("compression_benchmark", executable)
    run_id = build_run_id(input_dir, display_algorithm_token)
    run_root, raw_root, summaries_root = create_run_directories(
        results_root,
        run_id,
        benchmark_type="compression",
    )
    manifest_path = write_compression_run_manifest(
        run_root,
        input_dir,
        selected_algorithms,
        benchmark_executable,
    )

    summary_outputs = {}
    for algorithm in selected_algorithms:
        raw_algorithm = get_raw_algorithm_name(algorithm)
        algorithm_raw_dir = build_algorithm_raw_dir(raw_root, algorithm, input_dir)
        algorithm_summary_dir = build_algorithm_summary_dir(summaries_root, algorithm)

        print(f"Running {algorithm} into {algorithm_raw_dir}")
        run_algorithm_executable_on_files(
            input_dir,
            algorithm_raw_dir,
            benchmark_executable,
            raw_algorithm,
            include_file=lambda file_path: file_path.suffix.lower() == ".bin",
        )

        os.makedirs(algorithm_summary_dir, exist_ok=True)
        summary_outputs[algorithm] = walk_and_process_compression(
            str(algorithm_raw_dir),
            str(algorithm_summary_dir),
        )

    return {
        "run_id": run_id,
        "run_root": run_root,
        "raw_root": raw_root,
        "summaries_root": summaries_root,
        "manifest_path": manifest_path,
        "algorithms": selected_algorithms,
        "summary_outputs": summary_outputs,
    }


def main(argv=None):
    parser = build_argument_parser()
    parser.add_argument(
        "input_dir",
        nargs="?",
        help="Directory containing the input benchmark files",
    )
    parser.add_argument(
        "algorithms",
        nargs="*",
        help="One algorithm, multiple algorithms, or comma-separated algorithms",
    )
    add_results_root_argument(parser)
    add_executable_argument(parser)

    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        parser.print_help(sys.stderr)
        return 1

    args = parser.parse_args(argv)

    if args.input_dir is None or not args.algorithms:
        parser.print_help(sys.stderr)
        return 1

    if not os.path.isdir(args.input_dir):
        parser.error(f"Input directory does not exist: '{args.input_dir}'")

    try:
        pipeline_result = run_pipeline(
            args.input_dir,
            args.algorithms,
            results_root=args.results_root,
            executable=args.executable,
        )
    except (FileNotFoundError, ValueError) as error:
        parser.error(str(error))

    print(f"Run ID: {pipeline_result['run_id']}")
    print(f"Run root: {pipeline_result['run_root']}")
    print(f"Raw results: {pipeline_result['raw_root']}")
    print(f"Summaries: {pipeline_result['summaries_root']}")
    print(f"Manifest: {pipeline_result['manifest_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())