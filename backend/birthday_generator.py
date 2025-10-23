from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os, random
from datetime import datetime
import requests
from io import BytesIO

def generate_birthday_image(name, photo_url, sport="Football", team=None):
    """
    Generate a modern, clean birthday wish image with player photo, confetti, and typography.
    """
    try:
        # Download player image
        response = requests.get(photo_url, timeout=10)
        player_img = Image.open(BytesIO(response.content)).convert("RGBA")

    except Exception:
        # Use fallback image if failed
        player_img = Image.open("assets/default_player.jpg").convert("RGBA")

    base_size = (1080, 1080)
    bg_img = player_img.resize(base_size).filter(ImageFilter.GaussianBlur(15))

    # Overlay gradient
    overlay = Image.new("RGBA", base_size, (0, 0, 0, 180))
    bg_img = Image.alpha_composite(bg_img.convert("RGBA"), overlay)

    # Foreground (main face)
    face_img = player_img.copy()
    face_img.thumbnail((850, 850))
    x_offset = (1080 - face_img.width) // 2
    y_offset = (1080 - face_img.height) // 2 - 40
    bg_img.paste(face_img, (x_offset, y_offset), face_img)

    draw = ImageDraw.Draw(bg_img)

    # Fonts
    def load_font(name, size):
        try:
            return ImageFont.truetype(name, size)
        except:
            return ImageFont.load_default()

    font_big = load_font("arialbd.ttf", 90)
    font_small = load_font("arial.ttf", 50)

    title = f"🎉 Happy Birthday {name}!"
    w_text, _ = draw.textsize(title, font=font_big)
    draw.text(((1080 - w_text) / 2, 850), title, fill=(255, 215, 0), font=font_big)

    subtitle = f"{sport} Star" + (f" - {team}" if team else "")
    w_sub, _ = draw.textsize(subtitle, font=font_small)
    draw.text(((1080 - w_sub) / 2, 950), subtitle, fill=(255, 255, 255), font=font_small)

    # Confetti
    for _ in range(160):
        x, y = random.randint(0, 1080), random.randint(0, 1080)
        r = random.randint(3, 8)
        color = random.choice([(255, 215, 0), (255, 0, 120), (0, 255, 200), (0, 180, 255)])
        draw.ellipse((x, y, x + r, y + r), fill=color)

    output_dir = "static/birthday_posts"
    os.makedirs(output_dir, exist_ok=True)
    filename = f"birthday_{name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
    output_path = os.path.join(output_dir, filename)
    bg_img.convert("RGB").save(output_path, "JPEG", quality=90)
    return output_path
