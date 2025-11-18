import pytest

from backend.utils import clean_text, summarize_text


def test_clean_text_removes_html_and_entities():
    s = "<p>Hello &amp; <b>World</b>\nNew</p>"
    out = clean_text(s)
    assert "<" not in out and ">" not in out
    assert "&amp;" not in out
    assert "Hello" in out and "World" in out


def test_summarize_text_shorter_than_limit():
    text = "one two three"
    assert summarize_text(text, max_words=5) == text


def test_summarize_text_truncates_and_appends_ellipsis():
    text = "".join(["word "] * 50).strip()
    out = summarize_text(text, max_words=10)
    assert out.endswith("...")
    # Should contain the requested number of words (no extra space before ellipsis)
    assert len(out.split()) == 10
