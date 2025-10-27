import requests
import os
import json
from config import Config
from datetime import datetime, timedelta, timezone

def upload_to_facebook(image_path, caption):
    """
    Upload a local image to Facebook Page.
    """
    if not Config.FACEBOOK_PAGE_ID or not Config.FACEBOOK_ACCESS_TOKEN:
        return {"error": "Facebook credentials not configured"}

    url = f"https://graph.facebook.com/{Config.FACEBOOK_PAGE_ID}/photos"
    files = {'source': open(image_path, 'rb')}
    data = {'caption': caption, 'access_token': Config.FACEBOOK_ACCESS_TOKEN}

    try:
        response = requests.post(url, files=files, data=data)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"[FB ERROR] {response.text}")
            return {"error": response.text}
    except Exception as e:
        print(f"[FB Upload Exception] {e}")
        return {"error": str(e)}


# ✅ Add this alias for backward compatibility with app.py
def post_to_facebook(title, summary="", hashtags=None, image_path=None):
    """
    Wrapper alias around upload_to_facebook() for app.py compatibility.
    """
    caption_parts = [title]
    if summary:
        caption_parts.append(summary)
    if hashtags:
        caption_parts.append(" ".join(f"#{h.strip('#')}" for h in hashtags))
    caption = "\n\n".join([part for part in caption_parts if part])

    if not image_path:
        return {"error": "No image provided"}

    return upload_to_facebook(image_path, caption)

def post_to_facebook_scheduled(title, summary, hashtags, image_path=None, link=None, scheduled_time=None):
    """
    Posts to Facebook Page feed — can be scheduled or published immediately.
    Auto-adjusts time if too early (<10 min).
    """

    if not Config.FACEBOOK_PAGE_ID or not Config.FACEBOOK_ACCESS_TOKEN:
        return {"error": "Facebook credentials not configured"}

    # Combine message
    message = f"{title}\n\n{summary}\n\n{hashtags}".strip()

    # Prepare scheduled time (convert to UTC and ensure it's valid)
    scheduled_timestamp = None
    if scheduled_time:
        try:
            if isinstance(scheduled_time, str):
                scheduled_dt = datetime.fromisoformat(scheduled_time.replace("Z", "+00:00"))
            else:
                scheduled_dt = scheduled_time

            if scheduled_dt.tzinfo is None:
                scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)

            now_utc = datetime.now(timezone.utc)

            # Facebook requires at least 10 minutes ahead
            if scheduled_dt < now_utc + timedelta(minutes=10):
                scheduled_dt = now_utc + timedelta(minutes=11)

            scheduled_timestamp = scheduled_dt.isoformat()

        except Exception as e:
            return {"error": f"Invalid scheduled_time: {str(e)}"}

    # Prepare payload
    url = f"https://graph.facebook.com/v19.0/{Config.FACEBOOK_PAGE_ID}/feed"
    payload = {
        "message": message,
        "access_token": Config.FACEBOOK_ACCESS_TOKEN,
    }

    # Include optional link
    if link:
        payload["link"] = link

    # Determine if it's scheduled or immediate
    if scheduled_timestamp:
        payload["published"] = "false"
        payload["scheduled_publish_time"] = scheduled_timestamp
    else:
        payload["published"] = "true"

    # If there's an image, upload it first as unpublished and attach it
    if image_path and os.path.exists(image_path):
        photo_url = f"https://graph.facebook.com/v19.0/{Config.FACEBOOK_PAGE_ID}/photos"

        with open(image_path, "rb") as img:
            files = {"source": img}
            photo_res = requests.post(
                photo_url,
                params={
                    "published": "false",
                    "access_token": Config.FACEBOOK_ACCESS_TOKEN,
                },
                files=files,
            )

        photo_data = photo_res.json()

        if "id" in photo_data:
            # Must JSON-encode the array
            payload["attached_media"] = json.dumps([{"media_fbid": photo_data["id"]}])
        else:
            return {
                "error": "Failed to upload image to Facebook",
                "details": photo_data
            }

    # Send post request to /feed
    response = requests.post(url, data=payload)
    try:
        data = response.json()
    except Exception:
        data = {"error": "Invalid JSON response", "raw": response.text}

    data["debug_info"] = {
        "scheduled_time_final": scheduled_timestamp,
        "message": message,
        "published": payload.get("published"),
    }

    return data

