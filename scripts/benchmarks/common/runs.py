import json
import re
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS_ROOT = REPO_ROOT / "results" / "generated"
ARTICLE_RESULTS_ROOT = REPO_ROOT / "results" / "article"


def ensure_directory(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def sanitize_run_component(value):
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    sanitized = sanitized.strip("-._")
    return sanitized or "unnamed"


def build_input_label(input_dir):
    input_path = Path(input_dir).resolve()
    input_name = input_path.name
    layer_name = input_path.parent.name
    parent_root_name = input_path.parent.parent.name

    if parent_root_name == "benchmark_bin" and (layer_name == "full" or layer_name.isdigit()):
        return sanitize_run_component(f"{layer_name}_{input_name}")

    return sanitize_run_component(input_name)


def build_run_id(input_dir, algorithms_token, timestamp=None):
    if timestamp is None:
        timestamp = datetime.now()

    timestamp_token = timestamp.strftime("%Y%m%dT%H%M%S")
    input_name = build_input_label(input_dir)
    algorithm_name = sanitize_run_component(algorithms_token)
    return f"{timestamp_token}_{algorithm_name}_{input_name}"


def resolve_results_root(results_root=None):
    base_path = DEFAULT_RESULTS_ROOT if results_root is None else Path(results_root)
    return base_path.expanduser().resolve()


def create_run_directories(results_root, run_id, benchmark_type=None):
    run_parent = resolve_results_root(results_root)
    if benchmark_type is not None:
        run_parent = run_parent / sanitize_run_component(benchmark_type)

    run_root = run_parent / run_id
    raw_root = run_root / "raw"
    summaries_root = run_root / "summaries"
    ensure_directory(raw_root)
    ensure_directory(summaries_root)
    return run_root, raw_root, summaries_root


def write_run_manifest(run_root, manifest):
    manifest_path = Path(run_root) / "run_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return manifest_path
