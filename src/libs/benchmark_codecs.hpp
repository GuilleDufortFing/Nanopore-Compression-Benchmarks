#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "../common/compression_algorithms.hpp"

struct CompressedSignal
{
    std::vector<uint8_t> bytes;
};

struct DecompressedSignal
{
    std::vector<int16_t> samples;
    size_t size_bytes;
};

CompressedSignal compress_signal(
    CompressionAlgorithms algorithm,
    const std::vector<int16_t> &samples);

DecompressedSignal decompress_signal(
    CompressionAlgorithms algorithm,
    const CompressedSignal &compressed,
    size_t expected_sample_count);