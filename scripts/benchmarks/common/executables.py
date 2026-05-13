import platform
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BUILD_BIN_ROOT = REPO_ROOT / "build" / "bin"
PRECOMPILED_BIN_ROOT = REPO_ROOT / "pre-compiled-bins"


def normalize_platform_token():
    system_name = platform.system().lower()
    machine_name = platform.machine().lower()

    normalized_system = {
        "linux": "linux",
        "darwin": "macos",
        "windows": "windows",
    }.get(system_name, system_name)
    normalized_machine = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }.get(machine_name, machine_name)

    return f"{normalized_system}-{normalized_machine}"


def executable_file_name(executable_name):
    if platform.system().lower().startswith("win") and not executable_name.endswith(".exe"):
        return f"{executable_name}.exe"
    return executable_name


def build_local_executable_path(executable_name):
    return BUILD_BIN_ROOT / executable_file_name(executable_name)


def iter_local_executable_candidates(executable_name):
    executable = executable_file_name(executable_name)
    candidates = [build_local_executable_path(executable_name)]

    for build_dir in sorted(REPO_ROOT.glob("build*")):
        if not build_dir.is_dir() or build_dir.name == "build":
            continue
        candidates.append(build_dir / "bin" / executable)
        candidates.append(build_dir / "Release" / "bin" / executable)

    unique_candidates = []
    seen = set()
    for candidate in candidates:
        candidate_str = str(candidate)
        if candidate_str in seen:
            continue
        seen.add(candidate_str)
        unique_candidates.append(candidate)

    return unique_candidates


def build_precompiled_executable_path(executable_name, platform_token=None):
    token = normalize_platform_token() if platform_token is None else platform_token
    return (
        PRECOMPILED_BIN_ROOT
        / token
        / executable_name
        / executable_file_name(executable_name)
    )


def resolve_named_executable(executable_name, executable=None):
    if executable is not None:
        resolved = Path(executable).expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Executable override not found at '{resolved}'.")
        return resolved

    local_candidates = iter_local_executable_candidates(executable_name)
    for local_candidate in local_candidates:
        if local_candidate.is_file():
            return local_candidate.resolve()

    platform_token = normalize_platform_token()
    precompiled_candidate = build_precompiled_executable_path(executable_name, platform_token)
    if precompiled_candidate.is_file():
        return precompiled_candidate.resolve()

    searched_candidates = [str(path) for path in local_candidates]
    searched_candidates.append(str(precompiled_candidate))

    raise FileNotFoundError(
        "\n".join(
            [
                f"Executable '{executable_name}' was not found.",
                "Searched local build outputs:",
                *[f"  - {path}" for path in searched_candidates[:-1]],
                f"Searched pre-compiled fallback: '{searched_candidates[-1]}'.",
                (
                    f"No compatible pre-compiled binary was found for platform "
                    f"'{platform_token}'. Compile the binaries following README.md."
                ),
            ]
        )
    )
