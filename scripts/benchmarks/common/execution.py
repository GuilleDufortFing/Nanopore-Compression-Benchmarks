import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .inputs import build_output_path, iter_input_files
from .runs import ensure_directory


def _run_command_for_output(build_command, file_path, output_path):
    command = build_command(file_path, output_path)
    subprocess.run(command, check=True)
    return output_path


def run_command_on_input_files(
    input_dir,
    output_dir,
    build_command,
    include_file=None,
    max_workers=1,
):
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")

    input_root = Path(input_dir).resolve()
    output_root = Path(output_dir).resolve()

    ensure_directory(output_root)

    planned_runs = []
    for file_path in iter_input_files(input_root, include_file=include_file):
        output_path = build_output_path(output_root, input_root, file_path)
        ensure_directory(output_path.parent)
        print(f"output path: {output_path}")
        planned_runs.append((file_path, output_path))

    if max_workers == 1 or len(planned_runs) <= 1:
        generated_files = []
        for file_path, output_path in planned_runs:
            generated_files.append(
                _run_command_for_output(build_command, file_path, output_path)
            )
        return generated_files

    executor = ThreadPoolExecutor(max_workers=max_workers)
    futures = []
    try:
        for file_path, output_path in planned_runs:
            futures.append(
                executor.submit(
                    _run_command_for_output,
                    build_command,
                    file_path,
                    output_path,
                )
            )

        generated_files = []
        for future in futures:
            generated_files.append(future.result())
        return generated_files
    except Exception:
        for future in futures:
            future.cancel()
        raise
    finally:
        executor.shutdown(wait=True)


def run_algorithm_executable_on_files(
    input_dir,
    output_dir,
    executable,
    algorithm,
    include_file=None,
    max_workers=1,
):
    executable_path = Path(executable).resolve()
    return run_command_on_input_files(
        input_dir,
        output_dir,
        lambda file_path, output_path: [
            str(executable_path),
            f"--in={file_path}",
            f"--out={output_path}",
            f"--alg={algorithm}",
        ],
        include_file=include_file,
        max_workers=max_workers,
    )
