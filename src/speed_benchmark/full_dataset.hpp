#pragma once

#include <string>
#include "../compression_benchmark/streamed_dataset.hpp"
#include <vector>
#include <cstdint>
#include <cstddef>

class FullDataset
{
public:
    FullDataset(const std::string & path)
    {
        auto stream = StreamedDataset(path);

        std::vector<int16_t> input_data;

        while (stream.next(input_data))
        {
            data.push_back(input_data);
        }
    }

    const std::vector<std::vector<int16_t>> & get_data()
    {
        return data;
    }

private:
    std::vector<std::vector<int16_t>> data;
};