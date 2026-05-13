include_guard(GLOBAL)

set(_nanopore_zstd_hints)
if(DEFINED ENV{CONDA_PREFIX})
    list(APPEND _nanopore_zstd_hints "$ENV{CONDA_PREFIX}")
endif()

get_filename_component(_nanopore_legacy_zstd_dir "${CMAKE_SOURCE_DIR}/cmake" ABSOLUTE)
if(DEFINED zstd_DIR AND zstd_DIR STREQUAL "${_nanopore_legacy_zstd_dir}")
    unset(zstd_DIR CACHE)
endif()

# Prefer an upstream config package when one is available, which is the common
# case inside the supported conda environment.
find_package(zstd QUIET CONFIG HINTS ${_nanopore_zstd_hints})

set(_nanopore_zstd_target "")
if(TARGET zstd::zstd)
    set(_nanopore_zstd_target zstd::zstd)
elseif(TARGET zstd::libzstd)
    set(_nanopore_zstd_target zstd::libzstd)
elseif(TARGET zstd::libzstd_static)
    set(_nanopore_zstd_target zstd::libzstd_static)
elseif(TARGET zstd::libzstd_shared)
    set(_nanopore_zstd_target zstd::libzstd_shared)
endif()

if(NOT _nanopore_zstd_target)
    find_path(
        ZSTD_INCLUDE_DIR
        NAMES zstd.h
        HINTS ${_nanopore_zstd_hints}
        PATH_SUFFIXES include
    )

    find_library(
        ZSTD_LIBRARY
        NAMES zstd libzstd
        HINTS ${_nanopore_zstd_hints}
        PATH_SUFFIXES lib lib64
    )

    if(ZSTD_INCLUDE_DIR AND EXISTS "${ZSTD_INCLUDE_DIR}/zstd.h")
        file(STRINGS "${ZSTD_INCLUDE_DIR}/zstd.h" _nanopore_zstd_major_line REGEX "^#define ZSTD_VERSION_MAJOR[ 	]+[0-9]+$")
        file(STRINGS "${ZSTD_INCLUDE_DIR}/zstd.h" _nanopore_zstd_minor_line REGEX "^#define ZSTD_VERSION_MINOR[ 	]+[0-9]+$")
        file(STRINGS "${ZSTD_INCLUDE_DIR}/zstd.h" _nanopore_zstd_release_line REGEX "^#define ZSTD_VERSION_RELEASE[ 	]+[0-9]+$")

        string(REGEX REPLACE "^.*ZSTD_VERSION_MAJOR[ 	]+([0-9]+)$" "\\1" zstd_VERSION_MAJOR "${_nanopore_zstd_major_line}")
        string(REGEX REPLACE "^.*ZSTD_VERSION_MINOR[ 	]+([0-9]+)$" "\\1" zstd_VERSION_MINOR "${_nanopore_zstd_minor_line}")
        string(REGEX REPLACE "^.*ZSTD_VERSION_RELEASE[ 	]+([0-9]+)$" "\\1" zstd_VERSION_PATCH "${_nanopore_zstd_release_line}")
        set(zstd_VERSION "${zstd_VERSION_MAJOR}.${zstd_VERSION_MINOR}.${zstd_VERSION_PATCH}")
    endif()

    include(FindPackageHandleStandardArgs)
    find_package_handle_standard_args(
        zstd
        REQUIRED_VARS ZSTD_LIBRARY ZSTD_INCLUDE_DIR
        VERSION_VAR zstd_VERSION
        REASON_FAILURE_MESSAGE "Install the zstd development package or use the supported conda environment."
    )

    if(zstd_FOUND AND NOT TARGET zstd::zstd)
        add_library(zstd::zstd UNKNOWN IMPORTED)
        set_target_properties(
            zstd::zstd
            PROPERTIES
            IMPORTED_LOCATION "${ZSTD_LIBRARY}"
            INTERFACE_INCLUDE_DIRECTORIES "${ZSTD_INCLUDE_DIR}"
        )
    endif()

    if(zstd_FOUND)
        set(_nanopore_zstd_target zstd::zstd)
        set(ZSTD_INCLUDE_DIRS "${ZSTD_INCLUDE_DIR}")
        set(ZSTD_LIBRARIES "${ZSTD_LIBRARY}")
    endif()
else()
    set(zstd_FOUND TRUE)
    set(ZSTD_LIBRARIES "${_nanopore_zstd_target}")
endif()

if(zstd_FOUND)
    if(NOT TARGET zstd::zstd)
        add_library(zstd::zstd INTERFACE IMPORTED)
        target_link_libraries(zstd::zstd INTERFACE ${_nanopore_zstd_target})
    endif()

    if(NOT TARGET zstd::libzstd)
        add_library(zstd::libzstd INTERFACE IMPORTED)
        target_link_libraries(zstd::libzstd INTERFACE zstd::zstd)
    endif()

    if(NOT TARGET zstd::libzstd_shared)
        add_library(zstd::libzstd_shared INTERFACE IMPORTED)
        target_link_libraries(zstd::libzstd_shared INTERFACE zstd::zstd)
    endif()

    if(NOT TARGET zstd::libzstd_static)
        add_library(zstd::libzstd_static INTERFACE IMPORTED)
        target_link_libraries(zstd::libzstd_static INTERFACE zstd::zstd)
    endif()
endif()

mark_as_advanced(ZSTD_INCLUDE_DIR ZSTD_LIBRARY)