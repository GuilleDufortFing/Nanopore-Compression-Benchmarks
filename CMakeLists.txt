cmake_minimum_required(VERSION 3.20)
project(nanopore_compression_benchmarks)

list(PREPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/src/cmake")

include(CTest)

set(BUILD_BUNDLED false CACHE BOOLEAN "NULL")

if (BUILD_BUNDLED)
    set(CMAKE_BUILD_RPATH "$ORIGIN/lib")
endif()

include_directories(src/libs)
include_directories(src/libs/third_party/pod5-format-benchmark-fork/c++)
add_subdirectory(src)
