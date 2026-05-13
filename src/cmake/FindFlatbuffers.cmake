include_guard(GLOBAL)

set(_nanopore_flatbuffers_hints)
if(DEFINED ENV{CONDA_PREFIX})
    list(APPEND _nanopore_flatbuffers_hints "$ENV{CONDA_PREFIX}")
endif()

# Prefer an upstream config package when one is available, which is common in
# the supported conda environment.
find_package(Flatbuffers QUIET CONFIG HINTS ${_nanopore_flatbuffers_hints})

set(_nanopore_flatbuffers_target "")
foreach(_nanopore_flatbuffers_candidate
    flatbuffers::flatbuffers_shared
    flatbuffers::flatbuffers
    Flatbuffers::flatbuffers_shared
    Flatbuffers::flatbuffers
    Flatbuffers::FlatBuffers
    Flatbuffers::Flatbuffers
    flatbuffers_shared
    flatbuffers
)
    if(TARGET ${_nanopore_flatbuffers_candidate})
        set(_nanopore_flatbuffers_target ${_nanopore_flatbuffers_candidate})
        break()
    endif()
endforeach()

if(_nanopore_flatbuffers_target)
    get_target_property(_nanopore_flatbuffers_include_dirs ${_nanopore_flatbuffers_target} INTERFACE_INCLUDE_DIRECTORIES)
    if(_nanopore_flatbuffers_include_dirs)
        set(FLATBUFFERS_INCLUDE_DIRS ${_nanopore_flatbuffers_include_dirs})
        list(GET _nanopore_flatbuffers_include_dirs 0 FLATBUFFERS_INCLUDE_DIR)
    endif()

    set(FLATBUFFERS_LIBRARY ${_nanopore_flatbuffers_target})
    set(FLATBUFFERS_LIBRARIES ${_nanopore_flatbuffers_target})
endif()

if(NOT FLATBUFFERS_INCLUDE_DIR)
    find_path(
        FLATBUFFERS_INCLUDE_DIR
        NAMES flatbuffers/flatbuffers.h
        HINTS ${_nanopore_flatbuffers_hints}
        PATH_SUFFIXES include
    )

    if(FLATBUFFERS_INCLUDE_DIR)
        set(FLATBUFFERS_INCLUDE_DIRS ${FLATBUFFERS_INCLUDE_DIR})
    endif()
endif()

if(NOT FLATBUFFERS_LIBRARY)
    find_library(
        FLATBUFFERS_LIBRARY
        NAMES flatbuffers
        HINTS ${_nanopore_flatbuffers_hints}
        PATH_SUFFIXES lib lib64
    )

    if(FLATBUFFERS_LIBRARY)
        set(FLATBUFFERS_LIBRARIES ${FLATBUFFERS_LIBRARY})
    endif()
endif()

if(NOT FLATBUFFERS_FLATC_EXECUTABLE)
    if(TARGET flatbuffers::flatc)
        get_target_property(_nanopore_flatc_location flatbuffers::flatc IMPORTED_LOCATION)
    elseif(TARGET Flatbuffers::flatc)
        get_target_property(_nanopore_flatc_location Flatbuffers::flatc IMPORTED_LOCATION)
    endif()

    if(_nanopore_flatc_location)
        set(FLATBUFFERS_FLATC_EXECUTABLE "${_nanopore_flatc_location}")
    endif()
endif()

if(NOT FLATBUFFERS_FLATC_EXECUTABLE)
    find_program(
        FLATBUFFERS_FLATC_EXECUTABLE
        NAMES flatc
        HINTS ${_nanopore_flatbuffers_hints}
        PATH_SUFFIXES bin
    )
endif()

if(FLATBUFFERS_INCLUDE_DIR AND EXISTS "${FLATBUFFERS_INCLUDE_DIR}/flatbuffers/base.h")
    file(STRINGS "${FLATBUFFERS_INCLUDE_DIR}/flatbuffers/base.h" _nanopore_flatbuffers_major_line REGEX "^#define FLATBUFFERS_VERSION_MAJOR[ 	]+[0-9]+$")
    file(STRINGS "${FLATBUFFERS_INCLUDE_DIR}/flatbuffers/base.h" _nanopore_flatbuffers_minor_line REGEX "^#define FLATBUFFERS_VERSION_MINOR[ 	]+[0-9]+$")
    file(STRINGS "${FLATBUFFERS_INCLUDE_DIR}/flatbuffers/base.h" _nanopore_flatbuffers_revision_line REGEX "^#define FLATBUFFERS_VERSION_REVISION[ 	]+[0-9]+$")

    string(REGEX REPLACE "^.*FLATBUFFERS_VERSION_MAJOR[ 	]+([0-9]+)$" "\\1" Flatbuffers_VERSION_MAJOR "${_nanopore_flatbuffers_major_line}")
    string(REGEX REPLACE "^.*FLATBUFFERS_VERSION_MINOR[ 	]+([0-9]+)$" "\\1" Flatbuffers_VERSION_MINOR "${_nanopore_flatbuffers_minor_line}")
    string(REGEX REPLACE "^.*FLATBUFFERS_VERSION_REVISION[ 	]+([0-9]+)$" "\\1" Flatbuffers_VERSION_PATCH "${_nanopore_flatbuffers_revision_line}")

    if(Flatbuffers_VERSION_MAJOR AND Flatbuffers_VERSION_MINOR AND Flatbuffers_VERSION_PATCH)
        set(Flatbuffers_VERSION "${Flatbuffers_VERSION_MAJOR}.${Flatbuffers_VERSION_MINOR}.${Flatbuffers_VERSION_PATCH}")
    endif()
endif()

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(
    Flatbuffers
    REQUIRED_VARS FLATBUFFERS_INCLUDE_DIR FLATBUFFERS_LIBRARY FLATBUFFERS_FLATC_EXECUTABLE
    VERSION_VAR Flatbuffers_VERSION
    REASON_FAILURE_MESSAGE "Install the Flatbuffers development package and the flatc compiler, or use the supported conda environment."
)

if(Flatbuffers_FOUND)
    if(NOT _nanopore_flatbuffers_target)
        add_library(flatbuffers::flatbuffers UNKNOWN IMPORTED)
        set_target_properties(
            flatbuffers::flatbuffers
            PROPERTIES
            IMPORTED_LOCATION "${FLATBUFFERS_LIBRARY}"
            INTERFACE_INCLUDE_DIRECTORIES "${FLATBUFFERS_INCLUDE_DIR}"
        )
        set(_nanopore_flatbuffers_target flatbuffers::flatbuffers)
    endif()

    if(NOT TARGET flatbuffers::flatbuffers)
        add_library(flatbuffers::flatbuffers INTERFACE IMPORTED)
        target_link_libraries(flatbuffers::flatbuffers INTERFACE ${_nanopore_flatbuffers_target})
    endif()

    if(NOT TARGET flatbuffers::flatbuffers_shared)
        add_library(flatbuffers::flatbuffers_shared INTERFACE IMPORTED)
        target_link_libraries(flatbuffers::flatbuffers_shared INTERFACE flatbuffers::flatbuffers)
    endif()

    if(NOT TARGET flatbuffers::flatbuffers_static)
        add_library(flatbuffers::flatbuffers_static INTERFACE IMPORTED)
        target_link_libraries(flatbuffers::flatbuffers_static INTERFACE flatbuffers::flatbuffers)
    endif()
endif()

mark_as_advanced(FLATBUFFERS_INCLUDE_DIR FLATBUFFERS_LIBRARY FLATBUFFERS_FLATC_EXECUTABLE)