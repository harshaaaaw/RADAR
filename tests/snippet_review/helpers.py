"""
Shared helper functions for snippet review stress tests.
These are NOT fixtures (fixtures come from conftest.py),
but pure utility functions that test files can import directly.
"""
import io
import numpy as np
from PIL import Image, ImageDraw


def make_blank_page(w=2480, h=3508, fill=255):
    """A4 at 300 DPI, default white."""
    return Image.new("RGB", (w, h), (fill, fill, fill))


def make_page_with_text(text_coverage=0.80):
    """Simulated page with black text blocks covering text_coverage % of area."""
    img = make_blank_page()
    draw = ImageDraw.Draw(img)
    h = int(3508 * text_coverage)
    draw.rectangle([200, 200, 2280, 200 + h], fill=(20, 20, 20))
    return img


def make_faded_text_page():
    """Page where printed text is very faint (gray ~210/255)."""
    img = make_blank_page()
    draw = ImageDraw.Draw(img)
    for y in range(300, 800, 40):
        draw.rectangle([200, y, 2200, y + 22], fill=(210, 210, 210))
    return img


def make_signature_page():
    """Page with a signature-like cursive stroke in the lower half."""
    img = make_blank_page()
    draw = ImageDraw.Draw(img)
    points = [(400 + i * 5, 2800 + int(30 * np.sin(i / 5))) for i in range(200)]
    draw.line(points, fill=(0, 0, 0), width=3)
    return img


def make_stamp_page():
    """Page with a circular stamp in the lower right."""
    img = make_blank_page()
    draw = ImageDraw.Draw(img)
    draw.ellipse([1800, 2800, 2200, 3200], outline=(180, 0, 0), width=8)
    draw.rectangle([1850, 2900, 2150, 3100], fill=(180, 0, 0))
    return img


def img_to_bytes(pil_img):
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()
