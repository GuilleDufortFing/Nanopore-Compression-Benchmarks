"""Shared helpers for article analysis notebooks."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from common.algorithms import CANONICAL_ALGORITHM_ORDER, RAW_ALGORITHM_NAMES
from common.runs import REPO_ROOT as COMMON_REPO_ROOT


DISPLAY_TO_RAW_ALGORITHM = dict(RAW_ALGORITHM_NAMES)
RAW_TO_DISPLAY_ALGORITHM = {
    raw_name: display_name
    for display_name, raw_name in DISPLAY_TO_RAW_ALGORITHM.items()
}


def detect_repo_root(start: Path | None = None) -> Path:
    candidate = (start or Path.cwd()).resolve()
    for current in [candidate, *candidate.parents]:
        if (current / "results").is_dir() and (current / "scripts").is_dir():
            return current
    return COMMON_REPO_ROOT


def display_algorithm_name(algorithm: str) -> str:
    return RAW_TO_DISPLAY_ALGORITHM.get(algorithm, algorithm)


def candidate_algorithm_names(algorithm: str) -> list[str]:
    candidates = [algorithm]
    if algorithm in DISPLAY_TO_RAW_ALGORITHM:
        candidates.append(DISPLAY_TO_RAW_ALGORITHM[algorithm])
    if algorithm in RAW_TO_DISPLAY_ALGORITHM:
        candidates.append(RAW_TO_DISPLAY_ALGORITHM[algorithm])
    return list(dict.fromkeys(candidates))


def resolve_available_algorithm(algorithm: str, available_algorithms: set[str]) -> str:
    for candidate in candidate_algorithm_names(algorithm):
        if candidate in available_algorithms:
            return candidate
    return candidate_algorithm_names(algorithm)[0]


def normalize_requested_algorithms(algorithms: list[str]) -> list[str]:
    return list(
        dict.fromkeys(display_algorithm_name(algorithm) for algorithm in algorithms)
    )


def sort_algorithms(algorithms) -> list[str]:
    unique_algorithms = list(
        dict.fromkeys(display_algorithm_name(algorithm) for algorithm in algorithms)
    )
    canonical = [
        algorithm
        for algorithm in CANONICAL_ALGORITHM_ORDER
        if algorithm in unique_algorithms
    ]
    extras = sorted(
        algorithm
        for algorithm in unique_algorithms
        if algorithm not in CANONICAL_ALGORITHM_ORDER
    )
    return canonical + extras


def load_run_manifest(run_dir: Path) -> dict:
    manifest_path = Path(run_dir) / "run_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing run manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def dataset_input_dir_from_manifest(manifest: dict) -> Path:
    input_dir = manifest.get("input_dir")
    if not input_dir:
        raise KeyError("Run manifest is missing the 'input_dir' field.")
    return Path(input_dir)


def dataset_name_from_manifest(manifest: dict) -> str:
    return dataset_input_dir_from_manifest(manifest).name


def summary_stem_from_manifest(manifest: dict) -> str:
    input_dir = dataset_input_dir_from_manifest(manifest)
    parent_name = input_dir.parent.name
    if parent_name in {"full"} or parent_name.isdigit():
        return f"{parent_name}_{input_dir.name}"
    return input_dir.name


def discover_named_runs(
    results_root: Path,
    *,
    allowlist: list[str] | None = None,
    denylist: list[str] | None = None,
) -> list[dict[str, Path]]:
    discovered_runs: list[dict[str, Path]] = []
    denylist = denylist or []

    if not results_root.is_dir():
        raise FileNotFoundError(f"Missing results directory: {results_root}")

    for run_dir in sorted(results_root.iterdir()):
        if not run_dir.is_dir():
            continue
        if allowlist and run_dir.name not in allowlist:
            continue
        if run_dir.name in denylist:
            continue
        if not (run_dir / "run_manifest.json").is_file():
            continue
        if not (run_dir / "summaries").is_dir():
            continue
        discovered_runs.append({"label": run_dir.name, "run_dir": run_dir.resolve()})

    if not discovered_runs:
        raise FileNotFoundError(f"No run directories found under {results_root}")

    return discovered_runs


def latest_result_run(results_root: Path) -> Path:
    if not results_root.is_dir():
        raise FileNotFoundError(f"Missing results directory: {results_root}")

    run_dirs = sorted(
        child.resolve()
        for child in results_root.iterdir()
        if child.is_dir() and (child / "summaries").is_dir()
    )
    if not run_dirs:
        raise FileNotFoundError(f"No benchmark runs found under {results_root}")
    return run_dirs[-1]


def build_file_index_table(frame: pd.DataFrame) -> pd.DataFrame:
    file_order = sorted(frame["File"].dropna().unique())
    return pd.DataFrame(
        {
            "file_index": np.arange(1, len(file_order) + 1),
            "File": file_order,
        }
    )