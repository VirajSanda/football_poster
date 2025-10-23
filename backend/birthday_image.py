# birthday_generator.py
import os
import random
import requests
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def load_image(photo_path):
    """Load an image from a URL or local path."""
    try:
        if photo_path.startswith("http"):
            resp = requests.get(photo_path)
            resp.raise_for_status()
            return Image.open(BytesIO(resp.content)).convert("RGBA")
        else:
            return Image.open(photo_path).convert("RGBA")
    except Exception as e:
        raise Exception(f"Failed to load image: {photo_path} ({e})")

def load_font(font_name, size):
    """Try loading a TTF font, fallback to default if not found."""
    try:
        return ImageFont.truetype(font_name, size)
    except:
        return ImageFont.load_default()

def generate_birthday_image(name, photo_path, sport="Football", team=None):
    """Generate a stylish birthday wish image."""
    player_img = load_image(photo_path)
    base_size = (1080, 1080)

    # Background blur
    bg_img = player_img.resize(base_size).filter(ImageFilter.GaussianBlur(15))
    overlay = Image.new("RGBA", base_size, (0, 0, 0, 180))
    bg_img = Image.alpha_composite(bg_img.convert("RGBA"), overlay)

    # Foreground (player)
    face_img = player_img.copy()
    face_img.thumbnail((850, 850))
    x_offset = (1080 - face_img.width) // 2
    y_offset = (1080 - face_img.height) // 2 - 50
    bg_img.paste(face_img, (x_offset, y_offset), face_img)

    draw = ImageDraw.Draw(bg_img)

    # Fonts
    font_big = load_font("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 90)
    font_small = load_font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 50)

    # Title
    title = f"🎉 Happy Birthday {name}!"
    w_text, _ = draw.textsize(title, font=font_big)
    draw.text(((1080 - w_text) / 2, 850), title, fill=(255, 215, 0), font=font_big)

    subtitle = f"{sport} Star" + (f" - {team}" if team else "")
    w_sub, _ = draw.textsize(subtitle, font=font_small)
    draw.text(((1080 - w_sub) / 2, 950), subtitle, fill=(255, 255, 255), font=font_small)

    # Confetti
    for _ in range(180):
        x, y = random.randint(0, 1080), random.randint(0, 1080)
        size = random.randint(4, 10)
        color = random.choice([(255, 215, 0), (255, 0, 100), (0, 200, 255), (0, 255, 100)])
        draw.ellipse((x, y, x + size, y + size), fill=color)

    # Balloons
    for _ in range(8):
        bx, by = random.randint(50, 1030), random.randint(100, 600)
        balloon_color = random.choice([(255, 0, 0, 180), (0, 128, 255, 180), (255, 105, 180, 180)])
        r = random.randint(40, 70)
        draw.ellipse((bx - r, by - r, bx + r, by + r), fill=balloon_color)

    # Save output
    base_path = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_path, "static", "birthday_posts")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"birthday_{name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
    output_path = os.path.join(output_dir, filename)
    bg_img.convert("RGB").save(output_path, "JPEG", quality=90)

    return output_path
