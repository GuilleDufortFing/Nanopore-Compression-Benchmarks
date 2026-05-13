import argparse
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import numpy as np
import pod5
import pyslow5


END_REASON_MAP = {
    "unknown": pod5.EndReasonEnum.UNKNOWN,
    "partial": pod5.EndReasonEnum.UNKNOWN,
    "mux_change": pod5.EndReasonEnum.MUX_CHANGE,
    "unblock_mux_change": pod5.EndReasonEnum.UNBLOCK_MUX_CHANGE,
    "data_service_unblock_mux_change": pod5.EndReasonEnum.DATA_SERVICE_UNBLOCK_MUX_CHANGE,
    "signal_positive": pod5.EndReasonEnum.SIGNAL_POSITIVE,
    "signal_negative": pod5.EndReasonEnum.SIGNAL_NEGATIVE,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a BLOW5 file into a POD5 file using pyslow5 backed by slow5lib."
        )
    )
    parser.add_argument("input_blow5", help="Path to the input BLOW5 file")
    parser.add_argument("output_pod5", help="Path to the output POD5 file")
    return parser.parse_args()


def parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, timezone.utc)

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def to_int(value: object, default: int = 0) -> int:
    if value is None or value == "":
        return default
    return int(value)


def to_float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def to_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def to_uuid(read_id: str) -> UUID:
    try:
        return UUID(read_id)
    except ValueError:
        return uuid5(NAMESPACE_URL, read_id)


def build_run_info(headers: dict[str, object], sample_rate: int, digitisation: float) -> pod5.RunInfo:
    half_range = max(int(round(digitisation / 2.0)), 1)
    context_tags = {
        key: to_text(headers.get(key))
        for key in [
            "package",
            "package_version",
            "experiment_type",
            "sample_frequency",
            "sequencing_kit",
            "exp_script_name",
            "exp_script_purpose",
        ]
        if headers.get(key) is not None
    }
    tracking_id = {
        key: to_text(value)
        for key, value in headers.items()
        if value is not None
    }

    return pod5.RunInfo(
        acquisition_id=to_text(headers.get("run_id")),
        acquisition_start_time=parse_timestamp(to_text(headers.get("exp_start_time"), None)),
        adc_max=half_range - 1,
        adc_min=-half_range,
        context_tags=context_tags,
        experiment_name=to_text(headers.get("protocol_group_id")),
        flow_cell_id=to_text(headers.get("flow_cell_id")),
        flow_cell_product_code=to_text(headers.get("flow_cell_product_code")),
        protocol_name=to_text(headers.get("exp_script_name")),
        protocol_run_id=to_text(headers.get("protocol_run_id")),
        protocol_start_time=parse_timestamp(to_text(headers.get("protocol_start_time"), None)),
        sample_id=to_text(headers.get("sample_id")),
        sample_rate=sample_rate,
        sequencing_kit=to_text(headers.get("sequencing_kit")),
        sequencer_position=to_text(headers.get("device_id")),
        sequencer_position_type=to_text(headers.get("device_type")),
        software="pyslow5-slow5lib-to-pod5",
        system_name=to_text(headers.get("hostname")),
        system_type=to_text(headers.get("operating_system")),
        tracking_id=tracking_id,
    )


def map_end_reason(record: dict[str, object], labels: list[str]) -> pod5.EndReason:
    value = record.get("end_reason")
    if value is None:
        return pod5.EndReason.from_reason_with_default_forced(pod5.EndReasonEnum.UNKNOWN)

    if isinstance(value, str):
        label = value
    else:
        index = int(value)
        label = labels[index] if 0 <= index < len(labels) else "unknown"

    enum_value = END_REASON_MAP.get(label, pod5.EndReasonEnum.UNKNOWN)
    return pod5.EndReason.from_reason_with_default_forced(enum_value)


def convert_blow5_to_pod5(input_blow5: Path, output_pod5: Path) -> tuple[int, int]:
    reader = pyslow5.Open(str(input_blow5), "r")
    headers = reader.get_all_headers()
    end_reason_labels = reader.get_aux_enum_labels("end_reason")

    output_pod5.parent.mkdir(parents=True, exist_ok=True)

    read_count = 0
    sample_count = 0

    try:
        with pod5.Writer(output_pod5, software_name="nanopore-compression-benchmarks") as writer:
            for record in reader.seq_reads(aux="all"):
                signal = np.asarray(record["signal"], dtype=np.int16)
                sample_rate = to_int(record.get("sampling_rate"), to_int(headers.get("sample_frequency"), 4000))
                digitisation = to_float(record.get("digitisation"), 8192.0)
                read = pod5.Read(
                    read_id=to_uuid(to_text(record["read_id"])),
                    pore=pod5.Pore(
                        channel=to_int(record.get("channel_number"), 0),
                        well=max(to_int(record.get("start_mux"), 1), 1),
                        pore_type=to_text(headers.get("pore_type"), "not_set"),
                    ),
                    calibration=pod5.Calibration.from_range(
                        offset=to_float(record.get("offset"), 0.0),
                        adc_range=to_float(record.get("range"), 0.0),
                        digitisation=digitisation,
                    ),
                    read_number=to_int(record.get("read_number"), read_count),
                    start_sample=to_int(record.get("start_time"), 0),
                    median_before=to_float(record.get("median_before"), 0.0),
                    end_reason=map_end_reason(record, end_reason_labels),
                    run_info=build_run_info(headers, sample_rate, digitisation),
                    signal=signal,
                )
                writer.add_read(read)
                read_count += 1
                sample_count += int(signal.size)
    finally:
        reader.close()

    return read_count, sample_count


def main() -> int:
    args = parse_args()
    input_blow5 = Path(args.input_blow5)
    output_pod5 = Path(args.output_pod5)

    if not input_blow5.is_file():
        raise FileNotFoundError(f"Input BLOW5 file does not exist: {input_blow5}")

    read_count, sample_count = convert_blow5_to_pod5(input_blow5, output_pod5)
    print(
        f"Wrote {output_pod5} with {read_count} reads and {sample_count} total samples "
        f"from {input_blow5}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())