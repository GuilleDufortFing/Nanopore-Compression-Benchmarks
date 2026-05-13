#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import pod5


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_ROOT = REPO_ROOT / "data" / "pod5"
DEFAULT_DATASETS = tuple(f"DS{index}" for index in range(1, 11))
POD5_SUFFIX = ".pod5"

PORE_FAMILY_PATTERNS = (
    (re.compile(r"RNA\s*0*04", re.IGNORECASE), "RNA004"),
    (re.compile(r"R10\.4\.1", re.IGNORECASE), "R10.4.1"),
    (re.compile(r"R10\.4", re.IGNORECASE), "R10.4"),
    (re.compile(r"R10\.3\.1", re.IGNORECASE), "R10.3.1"),
    (re.compile(r"R10\.3", re.IGNORECASE), "R10.3"),
    (re.compile(r"R9\.4\.1", re.IGNORECASE), "R9.4.1"),
    (re.compile(r"R9\.4", re.IGNORECASE), "R9.4"),
)


@dataclass
class DatasetSummary:
    dataset_name: str
    pod5_file_count: int
    total_bytes: int
    total_gib: float
    read_count: int
    sample_count: int
    pore_types: list[str]
    technology_labels: list[str]
    flow_cell_product_codes: list[str]
    sequencing_kits: list[str]
    sample_rates_hz: list[int]
    digitisation_values: list[int]
    bit_resolution_bits: list[int]
    uniform_pore_type: bool
    uniform_technology_label: bool
    uniform_sample_rate: bool
    uniform_digitisation: bool

    def to_csv_row(self) -> dict[str, object]:
        return {
            "dataset_name": self.dataset_name,
            "pod5_file_count": self.pod5_file_count,
            "total_bytes": self.total_bytes,
            "total_gib": f"{self.total_gib:.3f}",
            "read_count": self.read_count,
            "sample_count": self.sample_count,
            "pore_types": ";".join(self.pore_types),
            "technology_labels": ";".join(self.technology_labels),
            "flow_cell_product_codes": ";".join(self.flow_cell_product_codes),
            "sequencing_kits": ";".join(self.sequencing_kits),
            "sample_rates_hz": ";".join(str(value) for value in self.sample_rates_hz),
            "digitisation_values": ";".join(str(value) for value in self.digitisation_values),
            "bit_resolution_bits": ";".join(str(value) for value in self.bit_resolution_bits),
            "uniform_pore_type": self.uniform_pore_type,
            "uniform_technology_label": self.uniform_technology_label,
            "uniform_sample_rate": self.uniform_sample_rate,
            "uniform_digitisation": self.uniform_digitisation,
        }


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize one or more POD5 datasets into supplementary-ready metadata, "
            "including file count, total size, pore metadata, sample rates, and "
            "digitisation-derived bit resolution."
        ),
        epilog=(
            "Examples:\n"
            "  python scripts/utils/summarize_pod5_datasets.py\n"
            "  python scripts/utils/summarize_pod5_datasets.py DS7 DS10 --output-csv results/generated/dataset_metadata/datasets.csv\n"
            "  python scripts/utils/summarize_pod5_datasets.py --output-json results/generated/dataset_metadata/datasets.json"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
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
        help=f"Root directory containing POD5 datasets (default: {DEFAULT_INPUT_ROOT})",
    )
    parser.add_argument(
        "--output-csv",
        default=None,
        help="Optional path for a CSV summary artifact.",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional path for a JSON summary artifact.",
    )
    return parser


def normalize_dataset_selection(dataset_tokens: list[str]) -> list[str]:
    if not dataset_tokens:
        return list(DEFAULT_DATASETS)

    selected: list[str] = []
    seen: set[str] = set()
    for token in dataset_tokens:
        for dataset_name in (part.strip() for part in token.split(",")):
            if not dataset_name or dataset_name in seen:
                continue
            selected.append(dataset_name)
            seen.add(dataset_name)

    if not selected:
        raise ValueError("No dataset names were provided")

    return selected


def iter_pod5_files(dataset_root: Path):
    for root, _, files in os.walk(dataset_root):
        for file_name in sorted(files):
            file_path = Path(root) / file_name
            if file_path.is_file() and file_path.suffix.lower() == POD5_SUFFIX:
                yield file_path


def normalize_pore_family(pore_type: str) -> str:
    cleaned = pore_type.strip()
    if not cleaned:
        return "unknown"

    for pattern, label in PORE_FAMILY_PATTERNS:
        if pattern.search(cleaned):
            return label

    return cleaned


def infer_technology_label(
    pore_type: str,
    flow_cell_product_code: str,
    sequencing_kit: str,
    protocol_name: str,
    basecall_config_filename: str,
) -> str:
    candidate_text = " ".join(
        value.strip()
        for value in [
            pore_type,
            flow_cell_product_code,
            sequencing_kit,
            protocol_name,
            basecall_config_filename,
        ]
        if value
    )

    if not candidate_text:
        return "unknown"

    normalized = candidate_text.upper()
    if "RNA004" in normalized or "PRO004RA" in normalized:
        return "RNA004"
    if "R10.4.1" in normalized or any(token in normalized for token in ["MIN114", "PRO114", "LSK114", "NBD114", "RBK114"]):
        return "R10.4.1"
    if "R10.3" in normalized or any(token in normalized for token in ["MIN111", "PRO111"]):
        return "R10.3"
    if "R9.4.1" in normalized or any(token in normalized for token in ["MIN106", "PRO001", "PRO002"]):
        return "R9.4.1"

    return normalize_pore_family(pore_type)


