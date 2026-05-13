set(
    COMPRESSION_BENCHMARK_SOURCES
    compression_benchmark.cpp
    streamed_dataset.cpp
)

add_executable(
    compression_benchmark
    ${COMPRESSION_BENCHMARK_SOURCES})

target_link_libraries(
    compression_benchmark
    PRIVATE
    benchmark-codecs
    alias-zstd-compression-benchmarks::zstd
)