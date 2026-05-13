#pragma once

#include "compression_algorithms.hpp"
#include <string>
#include "error_monad.hpp"

class CompressionAlgorithmParser
{
public:
    static SNPC::monads::Error<CompressionAlgorithms> from_string(const std::string &);
};