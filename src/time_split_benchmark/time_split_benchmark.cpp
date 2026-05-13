#include <cstring>
#include <iostream>
#include <cstdlib>
#include <string>
#include <pod5_format/c_api.h>
#include <pod5_format/split_benchmarker.h>
#include <stdint.h>
#include <chrono>
#include <memory>
#include <map>
#include <vector>
#include <numeric>
#include <cstdint>
#include <boost/filesystem.hpp>


#define LOG_POD5_ERROR_IF_ANY(pod5_errno_local) \
    do \
    { \
        if (pod5_errno_local != POD5_OK) \
        { \
            std::cerr << pod5_get_error_string() << "\n"; \
            exit(-1); \
        } \
    } while (false)

using Clock = std::chrono::steady_clock;

struct CompressArgs {
    std::string in_filename;
    std::string out_filename;
};

struct DecompressArgs {
    std::string in_filename;
};

struct ParseResult {
    bool is_compress;
    CompressArgs c_args;
    DecompressArgs d_args;
};

ParseResult parse_args(int argc, char **argv) {
    if (argc < 2) goto usage_error;

    if (std::string(argv[1]) == "--compress") {
        if (argc < 4) goto usage_error;

        return {true, {argv[2], argv[3]}, {}};
    } 
    
    if (std::string(argv[1]) == "--decompress") {
        if (argc < 3) goto usage_error;
        return {false, {}, {argv[2]}};
    }

usage_error:
    std::cerr << "Usage:\n"
              << "  " << argv[0] << " --compress <in> <out>\n"
              << "  " << argv[0] << " --decompress <in>\n";
    std::exit(EXIT_FAILURE);
}

struct Pod5BatchInfo
{
    size_t batch_count;

    std::vector<Pod5ReadRecordBatch_t *> read_record_batches;
    std::vector<size_t> read_record_batches_row_counts;
    std::vector<std::vector<ReadBatchRowInfo_t>> read_batch_row_infos;
    std::vector<std::vector<size_t>> read_batch_row_sample_counts;
    std::vector<std::vector<int16_t*>> read_batch_row_signal;

    Pod5BatchInfo(size_t count)
        : batch_count(count)
        , read_record_batches(count)
        , read_record_batches_row_counts(count)
        , read_batch_row_infos(count)
        , read_batch_row_sample_counts(count)
        , read_batch_row_signal(count)
    {}

    ~Pod5BatchInfo()
    {
        for (size_t i = 0; i < read_record_batches.size(); ++i)
        {
            if (i < read_batch_row_signal.size())
            {
                for (auto signal_ptr : read_batch_row_signal[i])
                {
                    std::free(signal_ptr);
                }
            }

            if (read_record_batches[i])
            {
                pod5_free_read_batch(read_record_batches[i]);
            }
        }
    }

    Pod5BatchInfo(const Pod5BatchInfo&) = delete;
    Pod5BatchInfo& operator=(const Pod5BatchInfo&) = delete;

    Pod5BatchInfo(Pod5BatchInfo&&) noexcept = default;
    Pod5BatchInfo& operator=(Pod5BatchInfo&&) noexcept = default;
};

struct Pod5RunInfo
{
    size_t file_run_info_count;
    std::vector<RunInfoDictData_t*> run_infos;

    Pod5RunInfo(size_t count) : file_run_info_count(count), run_infos(count) {}

    ~Pod5RunInfo()
    {
        for (auto run_info : run_infos)
        {
            if (run_info) pod5_free_run_info(run_info);
        }
    }

    Pod5RunInfo(const Pod5RunInfo&) = delete;
    Pod5RunInfo& operator=(const Pod5RunInfo&) = delete;

    Pod5RunInfo(Pod5RunInfo&&) noexcept = default;
    Pod5RunInfo& operator=(Pod5RunInfo&&) noexcept = default;
};

struct Pod5Info
{
    Pod5BatchInfo batch_info;
    Pod5RunInfo run_info;
};

