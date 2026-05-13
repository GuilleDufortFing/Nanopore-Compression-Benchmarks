import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

import pod5
from dataclasses import dataclass

from common.cli import add_results_root_argument
from common.runs import build_input_label, create_run_directories

@dataclass()
class UsagePercentSummary:
    total_bytes: int
    uncompressed_signal_bytes: int
    compressed_signal_bytes: int
    rows: int
    
    def __post_init__(self):
        self.total_signal_table_bytes: int = self.compressed_signal_bytes + 4 * self.rows + 16 * self.rows
        self.samples_percentage: float = self.compressed_signal_bytes / self.total_bytes if self.total_bytes > 0 else 0.0
        self.signal_table_percentage: float = self.total_signal_table_bytes / self.total_bytes if self.total_bytes > 0 else 0.0

def get_file_percent_summary(file: Path | str) -> UsagePercentSummary:
    rows = 0
    samples = 0
    compressed_bytes = 0
    with pod5.Reader(file) as r:
        for read in r.reads():
            compressed_bytes += read.byte_count
            samples += read.num_samples
            rows += len(read.signal_rows)
    total_bytes = os.stat(file).st_size
    return UsagePercentSummary(
        total_bytes=total_bytes,
        uncompressed_signal_bytes=samples * 2,
        compressed_signal_bytes=compressed_bytes,
        rows=rows
    )

def build_argument_parser():
    p = argparse.ArgumentParser(
        description="Analyze POD5 files to determine signal and table size percentages"
    )
    p.add_argument("input_dir", help="Directory containing the input POD5 files")
    add_results_root_argument(p)
    return p

def pipeline(input_dir: str | Path, results_root=None):
    if isinstance(input_dir, str):
        input_dir = Path(input_dir)
        
    run_id = f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_{build_input_label(input_dir)}"
    run_root, _, summaries_root = create_run_directories(
        results_root,
        run_id,
        benchmark_type="size_split",
    )

    csv_path = summaries_root / "pod5_size_summaries.csv"
    results = []

    for file in input_dir.glob("*.pod5"):
        if not file.is_file():
            continue

        stats = get_file_percent_summary(file)

        results.append({
            "filename": file.name,
            "total_bytes": stats.total_bytes,
            "uncompressed_signal_bytes": stats.uncompressed_signal_bytes,
            "compressed_signal_bytes": stats.compressed_signal_bytes,
            "total_signal_table_bytes": stats.total_signal_table_bytes,
            "samples_pct": stats.samples_percentage,
            "signal_table_pct": stats.signal_table_percentage,
            "rows": stats.rows
        })

    if results:
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    return csv_path

def main(argv=None):
    parser = build_argument_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if not os.path.isdir(args.input_dir):
        parser.error(f"Input directory does not exist: '{args.input_dir}'")

    output_csv = pipeline(args.input_dir, results_root=args.results_root)
    print(f"Summary written to: {output_csv}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())