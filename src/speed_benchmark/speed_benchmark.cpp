#include <algorithm>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

#include "../common/params_parser.hpp"
#include "../libs/benchmark_codecs.hpp"
#include "full_dataset.hpp"

class SpeedBenchmarkResult
{
public:
    SpeedBenchmarkResult(
        const size_t number_of_samples,
        const size_t compressed_size_bytes,
        const std::chrono::duration<double> compression_time,
        const std::chrono::duration<double> decompression_time,
        const bool decompression_was_successful)
        : number_of_samples(number_of_samples),
          compressed_size_bytes(compressed_size_bytes),
          decompression_was_successful(decompression_was_successful),
          compression_time(compression_time),
          decompression_time(decompression_time) {}

    const size_t number_of_samples;
    const size_t compressed_size_bytes;
    const bool decompression_was_successful;
    const std::chrono::duration<double> compression_time;
    const std::chrono::duration<double> decompression_time;
};

class SpeedBenchmarkCSVRow
{
public:
    SpeedBenchmarkCSVRow(
        const size_t number_of_samples,
        const size_t compressed_size_bytes,
        const std::chrono::duration<double> compression_time,
        const std::chrono::duration<double> decompression_time,
        const bool decompression_was_successful,
        const size_t id)
        : id(id),
          number_of_samples(number_of_samples),
          compressed_size_bytes(compressed_size_bytes),
          decompression_was_successful(decompression_was_successful),
          compression_time(compression_time),
          decompression_time(decompression_time),
          compression_speed_mb_sec(((number_of_samples * sizeof(int16_t)) / compression_time.count()) / (1 << 20)),
          decompression_speed_mb_sec((number_of_samples * sizeof(int16_t)) / decompression_time.count() / (1 << 20)) {}

    const size_t id;
    const size_t number_of_samples;
    const size_t compressed_size_bytes;
    const bool decompression_was_successful;
    const std::chrono::duration<double> compression_time;
    const std::chrono::duration<double> decompression_time;
    const double compression_speed_mb_sec;
    const double decompression_speed_mb_sec;
};

class SpeedBenchmarkCSVWriter
{
public:
    explicit SpeedBenchmarkCSVWriter(const std::string &path)
    {
        file.open(path);
        if (file.bad())
        {
            throw std::runtime_error("Failed to open file for writing");
        }
        write_header();
    }

    ~SpeedBenchmarkCSVWriter()
    {
        if (file.is_open())
        {
            file.close();
        }
    }

    void write_row(const SpeedBenchmarkCSVRow &row)
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
        file << ",";
        file << row.compression_time.count();
        file << ",";
        file << row.decompression_time.count();
        file << ",";
        file << row.compression_speed_mb_sec;
        file << ",";
        file << row.decompression_speed_mb_sec;
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
        file << ",compression_time";
        file << ",decompression_time";
        file << ",compression_speed_mb_sec";
        file << ",decompression_speed_mb_sec";
        file << "\n";
    }
};

void compress_data_in_chunks(
    const std::vector<std::vector<int16_t>> &dataset,
    size_t set_size,
    CompressionAlgorithms algorithm,
    std::vector<CompressedSignal> &compressed_buffers,
    std::vector<std::chrono::duration<double>> &compression_times)
{
    using clock = std::chrono::steady_clock;
    const size_t dataset_size = dataset.size();
    const size_t num_sets = (dataset_size + set_size - 1) / set_size;

    for (size_t set_index = 0; set_index < num_sets; ++set_index)
    {
        const auto t1 = clock::now();

        for (size_t i = 0; i < set_size; ++i)
        {
            const size_t data_index = set_index * set_size + i;
            if (data_index >= dataset_size)
            {
                break;
            }

            compressed_buffers.push_back(compress_signal(algorithm, dataset[data_index]));
        }

        const auto t2 = clock::now();
        compression_times.push_back(t2 - t1);
    }
}

