import argparse
import csv
from datetime import datetime
import os
from pathlib import Path
import re
import sys
import subprocess

from common.cli import add_executable_argument, add_results_root_argument
from common.executables import resolve_named_executable
from common.runs import build_input_label, create_run_directories

def build_argument_parser():
    p = argparse.ArgumentParser(
        description="Run a benchmark to determine the percentage of time spent compressing / decompressing POD5 files"
    )

    p.add_argument("input_dir", nargs="?", help="Directory containing the input benchmark files")
    add_results_root_argument(p)
    add_executable_argument(p)

    return p

def parse_benchmark_output(output: str):
    total_time = re.search(r"Total elapsed time: ([\d.]+)s", output)
    proc_time = re.search(r"(?:Compression|Decompression) time: ([\d.]+)s", output)
    ratio = re.search(r"is ([\d.]+)%", output)
    # New: Extracts the interval count from the C++ log
    intervals = re.search(r"summed over (\d+) intervals", output)

    return {
        "total_s": float(total_time.group(1)) if total_time else 0.0,
        "proc_s": float(proc_time.group(1)) if proc_time else 0.0,
        "percentage": float(ratio.group(1)) if ratio else 0.0,
        "intervals": int(intervals.group(1)) if intervals else 0
    }

def pipeline(input_dir: str | Path, results_root=None, executable=None):
    if isinstance(input_dir, str):
        input_dir = Path(input_dir)
    benchmark_executable = resolve_named_executable("time_split_benchmark", executable)
    run_id = f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_{build_input_label(input_dir)}"
    run_root, raw_root, summaries_root = create_run_directories(
        results_root,
        run_id,
        benchmark_type="time_split",
    )


    csv_path = summaries_root / "pod5_benchmarks.csv"
    results = []

    for file in input_dir.glob("*.pod5"):
        if not file.is_file(): continue

        temp_out = raw_root / f"{file.stem}_out.pod5"

        # Execution
        c_proc = subprocess.run([str(benchmark_executable), "--compress", str(file), str(temp_out)], 
                                capture_output=True, text=True)
        c_proc.check_returncode()
        d_proc = subprocess.run([str(benchmark_executable), "--decompress", str(file)], 
                                capture_output=True, text=True)
        d_proc.check_returncode()

        # Parsing
        c_stats = parse_benchmark_output(c_proc.stdout)
        d_stats = parse_benchmark_output(d_proc.stdout)

        results.append({
            "filename": file.name,
            "comp_total_s": c_stats["total_s"],
            "comp_proc_s": c_stats["proc_s"],
            "comp_pct": c_stats["percentage"],
            "comp_intervals": c_stats["intervals"],
            "decomp_total_s": d_stats["total_s"],
            "decomp_proc_s": d_stats["proc_s"],
            "decomp_pct": d_stats["percentage"],
            "decomp_intervals": d_stats["intervals"]
        })

        if temp_out.exists(): temp_out.unlink()

    # Write single CSV
    if results:
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    return csv_path

def main(argv=None):
    parser = build_argument_parser()

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

    pipeline(
        args.input_dir,
        results_root=args.results_root,
        executable=args.executable,
    )

if __name__ == "__main__":
    raise SystemExit(main())