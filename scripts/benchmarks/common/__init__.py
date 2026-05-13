"""Shared helpers for benchmark runner scripts."""

from .execution import run_command_on_input_files
from .executables import (
	BUILD_BIN_ROOT,
	PRECOMPILED_BIN_ROOT,
	REPO_ROOT,
	build_local_executable_path,
	executable_file_name,
	iter_local_executable_candidates,
	normalize_platform_token,
	resolve_named_executable,
)
from .inputs import build_output_path, iter_input_files
from .runs import (
	ARTICLE_RESULTS_ROOT,
	DEFAULT_RESULTS_ROOT,
	build_run_id,
	create_run_directories,
	ensure_directory,
	resolve_results_root,
	sanitize_run_component,
	write_run_manifest,
)

__all__ = [
	"ARTICLE_RESULTS_ROOT",
	"BUILD_BIN_ROOT",
	"DEFAULT_RESULTS_ROOT",
	"PRECOMPILED_BIN_ROOT",
	"REPO_ROOT",
	"build_local_executable_path",
	"build_output_path",
	"build_run_id",
	"create_run_directories",
	"ensure_directory",
	"executable_file_name",
	"iter_input_files",
	"iter_local_executable_candidates",
	"normalize_platform_token",
	"resolve_named_executable",
	"resolve_results_root",
	"run_command_on_input_files",
	"sanitize_run_component",
	"write_run_manifest",
]

