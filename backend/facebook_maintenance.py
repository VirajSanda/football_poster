import requests
import os
import re
import time
from datetime import datetime
from urllib.parse import urlparse
from collections import defaultdict
from config import Config

BASE = "https://graph.facebook.com/v25.0"

PAGE_ID = Config.FACEBOOK_PAGE_ID
PAGE_ACCESS_TOKEN = Config.FACEBOOK_ACCESS_TOKEN

REQUEST_DELAY = 0.5


# ---------------- Core ---------------- #

def get_scheduled_posts():
    url = f"{BASE}/{PAGE_ID}/scheduled_posts"
    params = {
        "fields": "id,message,scheduled_publish_time,attachments{media_type}",
        "access_token": PAGE_ACCESS_TOKEN
    }

    posts = []

    while url:
        r = requests.get(url, params=params).json()
        posts.extend(r.get("data", []))

        url = r.get("paging", {}).get("next")
        params = None

    return posts


def extract_url(message):
    if not message:
        return None
    
    match = re.search(r"(https?://[^\s]+)", message)
    return match.group(0) if match else None


def needs_preview_fix(post):
    message = post.get("message", "")
    attachments = post.get("attachments", {}).get("data", [])

    has_url = extract_url(message) is not None
    has_preview = bool(attachments)

    return has_url and not has_preview


def fix_message_format(message):
    url = extract_url(message)

    if not url:
        return message

    if url + "\n" in message:
        return message

    return message.replace(url, url + "\n")


def update_post_message(post_id, new_message):
    url = f"{BASE}/{post_id}"

    data = {
        "message": new_message,
        "access_token": PAGE_ACCESS_TOKEN
    }

    r = requests.post(url, data=data)
    return r.json()


def force_rescrape(url_to_scrape):
    scrape_url = f"{BASE}/"
    params = {
        "id": url_to_scrape,
        "scrape": "true",
        "access_token": PAGE_ACCESS_TOKEN
    }
    return requests.post(scrape_url, data=params).json()


# ---------------- Main Task ---------------- #

def run_facebook_maintenance(logger=None):

    if logger:
        logger.info("📘 Facebook maintenance started...")

    posts = get_scheduled_posts()

    updated_count = 0
    domain_failures = defaultdict(int)

    for post in posts:

        if needs_preview_fix(post):

            old_message = post.get("message", "")
            url = extract_url(old_message)

            if url:
                domain = urlparse(url).netloc
                domain_failures[domain] += 1

                force_rescrape(url)
                time.sleep(REQUEST_DELAY)

            new_message = fix_message_format(old_message)

            if new_message != old_message:
                update_post_message(post["id"], new_message)
                updated_count += 1
                time.sleep(REQUEST_DELAY)

    if logger:
        logger.info(f"✅ Facebook updates applied: {updated_count}")

        if domain_failures:
            logger.info("🌐 Domains with preview issues:")
            for d, c in sorted(domain_failures.items(), key=lambda x: -x[1]):
                logger.info(f"{d}: {c}")

    return {
        "updated": updated_count,
        "domains": dict(domain_failures)
    }