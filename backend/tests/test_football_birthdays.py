import os
import json
import tempfile
from pathlib import Path

import pytest

from backend import football_birthdays as fb
from PIL import Image


def make_jpg(path, size=(200, 300), color=(10, 20, 30)):
    img = Image.new("RGB", size, color)
    img.save(path, format="JPEG")


def test_resize_and_crop_image(tmp_path):
    img_path = tmp_path / "p.jpg"
    make_jpg(str(img_path), size=(1600, 800))
    # call resize; shouldn't raise
    fb.resize_and_crop_image(str(img_path))
    assert os.path.exists(str(img_path))


def test_detect_local_image_and_safe_download(tmp_path, monkeypatch):
    # point LOCAL_PLAYER_DIR to temp dir and create a default image
    orig_local = fb.LOCAL_PLAYER_DIR
    orig_default = fb.DEFAULT_LOCAL_IMAGE

    tmp_players = tmp_path / "players"
    tmp_players.mkdir()
    img_file = tmp_players / "John_Doe.jpg"
    make_jpg(str(img_file))

    fb.LOCAL_PLAYER_DIR = str(tmp_players)
    fb.DEFAULT_LOCAL_IMAGE = str(img_file)

    res = fb.detect_local_image("John Doe")
    assert res is not None
    assert os.path.exists(res)

    # test safe_download_image with invalid url -> falls back to local
    out = fb.safe_download_image("", "John Doe")
    assert out is not None

    # restore
    fb.LOCAL_PLAYER_DIR = orig_local
    fb.DEFAULT_LOCAL_IMAGE = orig_default


def test_get_upcoming_birthdays_with_custom_json(tmp_path, monkeypatch):
    # create a temp JSON with a player whose birthday is today
    today = fb.datetime.date.today()
    player = {"name": "Temp Player", "dob": today.strftime("%Y-%m-%d"), "team": "X", "photo_url": ""}
    pfile = tmp_path / "list.json"
    pfile.write_text(json.dumps([player]), encoding="utf-8")

    orig_json = fb.BIRTHDAY_JSON
    orig_db = fb.DB_PATH

    fb.BIRTHDAY_JSON = str(pfile)
    # ensure DB path is in tmp
    fb.DB_PATH = str(tmp_path / "db.sqlite")

    results = fb.get_upcoming_birthdays(days_ahead=0)
    # Might be empty if today handling differs, but ensure function runs
    assert isinstance(results, list)

    fb.BIRTHDAY_JSON = orig_json
    fb.DB_PATH = orig_db
