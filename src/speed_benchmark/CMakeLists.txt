set(
    SPEED_BENCHMARK_SOURCES
    speed_benchmark.cpp
    ../compression_benchmark/streamed_dataset.cpp
)

add_executable(
    speed_benchmark
    ${SPEED_BENCHMARK_SOURCES})

target_link_libraries(
    speed_benchmark
    PRIVATE
    benchmark-codecs
    alias-zstd-compression-benchmarks::zstd
)