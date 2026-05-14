# Running Benchmarks

This document describes how to run each benchmark type after following the repository and environment setup in [README.md](../README.md). All Python runners write their outputs under `results/generated/<benchmark-type>/` by default.

Binary resolution follows one repository-wide rule: check `build/bin/` first, then the bundled fallback at `pre-compiled-bins/linux-x86_64/<executable>/<executable>`. Each pre-compiled executable lives in its own bundle directory alongside a `lib/` folder. The only supported pre-compiled binary platform in this repository is `linux-x86_64`; on any other platform, build the binaries locally as described in [benchmark_binaries_compilation.md](benchmark_binaries_compilation.md).

---

## Speed benchmark

The speed benchmark measures compression and decompression throughput in MB/s on `.bin` input files.

**Direct executable:**

```sh
./build/bin/speed_benchmark --in=INPUT_FILE --out=RESULT.csv --alg=EX-ZD-ZSTD
```

**Python runner (single algorithm):**

```sh
python scripts/benchmarks/run_speed_benchmark.py \
    data/benchmark_bin/full/DS1 \
    EX-ZD-ZSTD
```

**Python runner (full algorithm suite):**

```sh
python scripts/benchmarks/run_speed_benchmark.py \
    data/benchmark_bin/full/DS1 \
    VBZ EX-ZD EX-ZD-ZLIB EX-ZD-ZSTD CA PDZSerial PDZ
```

The runner creates a unique run directory under `results/generated/speed/<timestamp>_<algorithms>_<input>/`, with raw per-algorithm CSVs in `raw/` and derived summaries in `summaries/`. The speed runner stays serialized because it measures runtime; do not use `-j`.

---

## Compression benchmark

The compression benchmark measures bits-per-sample and correctness on `.bin` input files.

**Direct executable:**

```sh
./build/bin/compression_benchmark --in=INPUT_FILE --out=RESULT.csv --alg=EX-ZD-ZSTD
```

**Python runner (single algorithm):**

```sh
python scripts/benchmarks/run_compression_benchmark.py \
    data/benchmark_bin/ExampleBin \
    EX-ZD-ZSTD
```

**Python runner (full algorithm suite):**

```sh
python scripts/benchmarks/run_compression_benchmark.py \
    data/benchmark_bin/full/DS1 \
    VBZ EX-ZD EX-ZD-ZLIB EX-ZD-ZSTD CA PDZSerial PDZ
```

**Parallel file processing** (useful for large datasets):

```sh
python scripts/benchmarks/run_compression_benchmark.py \
    data/benchmark_bin/full/DS1 \
    VBZ EX-ZD-ZSTD PDZ \
    --jobs 4
```

`-j/--jobs` controls how many `.bin` files are processed in parallel for each algorithm. The default is `1`.

Output goes to `results/generated/compression/<timestamp>_<algorithms>_<input>/`, with raw per-file CSVs in `raw/` and summaries in `summaries/`.

---

## Memory benchmark

The memory benchmark measures peak RSS (resident set size) during compression and decompression of POD5 files. It is **Linux-only** because it relies on `/usr/bin/time`.

It requires the standalone `copy` executable. Build it using the optional target in [benchmark_binaries_compilation.md](benchmark_binaries_compilation.md).

**Default run (VBZ and PDZ):**

```sh
python scripts/benchmarks/run_memory_benchmark.py \
    data/pod5/ExamplePod5
```

**Explicit algorithm subset with repeated measurements:**

```sh
python scripts/benchmarks/run_memory_benchmark.py \
    data/pod5/DS2 \
    PDZ \
    --repetitions 3
```

Optional algorithm names are positional arguments placed after `input_dir`. If you omit them, the runner defaults to `VBZ` and `PDZ`.

The measured workflow is:

1. **Unmeasured setup**: convert input → VBZ/PDZ POD5
2. **Measured stage 1**: VBZ/PDZ → uncompressed
3. **Measured stage 2**: uncompressed → VBZ/PDZ

Output goes to `results/generated/memory/<timestamp>_<algorithms>_<input>/`, with raw measurements in `raw/memory_measurements.csv` and stage-level summaries in `summaries/`.

Use `--keep-intermediates` to preserve the temporary POD5 files under `raw/intermediates/`. Use `--executable` if the `copy` binary is not under `build/bin/`.

---

## Size-split benchmark

The size-split benchmark analyses POD5 files to measure what fraction of each file is occupied by compressed signal data versus the signal table overhead versus the rest of the file. It takes POD5 files as input (not `.bin`).

```sh
python scripts/benchmarks/run_size_split_benchmark.py \
    data/pod5/DS2
```

Output goes to `results/generated/size_split/<timestamp>_<input>/summaries/pod5_size_summaries.csv`.

---

## Time-split benchmark

The time-split benchmark measures what fraction of total compression/decompression time is spent on signal processing versus everything else. It uses the `time_split_benchmark` C++ executable and takes POD5 files as input.

```sh
python scripts/benchmarks/run_time_split_benchmark.py \
    data/pod5/DS2
```

Output goes to `results/generated/time_split/<timestamp>_<input>/summaries/pod5_benchmarks.csv`.

---

## Tutorial notebook

For a small end-to-end example covering dataset download, all four benchmark types, and result plotting, open `notebooks/example_full_pipeline_tutorial.ipynb`.

If you created the `ncb-build` environment from [README.md](../README.md), the remaining prerequisite is compiling the benchmark binaries so that `build/bin/speed_benchmark` is present:

```sh
conda activate ncb-build
jupyter lab notebooks/example_full_pipeline_tutorial.ipynb
```
