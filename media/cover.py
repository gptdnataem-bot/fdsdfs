
import os, io, math, tempfile, requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH, HEIGHT = 1280, 720

def _load_font(size: int):
    # Try common fonts; fall back to default bitmap font.
    for name in ["DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "Arial.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()

def _wrap(draw, text, font, max_width):
    words = (text or "").strip().split()
    if not words:
        return [""]
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        wpx = draw.textlength(test, font=font)
        if wpx <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def _luminance(rgb):
    r,g,b = [c/255.0 for c in rgb[:3]]
    for v in (r,g,b):
        pass
    def srgb_to_lin(v):
        return v/12.92 if v <= 0.04045 else ((v+0.055)/1.055)**2.4
    r,g,b = srgb_to_lin(r), srgb_to_lin(g), srgb_to_lin(b)
    return 0.2126*r + 0.7152*g + 0.0722*b

def _best_text_color(bg_rgb):
    # Choose white or black depending on contrast.
    lum = _luminance(bg_rgb)
    # Contrast vs white(1.0) and black(0.0)
    cw = (1.05) / max(lum, 1e-6)
    cb = (lum + 0.05) / 0.05
    return (255,255,255) if cw >= cb else (0,0,0)

def _dominant_color(img):
    # Resize small, quantize to 8-bit palette, pick most common
    small = img.resize((64, 64)).convert("RGB")
    pal = small.quantize(colors=8, method=2)
    counts = pal.getcolors()
    if not counts:
        return (30, 30, 30)
    counts.sort(reverse=True, key=lambda x: x[0])
    idx = counts[0][1]
    return pal.palette.getcolor(idx)

def _download(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        fd, p = tempfile.mkstemp(suffix=".img")
        with os.fdopen(fd, "wb") as f:
            f.write(r.content)
        return p
    except Exception:
        return None

def generate_cover(title: str, *, tag: str = "HIGHLIGHT", subtitle: str = "", bg_url: str = None, out_dir: str = "./covers") -> str:
    os.makedirs(out_dir, exist_ok=True)
    bg_path = None
    if bg_url and bg_url.startswith(("http://","https://")):
        bg_path = _download(bg_url)
    elif bg_url and os.path.exists(bg_url):
        bg_path = bg_url

    # Base image
    if bg_path:
        try:
            img = Image.open(bg_path).convert("RGB")
            img = img.resize((WIDTH, HEIGHT))
            # heavy blur for stylish background
            img = img.filter(ImageFilter.GaussianBlur(radius=18))
        except Exception:
            img = Image.new("RGB", (WIDTH, HEIGHT), (18, 20, 26))
    else:
        img = Image.new("RGB", (WIDTH, HEIGHT), (18, 20, 26))

    draw = ImageDraw.Draw(img)

    # Gradient overlay (top-to-bottom)
    grad = Image.new("L", (1, HEIGHT), color=0)
    for y in range(HEIGHT):
        # darker at bottom
        grad.putpixel((0, y), int(180 * (y/HEIGHT)))
    grad = grad.resize((WIDTH, HEIGHT))
    img = Image.composite(Image.new("RGB", (WIDTH, HEIGHT), (0,0,0)), img, grad)
    draw = ImageDraw.Draw(img)

    # Dominant color for accents
    try:
        dc = _dominant_color(img)
    except Exception:
        dc = (255, 80, 0)
    text_color = _best_text_color(dc)

    # Tag badge (rounded rect)
    badge_text = (tag or "").upper()[:18]
    bfont = _load_font(32)
    bw = draw.textlength(badge_text, font=bfont)
    bh = bfont.getbbox("Ay")[3] - bfont.getbbox("Ay")[1]
    padx, pady = 24, 10
    bx, by = 48, 48
    rect = [bx, by, bx + bw + 2*padx, by + bh + 2*pady]
    draw.rounded_rectangle(rect, radius=14, fill=dc)
    draw.text((bx + padx, by + pady - 2), badge_text, font=bfont, fill=text_color)

    # Title
    tfont = _load_font(68)
    maxw = int(WIDTH * 0.86)
    lines = _wrap(draw, title or "NXT Esports", tfont, maxw)
    while (len(lines) > 3 or max(draw.textlength(ln, font=tfont) for ln in lines) > maxw) and getattr(tfont, "size", 68) > 34:
        tfont = _load_font(getattr(tfont, "size", 68)-4)
        lines = _wrap(draw, title or "NXT Esports", tfont, maxw)

    y = by + bh + 2*pady + 28
    for ln in lines:
        w = draw.textlength(ln, font=tfont)
        x = (WIDTH - w)//2
        # stroke
        draw.text((x+2, y+2), ln, font=tfont, fill=(0,0,0))
        draw.text((x, y), ln, font=tfont, fill=(255,255,255))
        y += (tfont.getbbox("Ay")[3]-tfont.getbbox("Ay")[1]) + 6

    # Subtitle + footer
    s = subtitle or "CS2 / Dota 2"
    sfont = _load_font(28)
    sw = draw.textlength(s, font=sfont)
    draw.text((WIDTH - sw - 36, HEIGHT - 40 - (sfont.getbbox("Ay")[3]-sfont.getbbox("Ay")[1])), s, font=sfont, fill=(210,210,210))

    footer = "t.me/NXT_Esports"
    ffont = _load_font(24)
    fw = draw.textlength(footer, font=ffont)
    draw.text((36, HEIGHT - 40 - (ffont.getbbox("Ay")[3]-ffont.getbbox("Ay")[1])), footer, font=ffont, fill=(200,200,200))

    out_dir = out_dir or "./covers"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"cover_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}.png")
    img.save(out_path, "PNG")
    return out_path
