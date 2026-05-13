# Nanopore Compression Benchmarks

This repository contains the benchmark suite used to produce the results reported in:

> **Efficient lossless compression of nanopore sequencing signals**
>
> Authors: Rafael Castelli, Tomás González, Rodrigo Torrado, Álvaro Martín, Guillermo Dufort y Álvarez

## Overview

This repository benchmarks lossless compression of nanopore raw signal data stored in POD5. The paper focuses on [VBZ (POD5)](https://github.com/nanoporetech/pod5-file-format), [EX-ZD-ZSTD (slow5lib)](https://github.com/hasindu2008/slow5lib), and [PDZ](https://github.com/Rafael-Cast/Piecewise-Differential-Zstd-Coder-POD5-Demo); the repository also contains the workflows used to generate, aggregate, and analyse the benchmark outputs.

The suite measures compression ratio (bits per sample), throughput (MB/s for compression and decompression), peak memory usage, and POD5 size/time split analyses across ten datasets (`DS1`–`DS10`).

## Recommended Setup

Use this setup once, then choose one of the three workflows below.

### 1. Clone the repository

```sh
git clone git@github.com:GuilleDufortFing/Nanopore-Compression-Benchmarks.git
cd Nanopore-Compression-Benchmarks
git submodule update --init --recursive
```

### 2. Install Conda if needed

To install Conda, we recommend **Miniconda**. It is the lightest supported path for creating the `ncb-build` environment used throughout this repository.

- Miniconda installation guide: <https://www.anaconda.com/docs/getting-started/miniconda/install>

### 3. Create the base `ncb-build` conda environment

#### Linux

```sh
conda create -y -n ncb-build -c conda-forge -c defaults \
python=3.10 \
cmake=3.26 \
make=4.3 \
libgcc-ng=13.1.0 \
libstdcxx-ng=12.3.0 \
gxx_linux-64=12.3.0 \
gcc_linux-64=12.3.0 \
sysroot_linux-64=2.39 \
ld_impl_linux-64 \
flatbuffers=2 \
arrow-cpp=8 \
boost-cpp \
zlib \
zstd \
gsl \
setuptools_scm=7.1 \
setuptools=68 \
patchelf
```

#### macOS

```sh
conda create -y -n ncb-build -c conda-forge \
python=3.10 \
cmake=3.26 \
ninja \
pkg-config \
c-compiler \
cxx-compiler \
flatbuffers=2 \
arrow-cpp=8 \
boost-cpp \
zlib \
zstd \
gsl \
setuptools_scm=7.1 \
setuptools=68
```

### 4. Install the shared Python packages

After creating the base environment on Linux or macOS, activate it and install the Python packages used by the notebooks and dataset tooling:

```sh
conda activate ncb-build
conda install -y -c conda-forge \
numpy \
pandas \
matplotlib \
seaborn \
scipy \
ipykernel \
jupyterlab \
awscli

python -m pip install pod5
```

## Choose a Workflow

### 1. Reproduce the article figures and tables from committed results

Open [notebooks/replicate_article_figures_and_tables.ipynb](notebooks/replicate_article_figures_and_tables.ipynb). It reads the curated summaries already stored under `results/article/`, so it does not require dataset downloads or a local benchmark build.

```sh
conda activate ncb-build
jupyter lab notebooks/replicate_article_figures_and_tables.ipynb
```

### 2. Run a small end-to-end example

Build the benchmark binaries first by following [docs/benchmark_binaries_compilation.md](docs/benchmark_binaries_compilation.md), then open [notebooks/example_full_pipeline_tutorial.ipynb](notebooks/example_full_pipeline_tutorial.ipynb).

The notebook uses the same `ncb-build` environment, downloads the curated `ExamplePod5` input automatically, and runs compression, speed, size-split, and time-split on a single example file.

```sh
conda activate ncb-build
jupyter lab notebooks/example_full_pipeline_tutorial.ipynb
```

### 3. Reproduce the full experiments from the paper

Follow [docs/replicating-paper-results.md](docs/replicating-paper-results.md). That workflow starts from the repository checkout and `ncb-build` environment above, then adds binary compilation, full dataset download, `.bin` generation, benchmark execution, and result promotion into `results/article/`.

Dataset-specific download and conversion tools, including `wget` and `pyslow5` where needed, are documented in [docs/datasets.md](docs/datasets.md).

## Documentation

- [docs/benchmark_binaries_compilation.md](docs/benchmark_binaries_compilation.md): build the C++ benchmark binaries and the optional `copy` executable on Linux and macOS.
- [docs/datasets.md](docs/datasets.md): download the POD5 datasets and generate the `.bin` benchmark inputs consumed by the C++ executables.
- [docs/running-benchmarks.md](docs/running-benchmarks.md): run each benchmark individually (compression, speed, memory, size-split, and time-split) and inspect the generated outputs.
- [docs/replicating-paper-results.md](docs/replicating-paper-results.md): execute the end-to-end pipeline used for the paper.

## Repository layout

- `src/`: C++ benchmarks and vendored dependencies.
- `build/bin/`: locally built executables.
- `pre-compiled-bins/`: fallback binaries bundled only for `linux-x86_64`, organized as `linux-x86_64/<executable>/<executable>` plus `lib/`.
- `scripts/benchmarks/`: Python runners and analysis helpers.
- `docs/`: build, dataset, benchmark, and replication instructions.
- `notebooks/`: article-analysis and tutorial notebooks.
- `data/pod5/`: downloaded POD5 inputs.
- `data/benchmark_bin/`: generated `.bin` benchmark inputs.
- `results/article/`: curated results committed for article analysis.
- `results/generated/`: default destination for locally generated benchmark runs.

## Acknowledgements

This repository vendors several third-party libraries under `src/libs/`. Their roles in this benchmark suite and their upstream licenses are listed below.

| Library | License |
| --- | --- |
| [slow5lib](https://github.com/hasindu2008/slow5lib) | MIT |
| [pod5-format](https://github.com/nanoporetech/pod5-file-format) (benchmark fork and time-split variant) | MPL-2.0 |

| Submodule path | Description |
| --- | --- |
| `src/libs/lib-682-nanopore-compression` | Core implementation of the PDZ (682) codec with SIMD acceleration |
| `src/libs/third_party/pod5-format-benchmark-fork` | Fork of the Oxford Nanopore POD5 library with benchmark-specific modifications |
| `src/libs/third_party/pod5-time-split` | POD5 variant that splits signals by time; used in the time-split benchmark |
| `src/libs/third_party/slow5lib` | Provides the EX-ZD transform used by the EX-ZD baselines |
| `src/libs/third_party/Piecewise-Differential-Zstd-Coder-POD5-Demo` | Standalone PDZ POD5 plugin; built separately to produce the `copy` binary required by the memory benchmark |

## License

This repository is released under the MIT License. See [LICENSE.md](LICENSE.md).
