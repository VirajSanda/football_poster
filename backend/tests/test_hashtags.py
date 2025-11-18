from backend.hashtags import generate_hashtags


def test_generate_hashtags_creates_hashtags():
    title = "Lionel Messi scores a beautiful goal"
    summary = "Amazing dribble and finish"
    tags = generate_hashtags(title, summary)
    assert isinstance(tags, list)
    assert all(t.startswith("#") for t in tags)
    # Should not include very short words
    assert not any(len(t) <= 2 for t in tags)


def test_generate_hashtags_limits_to_six():
    title = "".join([f"word{i} " for i in range(20)])
    tags = generate_hashtags(title)
    assert len(tags) <= 6
