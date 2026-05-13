#include "exzd_codec.hpp"

#include <cstdlib>
#include <cstring>
#include <stdexcept>

#include <slow5/slow5_press.h>

namespace
{
bool exzd_is_supported_platform()
{
    const uint16_t value = 0x1;
    return *reinterpret_cast<const uint8_t *>(&value) == 0x1;
}

void throw_if_exzd_unsupported()
{
    if (!exzd_is_supported_platform())
    {
        throw std::runtime_error("EX-ZD is unsupported on big-endian systems");
    }
}

const void *non_null_bytes(const uint8_t *bytes)
{
    static constexpr uint8_t kEmptyByte = 0;
    return bytes ? bytes : &kEmptyByte;
}

std::vector<uint8_t> copy_owned_buffer(void *buffer, size_t buffer_size, const char *label)
{
    if (buffer == nullptr)
    {
        throw std::runtime_error(std::string(label) + " returned a null buffer");
    }

    std::vector<uint8_t> result(buffer_size);
    if (buffer_size > 0)
    {
        std::memcpy(result.data(), buffer, buffer_size);
    }
    std::free(buffer);
    return result;
}

std::vector<uint8_t> wrap_encoded_signal(
    const uint8_t *encoded_bytes,
    size_t encoded_size,
    slow5_press_method method,
    const char *label)
{
    size_t wrapped_size = 0;
    void *wrapped = slow5_ptr_compress_solo(
        method,
        non_null_bytes(encoded_bytes),
        encoded_size,
        &wrapped_size);

    if (wrapped == nullptr)
    {
        std::string message = std::string("slow5_ptr_compress_solo failed for ") + label;
        if (method == SLOW5_COMPRESS_ZSTD)
        {
            message += "; slow5lib may have been built without zstd support";
        }
        throw std::runtime_error(message);
    }

    return copy_owned_buffer(wrapped, wrapped_size, label);
}

std::vector<uint8_t> unwrap_encoded_signal(
    const uint8_t *wrapped_bytes,
    size_t wrapped_size,
    slow5_press_method method,
    const char *label)
{
    size_t unwrapped_size = 0;
    void *unwrapped = slow5_ptr_depress_solo(
        method,
        non_null_bytes(wrapped_bytes),
        wrapped_size,
        &unwrapped_size);

    if (unwrapped == nullptr)
    {
        std::string message = std::string("slow5_ptr_depress_solo failed for ") + label;
        if (method == SLOW5_COMPRESS_ZSTD)
        {
            message += "; slow5lib may have been built without zstd support";
        }
        throw std::runtime_error(message);
    }

    return copy_owned_buffer(unwrapped, unwrapped_size, label);
}
}

std::vector<uint8_t> compress_signal_ex_zd(const int16_t *samples, size_t sample_count)
{
    throw_if_exzd_unsupported();

    size_t compressed_size = 0;
    void *compressed = slow5_ptr_compress_solo(
        SLOW5_COMPRESS_EX_ZD,
        samples,
        sample_count * sizeof(int16_t),
        &compressed_size);

    if (compressed == nullptr)
    {
        throw std::runtime_error("slow5_ptr_compress_solo failed for EX-ZD");
    }

    std::vector<uint8_t> result(compressed_size);
    if (compressed_size > 0)
    {
        std::memcpy(result.data(), compressed, compressed_size);
    }
    std::free(compressed);

    return result;
}

std::vector<uint8_t> compress_signal_ex_zd_zlib(const int16_t *samples, size_t sample_count)
{
    const auto encoded = compress_signal_ex_zd(samples, sample_count);
    return wrap_encoded_signal(encoded.data(), encoded.size(), SLOW5_COMPRESS_ZLIB, "EX-ZD-ZLIB");
}

std::vector<uint8_t> compress_signal_ex_zd_zstd(const int16_t *samples, size_t sample_count)
{
    const auto encoded = compress_signal_ex_zd(samples, sample_count);
    return wrap_encoded_signal(encoded.data(), encoded.size(), SLOW5_COMPRESS_ZSTD, "EX-ZD-ZSTD");
}

std::vector<int16_t> decompress_signal_ex_zd(
    const uint8_t *compressed_bytes,
    size_t compressed_size,
    size_t expected_sample_count)
{
    throw_if_exzd_unsupported();

    size_t decompressed_size = 0;
    void *decompressed = slow5_ptr_depress_solo(
        SLOW5_COMPRESS_EX_ZD,
        compressed_bytes,
        compressed_size,
        &decompressed_size);

    if (decompressed == nullptr)
    {
        throw std::runtime_error("slow5_ptr_depress_solo failed for EX-ZD");
    }

    const size_t expected_size = expected_sample_count * sizeof(int16_t);
    if (decompressed_size != expected_size)
    {
        std::free(decompressed);
        throw std::runtime_error("EX-ZD decompressed byte count did not match the expected sample count");
    }

    std::vector<int16_t> result(expected_sample_count);
    if (decompressed_size > 0)
    {
        std::memcpy(result.data(), decompressed, decompressed_size);
    }
    std::free(decompressed);

    return result;
}

std::vector<int16_t> decompress_signal_ex_zd_zlib(
    const uint8_t *compressed_bytes,
    size_t compressed_size,
    size_t expected_sample_count)
{
    const auto encoded = unwrap_encoded_signal(
        compressed_bytes,
        compressed_size,
        SLOW5_COMPRESS_ZLIB,
        "EX-ZD-ZLIB");
    return decompress_signal_ex_zd(encoded.data(), encoded.size(), expected_sample_count);
}

std::vector<int16_t> decompress_signal_ex_zd_zstd(
    const uint8_t *compressed_bytes,
    size_t compressed_size,
    size_t expected_sample_count)
{
    const auto encoded = unwrap_encoded_signal(
        compressed_bytes,
        compressed_size,
        SLOW5_COMPRESS_ZSTD,
        "EX-ZD-ZSTD");
    return decompress_signal_ex_zd(encoded.data(), encoded.size(), expected_sample_count);
}

bool exzd_zstd_secondary_available()
{
    static constexpr uint8_t probe = 0;
    size_t wrapped_size = 0;
    void *wrapped = slow5_ptr_compress_solo(
        SLOW5_COMPRESS_ZSTD,
        &probe,
        sizeof(probe),
        &wrapped_size);

    if (wrapped == nullptr)
    {
        return false;
    }

    std::free(wrapped);
    return true;
}