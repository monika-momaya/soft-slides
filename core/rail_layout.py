"""
rail_layout.py

Computes the TWO-ZONE layout used when a session has at least one
Moderator, Chair, Co-Moderator, or Co-Chair:

  LEFT RAIL             RIGHT ZONE
  ──────────────        ──────────────────────────────
  [MODERATOR]           SPEAKERS (or PANELISTS)
  [photo]               [photo] [photo] [photo]
  Name                  Name    Name    Name
  Title, Company        ...     ...     ...
                        [photo] [photo] [photo]
                        ...
  (up to 2 people)      (remaining speakers, 3 per row)

Layout decision rules (per project spec):
- ANY speakers in the list with role in
  {"moderator", "co-moderator", "chair", "co-chair"} →
  use this two-zone layout (rail + right grid).
- All other speakers (non-priority roles) go into the right grid.
- RIGHT ZONE HEADING:
    - Any Moderator/Co-Moderator present → heading = "SPEAKERS"
    - Only Chair/Co-Chair (no Moderator) → heading = "PANELISTS"
- If there are no non-priority speakers (everyone is a Moderator/Chair),
  fall back to the full-width grid - unusual edge case, but handled.

Returns normalized (0.0-1.0) coordinates relative to the FULL slide
(not the canvas below the header) for the PPTX compositor, since the
PPTX compositor works in absolute inches from the slide origin and
needs to account for the canvas_top_in offset itself.

Coordinates are expressed as fractions of the slide's CONTENT AREA
(the open canvas below the branding header), consistent with how
the existing layout_engine.Slot objects work - callers multiply by
the actual canvas dimensions to get absolute positions.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict
import math

# Rail / panelist zone proportions (as fractions of slide width)
RAIL_W_RATIO = 0.24          # width of the left rail (moderator zone)
RAIL_GAP_RATIO = 0.025       # horizontal gap between rail and panelist zone
PANELIST_ZONE_X = RAIL_W_RATIO + RAIL_GAP_RATIO   # x start of right zone
PANELIST_ZONE_W = 1.0 - PANELIST_ZONE_X - 0.01    # width of right zone

PANELISTS_PER_ROW = 3        # number of panelists per row in the right zone
RAIL_PHOTO_H_RATIO = 0.42    # photo height as fraction of canvas height (rail)
PANEL_PHOTO_H_RATIO = 0.34   # photo height for panelists (smaller than rail)
PHOTO_V_PADDING = 0.04       # vertical padding between rows

# Role sets for the heading decision rule
MODERATOR_ROLES = {"moderator", "co-moderator"}
CHAIR_ROLES = {"chair", "co-chair"}
ALL_PRIORITY_ROLES = MODERATOR_ROLES | CHAIR_ROLES


@dataclass
class RailSlot:
    """A slot in either the left rail or right panelist zone."""
    x: float           # left edge (fraction of canvas width)
    y: float           # top edge (fraction of canvas height)
    w: float           # width (fraction of canvas width)
    h: float           # height of the photo box (fraction of canvas height)
    zone: str = "panel"   # "rail" or "panel"


@dataclass
class RailLayout:
    """
    Complete two-zone layout for one session.
    `rail_slots` and `panel_slots` are parallel to the speaker lists
    passed into compose functions - callers split speakers by role first,
    then zip with these slots.
    """
    rail_slots: List[RailSlot]
    panel_slots: List[RailSlot]
    panel_heading: str     # "SPEAKERS" or "PANELISTS"
    heading_y: float       # y position for the panel heading label (canvas fraction)


def get_panel_heading(rail_speakers: List[Dict]) -> str:
    """
    Derives the right-zone heading from the actual roles present in the
    left rail:
    - Any Moderator/Co-Moderator → "SPEAKERS"
    - Only Chair/Co-Chair (no Moderator at all) → "PANELISTS"
    """
    roles = {sp.get("role", "").strip().lower() for sp in rail_speakers}
    if roles & MODERATOR_ROLES:
        return "SPEAKERS"
    return "PANELISTS"


def should_use_rail_layout(speakers: List[Dict]) -> bool:
    """
    Returns True if ANY speaker has a priority role (Moderator/Chair/
    Co-Moderator/Co-Chair), AND there is at least one non-priority
    speaker to put in the right zone. If everyone is a Moderator/Chair
    (unusual), falls back to the standard full-width grid.
    """
    has_priority = any(
        sp.get("role", "").strip().lower() in ALL_PRIORITY_ROLES
        for sp in speakers
    )
    has_non_priority = any(
        sp.get("role", "").strip().lower() not in ALL_PRIORITY_ROLES
        for sp in speakers
    )
    return has_priority and has_non_priority


def split_speakers(speakers: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Splits the speaker list into (rail_speakers, panel_speakers).
    Rail: Moderator/Chair/Co-Moderator/Co-Chair roles (up to 2 shown in rail).
    Panel: everyone else.
    If more than 2 priority speakers exist, the extras spill into the panel
    zone as regular panelists (rare, but handles it gracefully).
    """
    priority = [sp for sp in speakers if sp.get("role", "").strip().lower() in ALL_PRIORITY_ROLES]
    panel = [sp for sp in speakers if sp.get("role", "").strip().lower() not in ALL_PRIORITY_ROLES]

    if len(priority) > 2:
        # Spill excess priority speakers into panel zone
        panel = priority[2:] + panel
        priority = priority[:2]

    return priority, panel