Pod5Info read_pod5_info(Pod5FileReader_t *reader)
{
    run_info_index_t file_run_info_count;
    pod5_get_file_run_info_count(reader, &file_run_info_count);
    //LOG_POD5_ERROR_IF_ANY(pod5_get_file_run_info_count(reader, &file_run_info_count));
    
    Pod5RunInfo run_info(file_run_info_count);
    for (run_info_index_t i = 0; i < file_run_info_count; i++)
    {
        LOG_POD5_ERROR_IF_ANY(pod5_get_file_run_info(reader, i, &run_info.run_infos[i]));
    }

    size_t batch_count;
    LOG_POD5_ERROR_IF_ANY(pod5_get_read_batch_count(&batch_count, reader));

    Pod5BatchInfo batch_info(batch_count);
    for (size_t i = 0; i < batch_count; i++)
    {
        LOG_POD5_ERROR_IF_ANY(pod5_get_read_batch(&batch_info.read_record_batches[i], reader, i));
        
        Pod5ReadRecordBatch_t *batch = batch_info.read_record_batches[i];
        LOG_POD5_ERROR_IF_ANY(pod5_get_read_batch_row_count(&batch_info.read_record_batches_row_counts[i], batch));
        
        size_t row_count = batch_info.read_record_batches_row_counts[i];
        batch_info.read_batch_row_infos[i].resize(row_count);
        batch_info.read_batch_row_sample_counts[i].resize(row_count);
        batch_info.read_batch_row_signal[i].resize(row_count);

        for (size_t row = 0; row < row_count; row++)
        {
            uint16_t version;
            LOG_POD5_ERROR_IF_ANY(pod5_get_read_batch_row_info_data(
                batch, 
                row, 
                READ_BATCH_ROW_INFO_VERSION, 
                &batch_info.read_batch_row_infos[i][row], 
                &version
            ));

            LOG_POD5_ERROR_IF_ANY(pod5_get_read_complete_sample_count(
                reader, 
                batch, 
                row, 
                &batch_info.read_batch_row_sample_counts[i][row]
            ));

            size_t samples = batch_info.read_batch_row_sample_counts[i][row];
            batch_info.read_batch_row_signal[i][row] = static_cast<int16_t*>(std::malloc(samples * sizeof(int16_t)));

            LOG_POD5_ERROR_IF_ANY(pod5_get_read_complete_signal(
                reader, 
                batch, 
                row, 
                samples, 
                batch_info.read_batch_row_signal[i][row]
            ));
        }
    }

    return { std::move(batch_info), std::move(run_info) };
}


// So the compiler does not optimize away the read
uint64_t compute_pod5_deep_checksum(const Pod5Info& info) {
    uint64_t hash = 0xCBF29CE484222325ULL;
    const uint64_t prime = 0x100000001B3ULL;

    for (size_t b = 0; b < info.batch_info.batch_count; ++b) {
        size_t row_count = info.batch_info.read_record_batches_row_counts[b];
        
        for (size_t r = 0; r < row_count; ++r) {
            const int16_t* signal = info.batch_info.read_batch_row_signal[b][r];
            size_t samples = info.batch_info.read_batch_row_sample_counts[b][r];
            
            for (size_t s = 0; s < samples; ++s) {
                hash ^= static_cast<uint64_t>(signal[s]);
                hash *= prime;
            }

            const auto& row_info = info.batch_info.read_batch_row_infos[b][r];
            const uint8_t* info_ptr = reinterpret_cast<const uint8_t*>(&row_info);
            for (size_t k = 0; k < sizeof(ReadBatchRowInfo_t); ++k) {
                hash ^= static_cast<uint64_t>(info_ptr[k]);
                hash *= prime;
            }
        }
    }
    
    hash ^= static_cast<uint64_t>(info.run_info.file_run_info_count);
    hash *= prime;

    return hash;
}

