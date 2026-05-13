"""Speed benchmark algorithm registry and selection helpers."""

SUPPORTED_ALGORITHMS = {
    "VBZ": "VBZ implementation from pod5",
    "EX-ZD": "EX-ZD implementation from slow5lib",
    "EX-ZD-ZLIB": "EX-ZD wrapped with zlib on the encoded signal buffer",
    "EX-ZD-ZSTD": "EX-ZD wrapped with zstd on the encoded signal buffer",
    "CA": "Arithmetic compression",
    "PDZSerial": "PDZ compression without SIMD",
    "PDZ": "PDZ compression using SIMD acceleration",
}
RAW_ALGORITHM_NAMES = {
    "PDZSerial": "682Serial",
    "PDZ": "682SSE",
}
CANONICAL_ALGORITHM_ORDER = tuple(SUPPORTED_ALGORITHMS.keys())


def build_algorithms_help():
    return "\n".join(
        f"  {name:<10} {description}"
        for name, description in SUPPORTED_ALGORITHMS.items()
    )


def validate_algorithm(algorithm):
    if algorithm not in SUPPORTED_ALGORITHMS:
        supported = ", ".join(CANONICAL_ALGORITHM_ORDER)
        raise ValueError(
            f"Unsupported algorithm '{algorithm}'. Supported values: {supported}"
        )

    return algorithm


def get_raw_algorithm_name(algorithm):
    validated_algorithm = validate_algorithm(algorithm)
    return RAW_ALGORITHM_NAMES.get(validated_algorithm, validated_algorithm)


def get_raw_algorithm_names(algorithms):
    return [get_raw_algorithm_name(algorithm) for algorithm in algorithms]


def build_algorithm_token(algorithms, raw=False):
    if raw:
        return "-".join(get_raw_algorithm_names(algorithms))

    return "-".join(validate_algorithm(algorithm) for algorithm in algorithms)


def normalize_algorithm_selection(algorithm_tokens):
    if not algorithm_tokens:
        raise ValueError("At least one algorithm must be provided")

    normalized_tokens = []
    for token in algorithm_tokens:
        parts = [part.strip() for part in token.split(",")]
        normalized_tokens.extend(part for part in parts if part)

    if not normalized_tokens:
        raise ValueError("No valid algorithms were provided")

    invalid = [
        token for token in normalized_tokens if token not in SUPPORTED_ALGORITHMS
    ]
    if invalid:
        invalid_text = ", ".join(invalid)
        raise ValueError(f"Unsupported algorithms: {invalid_text}")

    seen = set()
    selected = []
    for algorithm in CANONICAL_ALGORITHM_ORDER:
        if algorithm in normalized_tokens and algorithm not in seen:
            selected.append(algorithm)
            seen.add(algorithm)

    if not selected:
        raise ValueError("No algorithms were selected")

    return selected, build_algorithm_token(selected)
