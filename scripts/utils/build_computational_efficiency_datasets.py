import argparse
import os
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from process_files_for_time_benchmark import (
    DEFAULT_CONVERTER_SCRIPT,
    SUPPORTED_INPUT_SUFFIXES,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_ROOT = REPO_ROOT / "data" / "pod5"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "data" / "benchmark_bin"
DEFAULT_DATASETS = tuple(f"DS{index}" for index in range(1, 11))
DEFAULT_PROCESS_COUNT = max(1, min(4, os.cpu_count() or 1))
FULL_LAYER_NAME = "full"
EXAMPLE_OUTPUT_DATASET = "ExampleBin"


@dataclass(frozen=True)
class ConversionTask:
    dataset_name: str
    source_file: Path
    output_file: Path


def resolve_cutoff_layer_name(cutoff_mb):
    return FULL_LAYER_NAME if cutoff_mb is None else str(cutoff_mb)


def validate_cutoff_mb(cutoff_mb):
    if cutoff_mb is not None and cutoff_mb < 1:
        raise ValueError("Cutoff must be at least 1 MB when provided")


def uses_layered_output(dataset_name):
    return build_output_dataset_name(dataset_name) != EXAMPLE_OUTPUT_DATASET


def build_output_dataset_root(output_root, dataset_name, cutoff_mb):
    output_dataset_name = build_output_dataset_name(dataset_name)
    if not uses_layered_output(dataset_name):
        return output_root / output_dataset_name
    return output_root / resolve_cutoff_layer_name(cutoff_mb) / output_dataset_name


def build_argument_parser():
    return argparse.ArgumentParser(
        description=(
            "Mirror one or more POD5 datasets into benchmark .bin files by "
            "invoking pod5_to_benchmark_time.py for every discovered .pod5 file."
        ),
        epilog=(
            "When no dataset names are provided, the script processes DS1 through DS10. "
            "Dataset names ending in 'Pod5' are mapped to output folders ending in 'Bin', "
            "so ExamplePod5 becomes ExampleBin. Generated DS datasets are written under "
            "data/benchmark_bin/<layer>/<dataset>, where <layer> is 'full' with no cutoff "
            "or the cutoff in MB when --cutoff-mb is provided."
            "\n\n"
            "Examples:\n"
            "  python scripts/utils/build_computational_efficiency_datasets.py\n"
            "  python scripts/utils/build_computational_efficiency_datasets.py --cutoff-mb 1000\n"
            "  python scripts/utils/build_computational_efficiency_datasets.py ExamplePod5 --overwrite\n"
            "  python scripts/utils/build_computational_efficiency_datasets.py DS1 DS2 DS3 -p 8"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )


def normalize_dataset_selection(dataset_tokens):
    if not dataset_tokens:
        return list(DEFAULT_DATASETS)

    selected_datasets = []
    for token in dataset_tokens:
        parts = [part.strip() for part in token.split(",")]
        selected_datasets.extend(part for part in parts if part)

    if not selected_datasets:
        raise ValueError("No dataset names were provided")

    deduplicated = []
    seen = set()
    for dataset_name in selected_datasets:
        if dataset_name in seen:
            continue
        deduplicated.append(dataset_name)
        seen.add(dataset_name)

    return deduplicated


def build_output_dataset_name(dataset_name):
    if dataset_name.endswith("Pod5"):
        return f"{dataset_name[:-4]}Bin"
    return dataset_name


def iter_pod5_files(dataset_root):
    for root, _, files in os.walk(dataset_root):
        for file_name in sorted(files):
            file_path = Path(root) / file_name
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_INPUT_SUFFIXES:
                yield file_path


def plan_conversion_tasks(input_root, output_root, dataset_names, cutoff_mb):
    tasks = []
    missing_datasets = []
    empty_datasets = []

    for dataset_name in dataset_names:
        dataset_input_root = input_root / dataset_name
        if not dataset_input_root.is_dir():
            missing_datasets.append(dataset_name)
            continue

        pod5_files = list(iter_pod5_files(dataset_input_root))
        if not pod5_files:
            empty_datasets.append(dataset_name)
            continue

        dataset_output_root = build_output_dataset_root(output_root, dataset_name, cutoff_mb)
        for source_file in pod5_files:
            relative_output_path = source_file.relative_to(dataset_input_root).with_suffix(".bin")
            tasks.append(
                ConversionTask(
                    dataset_name=dataset_name,
                    source_file=source_file,
                    output_file=dataset_output_root / relative_output_path,
                )
            )

    if missing_datasets:
        missing_text = ", ".join(missing_datasets)
        raise ValueError(
            f"Dataset directories were not found under '{input_root}': {missing_text}"
        )

    return tasks, empty_datasets


def run_conversion(task, converter_script, overwrite, cutoff_mb):
    task.output_file.parent.mkdir(parents=True, exist_ok=True)

    if task.output_file.exists() and not overwrite:
        return "skipped", task

    command = [
        sys.executable,
        str(converter_script),
        str(task.source_file),
        str(task.output_file),
    ]
    if cutoff_mb is not None and uses_layered_output(task.dataset_name):
        command.extend(["--cutoff-mb", str(cutoff_mb)])

    subprocess.run(command, check=True)
    return "converted", task


def main(argv=None):
    parser = build_argument_parser()
    parser.add_argument(
        "datasets",
        nargs="*",
        help=(
            "Dataset names to process. Defaults to DS1 through DS10. "
            "Comma-separated values are also accepted."
        ),
    )
    parser.add_argument(
        "--input-root",
        default=str(DEFAULT_INPUT_ROOT),
        help=(
            "Root directory containing the POD5 datasets "
            f"(default: {DEFAULT_INPUT_ROOT})"
        ),
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help=(
            "Root directory where mirrored .bin datasets will be written "
            f"(default: {DEFAULT_OUTPUT_ROOT})"
        ),
    )
    parser.add_argument(
        "-p",
        "--processes",
        type=int,
        default=DEFAULT_PROCESS_COUNT,
        help=(
            "Number of parallel workers to use while invoking the converter "
            f"(default: {DEFAULT_PROCESS_COUNT})"
        ),
    )
    parser.add_argument(
        "--converter-script",
        default=str(DEFAULT_CONVERTER_SCRIPT),
        help=(
            "Path to the per-file POD5 to .bin converter script "
            f"(default: {DEFAULT_CONVERTER_SCRIPT})"
        ),
    )
    parser.add_argument(
        "--cutoff-mb",
        type=int,
        default=None,
        help=(
            "Optional per-file output cutoff in MB for generated DS datasets. "
            "When omitted, DS outputs are written under the 'full' layer without a cutoff."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing .bin outputs instead of skipping them",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned conversions without generating any files",
    )

    args = parser.parse_args(argv)

    try:
        dataset_names = normalize_dataset_selection(args.datasets)
    except ValueError as error:
        parser.error(str(error))

    try:
        validate_cutoff_mb(args.cutoff_mb)
    except ValueError as error:
        parser.error(str(error))

    if args.cutoff_mb is not None and any(
        not uses_layered_output(dataset_name) for dataset_name in dataset_names
    ):
        parser.error(
            "ExamplePod5 cannot be combined with --cutoff-mb because ExampleBin stays at "
            "the root of data/benchmark_bin/."
        )

    input_root = Path(args.input_root).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve()
    converter_script = Path(args.converter_script).expanduser().resolve()

    if not input_root.is_dir():
        parser.error(f"Input root directory does not exist: '{input_root}'")

    if args.processes < 1:
        parser.error("Number of worker processes must be at least 1")

    if not converter_script.is_file():
        parser.error(f"Converter script was not found: '{converter_script}'")

    try:
        tasks, empty_datasets = plan_conversion_tasks(
            input_root,
            output_root,
            dataset_names,
            args.cutoff_mb,
        )
    except ValueError as error:
        parser.error(str(error))

    if not tasks:
        parser.error(
            "No POD5 files were found for the requested dataset selection. "
            f"Checked datasets: {', '.join(dataset_names)}"
        )

    dataset_task_counts = Counter(task.dataset_name for task in tasks)
    print(
        f"Planned {len(tasks)} conversions across {len(dataset_task_counts)} dataset(s)."
    )
    for dataset_name in dataset_names:
        if dataset_name not in dataset_task_counts:
            continue
        output_dataset_root = build_output_dataset_root(output_root, dataset_name, args.cutoff_mb)
        output_dataset_label = str(output_dataset_root.relative_to(output_root))
        print(
            f"  {dataset_name} -> {output_dataset_label} "
            f"({dataset_task_counts[dataset_name]} files)"
        )

    if empty_datasets:
        print(
            "Skipped datasets with no POD5 files: "
            + ", ".join(empty_datasets)
        )

    if args.dry_run:
        return 0

    output_root.mkdir(parents=True, exist_ok=True)

    converted_count = 0
    skipped_count = 0
    worker = partial(
        run_conversion,
        converter_script=converter_script,
        overwrite=args.overwrite,
        cutoff_mb=args.cutoff_mb,
    )

    with ThreadPoolExecutor(max_workers=args.processes) as executor:
        for status, task in executor.map(worker, tasks):
            if status == "converted":
                converted_count += 1
                print(f"converted: {task.output_file}")
            else:
                skipped_count += 1
                print(f"skipped existing: {task.output_file}")

    print(
        f"Completed {converted_count} conversion(s); skipped {skipped_count} existing file(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())