void compress_main(const CompressArgs &args) {
    pdz::split_benchmarker::SplitBenchmarker::init();
    Pod5FileReader_t *reader;
    Pod5FileWriter_t *writer;
    pod5_init();

    reader = pod5_open_file(args.in_filename.data());
    if (!reader)
    {
        std::cerr << "Invalid path " << args.in_filename << std::endl;
    }
    const auto pod5_info = read_pod5_info(reader);
    pod5_close_and_free_reader(reader);

    // 1. Normalize path to absolute
    boost::filesystem::path out_path(args.out_filename);
    if (out_path.is_relative()) {
        out_path = boost::filesystem::current_path() / out_path;
    }

    // 2. Remove existing file/directory to avoid POD5 writer conflicts
    if (boost::filesystem::exists(out_path)) {
        boost::filesystem::remove_all(out_path);
    }

    const auto t_start = Clock::now();

    const Pod5WriterOptions_t writer_options = {0, 1, 0, 0}; // 1 is VBZ Signal compression type
    writer = pod5_create_file(out_path.string().c_str(), "Time slice benchmark", &writer_options);
    if (!writer)
    {
        std::cerr << "Error when creating writer: " << pod5_get_error_string();
        exit(-1);
    }
    std::vector<int16_t> run_info_idxs(pod5_info.run_info.file_run_info_count);

    for (run_info_index_t i = 0; i < pod5_info.run_info.file_run_info_count; i++)
    {
        const auto run_info_struct = pod5_info.run_info.run_infos[i];
        LOG_POD5_ERROR_IF_ANY(pod5_add_run_info(
            &run_info_idxs[i],
            writer,
            run_info_struct->acquisition_id,
            run_info_struct->acquisition_start_time_ms, run_info_struct->adc_max,
            run_info_struct->adc_min, run_info_struct->context_tags.size,
            run_info_struct->context_tags.keys, run_info_struct->context_tags.values,
            run_info_struct->experiment_name, run_info_struct->flow_cell_id,
            run_info_struct->flow_cell_product_code, run_info_struct->protocol_name,
            run_info_struct->protocol_run_id, run_info_struct->protocol_start_time_ms,
            run_info_struct->sample_id, run_info_struct->sample_rate,
            run_info_struct->sequencing_kit, run_info_struct->sequencer_position,
            run_info_struct->sequencer_position_type, run_info_struct->software,
            run_info_struct->system_name, run_info_struct->system_type,
            run_info_struct->tracking_id.size, run_info_struct->tracking_id.keys,
            run_info_struct->tracking_id.values
        ));
    }

    std::map<std::string, int16_t> pore_type_cache;

    for (size_t i = 0; i < pod5_info.batch_info.batch_count; i++)
    {
        Pod5ReadRecordBatch_t *batch = pod5_info.batch_info.read_record_batches[i];
        size_t row_count = pod5_info.batch_info.read_record_batches_row_counts[i];
        const auto& row_infos = pod5_info.batch_info.read_batch_row_infos[i];
        const auto& sample_counts = pod5_info.batch_info.read_batch_row_sample_counts[i];
        const auto& signals = pod5_info.batch_info.read_batch_row_signal[i];

        auto read_ids = std::make_unique<read_id_t[]>(row_count);
        std::vector<uint32_t> read_numbers(row_count);
        std::vector<uint64_t> start_samples(row_count);
        std::vector<float> median_befores(row_count);
        std::vector<uint16_t> channels(row_count);
        std::vector<uint8_t> wells(row_count);
        std::vector<int16_t> pore_types(row_count);
        std::vector<float> calibration_offsets(row_count);
        std::vector<float> calibration_scales(row_count);
        std::vector<pod5_end_reason_t> end_reasons(row_count);
        std::vector<uint8_t> end_reason_forceds(row_count);
        std::vector<int16_t> mapped_run_info_ids(row_count);
        std::vector<uint64_t> num_minknow_events(row_count);
        std::vector<float> tracked_scaling_scales(row_count);
        std::vector<float> tracked_scaling_shifts(row_count);
        std::vector<float> predicted_scaling_scales(row_count);
        std::vector<float> predicted_scaling_shifts(row_count);
        std::vector<uint32_t> num_reads_since_mux_changes(row_count);
        std::vector<float> time_since_mux_changes(row_count);
        std::vector<uint32_t> signal_lengths(row_count);

        for (size_t j = 0; j < row_count; j++)
        {
            std::memcpy(read_ids[j], row_infos[j].read_id, sizeof(read_id_t));
            read_numbers[j] = row_infos[j].read_number;
            start_samples[j] = row_infos[j].start_sample;
            median_befores[j] = row_infos[j].median_before;
            channels[j] = row_infos[j].channel;
            wells[j] = row_infos[j].well;
            
            size_t pore_str_size = 256;
            std::string pore_str(pore_str_size, '\0');
            pod5_error_t err;
            do {
                err = pod5_get_pore_type(batch, row_infos[j].pore_type, &pore_str[0], &pore_str_size);
                if (err == POD5_ERROR_STRING_NOT_LONG_ENOUGH) {
                    pore_str.resize(pore_str_size);
                } else {
                    break;
                }
            } while (true);
            pore_str.resize(std::strlen(pore_str.c_str()));

            if (auto it = pore_type_cache.find(pore_str); it != pore_type_cache.end()) {
                pore_types[j] = it->second;
            } else {
                int16_t new_pore_type;
                LOG_POD5_ERROR_IF_ANY(pod5_add_pore(&new_pore_type, writer, pore_str.c_str()));
                pore_type_cache[pore_str] = new_pore_type;
                pore_types[j] = new_pore_type;
            }

            calibration_offsets[j] = row_infos[j].calibration_offset;
            calibration_scales[j] = row_infos[j].calibration_scale;

            size_t reason_str_size = 256;
            std::string reason_str(reason_str_size, '\0');
            do {
                err = pod5_get_end_reason(batch, row_infos[j].end_reason, &end_reasons[j], &reason_str[0], &reason_str_size);
                if (err == POD5_ERROR_STRING_NOT_LONG_ENOUGH) {
                    reason_str.resize(reason_str_size);
                } else {
                    break;
                }
            } while (true);

            end_reason_forceds[j] = row_infos[j].end_reason_forced;
            mapped_run_info_ids[j] = run_info_idxs[row_infos[j].run_info];
            num_minknow_events[j] = row_infos[j].num_minknow_events;
            tracked_scaling_scales[j] = row_infos[j].tracked_scaling_scale;
            tracked_scaling_shifts[j] = row_infos[j].tracked_scaling_shift;
            predicted_scaling_scales[j] = row_infos[j].predicted_scaling_scale;
            predicted_scaling_shifts[j] = row_infos[j].predicted_scaling_shift;
            num_reads_since_mux_changes[j] = row_infos[j].num_reads_since_mux_change;
            time_since_mux_changes[j] = row_infos[j].time_since_mux_change;
            
            signal_lengths[j] = static_cast<uint32_t>(sample_counts[j]);
        }

        ReadBatchRowInfoArray_t flattened_array = {};
        flattened_array.read_id = read_ids.get();
        flattened_array.read_number = read_numbers.data();
        flattened_array.start_sample = start_samples.data();
        flattened_array.median_before = median_befores.data();
        flattened_array.channel = channels.data();
        flattened_array.well = wells.data();
        flattened_array.pore_type = pore_types.data();
        flattened_array.calibration_offset = calibration_offsets.data();
        flattened_array.calibration_scale = calibration_scales.data();
        flattened_array.end_reason = end_reasons.data();
        flattened_array.end_reason_forced = end_reason_forceds.data();
        flattened_array.run_info_id = mapped_run_info_ids.data();
        flattened_array.num_minknow_events = num_minknow_events.data();
        flattened_array.tracked_scaling_scale = tracked_scaling_scales.data();
        flattened_array.tracked_scaling_shift = tracked_scaling_shifts.data();
        flattened_array.predicted_scaling_scale = predicted_scaling_scales.data();
        flattened_array.predicted_scaling_shift = predicted_scaling_shifts.data();
        flattened_array.num_reads_since_mux_change = num_reads_since_mux_changes.data();
        flattened_array.time_since_mux_change = time_since_mux_changes.data();

        LOG_POD5_ERROR_IF_ANY(pod5_add_reads_data(
            writer,
            row_count,
            READ_BATCH_ROW_INFO_VERSION,
            &flattened_array,
            const_cast<const int16_t **>(signals.data()),
            signal_lengths.data()
        ));
    }

    pod5_close_and_free_writer(writer);
    
    const auto t_end = Clock::now();

    pod5_terminate();

    const auto total_elapsed_time_ns = t_end - t_start;
    const auto compression_elapsed_time_ns = std::accumulate(
        pdz::split_benchmarker::SplitBenchmarker::compression_begin(),
        pdz::split_benchmarker::SplitBenchmarker::compression_end(),
        std::chrono::nanoseconds::zero()
    );

    const auto total_elapsed_time_s = std::chrono::duration<double>(total_elapsed_time_ns).count();
    const auto compression_elapsed_time_s = std::chrono::duration<double>(compression_elapsed_time_ns).count();
    const double ratio = compression_elapsed_time_s / total_elapsed_time_s;

    std::cout << "Total elapsed time: " << total_elapsed_time_s << "s\n";
    std::cout << "Compression time: " << compression_elapsed_time_s << "s (summed over " << pdz::split_benchmarker::SplitBenchmarker::compression_size() << " intervals)\n";
    std::cout << "Compression time is " << 100.0 * ratio << "% of total time\n";
}

