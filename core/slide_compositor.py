"""
slide_compositor.py

Final assembly step: takes the base template, the extracted slot shape,
the layout (slot positions), processed speaker photos, and text fields
(session name, hall, date, speaker name/title/company) and renders the
finished, ready-to-project slide.

Design choices baked in here:
- Text is auto-sized to fit within its allotted width (so long names/titles
  don't overflow), shrinking font size as needed rather than truncating.
- The "open canvas area" (where speakers go) is assumed to start below the
  branded header band. This boundary is currently a configurable constant
  (CANVAS_TOP_RATIO) - in production this should be confirmed against the
  real template or made designer-configurable per template.
"""

from dataclasses import dataclass
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFont

from core.layout_engine import Slot
from core.mask_parser import SlotShape

# Fraction of the template's height taken up by the fixed branded header
# (logo/date/banner band). Below this is the open canvas for speakers.
# Measured against the actual sample template (header band ends ~273px
# of 910px total height = 0.30); small extra margin added below it.
# NOTE: this should be made configurable per template in the UI, since
# different designer templates will have different header heights.
CANVAS_TOP_RATIO = 0.32

CAPTION_GAP_PX = 10          # gap between photo bottom and name text
NAME_TO_TITLE_GAP_PX = 2
TITLE_TO_COMPANY_GAP_PX = 0

TEXT_COLOR = (255, 255, 255, 255)
ROLE_LABEL_COLOR = (255, 210, 60, 255)   # amber, matches "MODERATOR"/"PANELISTS" style seen in samples


@dataclass
class SpeakerInfo:
    name: str
    title: str = ""
    company: str = ""
    photo: Optional[Image.Image] = None   # already-processed bust crop (RGB)
    role_label: str = ""                  # overrides slot's default role_label if set


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """
    Load a font at the given size. Falls back through a few common paths
    so this works across different environments without bundling font files.
    Production deployments should bundle a specific brand-approved font.
    """
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _fit_text_font(draw: ImageDraw.ImageDraw, text: str, max_width: int,
                    start_size: int, min_size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Shrink font size until `text` fits within `max_width` pixels, or hit min_size."""
    size = start_size
    while size > min_size:
        font = _font(size, bold=bold)
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            return font
        size -= 1
    return _font(min_size, bold=bold)


def _draw_centered_text(draw, text, center_x, top_y, max_width, start_size, min_size, color, bold=False):
    """Draw text horizontally centered at center_x, returns the height used."""
    if not text:
        return 0
    font = _fit_text_font(draw, text, max_width, start_size, min_size, bold=bold)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    draw.text((center_x - text_w / 2, top_y), text, font=font, fill=color)
    return text_h


def _apply_mask_shape(photo: Image.Image, slot_shape: SlotShape, target_w: int, target_h: int) -> Image.Image:
    """
    Resize the photo to cover the target box (cropping to fill, like
    CSS object-fit: cover) and apply the slot's alpha mask shape so it's
    cut to circle/hexagon/whatever the designer drew.
    """
    photo_ratio = photo.width / photo.height
    target_ratio = target_w / target_h

    if photo_ratio > target_ratio:
        # photo is wider than target -> match height, crop width
        new_h = target_h
        new_w = int(new_h * photo_ratio)
    else:
        new_w = target_w
        new_h = int(new_w / photo_ratio)

    resized = photo.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    cropped = resized.crop((left, top, left + target_w, top + target_h))

    mask_resized = slot_shape.resized(target_w, target_h)

    result = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    result.paste(cropped.convert("RGBA"), (0, 0))
    result.putalpha(mask_resized)
    return result


def compose_slide(
    template: Image.Image,
    slot_shape: SlotShape,
    slots: List[Slot],
    speakers: List[SpeakerInfo],
    session_name: str = "",
    hall_name: str = "",
    date_str: str = "",
) -> Image.Image:
    """
    Render the final slide. `slots` and `speakers` must be the same length
    (caller's responsibility - typically slots come from layout_engine.get_layout(len(speakers))).
    """
    if len(slots) != len(speakers):
        raise ValueError(
            f"Slot count ({len(slots)}) does not match speaker count ({len(speakers)})."
        )

    canvas = template.convert("RGBA").copy()
    W, H = canvas.size
    draw = ImageDraw.Draw(canvas)

    canvas_top = int(H * CANVAS_TOP_RATIO)
    title_reserved_height = 70 if (session_name or hall_name or date_str) else 0
    speaker_area_top = canvas_top + title_reserved_height
    canvas_height = H - speaker_area_top

    # --- Session title block (top-left of open canvas) ---
    if session_name:
        title_font = _fit_text_font(draw, session_name, int(W * 0.94), 32, 18, bold=True)
        draw.text((int(W * 0.03), canvas_top + 4), session_name, font=title_font, fill=TEXT_COLOR)

    meta_parts = [p for p in [hall_name, date_str] if p]
    if meta_parts:
        meta_text = "   |   ".join(meta_parts)
        meta_font = _font(16)
        draw.text((int(W * 0.03), canvas_top + 38), meta_text, font=meta_font, fill=(220, 220, 230, 255))

    # --- Speaker slots ---
    for slot, speaker in zip(slots, speakers):
        slot_x = int(slot.x * W)
        slot_y = speaker_area_top + int(slot.y * canvas_height)
        slot_w = int(slot.w * W)
        slot_h = int(slot.h * canvas_height)

        role_text = speaker.role_label or slot.role_label
        photo_top = slot_y
        if role_text:
            role_font = _font(18, bold=True)
            bbox = draw.textbbox((0, 0), role_text, font=role_font)
            draw.text(
                (slot_x + slot_w / 2 - (bbox[2] - bbox[0]) / 2, slot_y),
                role_text, font=role_font, fill=ROLE_LABEL_COLOR,
            )
            photo_top = slot_y + (bbox[3] - bbox[1]) + 10

        photo_h = slot_h - (photo_top - slot_y)

        if speaker.photo is not None:
            masked = _apply_mask_shape(speaker.photo, slot_shape, slot_w, int(photo_h))
            canvas.paste(masked, (slot_x, int(photo_top)), masked)

        caption_y = photo_top + photo_h + CAPTION_GAP_PX
        center_x = slot_x + slot_w / 2

        used_h = _draw_centered_text(
            draw, speaker.name, center_x, caption_y, slot_w, 22, 14, TEXT_COLOR, bold=True
        )
        caption_y += used_h + NAME_TO_TITLE_GAP_PX

        used_h = _draw_centered_text(
            draw, speaker.title, center_x, caption_y, slot_w, 16, 11, (210, 210, 220, 255)
        )
        caption_y += used_h + TITLE_TO_COMPANY_GAP_PX

        _draw_centered_text(
            draw, speaker.company, center_x, caption_y, slot_w, 16, 11, (210, 210, 220, 255)
        )

    return canvas
