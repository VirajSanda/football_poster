import os
import json
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

from config import Config

# --------------------------------------------------------------
#  Generate Metadata (title, description, tags)
# --------------------------------------------------------------
def generate_metadata(filename: str):
    """
    Cleans filename into:
    - Title without extension
    - Description without extension
    - No useless tags
    """

    # Remove extension completely
    base = os.path.splitext(filename)[0]

    # Clean formatting
    title = (
        base.replace("_", " ")
            .replace("-", " ")
            .strip()
            .title()
    )

    # Description: filename cleaned, WITHOUT extension
    description = f"{title}"

    # Tag strategy:
    # Use the full title as 1 tag + short keywords
    words = [w.lower() for w in title.split() if len(w) > 2]
    tags = list(dict.fromkeys(words))  # dedupe while keeping order

    return title, description, tags


# --------------------------------------------------------------
#  Get YouTube API Client (Auto refreshes token)
# --------------------------------------------------------------
def get_youtube_client():
    creds = Credentials(
        None,
        refresh_token=os.getenv("YOUTUBE_REFRESH_TOKEN") or Config.YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("YOUTUBE_CLIENT_ID") or Config.YOUTUBE_CLIENT_ID,
        client_secret=os.getenv("YOUTUBE_CLIENT_SECRET") or Config.YOUTUBE_CLIENT_SECRET,
    )

    try:
        creds.refresh(Request())
    except Exception as e:
        # Provide a clearer error message for calling code / logs
        raise RuntimeError(f"Failed to refresh YouTube credentials: {e}") from e

    try:
        youtube = build(
            "youtube", "v3",
            credentials=creds,
            cache_discovery=False
        )
    except Exception as e:
        raise RuntimeError(f"Failed to build YouTube client: {e}") from e

    return youtube


# --------------------------------------------------------------
#  Upload Video (Streaming)
# --------------------------------------------------------------
def upload_video_stream(file_stream, filename: str):
    youtube = get_youtube_client()
    title, description, tags = generate_metadata(filename)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "17",  # Sports
        },
        "status": {
            "privacyStatus": "private"
        }
    }

    media = MediaIoBaseUpload(
        file_stream,
        mimetype="video/*",
        resumable=True
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    try:
        while response is None:
            _status, response = request.next_chunk()
    except HttpError as he:
        # Bubble up a readable error
        content = None
        try:
            content = he.content.decode() if hasattr(he, "content") else str(he)
        except Exception:
            content = str(he)
        raise RuntimeError(f"YouTube upload failed: {content}") from he
    except Exception as e:
        raise RuntimeError(f"Unexpected error during upload: {e}") from e

    if not response or not isinstance(response, dict):
        raise RuntimeError("Upload finished but response missing or invalid")

    return {"id": response.get("id"), "raw": response}


# --------------------------------------------------------------
#  Quick local test
# --------------------------------------------------------------
def upload_from_path(path: str):
    with open(path, "rb") as f:
        return upload_video_stream(f, os.path.basename(path))
