"""
Pure local file → plate generator.
No Google code here; Drive is handled in runner.py.
"""

from __future__ import annotations
import io, math
from pathlib import Path
from typing import Tuple
from PIL import Image, ImageDraw, ImageFont
from rembg import new_session, remove

# ─ Visual constants ───────────────────────────────────────────────────────
FRAME_W, FRAME_H = 5000, 4000
SIDE_PAD = TOP_PAD = BOTTOM_PAD = 40
BANNER_PAD_Y = 60
MAX_FONT_SIZE, MIN_FONT_SIZE = 180, 40

FONT_PATH = "fonts/NotoSerifDisplay-Italic-VariableFont_wdth,wght.ttf"
TEXT_COLOR = (0, 0, 0)

LOGO_PATH = "logo/Shobha Emboss.png"
OVERLAY_RATIO = 0.10   # 10 % of saree width
OVERLAY_OPACITY = 0.11 # 11 % opacity
OVERLAY_MARGIN = 20

# ─ rembg session (tiny model → low RAM, no Numba) ─────────────────────────
SESSION = new_session("u2netp")

# ─ Helpers ────────────────────────────────────────────────────────────────
def _text_wh(txt: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int]:
    x0, y0, x1, y1 = font.getbbox(txt)
    return x1 - x0, y1 - y0

def _best_font(txt: str, max_w: int) -> ImageFont.FreeTypeFont:
    for size in range(MAX_FONT_SIZE, MIN_FONT_SIZE - 1, -2):
        try:
            f = ImageFont.truetype(
                FONT_PATH, size,
                layout_engine=ImageFont.LAYOUT_RAQM,
                font_variation={"wght":700, "ital":1}
            )
        except Exception:
            f = ImageFont.load_default()
        if _text_wh(txt, f)[0] <= max_w:
            return f
    return ImageFont.load_default()

def _place_logo(saree: Image.Image) -> Image.Image:
    logo = Image.open(LOGO_PATH).convert("RGBA")
    target_w = int(saree.width * OVERLAY_RATIO)
    scale = target_w / logo.width
    logo = logo.resize((target_w, int(logo.height * scale)),
                       Image.Resampling.LANCZOS)
    alpha = logo.split()[3].point(lambda p: int(p * OVERLAY_OPACITY))
    logo.putalpha(alpha)
    x = saree.width  - logo.width  - OVERLAY_MARGIN
    y = saree.height - logo.height - OVERLAY_MARGIN
    saree.paste(logo, (x, y), logo)
    return saree

# ─ Public function the runner calls ───────────────────────────────────────
def build_plate(src_path: Path,
                dst_path: Path,
                catalog: str,
                design: str) -> None:
    """Read src image → write plate to dst_path (JPEG)."""

    # 1 remove background
    with open(src_path, "rb") as f:
        fg_bytes = remove(f.read(), session=SESSION, alpha_matting=False)
    fg = Image.open(io.BytesIO(fg_bytes)).convert("RGBA").crop(
            Image.open(io.BytesIO(fg_bytes)).getbbox())

    # 2 downsize to 5 000×4 000 window
    scale = min(FRAME_W / fg.width, FRAME_H / fg.height, 1.0)
    if scale < 1.0:
        fg = fg.resize((int(fg.width*scale), int(fg.height*scale)),
                       Image.Resampling.LANCZOS)

    # 3 overlay logo
    fg = _place_logo(fg)

    # 4 banner
    banner_txt = f"{catalog}  D.No: {design}"
    font = _best_font(banner_txt, FRAME_W)
    tw, th = _text_wh(banner_txt, font)
    banner_h = th + 2*BANNER_PAD_Y

    # 5 compose
    canvas_w = FRAME_W + 2*SIDE_PAD
    canvas_h = TOP_PAD + banner_h + FRAME_H + BOTTOM_PAD
    cv = Image.new("RGB", (canvas_w, canvas_h), "white")
    draw = ImageDraw.Draw(cv)
    draw.text((SIDE_PAD+(FRAME_W-tw)//2,
               TOP_PAD + (banner_h-th)//2),
              banner_txt, font=font, fill=TEXT_COLOR)

    sx = SIDE_PAD + (FRAME_W - fg.width)//2
    sy = TOP_PAD + banner_h + (FRAME_H - fg.height)//2
    cv.paste(fg, (sx, sy), fg)

    cv.save(dst_path, "JPEG", quality=100, subsampling=0)
