"""
speaker_sheet.py

Reads the speaker list Excel file into a plain list of dicts the rest of
the app can use.

Per project decision: column headers are NOT enforced to be exact matches
("Name", "Title", "Company", "Moderator (Y/N)"). Staff may upload sheets
with differently worded headers - this module auto-detects which column
means what by matching against known synonyms, so the same flexible
approach used for photo-filename matching applies here too: automate the
matching, don't make staff conform to a rigid format.

Recognized column meanings:
- name        (required)       - synonyms: name, speaker, speaker name, full name, panelist
- title       (optional)       - synonyms: title, designation, role, position
- company     (optional)       - synonyms: company, organisation, organization, affiliation, firm
- moderator   (optional)       - synonyms: moderator, chair, moderator/chair, is moderator, role type
                                  (value is treated as a flag, not free text - see _looks_like_moderator)

If a column's meaning can't be confidently determined, it's ignored
(not treated as an error) - only a missing NAME column is fatal, since
every other field is optional.
"""

import re
from typing import List, Dict, Optional
import pandas as pd

# Each column "meaning" maps to a list of normalized keyword patterns we'll
# look for in the actual header text. Order matters slightly: more specific
# synonyms first, since we match by "any keyword appears in the header".
COLUMN_SYNONYMS = {
    "name": ["speaker name", "full name", "panelist name", "name", "speaker", "panelist"],
    "title": ["designation", "job title", "title", "role", "position"],
    "company": ["organisation", "organization", "affiliation", "company", "firm", "employer"],
    "moderator": ["moderator/chair", "moderator", "chair", "is moderator", "role type"],
}

MODERATOR_TRUE_VALUES = {"y", "yes", "moderator", "chair", "true", "1"}


def _normalize_header(header: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", str(header).strip().lower()).strip()


def _detect_column_mapping(columns: List[str]) -> Dict[str, Optional[str]]:
    """
    Returns a dict like {"name": "Speaker Name", "title": "Designation", ...}
    mapping each recognized meaning to the actual column name found in the
    sheet (or None if no matching column was found for that meaning).

    A column can only be claimed by ONE meaning. To avoid a generic synonym
    (like "title"'s "role") incorrectly grabbing a column meant for a more
    specific synonym (like "moderator"'s "role type"), matching happens in
    two passes:
      1. Multi-word / more specific synonyms across ALL meanings first
         (e.g. "role type", "speaker name", "job title").
      2. Single, more generic synonyms next (e.g. "role", "name", "title").
    Within each pass, COLUMN_SYNONYMS dict order decides priority on ties.
    """
    normalized_to_original = {_normalize_header(c): c for c in columns}
    available = dict(normalized_to_original)  # mutable copy we pop from

    mapping = {meaning: None for meaning in COLUMN_SYNONYMS}

    def _try_match(synonym_filter):
        for meaning, synonyms in COLUMN_SYNONYMS.items():
            if mapping[meaning] is not None:
                continue
            for norm_header, original in list(available.items()):
                matching_syns = [s for s in synonyms if s in norm_header and synonym_filter(s)]
                if matching_syns:
                    mapping[meaning] = original
                    del available[norm_header]
                    break

    # Pass 1: multi-word (more specific) synonyms claim columns first
    _try_match(lambda s: " " in s or "/" in s)
    # Pass 2: remaining single-word (more generic) synonyms
    _try_match(lambda s: True)

    return mapping


def _looks_like_moderator(value: str) -> bool:
    return value.strip().lower() in MODERATOR_TRUE_VALUES


def _safe_str(value) -> str:
    """Safely convert a pandas cell value to a stripped string, handling
    NaN (pandas' representation of blank cells, which is a float, not a
    string - so .strip() on it would crash otherwise)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def read_speaker_sheet(file_path_or_buffer) -> List[Dict]:
    """
    Reads the uploaded Excel file and returns a list of speaker dicts:
    [{"name": ..., "title": ..., "company": ..., "is_moderator": bool}, ...]

    Column headers are matched by MEANING, not exact text - see module
    docstring. Rows with a blank name are skipped (treated as empty
    trailing rows). Raises ValueError only if no name-like column can be
    found at all, since every other field is optional.
    """
    df = pd.read_excel(file_path_or_buffer, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    mapping = _detect_column_mapping(list(df.columns))

    if mapping["name"] is None:
        raise ValueError(
            "Could not find a column for speaker names. Please make sure "
            "one column header includes something like 'Name', 'Speaker', "
            "or 'Panelist'."
        )

    speakers = []
    for _, row in df.iterrows():
        name = _safe_str(row.get(mapping["name"]))
        if not name:
            continue

        title = _safe_str(row.get(mapping["title"])) if mapping["title"] else ""
        company = _safe_str(row.get(mapping["company"])) if mapping["company"] else ""
        mod_raw = _safe_str(row.get(mapping["moderator"])) if mapping["moderator"] else ""

        speakers.append({
            "name": name,
            "title": title,
            "company": company,
            "is_moderator": _looks_like_moderator(mod_raw),
        })

    if not speakers:
        raise ValueError("No speaker rows found in the sheet. Please add at least one speaker.")

    return speakers
