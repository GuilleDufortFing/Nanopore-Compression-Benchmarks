#include "compression_algorithm_parser.hpp"



SNPC::monads::Error<CompressionAlgorithms> CompressionAlgorithmParser::from_string(const std::string & s)
{
    if (s == "VBZ")
    {
        return CompressionAlgorithms::VBZ;
    }
    else if (s == "EX-ZD")
    {
        return CompressionAlgorithms::ExZd;
    }
    else if (s == "EX-ZD-ZLIB")
    {
        return CompressionAlgorithms::ExZdZlib;
    }
    else if (s == "EX-ZD-ZSTD")
    {
        return CompressionAlgorithms::ExZdZstd;
    }
    else if (s == "CA")
    {
        return CompressionAlgorithms::ArithmeticCompression;
    }
    else if (s == "682Serial")
    {
        return CompressionAlgorithms::Vb682CompressionSerial;
    }
    else if (s == "682SSE")
    {
        return CompressionAlgorithms::Vb682CompressionSSE;
    }
    else
    {
        return SNPC::monads::Error<CompressionAlgorithms>().with_error("Unrecognized compression algorithm");
    }
}