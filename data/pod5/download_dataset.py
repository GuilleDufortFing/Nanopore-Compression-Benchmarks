#!/usr/bin/env python3
"""Download benchmark datasets and normalize outputs to POD5.

DS1-DS5 are fetched from public S3 prefixes.
DS6-DS10 are fetched from public URLs and converted as needed.
After successful completion, each dataset directory contains only POD5 files.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from importlib import metadata as importlib_metadata
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent
BLOW5_TO_POD5_SCRIPT = REPO_ROOT / "scripts" / "utils" / "blow5_to_pod5.py"


DATASETS = {
    "DS1": {
        "s3_prefix": "s3://ont-open-data/contrib/melanogaster_bkim_2023.01/flowcells/D.melanogaster.R1041.400bps/",
        "file_list": Path("file_lists/DS1.txt"),
        "out_dir": Path("DS1"),
    },
    "example": {
        "s3_prefix": "s3://ont-open-data/contrib/melanogaster_bkim_2023.01/flowcells/D.melanogaster.R1041.400bps/",
        "base_name": "FAV70669_117da01a_45f6321d_0",
        "out_dir": Path("ExamplePod5"),
    },
    "DS2": {
        "s3_prefix": "s3://ont-open-data/gm24385_2020.09/",
        "file_list": Path("file_lists/DS2.txt"),
        "out_dir": Path("DS2"),
    },
    "DS3": {
        "s3_prefix": "s3://ont-open-data/colo829_2024.03/flowcells/colo829/",
        "file_list": Path("file_lists/DS3.txt"),
        "out_dir": Path("DS3"),
    },
    "DS4": {
        "s3_prefix": "s3://ont-open-data/Q20_ULK_Cliveome/",
        "file_list": Path("file_lists/DS4.txt"),
        "out_dir": Path("DS4"),
    },
    "DS5": {
        "s3_prefix": "s3://ont-open-data/giab_2023.05/flowcells/",
        "file_list": Path("file_lists/DS5.txt"),
        "out_dir": Path("DS5"),
    },
    "DS6": {
        "link": "https://zenodo.org/records/14676368/files/SIRV_from_MNXKXX240359.blow5",
        "out_dir": Path("DS6"),
        "raw_name": "SIRV_from_MNXKXX240359.blow5",
        "conversion": "blow5_to_pod5",
    },
    "DS7": {
        "link": "https://sra-pub-src-1.s3.amazonaws.com/SRR31990267/LM41_RKI_merged.0_0.fast5.1",
        "out_dir": Path("DS7"),
        "raw_name": "LM41_RKI_merged.0_0.fast5",
        "conversion": "fast5_to_pod5",
    },
    "DS8": {
        "link": "https://sra-pub-src-1.s3.amazonaws.com/SRR31990260/KP04_MUG_merged.0_0.fast5.1",
        "out_dir": Path("DS8"),
        "raw_name": "KP04_MUG_merged.0_0.fast5",
        "conversion": "fast5_to_pod5",
    },
    "DS9": {
        "link": "https://sra-pub-src-1.s3.amazonaws.com/SRR31990259/KP13_MUG_merged.0_0.fast5.1",
        "out_dir": Path("DS9"),
        "raw_name": "KP13_MUG_merged.0_0.fast5",
        "conversion": "fast5_to_pod5",
    },
    "DS10": {
        "link": "https://zenodo.org/records/10966311/files/poregen_rna004_dataset.zip",
        "out_dir": Path("DS10"),
        "archive_type": "zip",
        "archive_member": "archive_porgen_paper/PNXRXX240010_reads_20k.blow5",
        "raw_name": "poregen_rna004_dataset.blow5",
        "conversion": "blow5_to_pod5",
    },
}


def resolve_local_path(path_value: Path) -> Path:
    if path_value.is_absolute():
        return path_value
    return BASE_DIR / path_value


def format_command(parts: list[str]) -> str:
    return " ".join(parts)


def require_command(command: str, install_hint: str) -> None:
    if shutil.which(command) is None:
        raise SystemExit(f"Missing dependency: {command}. {install_hint}")


def resolve_pod5_python_cli() -> list[str] | None:
    entry_points = importlib_metadata.entry_points()
    if hasattr(entry_points, "select"):
        console_scripts = entry_points.select(group="console_scripts")
    else:
        console_scripts = entry_points.get("console_scripts", [])

    for entry_point in console_scripts:
        if entry_point.name != "pod5":
            continue

        module_name = entry_point.value.split(":", 1)[0]
        probe = subprocess.run(
            [sys.executable, "-m", module_name, "--help"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if probe.returncode == 0:
            return [sys.executable, "-m", module_name]
        break

    return None


def resolve_pod5_cli() -> list[str] | None:
    """Return a command prefix for invoking POD5 CLI, or None if unavailable."""
    python_cli = resolve_pod5_python_cli()
    if python_cli is not None:
        return python_cli

    if shutil.which("pod5") is not None:
        return ["pod5"]

    return None


def resolve_blow5_converter() -> list[str] | None:
    if not BLOW5_TO_POD5_SCRIPT.is_file():
        return None

    probe = subprocess.run(
        [sys.executable, str(BLOW5_TO_POD5_SCRIPT), "--help"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if probe.returncode == 0:
        return [sys.executable, str(BLOW5_TO_POD5_SCRIPT)]

    return None


def build_s3_file_index(s3_prefix: str) -> dict[str, tuple[str, str]]:
    s3_prefix = s3_prefix.rstrip("/") + "/"
    cmd = [
        "aws",
        "s3",
        "ls",
        "--recursive",
        "--no-sign-request",
        s3_prefix,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    bucket = s3_prefix.replace("s3://", "").split("/")[0]
    file_index: dict[str, tuple[str, str]] = {}

    for line in result.stdout.splitlines():
        parts = line.split(maxsplit=3)
        if len(parts) < 4:
            continue

        key = parts[3]
        filename = Path(key).name
        for ext in ("pod5", "fast5"):
            suffix = f".{ext}"
            if not filename.endswith(suffix):
                continue

            base_name = filename[: -len(suffix)]
            s3_path = f"s3://{bucket}/{key}"
            if ext == "pod5" or base_name not in file_index:
                file_index[base_name] = (s3_path, ext)
            break

    return file_index


def s3_find_file(
    base_name: str,
    file_index: dict[str, tuple[str, str]],
    s3_prefix: str,
) -> tuple[str, str]:
    try:
        return file_index[base_name]
    except KeyError as exc:
        raise FileNotFoundError(
            f"No .pod5 or .fast5 found for {base_name} under {s3_prefix}"
        ) from exc


def expected_pod5_path(base_name: str, out_dir: Path) -> Path:
    return out_dir / f"{base_name}.pod5"


def pod5_path_for_raw(raw_path: Path) -> Path:
    return raw_path.with_suffix(".pod5")


def remote_download_path(link: str, out_dir: Path) -> Path:
    return out_dir / os.path.basename(link)


def cleanup_files(paths: list[Path]) -> None:
    seen_paths: set[Path] = set()
    for path in paths:
        if path in seen_paths:
            continue
        seen_paths.add(path)
        if path.exists():
            print(f"Removing intermediate: {path}")
            path.unlink()


def print_dry_run(message: str) -> None:
    print(f"[dry-run] {message}")


def preview_s3_dataset(config: dict[str, object]) -> int:
    s3_prefix = str(config["s3_prefix"])
    file_list = resolve_local_path(config["file_list"])
    out_dir = resolve_local_path(config["out_dir"])

    with file_list.open(encoding="utf-8") as handle:
        base_names = [line.strip().rsplit(".", 1)[0] for line in handle if line.strip()]

    existing_outputs = 0
    pending_names: list[str] = []
    for base_name in base_names:
        pod5_path = expected_pod5_path(base_name, out_dir)
        if pod5_path.exists():
            existing_outputs += 1
        else:
            pending_names.append(base_name)

    print_dry_run(
        f"Dataset {out_dir.name}: inspect {len(base_names)} requested objects under {s3_prefix}"
    )
    if existing_outputs:
        print_dry_run(
            f"{existing_outputs} POD5 outputs already exist and would be skipped"
        )

    if not pending_names:
        print_dry_run("No downloads would be performed")
        return 0

    preview_count = min(len(pending_names), 5)
    for base_name in pending_names[:preview_count]:
        pod5_path = expected_pod5_path(base_name, out_dir)
        print_dry_run(
            f"Resolve {base_name} as .pod5 or .fast5 from {s3_prefix}; download into {out_dir}; convert FAST5 to {pod5_path} only if needed"
        )

    remaining = len(pending_names) - preview_count
    if remaining > 0:
        print_dry_run(f"... plus {remaining} more file(s)")

    return 0


def preview_url_dataset(config: dict[str, object]) -> int:
    out_dir = resolve_local_path(config["out_dir"])
    link = str(config["link"])
    download_path = remote_download_path(link, out_dir)
    conversion = str(config["conversion"])

    if conversion == "fast5_to_pod5":
        pod5_cli = resolve_pod5_cli()
        if pod5_cli is None:
            raise SystemExit(
                "Missing dependency: pod5 CLI. Install pod5 so either 'pod5' or 'python -m pod5' is available."
            )

        raw_path = out_dir / str(config["raw_name"])
        pod5_path = pod5_path_for_raw(raw_path)
        if pod5_path.exists():
            print_dry_run(f"Skip {link} because {pod5_path} already exists")
            return 0

        print_dry_run(f"Download {link} to {download_path}")
        if raw_path != download_path:
            print_dry_run(f"Rename {download_path} to {raw_path}")
        print_dry_run(
            f"Convert FAST5 to POD5 with {format_command([*pod5_cli, 'convert', 'fast5', str(raw_path), '--output', str(pod5_path.parent), '--one-to-one', str(pod5_path.parent), '-t', str(os.cpu_count() or 1)])}"
        )
        print_dry_run(f"Remove intermediates {raw_path} and {download_path}")
        return 0

    blow5_converter = resolve_blow5_converter()
    if blow5_converter is None:
        raise SystemExit(
            "Missing dependency: BLOW5 to POD5 converter. Ensure the repository utility and its Python dependencies are available."
        )

    raw_path = out_dir / str(config["raw_name"])
    pod5_path = pod5_path_for_raw(raw_path)
    if pod5_path.exists():
        print_dry_run(f"Skip {link} because {pod5_path} already exists")
        return 0

    print_dry_run(f"Download {link} to {download_path}")
    if config.get("archive_type") == "zip":
        print_dry_run(
            f"Extract {config['archive_member']} from {download_path} to {raw_path}"
        )
    elif raw_path != download_path:
        print_dry_run(f"Rename {download_path} to {raw_path}")
    print_dry_run(
        f"Convert BLOW5 to POD5 with {format_command([*blow5_converter, str(raw_path), str(pod5_path)])}"
    )
    print_dry_run(f"Remove intermediates {raw_path} and {download_path}")
    return 0


def download_s3_file(s3_path: str, out_dir: Path) -> None:
    cmd = ["aws", "s3", "cp", "--no-sign-request", s3_path, str(out_dir)]
    print(f"Downloading: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def download_public_url(link: str, out_dir: Path) -> Path:
    output_path = remote_download_path(link, out_dir)
    if output_path.exists():
        print(f"Resuming download: {output_path}")
    else:
        print(f"Downloading: wget -c -P {out_dir} {link}")
    subprocess.run(["wget", "-c", "-P", str(out_dir), link], check=True)
    return output_path


def ensure_direct_input(config: dict[str, object], out_dir: Path) -> tuple[Path, Path]:
    link = str(config["link"])
    raw_path = out_dir / str(config["raw_name"])
    download_path = remote_download_path(link, out_dir)

    if raw_path.exists() and raw_path != download_path:
        print(f"Reusing existing input: {raw_path}")
        return raw_path, download_path

    download_path = download_public_url(link, out_dir)
    if raw_path != download_path and not raw_path.exists():
        download_path.replace(raw_path)

    return raw_path, download_path


def extract_zip_member(zip_path: Path, member_name: str, output_path: Path) -> None:
    print(f"Extracting: {member_name} -> {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        try:
            with (
                archive.open(member_name) as source_handle,
                output_path.open("wb") as target_handle,
            ):
                shutil.copyfileobj(source_handle, target_handle)
        except KeyError as exc:
            raise FileNotFoundError(
                f"Archive member {member_name} was not found in {zip_path}"
            ) from exc


def convert_fast5_to_pod5(
    fast5_path: Path, pod5_path: Path, pod5_cli: list[str]
) -> None:
    threads = os.cpu_count() or 1
    cmd = [
        *pod5_cli,
        "convert",
        "fast5",
        str(fast5_path),
        "--output",
        str(pod5_path.parent),
        "--one-to-one",
        str(pod5_path.parent),
        "-t",
        str(threads),
    ]
    print("Converting to POD5:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    if not pod5_path.exists():
        raise RuntimeError(f"FAST5 to POD5 conversion did not create {pod5_path}")


def convert_blow5_to_pod5(
    blow5_path: Path, pod5_path: Path, blow5_converter: list[str]
) -> None:
    cmd = [*blow5_converter, str(blow5_path), str(pod5_path)]
    print("Converting to POD5:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    if not pod5_path.exists():
        raise RuntimeError(f"BLOW5 to POD5 conversion did not create {pod5_path}")


def preview_single_s3_file_dataset(config: dict[str, object]) -> int:
    s3_prefix = str(config["s3_prefix"])
    base_name = str(config["base_name"])
    out_dir = resolve_local_path(config["out_dir"])
    pod5_path = expected_pod5_path(base_name, out_dir)

    if pod5_path.exists():
        print_dry_run(f"Skip {base_name}: {pod5_path} already exists")
        return 0

    print_dry_run(
        f"Dataset {out_dir.name}: resolve {base_name} as .pod5 or .fast5 under {s3_prefix}"
    )
    print_dry_run(
        f"Download into {out_dir}; convert FAST5 to {pod5_path} only if needed"
    )
    return 0


def handle_single_s3_file_dataset(
    config: dict[str, object], dry_run: bool = False
) -> int:
    """Download a single named file from an S3 prefix into out_dir."""
    require_command("aws", "Install the AWS CLI and retry.")
    if dry_run:
        return preview_single_s3_file_dataset(config)

    s3_prefix = str(config["s3_prefix"])
    base_name = str(config["base_name"])
    out_dir = resolve_local_path(config["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    pod5_path = expected_pod5_path(base_name, out_dir)
    fast5_path = out_dir / f"{base_name}.fast5"

    if pod5_path.exists():
        cleanup_files([fast5_path])
        print(f"Skipping existing output: {pod5_path}")
        return 0

    s3_file_index = build_s3_file_index(s3_prefix)

    try:
        s3_path, extension = s3_find_file(base_name, s3_file_index, s3_prefix=s3_prefix)
    except FileNotFoundError as error:
        print(f"ERROR: {error}")
        return 1

    if extension == "pod5":
        download_s3_file(s3_path, out_dir)
        cleanup_files([fast5_path])
    else:
        if fast5_path.exists():
            print(f"Removing stale FAST5 before fresh download: {fast5_path}")
            fast5_path.unlink()

        download_s3_file(s3_path, out_dir)

        pod5_cli = resolve_pod5_cli()
        if pod5_cli is None:
            raise SystemExit(
                "Missing dependency: pod5 CLI. Install pod5 so either 'pod5' or 'python -m pod5' is available."
            )

        convert_fast5_to_pod5(fast5_path, pod5_path, pod5_cli)
        cleanup_files([fast5_path])

    print(f"Done. File processed in {out_dir}")
    return 0


def handle_s3_dataset(config: dict[str, object], dry_run: bool = False) -> int:
    require_command("aws", "Install the AWS CLI and retry.")
    if dry_run:
        return preview_s3_dataset(config)

    s3_prefix = str(config["s3_prefix"])
    file_list = resolve_local_path(config["file_list"])
    out_dir = resolve_local_path(config["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    s3_file_index = build_s3_file_index(s3_prefix)
    pod5_cli: list[str] | None = None

    with file_list.open(encoding="utf-8") as handle:
        base_names = [line.strip().rsplit(".", 1)[0] for line in handle if line.strip()]

    for base_name in base_names:
        pod5_path = expected_pod5_path(base_name, out_dir)
        fast5_path = out_dir / f"{base_name}.fast5"

        if pod5_path.exists():
            cleanup_files([fast5_path])
            print(f"Skipping existing output: {pod5_path}")
            continue

        try:
            s3_path, extension = s3_find_file(
                base_name, s3_file_index, s3_prefix=s3_prefix
            )
        except FileNotFoundError as error:
            print(f"WARNING: {error}")
            continue

        if extension == "pod5":
            download_s3_file(s3_path, out_dir)
            cleanup_files([fast5_path])
            continue

        if fast5_path.exists():
            print(f"Removing stale FAST5 before fresh download: {fast5_path}")
            fast5_path.unlink()

        download_s3_file(s3_path, out_dir)

        if pod5_cli is None:
            pod5_cli = resolve_pod5_cli()
            if pod5_cli is None:
                raise SystemExit(
                    "Missing dependency: pod5 CLI. Install pod5 so either 'pod5' or 'python -m pod5' is available."
                )

        convert_fast5_to_pod5(fast5_path, pod5_path, pod5_cli)
        cleanup_files([fast5_path])

    print(f"Done. All files processed in {out_dir}")
    return 0


def handle_single_file_url_dataset(
    config: dict[str, object],
    out_dir: Path,
    dry_run: bool = False,
) -> int:
    if dry_run:
        return preview_url_dataset(config)

    conversion = str(config["conversion"])
    if conversion == "fast5_to_pod5":
        raw_path, download_path = ensure_direct_input(config, out_dir)
        pod5_path = pod5_path_for_raw(raw_path)
        if pod5_path.exists():
            cleanup_files([raw_path, download_path])
            print(f"Skipping existing output: {pod5_path}")
            return 0

        pod5_cli = resolve_pod5_cli()
        if pod5_cli is None:
            raise SystemExit(
                "Missing dependency: pod5 CLI. Install pod5 so either 'pod5' or 'python -m pod5' is available."
            )
        convert_fast5_to_pod5(raw_path, pod5_path, pod5_cli)
        cleanup_files([raw_path, download_path])
        return 0

    raw_path = out_dir / str(config["raw_name"])
    pod5_path = pod5_path_for_raw(raw_path)
    download_path = remote_download_path(str(config["link"]), out_dir)
    if pod5_path.exists():
        cleanup_files([raw_path, download_path])
        print(f"Skipping existing output: {pod5_path}")
        return 0

    if config.get("archive_type") == "zip":
        download_path = download_public_url(str(config["link"]), out_dir)
        extract_zip_member(download_path, str(config["archive_member"]), raw_path)
    else:
        raw_path, download_path = ensure_direct_input(config, out_dir)

    blow5_converter = resolve_blow5_converter()
    if blow5_converter is None:
        raise SystemExit(
            "Missing dependency: BLOW5 to POD5 converter. Ensure the repository utility and its Python dependencies are available."
        )

    convert_blow5_to_pod5(raw_path, pod5_path, blow5_converter)
    cleanup_files([raw_path, download_path])
    return 0


def handle_url_dataset(config: dict[str, object], dry_run: bool = False) -> int:
    require_command("wget", "Install wget and retry.")
    out_dir = resolve_local_path(config["out_dir"])
    if dry_run:
        return handle_single_file_url_dataset(config, out_dir, dry_run=True)

    out_dir.mkdir(parents=True, exist_ok=True)

    result = handle_single_file_url_dataset(config, out_dir)
    print(f"Done. All files processed in {out_dir}")
    return result


def handle_dataset(dataset_name: str, dry_run: bool = False) -> int:
    selected_dataset = DATASETS[dataset_name]

    if "base_name" in selected_dataset:
        return handle_single_s3_file_dataset(selected_dataset, dry_run=dry_run)
    if "s3_prefix" in selected_dataset:
        return handle_s3_dataset(selected_dataset, dry_run=dry_run)
    if "link" in selected_dataset:
        return handle_url_dataset(selected_dataset, dry_run=dry_run)

    raise ValueError(f"Unknown dataset configuration for {dataset_name}.")


def build_parser() -> argparse.ArgumentParser:
    corpus_names = [name for name in DATASETS if name != "example"]
    dataset_choices = [*corpus_names, "example", "all"]
    parser = argparse.ArgumentParser(
        description="Download benchmark datasets and normalize them to POD5 outputs."
    )
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        choices=dataset_choices,
        help=(
            f"Dataset to download [{', '.join(dataset_choices)}]. "
            "'example' downloads a single representative file into data/pod5/ExamplePod5. "
            "'all' downloads the full corpus DS1–DS10."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned download and conversion steps without generating any files",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.dataset == "all":
        corpus_names = [name for name in DATASETS if name != "example"]
        for dataset_name in corpus_names:
            prefix = "[dry-run] " if args.dry_run else ""
            print(f"{prefix}Processing {dataset_name}...")
            handle_dataset(dataset_name, dry_run=args.dry_run)
        return 0

    return handle_dataset(args.dataset, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
