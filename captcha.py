"""
Minimal ASCII CAPTCHA generator (single-file).
Usage (CLI):
  python captcha.py -c config.json  # now we read everything from config.json, easier life
"""
from __future__ import annotations

import io
import json
import random
import string
from dataclasses import dataclass, field
from typing import Iterable, Optional, Dict, Any, Tuple
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import base64

ASCII_CHARS = "$@B%8&WM# "  # dark -> light  (still here as a sane default; config can override)

# --- tiny config helpers (keep it simple, keep it readable) ---

@dataclass
class TextToAsciiParams:
    font_path: Optional[str] = None
    font_size: int = 40
    scale: int = 2  # downscale before mapping to ASCII, looks better

@dataclass
class RenderParams:
    font_path: Optional[str] = None
    font_size: int = 9 # dont use mroe then 20 
    spacing: int = 1 # better to not change
    noise_lines: int = 24 # more = better
    blur_shapes: int = 40
    apply_blur: bool = True 
    extra_noise_shapes: int = 30
    pixel_noise_density: float = 0.04
    jitter: int = 1
    gaussian_blur_radius: float = 1.1
    shape_blur_radius: float = 2.0

@dataclass
class AppConfig:
    output: str = "captcha.png"
    print_code: bool = False
    data_url_output: Optional[str] = None  # if you want the data url in a file too

    # code generation stuff
    code_length: int = 6
    random_seed: Optional[int] = None
    fixed_code: Optional[str] = None
    
    # ASCII PALETTE (YOU CAN CHANGE IT) — USE BIG CHARACTERS FOR MORE READABLE — DARK -> LIGHT
    ascii_chars: str = "$@B%8&WM# "

    # sub-pieces
    text_to_ascii: TextToAsciiParams = field(default_factory=TextToAsciiParams)
    render: RenderParams = field(default_factory=RenderParams)

