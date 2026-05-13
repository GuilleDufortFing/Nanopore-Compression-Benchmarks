#!/bin/bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate PDZ

# Prerequisites for pod5 libraries
cd src/libs/third_party/pod5-format-benchmark-fork
python -c 'from pathlib import Path; from setuptools_scm import get_version; get_version(root=Path.cwd(), search_parent_directories=True, write_to="_version.py")'
python -m pod5_make_version
cd ../pod5-time-split
python -c 'from pathlib import Path; from setuptools_scm import get_version; get_version(root=Path.cwd(), search_parent_directories=True, write_to="_version.py")'
python -m pod5_make_version
cd ../../../../

# benchmarks
rm -rf build
mkdir -p build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DBUILD_BUNDLED=true
make -j
cd ..

rm -rf /builder/artifacts/*
mkdir -p /builder/artifacts
cd artifacts

for bin in compression_benchmark speed_benchmark time_split_benchmark; do
    DEST="/builder/artifacts/$bin"
    mkdir -p "$DEST/lib"
    
    cp "/builder/build/bin/$bin" "$DEST/"
    
    # Bundle libs specific to this binary
    lddtree -l "$DEST/$bin" | \
     grep -vE "$bin|libc\.so|libm\.so|libdl\.so|libpthread\.so|librt\.so|libresolv\.so|libnsl\.so|libutil\.so|ld-linux" | \
     xargs -I '{}' cp -v '{}' "$DEST/lib/"
    
    # # Patch binary to look in its local lib folder
    # patchelf --set-rpath '$ORIGIN/lib' "$DEST/$bin"
    
    # Patch libs to look for each other in their own directory
    find "$DEST/lib" -type f -name "*.so*" -exec patchelf --set-rpath '$ORIGIN' {} \;
done
cd ..

# copy

cd src/libs/third_party/Piecewise-Differential-Zstd-Coder-POD5-Demo/pod5
python -c 'from pathlib import Path; from setuptools_scm import get_version; get_version(root=Path.cwd(), search_parent_directories=True, write_to="_version.py")'
python -m pod5_make_version
cd ..
rm -rf build-copy
mkdir -p build-copy
cd build-copy
cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_BUNDLED=true ..
make -j copy
cd ../../../../..

cd artifacts
mkdir -p /builder/artifacts/copy/lib
cp /builder/src/libs/third_party/Piecewise-Differential-Zstd-Coder-POD5-Demo/build-copy/src/c++/copy /builder/artifacts/copy/
lddtree -l copy/copy | \
 grep -vE 'artifacts/copy/copy|libc\.so|libm\.so|libdl\.so|libpthread\.so|librt\.so|libresolv\.so|libnsl\.so|libutil\.so|ld-linux' | \
 xargs -I '{}' cp -v '{}' ./copy/lib/
find ./copy/lib -type f -name "*.so*" -exec patchelf --set-rpath '$ORIGIN' {} \;
cd ..

chown -R $HOST_UID:$HOST_GID /builder/artifacts