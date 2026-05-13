# Replicating Paper Results

This document describes the end-to-end pipeline used to produce the article results. Start with the repository checkout and `ncb-build` conda environment in [README.md](../README.md), then build the benchmark binaries as described in [benchmark_binaries_compilation.md](benchmark_binaries_compilation.md) before running the steps below.

The pipeline produces results for four benchmark types:

| Benchmark | Datasets | Platform |
| --- | --- | --- |
| Compression | DS1–DS10 (full) | Linux or macOS |
| Speed | DS1–DS10 (first file per dataset, ≤ ~200 MB each) | any machine, repeated per machine |
| Memory | DS2, DS7 | Linux only |
| Size-split + Time-split | DS2, DS7 | Linux or macOS |

---

## Step 1: Download all datasets

```sh
python data/pod5/download_dataset.py --dataset all
```

This populates `data/pod5/DS1` through `data/pod5/DS10`. Add `--dry-run` to preview without writing files.

---

## Step 2: Generate full `.bin` files

```sh
python scripts/utils/build_computational_efficiency_datasets.py
```

This mirrors all POD5 datasets into `.bin` format under `data/benchmark_bin/full/DS1` through `data/benchmark_bin/full/DS10`. These are used for the compression benchmark.

---

## Step 3: Prepare the speed benchmark dataset

The speed benchmark uses a smaller variant: the first `.bin` file from each dataset, capped at roughly 200 MB total per dataset. There is no automated script for this step. It was assembled manually.

For each dataset `DS1`–`DS10`:

1. Look inside `data/benchmark_bin/full/DSN/`.
2. Take only the **first** `.bin` file (alphabetically or by acquisition order, whichever was used originally).
3. Place it in a dedicated directory, for example `data/benchmark_bin/speed_dataset/DSN/`.

The resulting directory structure should mirror the full layout but contain only one file per dataset. This directory is what you pass to `run_speed_benchmark.py` for each machine.

---

## Step 4: Run the compression benchmark (DS1–DS10)

Run this once (on any machine). Algorithms used in the paper: `VBZ`, `EX-ZD-ZSTD`, `PDZ`.

```sh
for ds in DS1 DS2 DS3 DS4 DS5 DS6 DS7 DS8 DS9 DS10; do
    python scripts/benchmarks/run_compression_benchmark.py \
        data/benchmark_bin/full/$ds \
        VBZ EX-ZD-ZSTD PDZ \
        --jobs 4
done
```

Each run writes to `results/generated/compression/<run-id>/`. The run ID encodes the timestamp, algorithms, and dataset name.

---

## Step 5: Run the speed benchmark (per machine)

Run this on **each machine** you want to include. Pass the speed dataset directory prepared in Step 3.

```sh
python scripts/benchmarks/run_speed_benchmark.py \
    data/benchmark_bin/speed_dataset/DS1 \
    VBZ EX-ZD-ZSTD PDZ
```

Repeat for DS2–DS10. Each run writes to `results/generated/speed/<run-id>/`.

The article uses results from multiple machines. Collect the run directories from each machine and transfer them to the repository for analysis.

---

## Step 6: Run the memory benchmark (DS2 and DS7, Linux only)

The memory benchmark requires the `copy` executable built from the optional target in [benchmark_binaries_compilation.md](benchmark_binaries_compilation.md) and runs only on Linux.

```sh
python scripts/benchmarks/run_memory_benchmark.py \
  data/pod5/DS2 \
    VBZ PDZ

python scripts/benchmarks/run_memory_benchmark.py \
  data/pod5/DS7 \
    VBZ PDZ
```

Each run writes to `results/generated/memory/<run-id>/`.

---

## Step 7: Run the size-split and time-split benchmarks (DS2 and DS7)

**Size-split:**

```sh
python scripts/benchmarks/run_size_split_benchmark.py data/pod5/DS2
python scripts/benchmarks/run_size_split_benchmark.py data/pod5/DS7
```

**Time-split:**

```sh
python scripts/benchmarks/run_time_split_benchmark.py data/pod5/DS2
python scripts/benchmarks/run_time_split_benchmark.py data/pod5/DS7
```

Each run writes to `results/generated/size_split/<run-id>/` and `results/generated/time_split/<run-id>/` respectively.

---

## Step 8: Copy summaries into results/article/

The `results/article/` directory holds only the **summary** CSVs from each curated run. Raw per-file results are not committed because there are too many of them.

For each benchmark run you want to promote, copy the `summaries/` subfolder from `results/generated/<benchmark-type>/<run-id>/` into the corresponding path under `results/article/<benchmark-type>/<run-id>/summaries/`. Copy `run_manifest.json` as well for runners that emit one.

The expected layout under `results/article/` is:

```text
results/article/
  compression/
    <run-id>/
      summaries/
      run_manifest.json
  speed/
    <machine-name>/
      <run-id>/
        summaries/
        run_manifest.json
  memory/
    <run-id>/
      summaries/
      run_manifest.json
  size_split/
    <run-id>/
      summaries/
  time_split/
    <run-id>/
      summaries/
```

---

## Step 9: Run the analysis notebook

Open `notebooks/replicate_article_figures_and_tables.ipynb` and update the run ID constants at the top of each section to point to the run IDs you just promoted into `results/article/`.

Then run all cells in order. The notebook produces:

- Compression ratio tables and a LaTeX table under `notebooks/outputs/article_results/compression/`
- Speed comparison plots and summary tables
- Memory peak RSS plots
- Size-split and time-split decomposition plots

All exported figures are written as PDF files under `notebooks/outputs/article_results/`.