void decompress_main(const DecompressArgs &args) {
    // Init

    pdz::split_benchmarker::SplitBenchmarker::init();
    Pod5FileReader_t *reader;
    pod5_init();

    // Main body
    
    const auto t_start = Clock::now();
    reader = pod5_open_file(args.in_filename.data());
    const auto pod5_info = read_pod5_info(reader);
    pod5_close_and_free_reader(reader);
    const auto t_end = Clock::now();

    // Prevent the compiler from optimizing away the full read call 
    volatile uint64_t side_effect_sink = compute_pod5_deep_checksum(pod5_info);
    if (side_effect_sink == 0) { std::cout << "Checksum: " << side_effect_sink << "\n"; }

    // Cleanup
    pod5_terminate();

    // Stats
    const auto total_elapsed_time_ns = t_end - t_start;
    const auto decompression_elapsed_time_ns = std::accumulate(
        pdz::split_benchmarker::SplitBenchmarker::decompression_begin(),
        pdz::split_benchmarker::SplitBenchmarker::decompression_end(),
        std::chrono::nanoseconds::zero()
    );

    const auto total_elapsed_time_s = std::chrono::duration<double>(total_elapsed_time_ns).count();
    const auto decompression_elapsed_time_s = std::chrono::duration<double>(decompression_elapsed_time_ns).count();
    const double ratio =
        std::chrono::duration<double>(decompression_elapsed_time_ns) / 
        std::chrono::duration<double>(total_elapsed_time_ns);

    std::cout << "Total elapsed time: " << total_elapsed_time_s << "s\n";
    std::cout << "Decompression time: " << decompression_elapsed_time_s << "s (summed over " << pdz::split_benchmarker::SplitBenchmarker::decompression_size() << " intervals)\n";
    std::cout << "Decompression time is " << 100.0 * ratio << "% of total time" << std::endl;
}

int main(int argc, char **argv) {
    ParseResult res = parse_args(argc, argv);

    if (res.is_compress) {
        compress_main(res.c_args);
    } else {
        decompress_main(res.d_args);
    }

    return 0;
}