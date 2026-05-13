import argparse
import pod5
import numpy as np
import sys


BYTES_PER_MB = 1_000_000


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description="Convert one POD5 file into the benchmark .bin format."
    )
    parser.add_argument("pod5_file_path", help="Path to the source POD5 file")
    parser.add_argument("output_file", help="Path to the generated .bin file")
    parser.add_argument(
        "legacy_action",
        nargs="?",
        choices=["print_first_number"],
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--cutoff-mb",
        type=int,
        default=None,
        help=(
            "Optional per-file output cutoff in MB. "
            "When omitted, the full signal is written."
        ),
    )
    return parser


def resolve_cutoff_bytes(cutoff_mb):
    if cutoff_mb is None:
        return None
    if cutoff_mb < 1:
        raise ValueError("Cutoff must be at least 1 MB when provided")
    return cutoff_mb * BYTES_PER_MB


def maybe_print_first_chunk(pod5_file_path):
    with pod5.Reader(pod5_file_path) as reader:
        read = next(reader.reads())
        print(len(read.signal_for_chunk(0)))
        print(read.signal_for_chunk(0))



if __name__ == "__main__":
    args = build_argument_parser().parse_args()

    try:
        cutoff_bytes = resolve_cutoff_bytes(args.cutoff_mb)
    except ValueError as error:
        raise SystemExit(str(error))

    if args.legacy_action == "print_first_number":
        maybe_print_first_chunk(args.pod5_file_path)

    # -------------- Variable declaration ------------ #
    num_bytes = 0

    with open(args.output_file, "wb") as destination:
        with pod5.Reader(args.pod5_file_path) as r:
            remaining_reads = r.num_reads
            reads = r.reads()
            while remaining_reads > 0:
                if cutoff_bytes is not None and num_bytes > cutoff_bytes:
                    break
                read = next(reads)
                number_of_chunks = len(read.signal_rows)
                for i in range(number_of_chunks):
                    chunk = read.signal_for_chunk(i)
                    chunk_length = len(chunk)
                    written_bytes = destination.write(np.uint32(chunk_length))
                    assert(written_bytes == 4)
                    written_bytes = destination.write(chunk)
                    assert(written_bytes == chunk_length * 2)

                    num_bytes += 4 + chunk_length * 2

                remaining_reads -= 1