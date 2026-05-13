add_executable(time_split_benchmark time_split_benchmark.cpp)
target_compile_options(time_split_benchmark PRIVATE -Werror -Wall -Wno-comment -Wextra)

find_package(Boost REQUIRED COMPONENTS filesystem)
include_directories(${Boost_INCLUDE_DIRS})

target_link_libraries(time_split_benchmark PUBLIC pod5_format_time_split)
target_link_libraries(time_split_benchmark PUBLIC Boost::filesystem)
target_compile_features(time_split_benchmark PRIVATE cxx_std_20)