import os
import random
import requests
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Fallback image (if player's photo fails)
FALLBACK_IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/a/ac/Default_pfp.jpg"

BASE_SIZE = (1080, 1080)

def load_image(photo_path):
    """Load image from URL or local path with fallback."""
    try:
        if photo_path.startswith("http"):
            resp = requests.get(photo_path, timeout=10)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content))
        else:
            img = Image.open(photo_path)
        return img.convert("RGBA")
    except Exception as e:
        print(f"⚠️ Failed to load image {photo_path}, using fallback: {e}")
        resp = requests.get(FALLBACK_IMAGE_URL)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert("RGBA")

def resize_and_crop(img, size=BASE_SIZE):
    """Resize and crop to fit target size, preserving aspect ratio."""
    img_ratio = img.width / img.height
    target_ratio = size[0] / size[1]

    if img_ratio > target_ratio:
        # Wider than target
        new_height = size[1]
        new_width = int(new_height * img_ratio)
    else:
        # Taller than target
        new_width = size[0]
        new_height = int(new_width / img_ratio)

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Crop to center
    left = (new_width - size[0]) // 2
    top = (new_height - size[1]) // 2
    right = left + size[0]
    bottom = top + size[1]
    return img.crop((left, top, right, bottom))

def load_font(font_name, size):
    """Try loading a TTF font, fallback to default."""
    try:
        return ImageFont.truetype(font_name, size)
    except Exception:
        return ImageFont.load_default()

def add_gradient(image, height=400):
    """Add a bottom black gradient for better text visibility."""
    gradient = Image.new("L", (1, height), color=0xFF)
    for y in range(height):
        gradient.putpixel((0, y), int(255 * (y / height)))
    alpha = gradient.resize((image.width, height))
    black_img = Image.new("RGBA", (image.width, height), color=(0, 0, 0, 255))
    gradient_img = Image.composite(black_img, Image.new("RGBA", (image.width, height)), alpha)
    image.paste(gradient_img, (0, image.height - height), gradient_img)
    return image

def generate_birthday_image(name, photo_path, sport="Football", team=None):
    """Generate a stylish birthday post image."""
    player_img = load_image(photo_path)
    player_img = resize_and_crop(player_img, BASE_SIZE)

    # Create blurred background
    bg_img = player_img.filter(ImageFilter.GaussianBlur(20))
    overlay = Image.new("RGBA", BASE_SIZE, (0, 0, 0, 150))
    bg_img = Image.alpha_composite(bg_img, overlay)

    # Foreground player
    face_img = resize_and_crop(player_img, (850, 850))
    x_offset = (BASE_SIZE[0] - face_img.width) // 2
    y_offset = (BASE_SIZE[1] - face_img.height) // 2 - 40
    bg_img.paste(face_img, (x_offset, y_offset), face_img)

    # Add gradient bottom overlay
    bg_img = add_gradient(bg_img)

    draw = ImageDraw.Draw(bg_img)

    # Fonts
    font_big = load_font("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 90)
    font_small = load_font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)

    # Text
    title = f"🎉 Happy Birthday {name}!"
    subtitle = f"{sport} Star" + (f" - {team}" if team else "")

    # Use textbbox for Pillow 10+
    bbox_title = draw.textbbox((0, 0), title, font=font_big)
    w_title = bbox_title[2] - bbox_title[0]
    bbox_sub = draw.textbbox((0, 0), subtitle, font=font_small)
    w_sub = bbox_sub[2] - bbox_sub[0]

    # Draw text centered
    draw.text(
        ((BASE_SIZE[0] - w_title) / 2, 820),
        title,
        fill=(255, 215, 0),
        font=font_big,
    )
    draw.text(
        ((BASE_SIZE[0] - w_sub) / 2, 940),
        subtitle,
        fill=(255, 255, 255),
        font=font_small,
    )

    # Confetti
    for _ in range(200):
        x, y = random.randint(0, 1080), random.randint(0, 1080)
        size = random.randint(3, 9)
        color = random.choice([(255, 215, 0), (255, 0, 100), (0, 200, 255), (0, 255, 100)])
        draw.ellipse((x, y, x + size, y + size), fill=color)

    # Balloons
    for _ in range(10):
        bx, by = random.randint(80, 1000), random.randint(120, 550)
        r = random.randint(40, 70)
        balloon_color = random.choice([(255, 0, 0, 180), (0, 128, 255, 180), (255, 105, 180, 180)])
        balloon = Image.new("RGBA", (r * 2, r * 2))
        bd = ImageDraw.Draw(balloon)
        bd.ellipse((0, 0, r * 2, r * 2), fill=balloon_color)
        bg_img.paste(balloon, (bx - r, by - r), balloon)

    # Save output
    output_dir = os.path.join(os.path.dirname(__file__), "static", "birthday_posts")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"birthday_{name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
    output_path = os.path.join(output_dir, filename)
    bg_img.convert("RGB").save(output_path, "JPEG", quality=90)

    return output_path
