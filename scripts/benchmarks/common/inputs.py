import os
from pathlib import Path


def iter_input_files(input_dir, include_file=None):
    root_dir = Path(input_dir).resolve()

    for root, _, files in os.walk(root_dir):
        for file_name in sorted(files):
            file_path = Path(root) / file_name
            if not file_path.is_file():
                continue
            if include_file is not None and not include_file(file_path):
                continue
            yield file_path


def build_output_path(output_dir, input_dir, file_path, suffix=".csv"):
    relative_path = Path(file_path).resolve().relative_to(Path(input_dir).resolve())
    return Path(output_dir) / relative_path.with_suffix(suffix)
