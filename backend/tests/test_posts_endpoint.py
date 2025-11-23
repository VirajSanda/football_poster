import sys
import json
from types import SimpleNamespace
from datetime import datetime, timedelta
from pathlib import Path


def test_fetch_news_creates_draft_posts(monkeypatch):
    # Ensure the `backend` package root is on sys.path so `app.py`'s
    # absolute imports (like `from models import ...`) resolve when
    # importing as a top-level module.
    backend_dir = str(Path(__file__).resolve().parents[1])
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    # Import app and models
    import app as app_module
    from models import db, Post

    client = app_module.app.test_client()

    # Clean any existing posts
    with app_module.app.app_context():
        db.session.query(Post).delete()
        db.session.commit()

    # Fake feedparser.parse to return a single entry that supports
    # both attribute access (entry.title) and dict-like .get()
    class FakeEntry(dict):
        def __getattr__(self, name):
            return self.get(name)

    entry = FakeEntry(title="Fake Title", link="http://example.com/a", summary="Summary")
    monkeypatch.setattr(app_module.feedparser, "parse", lambda url: SimpleNamespace(entries=[entry]))

    # Stub out generate_post_image to avoid real downloads/IO
    monkeypatch.setattr(app_module, "generate_post_image", lambda title, image_url, article_url, summary: "static/uploads/fake.jpg")

    # Call fetch_news
    resp = client.post("/fetch_news")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1

    # Ensure GET /posts?status=draft returns the created post (within 24h)
    resp2 = client.get("/posts?status=draft")
    assert resp2.status_code == 200
    drafts = resp2.get_json()
    assert any(p["title"] == "Fake Title" for p in drafts)

    # Now mark the created post as older than 2 days and ensure it gets excluded
    with app_module.app.app_context():
        p = Post.query.filter_by(title="Fake Title").first()
        assert p is not None
        p.created_at = datetime.utcnow() - timedelta(days=2)
        db.session.commit()

    resp3 = client.get("/posts?status=draft")
    drafts_after = resp3.get_json()
    # The old post should no longer be returned by the default 24h filter
    assert all(p["title"] != "Fake Title" for p in drafts_after)
