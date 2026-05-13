from .runs import DEFAULT_RESULTS_ROOT


def add_results_root_argument(parser, default=str(DEFAULT_RESULTS_ROOT)):
    parser.add_argument(
        "--results-root",
        default=default,
        help=(
            "Area root where benchmark-type run folders will be created "
            f"(default: {DEFAULT_RESULTS_ROOT})"
        ),
    )


def add_executable_argument(
    parser,
    flag_name="--executable",
    help_text="Override the benchmark executable path",
):
    parser.add_argument(
        flag_name,
        default=None,
        help=help_text,
    )
