#include <cstddef>
#include <cstdint>
#include <fstream>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <vector>

#include "../common/params_parser.hpp"
#include "../libs/benchmark_codecs.hpp"
#include "streamed_dataset.hpp"

class CompressionBenchmarkResult
{
public:
    CompressionBenchmarkResult(
        const size_t number_of_samples,
        const size_t compressed_size_bytes,
        const bool decompression_was_successful)
        : number_of_samples(number_of_samples),
          compressed_size_bytes(compressed_size_bytes),
          decompression_was_successful(decompression_was_successful) {}

    const size_t number_of_samples;
    const size_t compressed_size_bytes;
    const bool decompression_was_successful;
};

class CompressionBenchmarkCSVRow
{
public:
    CompressionBenchmarkCSVRow(
        const CompressionBenchmarkResult &result,
        const size_t id)
        : id(id),
          number_of_samples(result.number_of_samples),
          compressed_size_bytes(result.compressed_size_bytes),
          decompression_was_successful(result.decompression_was_successful) {}

    const size_t id;
    const size_t number_of_samples;
    const size_t compressed_size_bytes;
    const bool decompression_was_successful;
};

class CompressionBenchmarkCSVWriter
{
public:
    explicit CompressionBenchmarkCSVWriter(const std::string &path)
    {
        file.open(path);
        if (file.bad())
        {
            throw std::runtime_error("Failed to open file for writing");
        }
        write_header();
    }

    ~CompressionBenchmarkCSVWriter()
    {
        if (file.is_open())
        {
            file.close();
        }
    }

    void write_row(const CompressionBenchmarkCSVRow &row)
    {
        file << row.id;
        file << ",";
        file << row.number_of_samples;
        file << ",";
        file << row.compressed_size_bytes;
        file << ",";
        file << static_cast<double>(row.compressed_size_bytes) * 8.0 / row.number_of_samples;
        file << ",";
        file << (row.decompression_was_successful ? 1 : 0);
        file << "\n";
    }

private:
    std::ofstream file;

    void write_header()
    {
        file << "chunk_id";
        file << ",num_samples";
        file << ",compressed_bytes";
        file << ",bits_per_sample";
        file << ",is_correct";
        file << "\n";
    }
};

using CompressionBenchmark = std::function<CompressionBenchmarkResult(const std::vector<int16_t> &)>;

CompressionBenchmarkResult run_compression_benchmark(
    const std::vector<int16_t> &samples,
    CompressionAlgorithms algorithm)
{
    const auto compressed = compress_signal(algorithm, samples);
    const auto decompressed = decompress_signal(algorithm, compressed, samples.size());
    const bool success =
        decompressed.size_bytes == samples.size() * sizeof(int16_t) &&
        samples == decompressed.samples;

    return CompressionBenchmarkResult(samples.size(), compressed.bytes.size(), success);
}

CompressionBenchmark get_compression_benchmark(CompressionAlgorithms algorithm)
{
    return [algorithm](const std::vector<int16_t> &samples)
    {
        return run_compression_benchmark(samples, algorithm);
    };
}

int main(int argc, char **argv)
{
    try
    {
        const auto params_res = ParamsParser::parse(argc, argv);
        if (!params_res.ok())
        {
            std::cerr << "Error: " << params_res.error() << std::endl;
            return EXIT_FAILURE;
        }

        const auto params = params_res.value();

        auto stream = StreamedDataset(params.input_file());
        std::vector<int16_t> input_data;

        const auto benchmark = get_compression_benchmark(params.algorithm());

        CompressionBenchmarkCSVWriter writer(params.output_file());
        size_t i = 0;
        bool benchmark_failed = false;

        while (stream.next(input_data))
        {
            const auto result = benchmark(input_data);
            writer.write_row(CompressionBenchmarkCSVRow(result, i));
            if (!result.decompression_was_successful)
            {
                benchmark_failed = true;
            }
            ++i;
        }

        return benchmark_failed ? EXIT_FAILURE : EXIT_SUCCESS;
    }
    catch (const std::exception &exception)
    {
        std::cerr << "Error: " << exception.what() << std::endl;
        return EXIT_FAILURE;
    }
}