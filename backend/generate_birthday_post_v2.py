import os
import random
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageStat

OUTPUT_DIR = "static/birthday_posts"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Fallback fonts
FONTS = ["DroidSerif-BoldItalic.ttf", "DejaVuSans-Bold.ttf", "arial.ttf"]


# --- Utilities ---

def download_image(url):
    """Download image with headers and convert to RGB."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://commons.wikimedia.org/"
        }
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        return img.convert("RGB")
    except Exception as e:
        print(f"[ERROR] Download failed: {url} → {e}")
        return None


def enhance_image(img):
    """Brightness, contrast, and sharpness enhancement."""
    img = ImageEnhance.Brightness(img).enhance(1.1)
    img = ImageEnhance.Contrast(img).enhance(1.1)
    img = ImageEnhance.Sharpness(img).enhance(1.15)
    return img

# --- Composition Helpers ---

def compose_images(images):
    """
    Combine up to 4 portrait or landscape images into a 1080x1080 collage.
    If only 1 image → center-cropped.
    """
    target_size = (1080, 1080)
    count = len(images)
    canvas = Image.new("RGB", target_size, (0, 0, 0))

    if count == 0:
        return canvas

    if count == 1:
        img = images[0].resize(target_size, Image.Resampling.LANCZOS)
        canvas.paste(img, (0, 0))
        return canvas

    if count == 2:
        w, h = target_size
        each_w = w // 2
        for i, im in enumerate(images[:2]):
            im = im.resize((each_w, h), Image.Resampling.LANCZOS)
            canvas.paste(im, (i * each_w, 0))
        return canvas

    if count == 3 or count == 4:
        w, h = target_size
        each_w = w // 2
        each_h = h // 2
        positions = [(0, 0), (each_w, 0), (0, each_h), (each_w, each_h)]
        for i, im in enumerate(images[:4]):
            im = im.resize((each_w, each_h), Image.Resampling.LANCZOS)
            canvas.paste(im, positions[i])
        return canvas

    return images[0].resize(target_size, Image.Resampling.LANCZOS)

# --- Main Entry ---
def generate_birthday_post_v2(name, image_urls, year=None, position="auto", theme="gold"):
    """
    Multi-image version.
    NO TEXT. NO OVERLAY. JUST COMPOSE + ENHANCE + SAVE.
    """
    print(f"[DEBUG] Generating post v2 → {name}, {len(image_urls)} image(s)")
    loaded_images = []

    for src in image_urls:
        try:
            img = None

            # 1️⃣ Local file
            if os.path.exists(src):
                img = Image.open(src).convert("RGB")
                print(f"[DEBUG] Loaded local image: {src}")

            # 2️⃣ Remote URL
            elif src.startswith("http://") or src.startswith("https://"):
                resp = requests.get(src, timeout=10)
                resp.raise_for_status()
                img = Image.open(BytesIO(resp.content)).convert("RGB")
                print(f"[DEBUG] Downloaded remote image: {src}")

            else:
                print(f"[WARN] Invalid image path: {src}")

            if img:
                loaded_images.append(img)

        except Exception as e:
            print(f"[ERROR] Failed to load image {src}: {e}")

    if not loaded_images:
        print("[ERROR] No valid images found.")
        return None

    print(f"[INFO] Loaded {len(loaded_images)} image(s)")

    # 3️⃣ Combine & enhance
    composed = compose_images(loaded_images)
    composed = enhance_image(composed)

    # NO TEXT — removed completely

    # 4️⃣ Save final output
    clean_name = name.split(",")[0].split("(")[0].strip()
    filename = f"{clean_name.replace(' ', '_')}_v2.jpg"
    save_path = os.path.join(OUTPUT_DIR, filename)

    composed.convert("RGB").save(save_path, format="JPEG", quality=95)
    print(f"[✅] Saved: {save_path}")

    return save_path

    