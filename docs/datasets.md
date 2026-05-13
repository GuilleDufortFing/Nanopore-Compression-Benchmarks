# Datasets

This document covers how to download the POD5 input datasets and how to generate the `.bin` benchmark files from them.

---

## POD5 datasets

The POD5 datasets (`DS1`–`DS10` and `ExamplePod5`) live under `data/pod5/`. They are not versioned in git; you download them locally with the provided script.

### Dependencies

#### AWS CLI (required for DS1–DS5 and the example file)

Datasets DS1–DS5 and the `example` file are hosted on public AWS S3. Downloading them requires the **AWS CLI** (`aws`). No credentials are needed. All requests use `--no-sign-request`.

```sh
conda install -c conda-forge awscli
```

Official installer: <https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html>

#### wget (required for DS6–DS10)

Datasets DS6–DS10 are fetched over HTTPS using `wget`.

```sh
conda install -c conda-forge wget
```

#### BLOW5 Python packages (required for DS6 and DS10)

Some datasets are distributed in BLOW5 format and must be converted to POD5 after download. The conversion script (`scripts/utils/blow5_to_pod5.py`) requires two Python packages:

```sh
pip install pyslow5 pod5
```

These are only needed for datasets that include a BLOW5-to-POD5 conversion step (currently DS6 and DS10).

### Download all datasets

```sh
python data/pod5/download_dataset.py --dataset all
```

### Download a single dataset

```sh
python data/pod5/download_dataset.py --dataset DS7
```

### Preview without writing files

```sh
python data/pod5/download_dataset.py --dataset all --dry-run
```

`--dry-run` prints the planned download and conversion steps without creating any files.

---

## Generating `.bin` benchmark files

The `.bin` format is what the C++ speed and compression benchmarks consume. The script `scripts/utils/build_computational_efficiency_datasets.py` mirrors one or more POD5 datasets into `.bin` files by invoking `scripts/utils/pod5_to_benchmark_time.py` for every discovered `.pod5` file.

Output is written under `data/benchmark_bin/<layer>/<dataset>`, where `<layer>` is:

- `full`: when no size cutoff is requested (default)
- a numeric MB value (e.g. `200`): when `--cutoff-mb` is used

`ExamplePod5` is a special case: it always maps to `data/benchmark_bin/ExampleBin` (no layer subdirectory).

### Generate the full mirror for all datasets (DS1–DS10)

```sh
python scripts/utils/build_computational_efficiency_datasets.py
```

Output goes to `data/benchmark_bin/full/DS1` through `data/benchmark_bin/full/DS10`.

### Generate with a size cutoff

```sh
python scripts/utils/build_computational_efficiency_datasets.py --cutoff-mb 200
```

Each output `.bin` file is truncated at the requested size. Output goes to `data/benchmark_bin/200/DS1` through `data/benchmark_bin/200/DS10`.

### Regenerate a specific dataset

```sh
python scripts/utils/build_computational_efficiency_datasets.py DS7 --overwrite
```

Without `--overwrite`, already-existing output files are skipped.

### Regenerate the example dataset only

```sh
python scripts/utils/build_computational_efficiency_datasets.py ExamplePod5 --overwrite
```

### Process a subset of datasets in parallel

```sh
python scripts/utils/build_computational_efficiency_datasets.py DS1 DS2 DS3 -p 8
```

`-p` controls how many files are converted in parallel (default: up to 4, capped at CPU count).

### Process only specific datasets with a cutoff

```sh
python scripts/utils/build_computational_efficiency_datasets.py DS1 DS2 --cutoff-mb 1000
```

---

## Data layout summary

```
data/
  pod5/
    DS1/ … DS10/       ← downloaded POD5 files
    ExamplePod5/        ← small curated example
  benchmark_bin/
    ExampleBin/         ← .bin files for ExamplePod5 (no layer)
    full/
      DS1/ … DS10/      ← full .bin mirrors
    200/
      DS1/ … DS10/      ← 200 MB cutoff .bin mirrors (if generated)
```

Downloaded datasets should not be committed to git. Only the download scripts and small curated examples are version-controlled.
