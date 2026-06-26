from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BRANDING_DIR = ROOT / "assets" / "branding"
ANDROID_RES_DIR = ROOT / "android-app" / "app" / "src" / "main" / "res"

BACKGROUND = "#07131f"
STROKE = "#1f4866"
GLOW = "#31d9ff"
ACCENT = "#79f7ff"
TEXT = "#daf8ff"


def main() -> None:
    """Generate the shared EchoText icon assets."""

    BRANDING_DIR.mkdir(parents=True, exist_ok=True)
    _write_svg(BRANDING_DIR / "echotext-icon.svg")

    primary_icon = _render_icon(1024)
    primary_icon.save(BRANDING_DIR / "echotext-icon-1024.png")
    primary_icon.resize((256, 256), Image.Resampling.LANCZOS).save(BRANDING_DIR / "echotext-icon-256.png")
    _write_ico(primary_icon, BRANDING_DIR / "EchoText.ico")

    _write_android_assets(primary_icon)


def _render_icon(size: int) -> Image.Image:
    scale = 4
    canvas_size = size * scale
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    radius = int(canvas_size * 0.23)
    margin = int(canvas_size * 0.08)
    draw.rounded_rectangle(
        (margin, margin, canvas_size - margin, canvas_size - margin),
        radius=radius,
        fill=BACKGROUND,
        outline=STROKE,
        width=max(8, canvas_size // 128),
    )
    inset = int(canvas_size * 0.09)
    draw.rounded_rectangle(
        (inset, inset, canvas_size - inset, canvas_size - inset),
        radius=int(radius * 0.85),
        outline=(73, 183, 216, 90),
        width=max(6, canvas_size // 192),
    )
    _draw_echo_motif(draw, canvas_size)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def _draw_echo_motif(draw: ImageDraw.ImageDraw, size: int) -> None:
    center_x = size * 0.5
    center_y = size * 0.31
    widths = [0.16, 0.24, 0.32]
    stroke_widths = [size * 0.018, size * 0.015, size * 0.012]
    colors = [ACCENT, GLOW, (49, 217, 255, 155)]

    for width_fraction, line_width, color in zip(widths, stroke_widths, colors, strict=True):
        radius = size * width_fraction
        box = (
            center_x - radius,
            center_y - radius * 0.75,
            center_x + radius,
            center_y + radius * 0.75,
        )
        draw.arc(box, start=205, end=335, fill=color, width=max(4, int(line_width)))

    top_y = size * 0.46
    stem_top = size * 0.48
    stem_bottom = size * 0.68
    stem_half_width = size * 0.028
    cross_half_width = size * 0.12
    line_radius = int(size * 0.016)
    draw.rounded_rectangle(
        (center_x - cross_half_width, top_y, center_x + cross_half_width, top_y + size * 0.038),
        radius=line_radius,
        fill=TEXT,
    )
    draw.rounded_rectangle(
        (center_x - stem_half_width, stem_top, center_x + stem_half_width, stem_bottom),
        radius=line_radius,
        fill=TEXT,
    )
    draw.rounded_rectangle(
        (center_x - size * 0.10, size * 0.73, center_x + size * 0.10, size * 0.77),
        radius=int(size * 0.010),
        fill=GLOW,
    )


def _write_ico(image: Image.Image, path: Path) -> None:
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    image.save(path, sizes=sizes)


def _write_svg(path: Path) -> None:
    svg = f"""<svg width="1024" height="1024" viewBox="0 0 1024 1024" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="82" y="82" width="860" height="860" rx="236" fill="{BACKGROUND}"/>
  <rect x="82" y="82" width="860" height="860" rx="236" stroke="{STROKE}" stroke-width="12"/>
  <rect x="122" y="122" width="780" height="780" rx="202" stroke="#49B7D8" stroke-opacity="0.35" stroke-width="8"/>
  <path d="M 400 378 A 112 84 0 0 1 624 378" stroke="{ACCENT}" stroke-width="20" stroke-linecap="round"/>
  <path d="M 360 337 A 152 114 0 0 1 664 337" stroke="{GLOW}" stroke-width="16" stroke-linecap="round"/>
  <path d="M 320 296 A 192 144 0 0 1 704 296" stroke="{GLOW}" stroke-opacity="0.52" stroke-width="13" stroke-linecap="round"/>
  <rect x="389" y="470" width="246" height="39" rx="16" fill="{TEXT}"/>
  <rect x="483" y="491" width="58" height="210" rx="16" fill="{TEXT}"/>
  <rect x="410" y="747" width="204" height="41" rx="10" fill="{GLOW}"/>
</svg>
"""
    path.write_text(svg, encoding="utf-8")


def _write_android_assets(image: Image.Image) -> None:
    sizes = {
        "mipmap-mdpi": 48,
        "mipmap-hdpi": 72,
        "mipmap-xhdpi": 96,
        "mipmap-xxhdpi": 144,
        "mipmap-xxxhdpi": 192,
    }
    for directory, size in sizes.items():
        output_dir = ANDROID_RES_DIR / directory
        output_dir.mkdir(parents=True, exist_ok=True)
        resized = image.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(output_dir / "ic_launcher.png")
        resized.save(output_dir / "ic_launcher_round.png")

    drawable_dir = ANDROID_RES_DIR / "drawable"
    drawable_dir.mkdir(parents=True, exist_ok=True)
    foreground = _render_foreground(432)
    foreground.save(drawable_dir / "ic_launcher_foreground.png")

    anydpi_dir = ANDROID_RES_DIR / "mipmap-anydpi-v26"
    anydpi_dir.mkdir(parents=True, exist_ok=True)
    for name in ("ic_launcher", "ic_launcher_round"):
        xml = """<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/ic_launcher_background" />
    <foreground android:drawable="@drawable/ic_launcher_foreground" />
</adaptive-icon>
"""
        (anydpi_dir / f"{name}.xml").write_text(xml, encoding="utf-8")

    colors_xml = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="ic_launcher_background">#07131F</color>
    <color name="echo_surface">#10283D</color>
    <color name="echo_surface_alt">#18344D</color>
    <color name="echo_stroke">#275374</color>
    <color name="echo_glow">#31D9FF</color>
    <color name="echo_glow_soft">#15384E</color>
    <color name="echo_text">#ECF8FF</color>
    <color name="echo_text_muted">#A3C0D7</color>
    <color name="echo_status_ok">#79F7FF</color>
    <color name="echo_status_warn">#FFBC6A</color>
</resources>
"""
    values_dir = ANDROID_RES_DIR / "values"
    values_dir.mkdir(parents=True, exist_ok=True)
    (values_dir / "colors.xml").write_text(colors_xml, encoding="utf-8")


def _render_foreground(size: int) -> Image.Image:
    scale = 4
    canvas_size = size * scale
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    _draw_echo_motif(draw, canvas_size)
    return image.resize((size, size), Image.Resampling.LANCZOS)


if __name__ == "__main__":
    main()
