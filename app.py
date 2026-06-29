"""
Conference Soft Slide Generator
Streamlit app for generating event soft slides from a designer template +
mask, session details, and speaker info/photos.

Run with: streamlit run app.py
"""

import io
import streamlit as st
from PIL import Image

from core.mask_parser import load_slot_shape
from core.layout_engine import get_layout, MAX_SUPPORTED
from core.photo_processor import process_photo
from core.slide_compositor import compose_slide, SpeakerInfo

st.set_page_config(page_title="Soft Slide Generator", layout="wide")

# ---------------------------------------------------------------------------
# Session state setup
# ---------------------------------------------------------------------------
if "processed_speakers" not in st.session_state:
    st.session_state.processed_speakers = None   # list of dicts after "Process Photos"
if "final_slide" not in st.session_state:
    st.session_state.final_slide = None

st.title("🖥️ Conference Soft Slide Generator")
st.caption("Upload a template + mask once per event. Generate as many session slides as you need.")

# ---------------------------------------------------------------------------
# STEP 1: Template + Mask (event-level, done once per event/theme)
# ---------------------------------------------------------------------------
st.header("1. Event Template & Photo Shape")

col1, col2 = st.columns(2)
with col1:
    template_file = st.file_uploader(
        "Base template (PNG) — includes logo/branding, empty canvas below",
        type=["png"],
    )
with col2:
    mask_file = st.file_uploader(
        "Photo placeholder mask (PNG) — the shape designers want photos cropped to "
        "(e.g. circle, hexagon). Draw ONE shape in white/opaque on a transparent "
        "or dark background.",
        type=["png"],
    )

template_img, slot_shape = None, None
if template_file:
    template_img = Image.open(template_file)
    st.image(template_img, caption=f"Template preview ({template_img.width}x{template_img.height}px)", width=500)

if mask_file:
    # load_slot_shape expects a file path, so write the upload to a temp file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(mask_file.getvalue())
        tmp_path = tmp.name
    try:
        slot_shape = load_slot_shape(tmp_path)
        if slot_shape.warning:
            st.warning(slot_shape.warning)
        st.success(f"Photo shape detected: {slot_shape.width}x{slot_shape.height}px, "
                    f"aspect ratio {slot_shape.aspect_ratio:.2f}")
        st.image(slot_shape.alpha_mask, caption="Extracted slot shape", width=150)
    except Exception as e:
        st.error(f"Could not read mask file: {e}")
        slot_shape = None

st.divider()

# ---------------------------------------------------------------------------
# STEP 2: Session details
# ---------------------------------------------------------------------------
st.header("2. Session Details")

c1, c2, c3 = st.columns(3)
with c1:
    session_name = st.text_input("Session name", placeholder="e.g. AI for India 2030 - Star Panel")
with c2:
    hall_name = st.text_input("Hall name", placeholder="e.g. Hall 1 / Bangalore Palace")
with c3:
    date_str = st.text_input("Date", placeholder="e.g. 19th November, 2026")

st.divider()

# ---------------------------------------------------------------------------
# STEP 3: Speakers (bulk entry)
# ---------------------------------------------------------------------------
st.header("3. Speakers")

if "num_speakers" not in st.session_state:
    st.session_state.num_speakers = 3

num_speakers = st.number_input(
    f"Number of speakers (moderator + panelists combined, max {MAX_SUPPORTED} supported)",
    min_value=1, max_value=MAX_SUPPORTED, value=st.session_state.num_speakers, step=1,
)
st.session_state.num_speakers = num_speakers

speaker_inputs = []
for i in range(num_speakers):
    with st.expander(f"Speaker {i+1}", expanded=(i < 3)):
        cols = st.columns([2, 2, 2, 1, 1])
        name = cols[0].text_input("Name", key=f"name_{i}")
        title = cols[1].text_input("Title", key=f"title_{i}")
        company = cols[2].text_input("Company", key=f"company_{i}")
        is_moderator = cols[3].checkbox("Moderator?", key=f"mod_{i}")
        photo = cols[4].file_uploader("Photo", type=["jpg", "jpeg", "png"], key=f"photo_{i}")
        speaker_inputs.append({
            "name": name, "title": title, "company": company,
            "is_moderator": is_moderator, "photo_file": photo,
        })

st.divider()

# ---------------------------------------------------------------------------
# STEP 4: Process photos -> review grid
# ---------------------------------------------------------------------------
st.header("4. Process & Review Photos")

if st.button("🔄 Process Photos", type="primary"):
    missing_photos = [s for s in speaker_inputs if s["photo_file"] is None]
    if missing_photos:
        st.error(f"{len(missing_photos)} speaker(s) are missing a photo upload. Please add all photos first.")
    else:
        processed = []
        for s in speaker_inputs:
            raw_img = Image.open(s["photo_file"])
            result = process_photo(raw_img)
            processed.append({**s, "processed_image": result.image,
                               "face_detected": result.face_detected, "note": result.note})
        st.session_state.processed_speakers = processed
        st.session_state.final_slide = None  # reset downstream state

if st.session_state.processed_speakers:
    st.subheader("Review processed photos before generating the final slide")
    review_cols = st.columns(min(len(st.session_state.processed_speakers), 5))
    needs_attention = False
    for i, sp in enumerate(st.session_state.processed_speakers):
        col = review_cols[i % len(review_cols)]
        with col:
            st.image(sp["processed_image"], caption=sp["name"] or f"Speaker {i+1}", width=150)
            if not sp["face_detected"]:
                st.warning("⚠️ " + sp["note"])
                needs_attention = True
    if needs_attention:
        st.info(
            "Some photos couldn't be auto-cropped confidently. You can still proceed, "
            "but consider re-uploading a clearer photo for flagged speakers above "
            "(crop the photo close to the face yourself before uploading) and re-process."
        )

st.divider()

# ---------------------------------------------------------------------------
# STEP 5: Generate final slide
# ---------------------------------------------------------------------------
st.header("5. Generate Final Slide")

ready = template_img is not None and slot_shape is not None and st.session_state.processed_speakers is not None

if not ready:
    st.info("Complete steps 1-4 above (template, mask, session details, and processed photos) to generate the slide.")

if st.button("✨ Generate Slide", disabled=not ready, type="primary"):
    try:
        layout_slots = get_layout(len(st.session_state.processed_speakers))
        speaker_infos = []
        for sp in st.session_state.processed_speakers:
            role = "MODERATOR" if sp["is_moderator"] else ""
            speaker_infos.append(SpeakerInfo(
                name=sp["name"], title=sp["title"], company=sp["company"],
                photo=sp["processed_image"], role_label=role,
            ))
        final = compose_slide(
            template=template_img, slot_shape=slot_shape, slots=layout_slots,
            speakers=speaker_infos, session_name=session_name,
            hall_name=hall_name, date_str=date_str,
        )
        st.session_state.final_slide = final
    except ValueError as e:
        st.error(str(e))

if st.session_state.final_slide is not None:
    st.subheader("Final Slide")
    st.image(st.session_state.final_slide, use_container_width=True)

    buf = io.BytesIO()
    st.session_state.final_slide.convert("RGB").save(buf, format="PNG")
    st.download_button(
        "⬇️ Download Slide (PNG)", data=buf.getvalue(),
        file_name=f"{(session_name or 'soft_slide').replace(' ', '_')}.png",
        mime="image/png",
    )
