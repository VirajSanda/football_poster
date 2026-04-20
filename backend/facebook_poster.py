import requests
import os
import json
from config import Config
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from models import db, TelePost
# For backward compatibility if needed

load_dotenv()
FACEBOOK_PAGE_ID = Config.FACEBOOK_PAGE_ID
FACEBOOK_ACCESS_TOKEN = Config.FACEBOOK_ACCESS_TOKEN
SG_TZ = timezone(timedelta(hours=8))

def upload_to_facebook(image_path, caption):
    """
    Upload a local image to Facebook Page.
    """
    if not FACEBOOK_PAGE_ID or not FACEBOOK_ACCESS_TOKEN:
        return {"error": "Facebook credentials not configured"}

    url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/photos"
    files = {'source': open(image_path, 'rb')}
    data = {'caption': caption, 'access_token': FACEBOOK_ACCESS_TOKEN}

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

    if not FACEBOOK_PAGE_ID or not FACEBOOK_ACCESS_TOKEN:
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

            scheduled_timestamp = int(scheduled_dt.timestamp())

        except Exception as e:
            return {"error": f"Invalid scheduled_time: {str(e)}"}

    # Prepare payload
    url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/feed"
    payload = {
        "message": message,
        "access_token": FACEBOOK_ACCESS_TOKEN,
    }

    # Include optional link
    if link:
        payload["link"] = link

    # Determine if it's scheduled or immediate
    if scheduled_timestamp is not None:
        payload["published"] = "false"
        payload["scheduled_publish_time"] = scheduled_timestamp
    else:
        payload["published"] = "true"

    # If there's an image, upload it first as unpublished and attach it
    if image_path and os.path.exists(image_path):
        photo_url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/photos"

        with open(image_path, "rb") as img:
            files = {"source": img}
            photo_res = requests.post(
                photo_url,
                params={
                    "published": "false",
                    "access_token": FACEBOOK_ACCESS_TOKEN,
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

def upload_video_to_facebook(video_path, caption):
    """
    Upload a local video to Facebook Page.
    """
    if not FACEBOOK_PAGE_ID or not FACEBOOK_ACCESS_TOKEN:
        return {"error": "Facebook credentials not configured"}

    url = f"https://graph-video.facebook.com/{FACEBOOK_PAGE_ID}/videos"
    files = {'source': open(video_path, 'rb')}
    data = {'access_token': FACEBOOK_ACCESS_TOKEN, 'description': caption}

    response = requests.post(url, files=files, data=data)
    return response.json()

def post_multiple_to_facebook_scheduled(title, summary, hashtags, image_paths=None, link=None, scheduled_time=None):
    # Final message
    
    if not FACEBOOK_PAGE_ID or not FACEBOOK_ACCESS_TOKEN:
        print("❌ FACEBOOK CREDS FAILED →", FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN)
        return {"error": "Facebook credentials not configured"}

    message = f"{title}\n\n{summary}\n\n{hashtags}".strip()

    # Handle scheduled posting
    scheduled_timestamp = None
    if scheduled_time:
        dt = datetime.fromisoformat(scheduled_time.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        now_utc = datetime.now(timezone.utc)
        if dt < now_utc + timedelta(minutes=10):
            dt = now_utc + timedelta(minutes=11)

        scheduled_timestamp = int(dt.timestamp())

    # 1️⃣ Upload photos as unpublished
    media_items = []
    if image_paths:
        for path in image_paths:
            if not os.path.exists(path):
                print(f"[WARN] Missing image: {path}")
                continue

            photo_url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/photos"
            with open(path, "rb") as img:
                res = requests.post(
                    photo_url,
                    params={"published": "false", "access_token": FACEBOOK_ACCESS_TOKEN},
                    files={"source": img}
                )

            data = res.json()
            if "id" in data:
                media_items.append({"media_fbid": data["id"]})
            else:
                print("❌ Facebook photo upload failed:", data)

    # 2️⃣ Final feed post
    feed_url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/feed"
    payload = {
        "message": message,
        "access_token": FACEBOOK_ACCESS_TOKEN,
        "published": "false" if scheduled_timestamp else "true"
    }

    if scheduled_timestamp:
        payload["scheduled_publish_time"] = scheduled_timestamp

    if media_items:
        payload["attached_media"] = json.dumps(media_items)

    res = requests.post(feed_url, data=payload)
    result = res.json()
    result["attached_media_count"] = len(media_items)

    return result

def upload_video_to_facebook_scheduled(video_path, caption):
    """
    Upload video as scheduled post (reel safe spacing).
    """

    if not FACEBOOK_PAGE_ID or not FACEBOOK_ACCESS_TOKEN:
        return {"error": "Facebook credentials not configured"}

    scheduled_dt_utc = get_safe_video_schedule_time_from_db()

# ✅ Correct format for Facebook
    scheduled_timestamp = int(scheduled_dt_utc.timestamp())

    url = f"https://graph-video.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/videos"

    with open(video_path, "rb") as vid:
        files = {"source": vid}
        data = {
            "access_token": FACEBOOK_ACCESS_TOKEN,
            "description": caption,
            "published": "false",
            "scheduled_publish_time": scheduled_timestamp
        }

        response = requests.post(url, files=files, data=data)

    try:
        res_data = response.json()
    except Exception:
        res_data = {"error": "Invalid JSON", "raw": response.text}

    res_data["debug_info"] = {
        "scheduled_time_utc": scheduled_dt_utc.isoformat(),
        "scheduled_timestamp": scheduled_timestamp
    }

    return res_data, scheduled_dt_utc

def get_safe_video_schedule_time_from_db():
    """
    Uses DB to enforce 30-min gap between video posts.
    Works in Singapore timezone.
    """

    try:
        # 🔥 Get last VIDEO post (most recent)
        last_post = (
            TelePost.query
            .filter(TelePost.image_path.isnot(None))  # assuming videos saved here too
            .order_by(TelePost.created_at.desc())
            .first()
        )

        now_sg = datetime.now(SG_TZ)
        min_fb_time_sg = now_sg + timedelta(minutes=11)

        if not last_post:
            return min_fb_time_sg.astimezone(timezone.utc)

        last_time_utc = last_post.created_at

        if last_time_utc.tzinfo is None:
            last_time_utc = last_time_utc.replace(tzinfo=timezone.utc)

        # convert to SG time
        last_time_sg = last_time_utc.astimezone(SG_TZ)

        # enforce 30 min gap
        next_time_sg = last_time_sg + timedelta(minutes=30)

        final_sg = max(next_time_sg, min_fb_time_sg)

        return final_sg.astimezone(timezone.utc)

    except Exception as e:
        print(f"[DB Schedule Error] {e}")
        return (datetime.now(SG_TZ) + timedelta(minutes=11)).astimezone(timezone.utc)

