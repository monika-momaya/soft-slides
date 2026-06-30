# Conference Soft Slide Generator (v1 Prototype)

Generates ready-to-project soft slides for LED screens from:
- a designer's base template (PNG, branding pre-baked in)
- a designer's mask PNG (one reusable photo-slot shape, e.g. circle/hexagon)
- session details + speaker info/photos entered by event staff

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL Streamlit prints (usually http://localhost:8501).

## What's new in this version

- **Flexible Excel headers.** The speaker sheet no longer requires exact
  column names. Any reasonable header naming works — `Speaker Name` /
  `Full Name` / `Name`, `Title` / `Designation` / `Role`, `Company` /
  `Organisation` / `Affiliation`, and `Moderator` / `Chair` / `Role Type`
  are all recognized automatically. Only a name-like column is required;
  everything else is optional.
- **PowerPoint-equivalent font sizing.** Text sizes are specified in "pt",
  matching how these slides are normally authored in PowerPoint, and scaled
  to the actual template resolution so they look consistent regardless of
  the exported template's pixel dimensions.
  - Session name: bold, 20pt ideal, never shrinks below 16pt (wraps to a
    second line instead if it's genuinely too long).
  - Speaker name: bold, vibrant accent color, sized larger than the
    title/company line below it. Shrinks (never wraps) if a long name
    doesn't fit its slot, so it never collides with neighboring content.
  - Title + Company: regular weight, no special color, smaller than the
    speaker name.
- **Automatic theme detection.** No manual light/dark flag needed — the
  app samples the actual template's background color near the title and
  caption areas and picks readable, theme-appropriate text colors
  automatically (white/gold on dark templates, near-black/deep red on
  light templates, etc.). Since every event's template differs, this
  adapts per-upload rather than assuming one style.

## How to use

1. **Step 1 — Template & Mask** (do this once per event/theme)
   - Upload the base template PNG.
   - Upload a mask PNG: a single shape (circle, hexagon, anything) drawn in
     white/opaque on a transparent (or dark) background. This defines what
     shape every speaker photo gets cropped into. Draw only ONE shape — the
     app reuses it for every speaker slot.

2. **Step 2 — Session Details**
   - Session name, hall name, date.

3. **Step 3 — Speakers**
   - Choose **Bulk upload** (recommended for most sessions) or **Manual entry**
     (fine for 1-2 speakers).
   - **Bulk upload:**
     - Download the Excel template (or use your own sheet — headers don't
       need to match exactly, see "What's new" above), fill in speaker
       details, one row per speaker.
     - Bulk-upload all speaker photos at once. Filenames don't need to match
       exactly — `ravi_singh.jpg`, `Singh_Ravi.PNG`, `Singh, Ravi.jpg` all
       match "Ravi Singh" automatically (matching ignores order, case,
       separators, and common honorifics like Dr./Shri/IRS).
     - **Review the match table** that appears — every speaker shows its
       auto-matched photo. Low-confidence matches are flagged; use the
       dropdown to fix any wrong or missing match before continuing. This
       review step exists specifically so a bad auto-match never goes
       through silently.
   - **Manual entry:** same as before — type each speaker's details and
     upload their photo individually.

4. **Step 4 — Process & Review**
   - Click "Process Photos." The app auto-detects each face, crops to a
     head-to-collar bust shot, and lightly sharpens/enhances it.
   - **Review the thumbnails.** If a photo couldn't be auto-detected
     confidently, it's flagged with a warning — re-upload a clearer/more
     front-facing photo for that speaker and re-process if needed.

5. **Step 5 — Generate**
   - Click "Generate Slide" to composite everything onto the template.
   - Download the final PNG.

## What this version does NOT do (by design, for now)

- **No background removal** on speaker photos — backgrounds are kept as
  submitted, intentionally (per project decision — removal models are
  unreliable enough on amateur photos that the failure mode looked worse
  than the problem it solves).
- **Fixed grid layouts, not true dynamic reflow** — layouts are predefined
  per speaker count (1 through 8). This was a deliberate v1 simplification
  to get something working and visually predictable fast. Adding a new
  count = adding one entry to `core/layout_engine.py`, no other code
  changes needed. A future version can replace this with true auto-tiling
  if needed.
- **Single mask shape only** — if a mask file contains multiple disconnected
  shapes, the app uses the largest one and warns you. It does not yet
  support masks with deliberately different shapes per slot.
- **`CANVAS_TOP_RATIO` is currently a tuned constant** (in
  `core/slide_compositor.py`), calibrated against the one sample template
  provided. If a new template has a taller or shorter header band, this
  will need adjusting (or it'll need to become a per-template setting in
  the UI) — that's flagged as a near-term follow-up.

## Project structure

```
app.py                      Streamlit UI (what staff interacts with)
core/
  mask_parser.py            Extracts the slot shape from a designer mask PNG
  photo_processor.py        Face detection, bust crop, sharpen/enhance
  layout_engine.py          Predefined grid layouts by speaker count
  slide_compositor.py       Final assembly: template + slots + photos + text,
                             PPT-equivalent pt sizing, theme-aware coloring
  theme_detector.py         Samples template background to pick readable,
                             theme-appropriate text colors automatically
  speaker_sheet.py          Reads the speaker Excel sheet (flexible headers)
  name_matcher.py           Fuzzy-matches photo filenames to speaker names
assets/
  speaker_list_template.xlsx  Downloadable Excel template for bulk speaker entry
requirements.txt
```

## Known rough edges to watch for in testing

- Face detection (OpenCV Haar cascade) is reliable on clear, front-facing
  photos but can miss side profiles, sunglasses, heavy shadows, or very
  low-resolution images. This is exactly what the Step 4 review grid is
  for — it's intentionally a manual checkpoint, not a fully blind pipeline.
- **Speaker names never wrap** — by design, a very long name shrinks to
  fit its slot on one line rather than wrapping to two, since wrapping
  risked colliding with the next row in multi-row layouts. At extreme
  name lengths in narrow slots (7-8 speaker layouts), this may look
  noticeably smaller than other speakers' names in the same slide.
- **Fuzzy name matching** works well for typical cases (reordered names,
  different separators/case, common honorific suffixes like "IRS"/"Dr.")
  but isn't magic — completely generic filenames (`IMG_2024.jpg`) or two
  speakers with very similar names sharing a first or last name can produce
  an ambiguous or empty match. The Step 3 review table is the safety net:
  always glance over the assigned photo next to each name before moving on,
  since a wrong photo-to-name assignment going live on the big screen is
  the one mistake worth double-checking for.
- **Flexible Excel header matching** covers common phrasings (Name/Speaker/
  Panelist, Title/Designation/Role, Company/Organisation/Affiliation,
  Moderator/Chair/Role Type) but isn't infinitely smart — a sheet with
  genuinely unconventional headers (e.g. just "Info" or "Details") won't
  be recognized. If a column isn't detected, that field is simply left
  blank for all speakers rather than erroring out (except the name column,
  which is required).
- **Theme detection samples a fixed region** near the title/caption areas
  to decide light vs. dark. A template with a highly varied or textured
  background in that exact region (e.g. a busy photo background) could
  occasionally pick a less-than-ideal color. Worth a quick visual check
  on any new template style the first time it's used.
