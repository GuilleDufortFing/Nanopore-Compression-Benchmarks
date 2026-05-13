find_package(zstd REQUIRED)

set(BENCHMARK_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${BENCHMARK_RUNTIME_OUTPUT_DIRECTORY}")

foreach(config Debug Release RelWithDebInfo MinSizeRel)
    string(TOUPPER "${config}" config_upper)
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_${config_upper} "${BENCHMARK_RUNTIME_OUTPUT_DIRECTORY}")
endforeach()

add_library(alias-zstd-compression-benchmarks::zstd INTERFACE IMPORTED)
target_link_libraries(alias-zstd-compression-benchmarks::zstd INTERFACE zstd::zstd)

add_subdirectory(common)
add_subdirectory(libs)
add_subdirectory(compression_benchmark)
add_subdirectory(speed_benchmark)
add_subdirectory(time_split_benchmark)