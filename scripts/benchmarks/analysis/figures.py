"""Figure styling and export helpers for analysis notebooks."""

from __future__ import annotations

import matplotlib.pyplot as plt

from .shared import display_algorithm_name


DEFAULT_ALGORITHM_COLORS = {
    "VBZ": "#DC6E62",
    "PDZ": "#5CB9E4",
    "EX-ZD-ZSTD": "#E8A425",
    "PDZSerial": "#7BC67B",
    "EX-ZD": "#3F6BAA",
    "EX-ZD-ZLIB": "#4B9E7A",
    "CA": "#8E44AD",
}
DEFAULT_LIGHT_ALGORITHM_COLORS = {
    "VBZ": "#EB9E8D",
    "PDZ": "#96DCF1",
    "EX-ZD-ZSTD": "#E8BF81",
    "PDZSerial": "#B6E2B0",
    "EX-ZD": "#A8BEE6",
    "EX-ZD-ZLIB": "#A4D5C7",
    "CA": "#D2B4DE",
}
DEFAULT_ALGORITHM_MARKERS = {
    "VBZ": "s",
    "PDZ": "o",
    "EX-ZD-ZSTD": "^",
    "PDZSerial": "D",
    "EX-ZD": "P",
    "EX-ZD-ZLIB": "X",
    "CA": "v",
}


def color_for_algorithm(algorithm: str) -> str:
    display_name = display_algorithm_name(algorithm)
    return DEFAULT_ALGORITHM_COLORS.get(display_name, "#4C72B0")


def light_color_for_algorithm(algorithm: str) -> str:
    display_name = display_algorithm_name(algorithm)
    return DEFAULT_LIGHT_ALGORITHM_COLORS.get(display_name, "#D9D9D9")


def marker_for_algorithm(algorithm: str) -> str:
    display_name = display_algorithm_name(algorithm)
    return DEFAULT_ALGORITHM_MARKERS.get(display_name, "o")


def _figure_title_artists(fig: plt.Figure) -> list[tuple[object, str]]:
    title_artists: list[tuple[object, str]] = []
    if getattr(fig, "_suptitle", None) is not None:
        title_artists.append((fig._suptitle, fig._suptitle.get_text()))
    for ax in fig.axes:
        for title_artist in (ax.title, ax._left_title, ax._right_title):
            title_artists.append((title_artist, title_artist.get_text()))
    return title_artists


def maybe_export_figure(
    fig: plt.Figure,
    section: str,
    stem: str,
    *,
    export_enabled: bool,
    output_dir,
    export_format: str = "png",
    include_titles: bool = True,
) -> None:
    if not export_enabled:
        return

    target_dir = output_dir / section
    target_dir.mkdir(parents=True, exist_ok=True)
    export_path = target_dir / f"{stem}.{export_format}"

    title_artists = _figure_title_artists(fig)
    if not include_titles:
        for title_artist, _ in title_artists:
            title_artist.set_text("")

    try:
        fig.savefig(export_path, bbox_inches="tight", format=export_format)
    finally:
        if not include_titles:
            for title_artist, original_text in title_artists:
                title_artist.set_text(original_text)