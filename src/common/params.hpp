#pragma once

#include "compression_algorithms.hpp"
#include <string>

struct Params
{
public:
    Params(
        std::string input_file,
        std::string output_file,
        CompressionAlgorithms algorithm 
    ) : m_input_file(input_file),
    m_output_file(output_file),
    m_algorithm(algorithm) {}

    Params(){}; //FIXME: params should not be default initializable

    const std::string& input_file() const noexcept { return m_input_file; }
    const std::string& output_file() const noexcept { return m_output_file; }
    CompressionAlgorithms algorithm() const noexcept { return m_algorithm; }

private:
    std::string m_input_file;
    std::string m_output_file;
    CompressionAlgorithms m_algorithm;
};