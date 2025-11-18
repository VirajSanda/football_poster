import os
import tempfile
from io import BytesIO

import pytest

from backend import image_generator as ig
from PIL import Image, ImageDraw


def make_temp_image(path, size=(800, 600), color=(255, 0, 0)):
    img = Image.new("RGBA", size, color)
    img.save(path, format="PNG")


def test_wrap_text_and_load_font():
    # Create a small image and draw object
    img = Image.new("RGBA", (400, 300), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ig.load_sport_font(20)
    lines = ig.wrap_text(draw, "This is a test of wrap text function for image generator", font, max_width=200)
    assert isinstance(lines, list)
    assert len(lines) >= 1


def test_download_and_rebrand_with_local_image(tmp_path):
    # Create a temp image file
    src = tmp_path / "src.png"
    make_temp_image(str(src), size=(1600, 900))

    # Ensure STATIC_DIR exists in temp workspace
    orig_static = ig.STATIC_DIR
    ig.STATIC_DIR = str(tmp_path / "static_images")
    os.makedirs(ig.STATIC_DIR, exist_ok=True)

    out = ig.download_and_rebrand(str(src), article_url=None, title="Test Title")
    assert out is not None
    assert os.path.exists(out)

    # cleanup
    ig.STATIC_DIR = orig_static


def test_download_and_rebrand_nocrop_with_local_image(tmp_path):
    src = tmp_path / "src2.png"
    make_temp_image(str(src), size=(500, 400))

    orig_static = ig.STATIC_DIR
    ig.STATIC_DIR = str(tmp_path / "static_images2")
    os.makedirs(ig.STATIC_DIR, exist_ok=True)

    out = ig.download_and_rebrand_nocrop(str(src), article_url=None, title="NoCrop Title")
    assert out is not None
    assert os.path.exists(out)

    ig.STATIC_DIR = orig_static


def test_get_main_image_from_html(monkeypatch):
    class DummyResp:
        status_code = 200

        def __init__(self, text):
            self.text = text

    def fake_get(url, timeout=10, headers=None):
        return DummyResp('<html><body><img src="/images/pic.jpg"/></body></html>')

    monkeypatch.setattr(ig.requests, "get", fake_get)
    res = ig.get_main_image("http://example.com/article")
    assert res.endswith("/images/pic.jpg")
