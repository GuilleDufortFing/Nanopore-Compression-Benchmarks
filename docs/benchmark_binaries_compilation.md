# Build Benchmark Binaries

This document covers compilation of the C++ benchmark binaries. Start with the repository checkout and `ncb-build` conda environment described in [README.md](../README.md), then return here to build the executables.

Compiled binaries are written to `build/bin/`. Benchmark runners look there first and fall back to the bundled layout at `pre-compiled-bins/linux-x86_64/<executable>/<executable>` only if no local build is present. Each bundled executable directory also contains a sibling `lib/` folder with its runtime dependencies. The only supported pre-compiled binary platform in this repository is `linux-x86_64`; macOS and any other platform should build the binaries locally.

---

## Shared preparation

From the repository root, generate the vendored POD5 version files before configuring CMake:

```sh
for pod5_dir in \
    src/libs/third_party/pod5-format-benchmark-fork \
    src/libs/third_party/pod5-time-split
do
    (
        cd "$pod5_dir"
        python -c 'from setuptools_scm import get_version; get_version(root=".", write_to="_version.py")'
        python -m pod5_make_version
    )
done
```

---

## Linux

Use these commands with the activated `ncb-build` environment from the README.

```sh
rm -rf build

cmake -S . -B build \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_PREFIX_PATH="$CONDA_PREFIX" \
    -DCMAKE_C_COMPILER="$CONDA_PREFIX/bin/x86_64-conda-linux-gnu-gcc" \
    -DCMAKE_CXX_COMPILER="$CONDA_PREFIX/bin/x86_64-conda-linux-gnu-g++"

cmake --build build -j
```


### Optional: build the standalone `copy` executable

This target is required for the memory benchmark and the copy appendix.

```sh
REPO_ROOT=$PWD

cd src/libs/third_party/Piecewise-Differential-Zstd-Coder-POD5-Demo/pod5
python -c 'from pathlib import Path; from setuptools_scm import get_version; get_version(root=Path.cwd(), search_parent_directories=True, write_to="_version.py")'
python -m pod5_make_version

cd ..
rm -rf build-copy
cmake -S . -B build-copy \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_PREFIX_PATH="$CONDA_PREFIX" \
    -DCMAKE_RUNTIME_OUTPUT_DIRECTORY="$REPO_ROOT/build/bin" \
    -DCMAKE_C_COMPILER="$CONDA_PREFIX/bin/x86_64-conda-linux-gnu-gcc" \
    -DCMAKE_CXX_COMPILER="$CONDA_PREFIX/bin/x86_64-conda-linux-gnu-g++"

cmake --build build-copy --target copy -j
cd ../../../..
```

### Optional: patch the binaries for older host glibc

If the host glibc is older than the conda sysroot, patch every executable under `build/bin/` to use the runtime from the active environment:

```sh
for binary in build/bin/*; do
    [ -f "$binary" ] || continue
    patchelf \
        --set-interpreter "$CONDA_PREFIX/x86_64-conda-linux-gnu/sysroot/lib64/ld-linux-x86-64.so.2" \
        --force-rpath \
        --set-rpath "$CONDA_PREFIX/lib:$CONDA_PREFIX/x86_64-conda-linux-gnu/sysroot/lib64:$CONDA_PREFIX/x86_64-conda-linux-gnu/sysroot/usr/lib64" \
        "$binary"
done
```

---

## macOS

Use these commands with the activated `ncb-build` environment from the README.

```sh
rm -rf build

cmake -S . -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_PREFIX_PATH="$CONDA_PREFIX" \
    -DZLIB_ROOT="$CONDA_PREFIX"

cmake --build build -j
```

If the conda activation hooks export `CC` and `CXX`, you can make the compiler selection explicit by adding `-DCMAKE_C_COMPILER="$CC"` and `-DCMAKE_CXX_COMPILER="$CXX"` to the configure command.

### Notes for Apple Silicon and Intel Macs

- The `c-compiler` and `cxx-compiler` packages from the README environment resolve to the correct toolchain for the active architecture.
- Native builds use the host architecture by default. Leave `CMAKE_OSX_ARCHITECTURES` unset unless you are intentionally cross-compiling.
- Delete `build/` before reconfiguring if you switch architectures, compiler roots, or dependency prefixes.

### Troubleshooting

- **`Could NOT find ZLIB`**: confirm `zlib` is installed in the active environment and rerun configure with `-DZLIB_ROOT="$CONDA_PREFIX"`.
- **Missing Arrow, Flatbuffers, or zstd**: confirm those packages are installed and keep `-DCMAKE_PREFIX_PATH="$CONDA_PREFIX"` in the configure command.
- **Benchmark script cannot find the binary**: verify the executable exists under `build/bin/`, or under the matching bundled fallback directory `pre-compiled-bins/linux-x86_64/<executable>/<executable>`. If you are not on `linux-x86_64`, build the binaries locally instead of relying on `pre-compiled-bins/`.