void decompress_data_in_chunks(
    const std::vector<std::vector<int16_t>> &dataset,
    size_t set_size,
    CompressionAlgorithms algorithm,
    const std::vector<CompressedSignal> &compressed_buffers,
    std::vector<DecompressedSignal> &decompressed_buffers,
    std::vector<std::chrono::duration<double>> &decompression_times)
{
    using clock = std::chrono::steady_clock;
    const size_t dataset_size = dataset.size();
    const size_t num_sets = (dataset_size + set_size - 1) / set_size;

    for (size_t set_index = 0; set_index < num_sets; ++set_index)
    {
        const auto t1 = clock::now();

        for (size_t i = 0; i < set_size; ++i)
        {
            const size_t data_index = set_index * set_size + i;
            if (data_index >= dataset_size)
            {
                break;
            }

            decompressed_buffers.push_back(decompress_signal(
                algorithm,
                compressed_buffers[data_index],
                dataset[data_index].size()));
        }

        const auto t2 = clock::now();
        decompression_times.push_back(t2 - t1);
    }
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

        auto dataset_loader = FullDataset(params.input_file());
        const auto dataset = dataset_loader.get_data();

        const auto number_of_chunks = dataset.size();

        std::vector<CompressedSignal> compressed_buffers;
        std::vector<std::chrono::duration<double>> compression_times;
        std::vector<std::chrono::duration<double>> decompression_times;
        std::vector<DecompressedSignal> decompressed_buffers;

        compressed_buffers.reserve(number_of_chunks);
        compression_times.reserve(number_of_chunks);
        decompression_times.reserve(number_of_chunks);
        decompressed_buffers.reserve(number_of_chunks);

        constexpr size_t chunk_set_size = 100;
        compress_data_in_chunks(dataset, chunk_set_size, params.algorithm(), compressed_buffers, compression_times);
        decompress_data_in_chunks(dataset, chunk_set_size, params.algorithm(), compressed_buffers, decompressed_buffers, decompression_times);

        if (compressed_buffers.size() != decompressed_buffers.size())
        {
            std::cerr << "Error: compressed and decompressed buffers have different sizes" << std::endl;
            return EXIT_FAILURE;
        }

        if (decompressed_buffers.size() != dataset.size())
        {
            std::cerr << "Error: compressed buffers have different size than the dataset" << std::endl;
            return EXIT_FAILURE;
        }

        if (compression_times.size() != decompression_times.size())
        {
            std::cerr << "Error: compression and decompression times have different sizes" << std::endl;
            return EXIT_FAILURE;
        }

        SpeedBenchmarkCSVWriter csv_writer(params.output_file());

        bool benchmark_failed = false;
        const size_t number_of_sets = (dataset.size() + chunk_set_size - 1) / chunk_set_size;

        for (size_t set_index = 0; set_index < number_of_sets; ++set_index)
        {
            const size_t set_start = set_index * chunk_set_size;
            const size_t set_end = std::min(set_start + chunk_set_size, dataset.size());

            size_t total_samples = 0;
            size_t total_compressed_size = 0;
            bool chunk_success = true;

            for (size_t i = set_start; i < set_end; ++i)
            {
                const size_t number_of_samples = dataset[i].size();
                const size_t expected_decompressed_size = number_of_samples * sizeof(int16_t);

                total_samples += number_of_samples;
                total_compressed_size += compressed_buffers[i].bytes.size();

                const bool success =
                    decompressed_buffers[i].size_bytes == expected_decompressed_size &&
                    dataset[i] == decompressed_buffers[i].samples;
                chunk_success = chunk_success && success;
            }

            csv_writer.write_row(
                SpeedBenchmarkCSVRow(
                    total_samples,
                    total_compressed_size,
                    compression_times[set_index],
                    decompression_times[set_index],
                    chunk_success,
                    set_index));

            benchmark_failed = benchmark_failed || !chunk_success;
        }

        return benchmark_failed ? EXIT_FAILURE : EXIT_SUCCESS;
    }
    catch (const std::exception &exception)
    {
        std::cerr << "Error: " << exception.what() << std::endl;
        return EXIT_FAILURE;
    }
}