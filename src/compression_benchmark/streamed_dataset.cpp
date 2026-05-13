#include "streamed_dataset.hpp"

#include <memory>
#include <stdexcept>

StreamedDataset::StreamedDataset(const std::string & path)
{
    m_file = fopen(path.data(), "rb");
    if (!m_file)
    {
        throw std::runtime_error("Couldn't load samples from binary file!");
    }
}

StreamedDataset::~StreamedDataset()
{
    if (m_file != NULL)
    {
        fclose(m_file);
    }
}

bool StreamedDataset::next(std::vector<int16_t> &out)
{
    size_t items_read;
    uint32_t number_of_samples;
    items_read = fread(&number_of_samples, sizeof(uint32_t), 1, m_file);
    if (items_read != 1)
    {
        return false;
    }

    out.clear();
    out.reserve(number_of_samples);
    auto buffer = std::make_unique<int16_t[]>(number_of_samples);
    items_read = fread(buffer.get(), sizeof(int16_t), number_of_samples, m_file);
    if (items_read != number_of_samples)
    {
        return false;
    }

    for (size_t i = 0; i < number_of_samples; ++i)
    {
        out.push_back(buffer[i]);
    }

    return true;
}
