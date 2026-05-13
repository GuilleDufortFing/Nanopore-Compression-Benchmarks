#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

std::vector<uint8_t> compress_signal_ex_zd(const int16_t *samples, size_t sample_count);

std::vector<uint8_t> compress_signal_ex_zd_zlib(const int16_t *samples, size_t sample_count);

std::vector<uint8_t> compress_signal_ex_zd_zstd(const int16_t *samples, size_t sample_count);

std::vector<int16_t> decompress_signal_ex_zd(
    const uint8_t *compressed_bytes,
    size_t compressed_size,
    size_t expected_sample_count);

std::vector<int16_t> decompress_signal_ex_zd_zlib(
    const uint8_t *compressed_bytes,
    size_t compressed_size,
    size_t expected_sample_count);

std::vector<int16_t> decompress_signal_ex_zd_zstd(
    const uint8_t *compressed_bytes,
    size_t compressed_size,
    size_t expected_sample_count);

bool exzd_zstd_secondary_available();