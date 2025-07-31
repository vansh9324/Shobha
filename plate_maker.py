"""
Pure-function plate builder for Shobha Sarees.
Called by app.py with Drive credentials already set up.
"""

from __future__ import annotations
import io, os, sys, csv, json, math, tempfile
from pathlib import Path
from typing import Tuple
from PIL import Image, ImageDraw, ImageFont
from rembg import remove as rembg_remove
from googleapiclient.discovery import Resource
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

# ── VISUAL CONSTANTS ────────────────────────────────────────────────────
FRAME_W, FRAME_H = 5000, 4000
SIDE_PAD, TOP_PAD, BOTTOM_PAD = 40, 40, 40
BANNER_PAD_Y = 60
MAX_FONT_SIZE, MIN_FONT_SIZE = 180, 40
FONT_PATH = "fonts/NotoSerifDisplay-Italic-VariableFont_wdth,wght.ttf"
TEXT_COLOR = (0, 0, 0)

# On-fabric logo overlay
LOGO_PATH = "logo/Shobha Emboss.png"   # make sure this file is in the repo
OVERLAY_RATIO = 0.20
OVERLAY_OPACITY = 0.31
OVERLAY_MARGIN = 150                   # px inside saree bounds
# ── FONT HELPERS ────────────────────────────────────────────────────────
def _load_font(pt: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(
            FONT_PATH, pt,
            layout_engine=ImageFont.LAYOUT_RAQM,
            font_variation={"wght": 700, "ital": 1}
        )
    except Exception:
        return ImageFont.load_default()

def _text_wh(txt: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int]:
    x0, y0, x1, y1 = font.getbbox(txt)
    return x1 - x0, y1 - y0

def _best_font(txt: str, max_w: int) -> ImageFont.FreeTypeFont:
    for size in range(MAX_FONT_SIZE, MIN_FONT_SIZE - 1, -2):
        f = _load_font(size)
        if _text_wh(txt, f)[0] <= max_w:
            return f
    return _load_font(MIN_FONT_SIZE)

# ── GOOGLE DRIVE HELPERS ────────────────────────────────────────────────
def _download_drive_file(service: Resource, file_id: str) -> bytes:
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return fh.read()

def _ensure_subfolder(service: Resource,
                      parent_id: str,
                      name: str) -> str:
    """Return folderId inside parent; create if missing."""
    resp = service.files().list(
        q=f"'{parent_id}' in parents and name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed = false",
        fields="files(id,name)",
        pageSize=1).execute()
    if resp["files"]:
        return resp["files"][0]["id"]
    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id]
    }
    folder = service.files().create(body=meta, fields="id").execute()
    return folder["id"]

def _upload_jpeg(service: Resource,
                 parent_id: str,
                 name: str,
                 data: bytes) -> str:
    media = MediaIoBaseUpload(io.BytesIO(data),
                              mimetype="image/jpeg",
                              resumable=False)
    meta = {"name": name, "parents": [parent_id]}
    file = service.files().create(
        body=meta,
        media_body=media,
        fields="id").execute()
    file_id = file["id"]
    return f"https://drive.google.com/uc?id={file_id}"

# ── IMAGE PIPELINE (same maths as before) ───────────────────────────────
def _place_logo_on_saree(saree: Image.Image) -> Image.Image:
    logo = Image.open(LOGO_PATH).convert("RGBA")
    target_w = int(saree.width * OVERLAY_RATIO)
    scale = target_w / logo.width
    logo = logo.resize(
        (target_w, int(logo.height * scale)),
        Image.Resampling.LANCZOS
    )
    alpha = logo.split()[3].point(lambda p: int(p * OVERLAY_OPACITY))
    logo.putalpha(alpha)
    x = saree.width  - logo.width  - OVERLAY_MARGIN
    y = saree.height - logo.height - OVERLAY_MARGIN
    saree.paste(logo, (x, y), logo)
    return saree

def _make_canvas(banner_h: int) -> Image.Image:
    w = FRAME_W + 2 * SIDE_PAD
    h = TOP_PAD + banner_h + FRAME_H + BOTTOM_PAD
    return Image.new("RGB", (w, h), "white")

def build_plate(service: Resource,
                file_id: str,
                catalog: str,
                design: str,
                out_folder_id: str) -> str:
    """
    • downloads Drive file_id
    • processes it
    • uploads JPEG into /<out_folder>/<catalog>/
    • returns public URL
    """
    # 1. pull bytes & background-remove
    raw_bytes = _download_drive_file(service, file_id)
    fg_rgba   = Image.open(io.BytesIO(rembg_remove(raw_bytes, alpha_matting=False))).convert("RGBA")

    # 2. trim and downsize
    fg_rgba = fg_rgba.crop(fg_rgba.getbbox())
    scale = min(FRAME_W / fg_rgba.width, FRAME_H / fg_rgba.height, 1.0)
    if scale < 1.0:
        fg_rgba = fg_rgba.resize(
            (int(fg_rgba.width * scale), int(fg_rgba.height * scale)),
            Image.Resampling.LANCZOS
        )

    # 3. add faint logo overlay
    fg_rgba = _place_logo_on_saree(fg_rgba)

    # 4. banner text
    banner_txt = f"{catalog}  D.No: {design}"
    font = _best_font(banner_txt, FRAME_W)
    tw, th = _text_wh(banner_txt, font)
    banner_h = th + 2 * BANNER_PAD_Y

    # 5. compose on white canvas
    cv = _make_canvas(banner_h)
    draw = ImageDraw.Draw(cv)
    draw.text(
        (SIDE_PAD + (FRAME_W - tw)//2,
         TOP_PAD   + (banner_h - th)//2),
        banner_txt, font=font, fill=TEXT_COLOR
    )
    # place saree
    sx = SIDE_PAD + (FRAME_W - fg_rgba.width)//2
    sy = TOP_PAD + banner_h + (FRAME_H - fg_rgba.height)//2
    cv.paste(fg_rgba, (sx, sy), fg_rgba)

    # 6. encode JPEG
    out = io.BytesIO()
    cv.convert("RGB").save(out, "JPEG", quality=100, subsampling=0)
    out.seek(0)
    jpeg_bytes = out.read()

    # 7. ensure catalog folder, upload
    cat_folder = _ensure_subfolder(service, out_folder_id, catalog)
    out_name   = f"{design}_{catalog}.jpg"
    return _upload_jpeg(service, cat_folder, out_name, jpeg_bytes)
