"""
speaker_sheet.py

Reads the speaker list Excel file (Name, Title, Company, Moderator (Y/N))
into a plain list of dicts the rest of the app can use.
"""

from typing import List, Dict
import pandas as pd

REQUIRED_COLUMNS = ["Name", "Title", "Company", "Moderator (Y/N)"]


def read_speaker_sheet(file_path_or_buffer) -> List[Dict]:
    """
    Reads the uploaded Excel file and returns a list of speaker dicts:
    [{"name": ..., "title": ..., "company": ..., "is_moderator": bool}, ...]

    Rows with a blank Name are skipped (treated as empty trailing rows).
    Raises ValueError with a clear message if required columns are missing.
    """
    df = pd.read_excel(file_path_or_buffer, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Expected columns: {', '.join(REQUIRED_COLUMNS)}. "
            "Please use the provided template."
        )

    speakers = []
    for _, row in df.iterrows():
        name = (row.get("Name") or "").strip()
        if not name:
            continue
        mod_flag = (row.get("Moderator (Y/N)") or "").strip().upper()
        speakers.append({
            "name": name,
            "title": (row.get("Title") or "").strip(),
            "company": (row.get("Company") or "").strip(),
            "is_moderator": mod_flag == "Y",
        })

    if not speakers:
        raise ValueError("No speaker rows found in the sheet. Please add at least one speaker.")

    return speakers
