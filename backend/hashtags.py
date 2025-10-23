def generate_hashtags(title: str, summary: str = ""):
    """Generate up to 6 unique hashtags."""
    words = (title + " " + summary).split()
    hashtags = []
    for w in words:
        clean = "".join(c for c in w if c.isalnum())
        if len(clean) > 3:
            hashtags.append(f"#{clean.capitalize()}")
    return list(dict.fromkeys(hashtags))[:6]
