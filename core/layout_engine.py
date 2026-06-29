"""
layout_engine.py

v1 approach (deliberately simple, per project decision): rather than true
dynamic reflow, we use a small set of PREDEFINED grid layouts keyed by
speaker count. Each layout defines normalized (0-1) slot positions within
the open canvas area, so it scales to any canvas size.

This covers the common cases seen across the reference samples:
- 1 moderator + N panelists (asymmetric, moderator highlighted separately)
- a clean symmetric grid of speakers only

Adding a new layout = adding one entry to LAYOUTS. No other code changes
needed elsewhere in the app.

NOTE for future upgrade path: if/when true auto-tile reflow is wanted,
this module is the ONLY place that needs to change - everything downstream
(photo processing, compositing) just consumes whatever slot list this
module returns, regardless of how it was computed.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class Slot:
    """A single photo+caption slot, in NORMALIZED coordinates (0.0-1.0)
    relative to the open canvas area (the space below the template header)."""
    x: float       # left edge
    y: float        # top edge
    w: float        # width
    h: float        # height (photo only; caption text goes below this)
    role_label: str = ""   # e.g. "MODERATOR" - shown above photo if set


# Each layout is a list of Slot objects for a specific total speaker count.
# Coordinates designed for a roughly 16:9 open canvas area.
LAYOUTS = {
    1: [
        Slot(x=0.36, y=0.10, w=0.28, h=0.55),
    ],
    2: [
        Slot(x=0.18, y=0.12, w=0.26, h=0.50),
        Slot(x=0.56, y=0.12, w=0.26, h=0.50),
    ],
    3: [
        Slot(x=0.10, y=0.12, w=0.24, h=0.48),
        Slot(x=0.38, y=0.12, w=0.24, h=0.48),
        Slot(x=0.66, y=0.12, w=0.24, h=0.48),
    ],
    4: [
        Slot(x=0.06, y=0.12, w=0.21, h=0.46),
        Slot(x=0.29, y=0.12, w=0.21, h=0.46),
        Slot(x=0.52, y=0.12, w=0.21, h=0.46),
        Slot(x=0.75, y=0.12, w=0.21, h=0.46),
    ],
    5: [
        # 1 moderator (left, slightly larger/offset) + 4 panelists, 2 rows
        Slot(x=0.03, y=0.08, w=0.18, h=0.42, role_label="MODERATOR"),
        Slot(x=0.25, y=0.03, w=0.16, h=0.36),
        Slot(x=0.44, y=0.03, w=0.16, h=0.36),
        Slot(x=0.63, y=0.03, w=0.16, h=0.36),
        Slot(x=0.25, y=0.48, w=0.16, h=0.36),
    ],
    6: [
        # 1 moderator + 5 panelists, 2 rows - mirrors Image 1 / Image 3 style
        Slot(x=0.03, y=0.22, w=0.16, h=0.36, role_label="MODERATOR"),
        Slot(x=0.23, y=0.03, w=0.14, h=0.32),
        Slot(x=0.41, y=0.03, w=0.14, h=0.32),
        Slot(x=0.59, y=0.03, w=0.14, h=0.32),
        Slot(x=0.23, y=0.48, w=0.14, h=0.32),
        Slot(x=0.41, y=0.48, w=0.14, h=0.32),
    ],
    7: [
        Slot(x=0.02, y=0.22, w=0.14, h=0.32, role_label="MODERATOR"),
        Slot(x=0.18, y=0.03, w=0.12, h=0.30),
        Slot(x=0.32, y=0.03, w=0.12, h=0.30),
        Slot(x=0.46, y=0.03, w=0.12, h=0.30),
        Slot(x=0.60, y=0.03, w=0.12, h=0.30),
        Slot(x=0.18, y=0.48, w=0.12, h=0.30),
        Slot(x=0.32, y=0.48, w=0.12, h=0.30),
    ],
    8: [
        Slot(x=0.02, y=0.22, w=0.13, h=0.32, role_label="MODERATOR"),
        Slot(x=0.17, y=0.03, w=0.11, h=0.28),
        Slot(x=0.30, y=0.03, w=0.11, h=0.28),
        Slot(x=0.43, y=0.03, w=0.11, h=0.28),
        Slot(x=0.56, y=0.03, w=0.11, h=0.28),
        Slot(x=0.17, y=0.46, w=0.11, h=0.28),
        Slot(x=0.30, y=0.46, w=0.11, h=0.28),
        Slot(x=0.43, y=0.46, w=0.11, h=0.28),
    ],
}

MAX_SUPPORTED = max(LAYOUTS.keys())


def get_layout(speaker_count: int) -> List[Slot]:
    """
    Return the slot list for the given speaker count. If the count exceeds
    what we have a hand-tuned layout for, we raise a clear error rather
    than silently producing an ugly result - the calling UI should surface
    this so staff knows to ask for a layout to be added, or split the
    panel across two slides.
    """
    if speaker_count < 1:
        raise ValueError("Need at least 1 speaker to generate a layout.")
    if speaker_count not in LAYOUTS:
        raise ValueError(
            f"No predefined layout for {speaker_count} speakers yet. "
            f"Currently supported: 1-{MAX_SUPPORTED} speakers. "
            "Consider splitting this panel across two slides, or ask "
            "to have a new layout added for this count."
        )
    return LAYOUTS[speaker_count]
