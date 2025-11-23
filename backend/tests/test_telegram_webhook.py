import sys
from pathlib import Path
import json
from types import SimpleNamespace


def test_telegram_video_upload_flow(monkeypatch, tmp_path):
    # Ensure backend package is importable
    backend_dir = str(Path(__file__).resolve().parents[1])
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    import app as app_module
    from models import db, TelePost
    import telegram_webhook as tw

    client = app_module.app.test_client()

    # Clean TelePost
    from sqlalchemy import inspect

    with app_module.app.app_context():
        inspector = inspect(db.engine)
        # If old table exists without new columns, drop and recreate to match model
        if inspector.has_table(TelePost.__tablename__):
            try:
                TelePost.__table__.drop(db.engine)
            except Exception:
                pass
        db.create_all()

    # Prepare fake responses for requests.get
    def fake_requests_get(url, *args, **kwargs):
        class Resp:
            def __init__(self, url):
                self._url = url
                self.content = b"FAKEVIDEO"
            def json(self):
                # Simulate getFile response
                return {"result": {"file_path": "videos/fake.mp4"}}
        return Resp(url)

    monkeypatch.setattr(tw, "requests", SimpleNamespace(get=fake_requests_get))

    # Monkeypatch facebook/video upload functions to be no-ops
    monkeypatch.setattr(tw, "upload_video_to_facebook", lambda path, caption: {"fb": "ok"})

    # Monkeypatch youtube upload to return an id
    monkeypatch.setattr(tw, "upload_video_stream", lambda f, name: {"id": "YT_FAKE_ID"})

    # Allow any channel
    monkeypatch.setattr(tw, "ALLOWED_CHANNELS", [])

    # Build payload similar to Telegram
    payload = {
        "message": {
            "chat": {"id": 12345, "title": "Test Channel"},
            "caption": "Test video caption",
            "video": {"file_id": "file_1"}
        }
    }

    # Ensure /tmp exists (tests run on Windows too)
    import os
    try:
        os.makedirs(os.path.join(os.sep, 'tmp'), exist_ok=True)
    except Exception:
        pass

    resp = client.post("/telegram/test_webhook", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("status") == "ok"
    # youtube_video_id should be present in response
    assert data.get("youtube_video_id") == "YT_FAKE_ID"

    # Check DB record saved with youtube_video_id
    with app_module.app.app_context():
        rec = TelePost.query.filter_by(channel_id=str(12345)).first()
        assert rec is not None
        assert rec.youtube_video_id == "YT_FAKE_ID"
