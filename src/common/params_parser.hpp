#pragma once

#include "error_monad.hpp"
#include "params.hpp"
#include "compression_algorithm_parser.hpp"

class ParamsParser
{
public:
    static SNPC::monads::Error<Params> parse(int argc, char **argv)
    {
        if (argc != 4)
        {
            return SNPC::monads::Error<Params>().with_error("Wrong number of arguments");
        }
        std::string input_file_input_str = "";
        std::string output_file_input_str = "";
        std::string compression_algorithm_input_str = "";
        for (int i = 1; i < argc; ++i)
        {
            if (std::string(argv[i]).rfind("--in=") == 0)
            {
                input_file_input_str = argv[i];
            }
            else if (std::string(argv[i]).rfind("--out=") == 0)
            {
                output_file_input_str = argv[i];
            }
            else if (std::string(argv[i]).rfind("--alg=") == 0)
            {
                compression_algorithm_input_str = argv[i];
            }
        }

        if (input_file_input_str.empty()
            || output_file_input_str.empty()
            || compression_algorithm_input_str.empty())
        {
            return SNPC::monads::Error<Params>().with_error("Wrong arguments");
        }

        const auto compression_algorithm = CompressionAlgorithmParser::from_string(compression_algorithm_input_str.substr(6));
        if (!compression_algorithm.ok())
        {
            auto inner_error = compression_algorithm.error();
            return SNPC::monads::Error<Params>().with_error(std::move(inner_error));
        }
        return Params(
                input_file_input_str.substr(5),
                output_file_input_str.substr(6),
                compression_algorithm.value());
    }
};