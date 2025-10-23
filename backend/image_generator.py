import os
import uuid
import random
import requests
from PIL import Image, ImageDraw, ImageFont, ImageStat
from urllib.parse import urljoin
from bs4 import BeautifulSoup

# ---------------- Paths & Setup ---------------- #
STATIC_DIR = os.path.join("static", "images")
LOGO_PATH = os.path.join("static", "logo.png")
PLACEHOLDER_PATH = os.path.join("static", "placeholder.png")

os.makedirs(STATIC_DIR, exist_ok=True)

# ⚽ Sporty font priority — add these TTFs in your root folder if possible
SPORT_FONT_PATHS = [
    "bebasneue.ttf",
    "anton.ttf",
    "impact.ttf",
    "arialbd.ttf",
]

TITLE_FONT_SIZE = 60
WATERMARK_FONT_SIZE = 24

FACEBOOK_WIDTH = 1200
FACEBOOK_HEIGHT = 630

# Team-color pairs for gradient (like match banners)
TEAM_COLORS = [
    ((220, 20, 60), (0, 0, 139)),    # red vs dark blue
    ((34, 139, 34), (255, 255, 255)),# green vs white
    ((255, 140, 0), (0, 0, 0)),      # orange vs black
    ((70, 130, 180), (255, 255, 255)),# steel blue vs white
    ((0, 0, 0), (255, 215, 0)),      # black vs gold
    ((128, 0, 128), (255, 255, 255)),# purple vs white
]


def load_sport_font(size):
    """Try multiple sporty fonts before fallback."""
    for path in SPORT_FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def get_main_image(article_url):
    """Scrape first <img> from article page."""
    try:
        resp = requests.get(article_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        img_tag = soup.find("img")
        if not img_tag:
            return None
        return urljoin(article_url, img_tag.get("src")) if img_tag.get("src") else None
    except Exception as e:
        print("[ERROR] get_main_image:", e)
    return None


def get_image_brightness(img):
    """Estimate brightness of an image to choose text color dynamically."""
    stat = ImageStat.Stat(img.convert("L"))
    return stat.mean[0]


def wrap_text(draw, text, font, max_width):
    """Wrap text into lines that fit the given width."""
    words = text.split()
    lines, line = [], ""
    for w in words:
        test = f"{line} {w}".strip()
        if draw.textlength(test, font=font) <= max_width:
            line = test
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def add_bottom_banner(img, title_text):
    """Draw a semi-transparent bottom gradient banner with sporty multi-line title."""
    W, H = img.size
    banner_h = int(H * 0.25)  # compact height
    banner = Image.new("RGBA", (W, banner_h))

    # Random team-color gradient
    team1, team2 = random.choice(TEAM_COLORS)
    for y in range(banner_h):
        # Fades from nearly transparent (top) to solid (bottom)
        fade = y / banner_h
        for x in range(W):
            t = x / W
            r = int(team1[0] * (1 - t) + team2[0] * t)
            g = int(team1[1] * (1 - t) + team2[1] * t)
            b = int(team1[2] * (1 - t) + team2[2] * t)
            alpha = int(40 + 200 * (fade ** 1.5))  # soft fade-in curve
            banner.putpixel((x, y), (r, g, b, alpha))

    img.paste(banner, (0, H - banner_h), banner)

    draw = ImageDraw.Draw(img)
    font_size = TITLE_FONT_SIZE
    font = load_sport_font(font_size)
    lines = wrap_text(draw, title_text, font, W - 100)
    while len(lines) > 2 and font_size > 24:
        font_size = int(font_size * 0.9)
        font = load_sport_font(font_size)
        lines = wrap_text(draw, title_text, font, W - 100)

    total_h = len(lines) * (font_size + 6)
    y = H - banner_h + (banner_h - total_h) // 2 + 5

    brightness = get_image_brightness(img)
    text_color = (255, 255, 255, 255) if brightness < 140 else (10, 10, 10, 255)

    # Text with subtle shadow
    for line in lines:
        tw = draw.textlength(line, font=font)
        x = (W - tw) // 2
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 160))
        draw.text((x, y), line, font=font, fill=text_color)
        y += font_size + 4

    return img


def download_and_rebrand(img_url, article_url, title="Kick Off Zone"):
    """Download, resize, and brand image for Facebook posts."""
    try:
        if not img_url:
            img_url = get_main_image(article_url)
        if not img_url:
            return PLACEHOLDER_PATH if os.path.exists(PLACEHOLDER_PATH) else None

        resp = requests.get(img_url, timeout=10, stream=True)
        if resp.status_code != 200:
            return PLACEHOLDER_PATH if os.path.exists(PLACEHOLDER_PATH) else None

        img = Image.open(resp.raw).convert("RGBA")

        # --- Crop/resize to Facebook aspect ratio (1200x630) --- #
        img_ratio = img.width / img.height
        target_ratio = FACEBOOK_WIDTH / FACEBOOK_HEIGHT
        if img_ratio > target_ratio:
            new_width = int(img.height * target_ratio)
            left = (img.width - new_width) // 2
            img = img.crop((left, 0, left + new_width, img.height))
        else:
            new_height = int(img.width / target_ratio)
            top = (img.height - new_height) // 2
            img = img.crop((0, top, img.width, top + new_height))
        img = img.resize((FACEBOOK_WIDTH, FACEBOOK_HEIGHT), Image.Resampling.LANCZOS)

        # Add bottom banner title
        img = add_bottom_banner(img, title)

        # --- Add watermark --- #
        draw = ImageDraw.Draw(img)
        font_wm = load_sport_font(WATERMARK_FONT_SIZE)
        wm_text = "Kick Off Zone"
        draw.text((25, FACEBOOK_HEIGHT - 45), wm_text, font=font_wm, fill=(255, 215, 0, 255))

        # --- Paste logo if available --- #
        if os.path.exists(LOGO_PATH):
            try:
                logo = Image.open(LOGO_PATH).convert("RGBA")
                logo_w = int(FACEBOOK_WIDTH * 0.1)
                ratio = logo_w / logo.width
                logo = logo.resize((logo_w, int(logo.height * ratio)), Image.Resampling.LANCZOS)
                img.paste(logo, (FACEBOOK_WIDTH - logo_w - 20, FACEBOOK_HEIGHT - logo.height - 20), logo)
            except Exception as e:
                print("[WARN] Failed to paste logo:", e)

        # Save
        filename = f"{uuid.uuid4().hex}.png"
        filepath = os.path.join(STATIC_DIR, filename)
        img.save(filepath, "PNG")
        return filepath

    except Exception as e:
        print("[ERROR] download_and_rebrand:", e)
        return PLACEHOLDER_PATH if os.path.exists(PLACEHOLDER_PATH) else None


def generate_post_image(title, image_url, article_url, summary=""):
    """Main entry for backend to generate post image."""
    return download_and_rebrand(image_url, article_url, title)


def generate_hashtags(title, summary=""):
    """Generate simple hashtags from title + summary."""
    base_words = (title + " " + summary).split()
    hashtags = []
    for word in base_words:
        clean = "".join(ch for ch in word if ch.isalnum())
        if len(clean) > 3:
            hashtags.append(f"#{clean.capitalize()}")
    hashtags = list(dict.fromkeys(hashtags))
    return hashtags[:6]
