#include "benchmark_codecs.hpp"

#include <stdexcept>

#include "exzd_codec.hpp"
#include "lib-nanopore-arithmetic-compression/compressionLib/compressor.h"
#include "lib-nanopore-arithmetic-compression/compressionLib/decompressor.h"
#include "pod5_format/c_api.h"
#include "../libs/lib-682-nanopore-compression/c++/src/definitions/unconditional286/unconditional286_compressor_sse.hpp"

namespace
{
CompressedSignal compress_vb682(const std::vector<int16_t> &samples, SIMDAcceleration acceleration)
{
    CompressedSignal compressed;
    compressed.bytes.resize(Unconditional286CompressorSSE::encode_bound(samples.size()));

    const size_t encoded_size = Unconditional286CompressorSSE::encode(
        samples.data(),
        samples.size(),
        compressed.bytes.data(),
        acceleration);

    compressed.bytes.resize(encoded_size);
    return compressed;
}

DecompressedSignal decompress_vb682(
    const CompressedSignal &compressed,
    size_t expected_sample_count,
    SIMDAcceleration acceleration)
{
    DecompressedSignal decompressed;
    decompressed.samples.resize(expected_sample_count);
    Unconditional286CompressorSSE::decode(
        compressed.bytes.data(),
        decompressed.samples.data(),
        acceleration);
    decompressed.size_bytes = expected_sample_count * sizeof(int16_t);
    return decompressed;
}
}

CompressedSignal compress_signal(
    CompressionAlgorithms algorithm,
    const std::vector<int16_t> &samples)
{
    switch (algorithm)
    {
    case CompressionAlgorithms::Vb682CompressionSSE:
        return compress_vb682(samples, SIMDAcceleration::SSE);
    case CompressionAlgorithms::Vb682CompressionSerial:
        return compress_vb682(samples, SIMDAcceleration::None);
    case CompressionAlgorithms::ArithmeticCompression:
    {
        pgnano::standalone::Compressor compressor;
        CompressedSignal compressed;
        compressed.bytes.resize(compressor.compressed_signal_max_size(samples.size()));
        const size_t encoded_words = compressor.compress(
            samples.data(),
            samples.size(),
            reinterpret_cast<int16_t *>(compressed.bytes.data()));
        compressed.bytes.resize(encoded_words * sizeof(uint16_t));
        return compressed;
    }
    case CompressionAlgorithms::VBZ:
    {
        CompressedSignal compressed;
        compressed.bytes.resize(pod5_vbz_compressed_signal_max_size(samples.size()));
        size_t compressed_size = compressed.bytes.size();
        const auto error_code = pod5_vbz_compress_signal(
            samples.data(),
            samples.size(),
            reinterpret_cast<char *>(compressed.bytes.data()),
            &compressed_size);

        if (error_code != POD5_OK)
        {
            throw std::runtime_error("pod5_vbz_compress_signal failed");
        }

        compressed.bytes.resize(compressed_size);
        return compressed;
    }
    case CompressionAlgorithms::ExZd:
        return CompressedSignal{compress_signal_ex_zd(samples.data(), samples.size())};
    case CompressionAlgorithms::ExZdZlib:
        return CompressedSignal{compress_signal_ex_zd_zlib(samples.data(), samples.size())};
    case CompressionAlgorithms::ExZdZstd:
        return CompressedSignal{compress_signal_ex_zd_zstd(samples.data(), samples.size())};
    default:
        throw std::runtime_error("Unsupported compression algorithm");
    }
}

DecompressedSignal decompress_signal(
    CompressionAlgorithms algorithm,
    const CompressedSignal &compressed,
    size_t expected_sample_count)
{
    switch (algorithm)
    {
    case CompressionAlgorithms::Vb682CompressionSSE:
        return decompress_vb682(compressed, expected_sample_count, SIMDAcceleration::SSE);
    case CompressionAlgorithms::Vb682CompressionSerial:
        return decompress_vb682(compressed, expected_sample_count, SIMDAcceleration::None);
    case CompressionAlgorithms::ArithmeticCompression:
    {
        pgnano::standalone::Decompressor decompressor;
        DecompressedSignal output;
        output.samples.resize(expected_sample_count);
        decompressor.decompress(
            reinterpret_cast<int16_t *>(const_cast<uint8_t *>(compressed.bytes.data())),
            output.samples.data());
        output.size_bytes = expected_sample_count * sizeof(int16_t);
        return output;
    }
    case CompressionAlgorithms::VBZ:
    {
        DecompressedSignal output;
        output.samples.resize(expected_sample_count);
        const auto error_code = pod5_vbz_decompress_signal(
            reinterpret_cast<const char *>(compressed.bytes.data()),
            compressed.bytes.size(),
            expected_sample_count,
            output.samples.data());

        if (error_code != POD5_OK)
        {
            throw std::runtime_error("pod5_vbz_decompress_signal failed");
        }

        output.size_bytes = expected_sample_count * sizeof(int16_t);
        return output;
    }
    case CompressionAlgorithms::ExZd:
    {
        auto samples = decompress_signal_ex_zd(
            compressed.bytes.data(),
            compressed.bytes.size(),
            expected_sample_count);
        return DecompressedSignal{std::move(samples), expected_sample_count * sizeof(int16_t)};
    }
    case CompressionAlgorithms::ExZdZlib:
    {
        auto samples = decompress_signal_ex_zd_zlib(
            compressed.bytes.data(),
            compressed.bytes.size(),
            expected_sample_count);
        return DecompressedSignal{std::move(samples), expected_sample_count * sizeof(int16_t)};
    }
    case CompressionAlgorithms::ExZdZstd:
    {
        auto samples = decompress_signal_ex_zd_zstd(
            compressed.bytes.data(),
            compressed.bytes.size(),
            expected_sample_count);
        return DecompressedSignal{std::move(samples), expected_sample_count * sizeof(int16_t)};
    }
    default:
        throw std::runtime_error("Unsupported compression algorithm");
    }
}