def _deep_update(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_update(out[k], v)
        else:
            out[k] = v
    return out

def load_config(path: Path) -> AppConfig:
    # defaults here so config can be short if you want
    defaults: Dict[str, Any] = {
        "output": "captcha.png",
        "print_code": False,
        "data_url_output": None,
        "code_length": 6,
        "random_seed": None,
        "fixed_code": None,
        "ascii_chars": "$@B%8&WM# ",
        "text_to_ascii": {
            "font_path": None,
            "font_size": 40,
            "scale": 2
        },
        "render": {
            "font_path": None,
            "font_size": 9, # dont use mroe then 20 
            "spacing": 1, # better to not change
            "noise_lines": 24, # more = better
            "blur_shapes": 40,
            "apply_blur": True,
            "extra_noise_shapes": 30,
            "pixel_noise_density": 0.04,
            "jitter": 1,
            "gaussian_blur_radius": 1.1,
            "shape_blur_radius": 2.0
        }
    }

    with path.open("r", encoding="utf-8") as f:
        user = json.load(f)

    merged = _deep_update(defaults, user)

    # build dataclasses (not fancy, just straight)
    tta = merged.get("text_to_ascii", {})
    rp = merged.get("render", {})
    return AppConfig(
        output=merged["output"],
        print_code=merged["print_code"],
        data_url_output=merged.get("data_url_output"),
        code_length=int(merged["code_length"]),
        random_seed=merged.get("random_seed"),
        fixed_code=merged.get("fixed_code"),
        ascii_chars=merged["ascii_chars"],
        text_to_ascii=TextToAsciiParams(
            font_path=tta.get("font_path"),
            font_size=int(tta.get("font_size", 40)),
            scale=int(tta.get("scale", 2))
        ),
        render=RenderParams(
            font_path=rp.get("font_path"),
            font_size=int(rp.get("font_size", 9)), # dont use mroe then 20 
            spacing=int(rp.get("spacing", 1)), # better to not change
            noise_lines=int(rp.get("noise_lines", 24)), # more = better
            blur_shapes=int(rp.get("blur_shapes", 40)),
            apply_blur=bool(rp.get("apply_blur", True)),
            extra_noise_shapes=int(rp.get("extra_noise_shapes", 30)),
            pixel_noise_density=float(rp.get("pixel_noise_density", 0.04)),
            jitter=int(rp.get("jitter", 1)),
            gaussian_blur_radius=float(rp.get("gaussian_blur_radius", 1.1)),
            shape_blur_radius=float(rp.get("shape_blur_radius", 2.0))
        )
    )

def generate_code(length: int = 6, *, rng: Optional[random.Random] = None) -> str:
    rng = rng or random
    alphabet = string.ascii_uppercase + string.digits
    return "".join(rng.choices(alphabet, k=length))

def _load_font(preferred: Optional[str], size: int):
    candidates = [preferred] if preferred else []
    candidates += [
        "consola.ttf",
        "DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "Menlo.ttf",
        "Courier New.ttf",
    ]
    for path in candidates:
        if not path:
            continue
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()

def _text_to_ascii_lines(text: str, font_path: Optional[str] = None, font_size: int = 40, scale: int = 2, ascii_chars: str = ASCII_CHARS):
    if not text:
        return []
    font = _load_font(font_path, font_size)
    blocks = []
    for ch in text.replace(" ", ""):
        img = Image.new("L", (font_size * 2, font_size * 2), color=255)
        ImageDraw.Draw(img).text((10, 10), ch, font=font, fill=0)
        img = img.resize((max(1, img.width // scale), max(1, img.height // scale)))
        pixels = img.getdata()
        ascii_str = "".join(ascii_chars[p * (len(ascii_chars) - 1) // 255] for p in pixels)
        lines = [ascii_str[i : i + img.width] for i in range(0, len(ascii_str), img.width)]
        blocks.append(lines)
    combined = []
    for r in range(len(blocks[0])):
        combined.append("   ".join(b[r] for b in blocks))
    return combined

def make_image(ascii_lines: Iterable[str], params: RenderParams = RenderParams(), *, rng: Optional[random.Random] = None):
    rng = rng or random
    ascii_lines = list(ascii_lines)
    if not ascii_lines:
        return Image.new("RGB", (2, 2), "white")

    char_w = params.font_size // 2 + params.spacing
    char_h = params.font_size + 2
    width = char_w * max(len(line) for line in ascii_lines)
    height = char_h * len(ascii_lines)

    base = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(base)
    font = _load_font(params.font_path, params.font_size)

    # ASCII text with tiny jitter
    for r, line in enumerate(ascii_lines):
        for c, ch in enumerate(line):
            x = c * char_w + rng.randint(-params.jitter, params.jitter)
            y = r * char_h + rng.randint(-params.jitter, params.jitter)
            draw.text((x, y), ch, font=font, fill=(0, 0, 0, 255))

    # random gray lines (it will make captcha harder to solve by bots)
    for _ in range(params.noise_lines):
        x1, y1 = rng.randint(0, width), rng.randint(0, height)
        x2, y2 = rng.randint(0, width), rng.randint(0, height)
        g = rng.randint(100, 180)
        t = rng.randint(1, 2)
        draw.line([(x1, y1), (x2, y2)], fill=(g, g, g, 255), width=t)

    # transparent blurry shapes (it will make captcha harder to solve by bots)
    shape = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    sdraw = ImageDraw.Draw(shape)
    for _ in range(params.blur_shapes):
        x1, y1 = rng.randint(0, max(0, width - 30)), rng.randint(0, max(0, height - 30))
        x2, y2 = x1 + rng.randint(15, 50), y1 + rng.randint(15, 50)
        g = rng.randint(90, 160); a = rng.randint(60, 120)
        if rng.random() < 0.5:
            sdraw.ellipse([x1, y1, x2, y2], fill=(g, g, g, a))
        else:
            sdraw.rectangle([x1, y1, x2, y2], fill=(g, g, g, a))

    for _ in range(params.extra_noise_shapes):
        x1, y1 = rng.randint(0, max(0, width - 50)), rng.randint(0, max(0, height - 50))
        x2, y2 = x1 + rng.randint(10, 50), y1 + rng.randint(10, 50)
        g = rng.randint(60, 180); a = rng.randint(40, 100)
        choice = rng.choice(["arc", "chord", "triangle", "circle"])
        if choice == "arc":
            s, e = rng.randint(0, 360), rng.randint(0, 360)
            sdraw.arc([x1, y1, x2, y2], start=s, end=e, fill=(g, g, g))
        elif choice == "chord":
            s, e = rng.randint(0, 360), rng.randint(0, 360)
            sdraw.chord([x1, y1, x2, y2], s, e, fill=(g, g, g, a))
        elif choice == "triangle":
            pts = [(x1, y1), (x2, y1), ((x1 + x2) // 2, y2)]
            sdraw.polygon(pts, fill=(g, g, g, a))
        else:
            r = (x2 - x1) // 2
            sdraw.ellipse([x1, y1, x1 + r * 2, y1 + r * 2], fill=(g, g, g, a))

    if params.shape_blur_radius > 0:
        shape = shape.filter(ImageFilter.GaussianBlur(radius=params.shape_blur_radius))
    base = Image.alpha_composite(base, shape)

    # pixel noise (it will make captcha much more harder to solve by bots)
    pixels = base.load()
    total = width * height
    for _ in range(int(total * params.pixel_noise_density)):
        x, y = rng.randint(0, width - 1), rng.randint(0, height - 1)
        v = rng.randint(0, 255)
        pixels[x, y] = (v, v, v, 255)

    if params.apply_blur and params.gaussian_blur_radius > 0:
        base = base.filter(ImageFilter.GaussianBlur(radius=params.gaussian_blur_radius))

    return base.convert("RGB")

def generate_image(text: Optional[str] = None, *, length: int = 6, seed: Optional[int] = None, font_path: Optional[str] = None) -> Tuple[Image.Image, str]:
    # keeping the old API for compatibility (yea legacy callers), but we will actually drive from cfg in main
    rng = random.Random(seed) if seed is not None else random
    code = text or generate_code(length, rng=rng)
    ascii_lines = _text_to_ascii_lines(code, font_path=font_path, font_size=40)
    img = make_image(ascii_lines, rng=rng)
    return img, code

def generate_image_from_cfg(cfg: AppConfig) -> Tuple[Image.Image, str]:
    # single source of truth now (config-first)
    rng = random.Random(cfg.random_seed) if cfg.random_seed is not None else random
    code = (cfg.fixed_code or generate_code(cfg.code_length, rng=rng))
    ascii_lines = _text_to_ascii_lines(
        code,
        font_path=cfg.text_to_ascii.font_path,
        font_size=cfg.text_to_ascii.font_size,
        scale=cfg.text_to_ascii.scale,
        ascii_chars=cfg.ascii_chars
    )
    img = make_image(ascii_lines, params=cfg.render, rng=rng)
    return img, code

def to_data_url(img: Image.Image) -> str:
    """Return a data:image/png;base64,... string."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Minimal ASCII CAPTCHA generator (config-driven)")
    p.add_argument("-c", "--config", default="config.json", help="Path to config.json")
    args = p.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")

    cfg = load_config(cfg_path)

    # set global palette too (leave it here so old funcs still use it)
    ASCII_CHARS = cfg.ascii_chars  # dark -> light (yes still true)

    # generate using config (the new way)
    img, code = generate_image_from_cfg(cfg)

    Path(cfg.output).parent.mkdir(parents=True, exist_ok=True)
    img.save(cfg.output)

    if cfg.print_code:
        print(code)
    else:
        print(f"Saved {cfg.output}")

    if cfg.data_url_output:
        Path(cfg.data_url_output).write_text(to_data_url(img), encoding="utf-8")
