import requests
from config import FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN  # ✅ use config file

def upload_to_facebook(image_path, caption):
    """
    Upload a local image to Facebook Page.
    """
    if not FACEBOOK_PAGE_ID or not FACEBOOK_ACCESS_TOKEN:
        return {"error": "Facebook credentials not configured"}

    url = f"https://graph.facebook.com/{FACEBOOK_PAGE_ID}/photos"
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