def compute_rail_layout(rail_speakers: List[Dict], panel_speakers: List[Dict]) -> RailLayout:
    """
    Computes normalized slot positions for the two-zone layout.
    All coordinates are fractions of the open canvas area (0.0-1.0).
    """
    n_rail = len(rail_speakers)
    n_panel = len(panel_speakers)

    # --- LEFT RAIL slots ---
    rail_slots = []
    rail_photo_h = RAIL_PHOTO_H_RATIO
    rail_photo_w = RAIL_W_RATIO

    if n_rail == 1:
        # Single moderator/chair: center vertically in the rail
        y_center = 0.05
        rail_slots.append(RailSlot(
            x=0.01, y=y_center, w=rail_photo_w * 0.92, h=rail_photo_h, zone="rail"
        ))
    else:
        # Two moderators/chairs: stack them vertically in the rail
        slot_h = min(RAIL_PHOTO_H_RATIO * 0.75, 0.30)
        gap = 0.04
        total = slot_h * n_rail + gap * (n_rail - 1)
        y_start = max(0.02, (1.0 - total) / 2)
        for i in range(n_rail):
            rail_slots.append(RailSlot(
                x=0.01,
                y=y_start + i * (slot_h + gap),
                w=rail_photo_w * 0.92,
                h=slot_h,
                zone="rail",
            ))

    # --- RIGHT ZONE (panelist grid) slots ---
    panel_slots = []
    if n_panel > 0:
        per_row = PANELISTS_PER_ROW
        n_rows = math.ceil(n_panel / per_row)
        slot_w = PANELIST_ZONE_W / per_row
        photo_h = PANEL_PHOTO_H_RATIO

        # heading takes up space at the top of the right zone
        heading_y = 0.02
        grid_y_start = 0.12   # below the heading label

        # Distribute rows evenly in the available vertical space
        total_content_h = 1.0 - grid_y_start - 0.05
        row_h = min(photo_h, total_content_h / n_rows)

        for idx in range(n_panel):
            row = idx // per_row
            col = idx % per_row

            # Centre the last row if it's not full
            items_in_this_row = min(per_row, n_panel - row * per_row)
            row_offset = (per_row - items_in_this_row) * slot_w / 2

            panel_slots.append(RailSlot(
                x=PANELIST_ZONE_X + col * slot_w + row_offset,
                y=grid_y_start + row * (row_h + PHOTO_V_PADDING),
                w=slot_w * 0.92,
                h=row_h,
                zone="panel",
            ))
    else:
        heading_y = 0.02

    heading_y = 0.02
    panel_heading = get_panel_heading(rail_speakers)

    return RailLayout(
        rail_slots=rail_slots,
        panel_slots=panel_slots,
        panel_heading=panel_heading,
        heading_y=heading_y,
    )
