import re

def clean_text(text: str) -> str:
    """Remove HTML tags, entities, and trim spaces."""
    text = re.sub(r"<.*?>", "", text)   # remove HTML tags
    text = re.sub(r"&.*?;", "", text)   # remove HTML entities
    text = text.replace("\n", " ").strip()
    return text

def summarize_text(text: str, max_words: int = 40) -> str:
    """Create a short summary by trimming words."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."
