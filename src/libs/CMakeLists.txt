find_package(ZLIB REQUIRED)

set(SLOW5_LINK_STATIC ON CACHE BOOL "Build slow5lib as a static library" FORCE)

if (TARGET zstd::zstd)
	set(SLOW5_USE_ZSTD ON CACHE BOOL "Enable zstd support in slow5lib" FORCE)
endif()

add_subdirectory(lib-682-nanopore-compression)
add_subdirectory(lib-nanopore-arithmetic-compression)
add_subdirectory(third_party)
add_subdirectory(third_party/slow5lib)

target_link_libraries(slow5 ZLIB::ZLIB)
if (TARGET zstd::zstd)
	target_link_libraries(slow5 zstd::zstd)
endif()

if (UNIX AND NOT APPLE)
	target_link_libraries(slow5 m)
endif()

add_library(
	exzd-wrapper
	STATIC
	exzd_codec.cpp
	exzd_codec.hpp
)

target_include_directories(
	exzd-wrapper
	PUBLIC
	${CMAKE_CURRENT_SOURCE_DIR}
	${CMAKE_CURRENT_SOURCE_DIR}/third_party/slow5lib/include
)

target_link_libraries(
	exzd-wrapper
	PUBLIC
	slow5
)

target_compile_features(exzd-wrapper PUBLIC cxx_std_20)

add_library(
	benchmark-codecs
	STATIC
	benchmark_codecs.cpp
	benchmark_codecs.hpp
)

target_include_directories(
	benchmark-codecs
	PUBLIC
	${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(
	benchmark-codecs
	PUBLIC
	benchmark-common-lib
	exzd-wrapper
	lib-682-nanopore-compression
	pod5_format
	pgnanoCompressionLib
)

target_compile_features(benchmark-codecs PUBLIC cxx_std_20)