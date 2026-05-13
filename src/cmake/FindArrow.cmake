include_guard(GLOBAL)

function(_nanopore_arrow_get_imported_location target_name output_variable)
    foreach(property_name
        IMPORTED_LOCATION_RELEASE
        IMPORTED_LOCATION_RELWITHDEBINFO
        IMPORTED_LOCATION_MINSIZEREL
        IMPORTED_LOCATION_DEBUG
        IMPORTED_LOCATION
    )
        get_target_property(_nanopore_arrow_location ${target_name} ${property_name})
        if(_nanopore_arrow_location AND NOT _nanopore_arrow_location MATCHES "-NOTFOUND$")
            set(${output_variable} "${_nanopore_arrow_location}" PARENT_SCOPE)
            return()
        endif()
    endforeach()

    set(${output_variable} "" PARENT_SCOPE)
endfunction()

set(_nanopore_arrow_hints)
if(DEFINED ENV{CONDA_PREFIX})
    list(APPEND _nanopore_arrow_hints "$ENV{CONDA_PREFIX}")
endif()
if(DEFINED ENV{ARROW_HOME})
    list(APPEND _nanopore_arrow_hints "$ENV{ARROW_HOME}")
endif()

# Prefer an upstream config package when one is available, which is common in
# the supported conda environment and on some native distributions.
find_package(Arrow QUIET CONFIG NO_MODULE HINTS ${_nanopore_arrow_hints})

set(_nanopore_arrow_target "")
foreach(_nanopore_arrow_candidate
    Arrow::arrow_shared
    Arrow::arrow_static
    Arrow::arrow
    arrow::arrow
    arrow::arrow_shared
    arrow::arrow_static
    arrow_shared
    arrow
)
    if(TARGET ${_nanopore_arrow_candidate})
        set(_nanopore_arrow_target ${_nanopore_arrow_candidate})
        break()
    endif()
endforeach()

if(_nanopore_arrow_target)
    get_target_property(_nanopore_arrow_include_dirs ${_nanopore_arrow_target} INTERFACE_INCLUDE_DIRECTORIES)
    if(_nanopore_arrow_include_dirs)
        set(ARROW_INCLUDE_DIRS ${_nanopore_arrow_include_dirs})
        list(GET _nanopore_arrow_include_dirs 0 ARROW_INCLUDE_DIR)
    endif()

    _nanopore_arrow_get_imported_location(${_nanopore_arrow_target} _nanopore_arrow_imported_location)
    if(_nanopore_arrow_imported_location)
        set(ARROW_SHARED_LIB ${_nanopore_arrow_imported_location})
        set(ARROW_LIBRARIES ${_nanopore_arrow_imported_location})
    else()
        set(ARROW_LIBRARIES ${_nanopore_arrow_target})
    endif()

    if(DEFINED Arrow_VERSION AND NOT DEFINED ARROW_VERSION)
        set(ARROW_VERSION ${Arrow_VERSION})
    endif()
endif()

if(NOT _nanopore_arrow_target)
    find_package(PkgConfig QUIET)
    if(PkgConfig_FOUND)
        pkg_check_modules(PC_ARROW QUIET arrow)
    endif()

    set(_nanopore_arrow_include_hints ${_nanopore_arrow_hints})
    set(_nanopore_arrow_library_hints ${_nanopore_arrow_hints})
    if(PC_ARROW_INCLUDE_DIRS)
        list(APPEND _nanopore_arrow_include_hints ${PC_ARROW_INCLUDE_DIRS})
    endif()
    if(PC_ARROW_LIBRARY_DIRS)
        list(APPEND _nanopore_arrow_library_hints ${PC_ARROW_LIBRARY_DIRS})
    endif()

    find_path(
        ARROW_INCLUDE_DIR
        NAMES arrow/api.h
        HINTS ${_nanopore_arrow_include_hints}
        PATH_SUFFIXES include
    )

    find_library(
        ARROW_SHARED_LIB
        NAMES arrow libarrow
        HINTS ${_nanopore_arrow_library_hints}
        PATH_SUFFIXES lib lib64
    )

    if(PC_ARROW_VERSION)
        set(ARROW_VERSION ${PC_ARROW_VERSION})
    elseif(ARROW_INCLUDE_DIR AND EXISTS "${ARROW_INCLUDE_DIR}/arrow/util/config.h")
        file(STRINGS "${ARROW_INCLUDE_DIR}/arrow/util/config.h" _nanopore_arrow_major_line REGEX "^#define ARROW_VERSION_MAJOR[ \t]+[0-9]+$")
        file(STRINGS "${ARROW_INCLUDE_DIR}/arrow/util/config.h" _nanopore_arrow_minor_line REGEX "^#define ARROW_VERSION_MINOR[ \t]+[0-9]+$")
        file(STRINGS "${ARROW_INCLUDE_DIR}/arrow/util/config.h" _nanopore_arrow_patch_line REGEX "^#define ARROW_VERSION_PATCH[ \t]+[0-9]+$")

        string(REGEX REPLACE "^.*ARROW_VERSION_MAJOR[ \t]+([0-9]+)$" "\\1" ARROW_VERSION_MAJOR "${_nanopore_arrow_major_line}")
        string(REGEX REPLACE "^.*ARROW_VERSION_MINOR[ \t]+([0-9]+)$" "\\1" ARROW_VERSION_MINOR "${_nanopore_arrow_minor_line}")
        string(REGEX REPLACE "^.*ARROW_VERSION_PATCH[ \t]+([0-9]+)$" "\\1" ARROW_VERSION_PATCH "${_nanopore_arrow_patch_line}")

        if(ARROW_VERSION_MAJOR AND ARROW_VERSION_MINOR AND ARROW_VERSION_PATCH)
            set(ARROW_VERSION "${ARROW_VERSION_MAJOR}.${ARROW_VERSION_MINOR}.${ARROW_VERSION_PATCH}")
        endif()
    endif()

    include(FindPackageHandleStandardArgs)
    find_package_handle_standard_args(
        Arrow
        REQUIRED_VARS ARROW_INCLUDE_DIR ARROW_SHARED_LIB
        VERSION_VAR ARROW_VERSION
        REASON_FAILURE_MESSAGE "Install the Arrow development package or use the supported conda environment."
    )

    if(Arrow_FOUND)
        set(ARROW_INCLUDE_DIRS ${ARROW_INCLUDE_DIR})
        set(ARROW_LIBRARIES ${ARROW_SHARED_LIB})

        add_library(Arrow::arrow_shared UNKNOWN IMPORTED)
        set_target_properties(
            Arrow::arrow_shared
            PROPERTIES
            IMPORTED_LOCATION "${ARROW_SHARED_LIB}"
            INTERFACE_INCLUDE_DIRECTORIES "${ARROW_INCLUDE_DIR}"
        )
        set(_nanopore_arrow_target Arrow::arrow_shared)
    endif()
endif()

if(_nanopore_arrow_target AND NOT TARGET Arrow::arrow_shared)
    add_library(Arrow::arrow_shared INTERFACE IMPORTED)
    target_link_libraries(Arrow::arrow_shared INTERFACE ${_nanopore_arrow_target})
endif()

if(TARGET Arrow::arrow_shared)
    set(Arrow_FOUND TRUE)
    set(ARROW_FOUND TRUE)

    if(NOT ARROW_LIBRARIES)
        set(ARROW_LIBRARIES Arrow::arrow_shared)
    endif()
endif()

mark_as_advanced(ARROW_INCLUDE_DIR ARROW_SHARED_LIB)