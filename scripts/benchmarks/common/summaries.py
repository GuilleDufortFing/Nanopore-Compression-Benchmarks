import csv
import glob
import os
import statistics


COMPRESSION_SUMMARY_FIELDNAMES = [
    "File",
    "total_chunks",
    "total_samples",
    "total_compressed_bytes",
    "bits_per_sample",
    "successful_chunk_count",
    "failed_chunk_count",
    "success_rate",
    "any_failed",
]


def _build_summary_output_name(input_dir, root):
    input_dir_name = os.path.basename(os.path.normpath(input_dir))
    relative_dir = os.path.relpath(root, input_dir)
    if relative_dir == ".":
        return f"{input_dir_name}.csv"
    return relative_dir.replace(os.sep, "__") + ".csv"


def _walk_and_process(input_dir, output_path, process_directory):
    generated_files = []
    for root, _, _ in os.walk(input_dir):
        output_name = _build_summary_output_name(input_dir, root)
        output_file = os.path.join(output_path, output_name)
        print(root, output_file)
        if process_directory(root, output_file):
            generated_files.append(output_file)

    return generated_files


def _parse_required_int(row, column_name, file_path):
    raw_value = row.get(column_name)
    if raw_value in (None, ""):
        raise ValueError(f"Missing required column '{column_name}' in {file_path}")

    try:
        return int(raw_value)
    except ValueError:
        try:
            return int(float(raw_value))
        except ValueError as error:
            raise ValueError(
                f"Invalid integer value for column '{column_name}' in {file_path}: {raw_value!r}"
            ) from error


def _parse_required_success_flag(row, column_name, file_path):
    raw_value = row.get(column_name)
    if raw_value in (None, ""):
        raise ValueError(f"Missing required column '{column_name}' in {file_path}")

    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False

    try:
        return float(normalized) != 0.0
    except ValueError as error:
        raise ValueError(
            f"Invalid success flag for column '{column_name}' in {file_path}: {raw_value!r}"
        ) from error


def process_csv_files(directory, output_file):
    """
    Input: directory containing csv files

    Writes in the given output csv file the averages of the columns on each
    input file and the name of the file.
    """

    csv_files = glob.glob(os.path.join(directory, "*.csv"))
    print(f"Found {len(csv_files)} CSV files in directory {directory}")

    if not csv_files:
        return False

    averages_list = []

    for file in csv_files:
        print(f"Processing file: {file}")
        with open(file, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)

        print(f"DataFrame shape: ({len(rows)}, {len(reader.fieldnames or [])})")

        if not rows:
            continue

        numeric_values = {}
        for row in rows:
            for column, raw_value in row.items():
                if column == "File" or raw_value in (None, ""):
                    continue

                try:
                    value = float(raw_value)
                except ValueError:
                    continue

                numeric_values.setdefault(column, []).append(value)

        averages = {
            column: statistics.fmean(values)
            for column, values in numeric_values.items()
            if values
        }
        averages["File"] = os.path.basename(file)

        compression_values = numeric_values.get("compression_speed_mb_sec", [])
        decompression_values = numeric_values.get("decompression_speed_mb_sec", [])
        std_dev_compression = (
            statistics.stdev(compression_values)
            if len(compression_values) > 1
            else 0.0
        )
        std_dev_decompression = (
            statistics.stdev(decompression_values)
            if len(decompression_values) > 1
            else 0.0
        )
        print(f"Standard Deviation Compression speed: {std_dev_compression}")
        print(f"Standard Deviation Decompression speed: {std_dev_decompression}")

        averages["StdDev_Compression_speed"] = std_dev_compression
        averages["StdDev_Decompression_speed"] = std_dev_decompression

        averages_list.append(averages)

    if not averages_list:
        return False

    fieldnames = ["File"]
    for record in averages_list:
        for column in record:
            if column != "File" and column not in fieldnames:
                fieldnames.append(column)

    print(averages_list)

    with open(output_file, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(averages_list)

    return True


def process_compression_csv_files(directory, output_file):
    csv_files = glob.glob(os.path.join(directory, "*.csv"))
    print(f"Found {len(csv_files)} CSV files in directory {directory}")

    if not csv_files:
        return False

    summary_rows = []
    for file_path in csv_files:
        print(f"Processing file: {file_path}")
        with open(file_path, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        if not rows:
            continue

        total_chunks = len(rows)
        total_samples = sum(
            _parse_required_int(row, "num_samples", file_path)
            for row in rows
        )
        total_compressed_bytes = sum(
            _parse_required_int(row, "compressed_bytes", file_path)
            for row in rows
        )
        successful_chunk_count = sum(
            1
            for row in rows
            if _parse_required_success_flag(row, "is_correct", file_path)
        )
        failed_chunk_count = total_chunks - successful_chunk_count

        summary_rows.append(
            {
                "File": os.path.basename(file_path),
                "total_chunks": total_chunks,
                "total_samples": total_samples,
                "total_compressed_bytes": total_compressed_bytes,
                "bits_per_sample": (
                    (8.0 * total_compressed_bytes) / total_samples
                    if total_samples > 0
                    else 0.0
                ),
                "successful_chunk_count": successful_chunk_count,
                "failed_chunk_count": failed_chunk_count,
                "success_rate": successful_chunk_count / total_chunks,
                "any_failed": 1 if failed_chunk_count > 0 else 0,
            }
        )

    if not summary_rows:
        return False

    with open(output_file, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPRESSION_SUMMARY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(summary_rows)

    return True


def walk_and_process(input_dir, output_path):
    return _walk_and_process(input_dir, output_path, process_csv_files)


def walk_and_process_compression(input_dir, output_path):
    return _walk_and_process(input_dir, output_path, process_compression_csv_files)