def digitisation_to_bits(digitisation: int) -> int | None:
    if digitisation <= 0:
        return None

    if digitisation & (digitisation - 1):
        return None

    return int(math.log2(digitisation))


def summarize_dataset(dataset_name: str, input_root: Path) -> DatasetSummary:
    dataset_root = input_root / dataset_name
    if not dataset_root.is_dir():
        raise FileNotFoundError(f"Dataset directory does not exist: {dataset_root}")

    pod5_files = list(iter_pod5_files(dataset_root))
    if not pod5_files:
        raise FileNotFoundError(f"No POD5 files were found under: {dataset_root}")

    total_bytes = 0
    read_count = 0
    sample_count = 0
    pore_types: set[str] = set()
    technology_labels: set[str] = set()
    flow_cell_product_codes: set[str] = set()
    sequencing_kits: set[str] = set()
    sample_rates_hz: set[int] = set()
    digitisation_values: set[int] = set()
    bit_resolution_bits: set[int] = set()

    for pod5_file in pod5_files:
        total_bytes += pod5_file.stat().st_size
        with pod5.Reader(pod5_file) as reader:
            for read in reader.reads():
                read_count += 1
                sample_count += int(read.num_samples)

                pore_type = str(read.pore.pore_type).strip() or "unknown"
                pore_types.add(pore_type)

                flow_cell_product_code = str(read.run_info.flow_cell_product_code).strip()
                sequencing_kit = str(read.run_info.sequencing_kit).strip()
                protocol_name = str(read.run_info.protocol_name).strip()
                context_tags = dict(read.run_info.context_tags)
                basecall_config_filename = str(context_tags.get("basecall_config_filename", "")).strip()

                if flow_cell_product_code:
                    flow_cell_product_codes.add(flow_cell_product_code)
                if sequencing_kit:
                    sequencing_kits.add(sequencing_kit)

                technology_labels.add(
                    infer_technology_label(
                        pore_type=pore_type,
                        flow_cell_product_code=flow_cell_product_code,
                        sequencing_kit=sequencing_kit,
                        protocol_name=protocol_name,
                        basecall_config_filename=basecall_config_filename,
                    )
                )

                sample_rate = int(read.run_info.sample_rate)
                sample_rates_hz.add(sample_rate)

                digitisation = int(read.calibration_digitisation)
                digitisation_values.add(digitisation)
                bit_resolution = digitisation_to_bits(digitisation)
                if bit_resolution is not None:
                    bit_resolution_bits.add(bit_resolution)

    sorted_pore_types = sorted(pore_types)
    sorted_technology_labels = sorted(technology_labels)
    sorted_flow_cell_product_codes = sorted(flow_cell_product_codes)
    sorted_sequencing_kits = sorted(sequencing_kits)
    sorted_sample_rates_hz = sorted(sample_rates_hz)
    sorted_digitisation_values = sorted(digitisation_values)
    sorted_bit_resolution_bits = sorted(bit_resolution_bits)

    return DatasetSummary(
        dataset_name=dataset_name,
        pod5_file_count=len(pod5_files),
        total_bytes=total_bytes,
        total_gib=total_bytes / (1024 ** 3),
        read_count=read_count,
        sample_count=sample_count,
        pore_types=sorted_pore_types,
        technology_labels=sorted_technology_labels,
        flow_cell_product_codes=sorted_flow_cell_product_codes,
        sequencing_kits=sorted_sequencing_kits,
        sample_rates_hz=sorted_sample_rates_hz,
        digitisation_values=sorted_digitisation_values,
        bit_resolution_bits=sorted_bit_resolution_bits,
        uniform_pore_type=len(sorted_pore_types) == 1,
        uniform_technology_label=len(sorted_technology_labels) == 1,
        uniform_sample_rate=len(sorted_sample_rates_hz) == 1,
        uniform_digitisation=len(sorted_digitisation_values) == 1,
    )


def write_csv(output_path: Path, summaries: list[DatasetSummary]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [summary.to_csv_row() for summary in summaries]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(output_path: Path, summaries: list[DatasetSummary]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump([asdict(summary) for summary in summaries], handle, indent=2)
        handle.write("\n")


def print_csv_stdout(summaries: list[DatasetSummary]) -> None:
    writer = csv.DictWriter(sys.stdout, fieldnames=list(summaries[0].to_csv_row().keys()))
    writer.writeheader()
    for summary in summaries:
        writer.writerow(summary.to_csv_row())


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    try:
        dataset_names = normalize_dataset_selection(args.datasets)
    except ValueError as error:
        parser.error(str(error))

    input_root = Path(args.input_root).expanduser().resolve()
    if not input_root.is_dir():
        parser.error(f"Input root does not exist: {input_root}")

    summaries = [summarize_dataset(dataset_name, input_root) for dataset_name in dataset_names]

    if args.output_csv:
        write_csv(Path(args.output_csv).expanduser().resolve(), summaries)

    if args.output_json:
        write_json(Path(args.output_json).expanduser().resolve(), summaries)

    if not args.output_csv and not args.output_json:
        print_csv_stdout(summaries)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())