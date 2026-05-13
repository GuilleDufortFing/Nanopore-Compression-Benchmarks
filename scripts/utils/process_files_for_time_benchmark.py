import argparse
import os
import random
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONVERTER_SCRIPT = REPO_ROOT / "scripts" / "utils" / "pod5_to_benchmark_time.py"
DEFAULT_SAMPLE_SIZE = 5
SUPPORTED_INPUT_SUFFIXES = {".pod5"}


def build_argument_parser():
    return argparse.ArgumentParser(
        description=(
            "Recursively walk an input directory, select up to 5 random files per "
            "discovered group, convert matching POD5 files with "
            "pod5_to_benchmark_time.py, and "
            "write .bin outputs into the output directory."
        ),
        epilog=(
            "The script preserves subdirectory names under the output directory and "
            "uses a multiprocessing pool to process groups in parallel.\n\n"
            "Example:\n"
            "  python scripts/utils/process_files_for_time_benchmark.py "
            "data/pod5/ExamplePod5 "
            "data/benchmark_bin/ExampleBin -p 4 --sample-size 1"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )


def iter_supported_files(source_dir):
    return [
        file_name
        for file_name in os.listdir(source_dir)
        if os.path.isfile(os.path.join(source_dir, file_name))
        and Path(file_name).suffix.lower() in SUPPORTED_INPUT_SUFFIXES
    ]


def process_subdirectory(args):
    source_dir, output_dir, converter_script, sample_size = args

    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    files = iter_supported_files(source_dir)
    if not files:
        return []

    selected_files = random.sample(files, min(sample_size, len(files)))

    outputs = []
    for file_name in selected_files:
        file_path = os.path.join(source_dir, file_name)
        output_file = os.path.join(output_dir, os.path.splitext(file_name)[0] + ".bin")

        subprocess.run(
            [sys.executable, converter_script, file_path, output_file],
            check=True,
        )

        outputs.append((source_dir, output_file))

    return outputs


def process_directory(input_dir, output_dir, num_processes, converter_script, sample_size):
    os.makedirs(output_dir, exist_ok=True)

    args_list = []
    for root, _, _ in os.walk(input_dir):
        files = iter_supported_files(root)
        if not files:
            continue

        relative_dir = os.path.relpath(root, input_dir)
        target_dir = output_dir if relative_dir == "." else os.path.join(output_dir, relative_dir)
        args_list.append((root, target_dir, converter_script, sample_size))

    if not args_list:
        print(f"No supported input files found under {input_dir}")
        return []

    with Pool(num_processes) as pool:
        results = pool.map(process_subdirectory, args_list)

        flattened_results = [result for sublist in results for result in sublist]
        for result in flattened_results:
            print(f"Processed directory {result[0]} with output: {result[1]}")

    return flattened_results

if __name__ == "__main__":
    parser = build_argument_parser()
    parser.add_argument(
        "input_dir",
        nargs="?",
        help="Root directory containing the source files to sample and convert",
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        help="Directory where generated .bin files will be written",
    )
    parser.add_argument(
        "-p",
        "--processes",
        type=int,
        default=4,
        help="Number of worker processes to use (default: 4)",
    )
    parser.add_argument(
        "--converter-script",
        default=str(DEFAULT_CONVERTER_SCRIPT),
        help=(
            "Path to the converter script to run for each sampled file "
            f"(default: {DEFAULT_CONVERTER_SCRIPT})"
        ),
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
        help=f"Maximum number of random files to select per directory (default: {DEFAULT_SAMPLE_SIZE})",
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    if args.input_dir is None or args.output_dir is None:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if not os.path.isdir(args.input_dir):
        parser.error(f"Input directory does not exist: '{args.input_dir}'")

    if args.processes < 1:
        parser.error("Number of worker processes must be at least 1")

    if args.sample_size < 1:
        parser.error("Sample size must be at least 1")

    if not os.path.isfile(args.converter_script):
        parser.error(
            f"Converter script not found: '{args.converter_script}'. "
            "Use --converter-script to provide the correct path."
        )

    process_directory(
        args.input_dir,
        args.output_dir,
        args.processes,
        args.converter_script,
        args.sample_size,
    )
