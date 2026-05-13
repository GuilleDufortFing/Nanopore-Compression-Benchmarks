set(
    BENCHMARK_COMMON_LIB_SOURCES
)

add_library(
    benchmark-common-lib
    STATIC
    compression_algorithm_parser.cpp
    compression_algorithm_parser.hpp
    compression_algorithms.hpp
    error_monad.hpp
    params_parser.hpp
    params.hpp
)