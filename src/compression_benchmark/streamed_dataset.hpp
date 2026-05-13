#pragma once

#include <cstdio>
#include <string>
#include <vector>
#include <cstdint>

class StreamedDataset
{
public:
    StreamedDataset(const std::string & path);
    ~StreamedDataset();

    bool next(std::vector<int16_t> & out);
private:
    FILE* m_file = NULL;
};