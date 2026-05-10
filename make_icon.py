"""Generates assets/logo.ico matching the Externo Browser shield logo."""
import os
import math
from PIL import Image, ImageDraw, ImageFont

SIZES = [256, 128, 64, 48, 32, 16]

def make_frame(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size
    pad = s * 0.04

    # ── Shield path (polygon approximation) ───────────────────────────────────
    cx = s / 2
    # Shield points: wide top, taper to point at bottom
    top_y    = pad
    top_lx   = pad
    top_rx   = s - pad
    mid_y    = s * 0.62
    mid_lx   = pad * 0.5
    mid_rx   = s - pad * 0.5
    bot_y    = s - pad
    shield = [
        (top_lx, top_y),          # top-left
        (top_rx, top_y),          # top-right
        (mid_rx, mid_y),          # mid-right
        (cx, bot_y),              # bottom tip
        (mid_lx, mid_y),          # mid-left
    ]

    # Dark outline
    outline_pad = s * 0.03
    outline = [
        (top_lx - outline_pad, top_y - outline_pad),
        (top_rx + outline_pad, top_y - outline_pad),
        (mid_rx + outline_pad, mid_y + outline_pad * 0.5),
        (cx, bot_y + outline_pad * 1.5),
        (mid_lx - outline_pad, mid_y + outline_pad * 0.5),
    ]
    d.polygon(outline, fill=(10, 20, 35, 255))

    # Gradient fill: draw horizontal strips from cyan-blue (top) to green (bottom)
    mask = Image.new("L", (s, s), 0)
    md = ImageDraw.Draw(mask)
    md.polygon(shield, fill=255)

    gradient = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gradient)
    for y in range(s):
        t = y / s
        # cyan-blue (#00c8e8) → green (#00e676)
        r = int(0   * (1 - t) + 0   * t)
        g = int(200 * (1 - t) + 230 * t)
        b = int(232 * (1 - t) + 118 * t)
        gd.line([(0, y), (s, y)], fill=(r, g, b, 255))

    gradient.putalpha(mask)
    img.paste(gradient, mask=mask)

    # Inner shield highlight (lighter left half)
    hi_shield = [
        (top_lx + s*0.06, top_y + s*0.06),
        (cx - s*0.03,     top_y + s*0.06),
        (cx - s*0.03,     mid_y - s*0.04),
        (mid_lx + s*0.06, mid_y - s*0.04),
    ]
    hi_mask = Image.new("L", (s, s), 0)
    hd = ImageDraw.Draw(hi_mask)
    hd.polygon(hi_shield, fill=60)
    hi_layer = Image.new("RGBA", (s, s), (255, 255, 255, 0))
    hi_layer.putalpha(hi_mask)
    img = Image.alpha_composite(img, hi_layer)
    d = ImageDraw.Draw(img)

    # ── Swoosh ring (ellipse arc, green/yellow) ────────────────────────────────
    sw = s * 0.82
    sh = s * 0.28
    sx = (s - sw) / 2
    sy = s * 0.44
    lw = max(2, int(s * 0.045))
    # Back arc (darker)
    d.arc([sx, sy, sx + sw, sy + sh], start=200, end=340,
          fill=(20, 160, 60, 180), width=lw)
    # Front arc (bright lime-green)
    d.arc([sx, sy, sx + sw, sy + sh], start=340, end=200,
          fill=(140, 220, 0, 240), width=lw + 1)

    # ── "E" letter ────────────────────────────────────────────────────────────
    font_size = max(8, int(s * 0.42))
    try:
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    # Shadow
    d.text((cx + s*0.03, s*0.22 + s*0.03), "E", font=font,
           fill=(0, 30, 20, 120), anchor="mt")
    # Main E — white
    d.text((cx, s * 0.22), "E", font=font,
           fill=(255, 255, 255, 255), anchor="mt")

    # ── Star sparkle top-right ─────────────────────────────────────────────────
    sp = s * 0.78
    sp_y = s * 0.10
    sr = max(1, int(s * 0.04))
    d.ellipse([sp - sr, sp_y - sr, sp + sr, sp_y + sr],
              fill=(220, 245, 255, 220))
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        ex = sp + math.cos(rad) * sr * 2.5
        ey = sp_y + math.sin(rad) * sr * 2.5
        d.line([sp, sp_y, ex, ey], fill=(200, 240, 255, 160), width=max(1, sr // 2))

    return img


assets_dir = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(assets_dir, exist_ok=True)

frames = [make_frame(s).resize((s, s), Image.LANCZOS) for s in SIZES]

ico_path = os.path.join(assets_dir, "logo.ico")
png_path = os.path.join(assets_dir, "logo.png")

frames[0].save(ico_path, format="ICO", sizes=[(s, s) for s in SIZES],
               append_images=frames[1:])
frames[0].save(png_path, format="PNG")

print(f"Saved {ico_path}")
print(f"Saved {png_path}")
