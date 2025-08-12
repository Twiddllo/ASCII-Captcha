# ASCII CAPTCHA

Config-first **ASCII → image** CAPTCHA generator. Single-file Python + Pillow. Works as a CLI or a library, with deterministic seeding for tests/CI.

- Single-file, developer-friendly (simple to customize)
- Fully `config.json` driven (fonts, noise, palette, seed, output)
- Importable API + CLI
- Deterministic mode via `random_seed`

---

## Quick start

```bash
pip install Pillow
python captcha.py -c config.json
# (classic still works) python captcha.py -o out.png --print-code
```

---

## Configuration

Everything lives in `config.json`. Drop this next to `captcha.py`:

```json
{
  "output": "out/captcha.png",
  "print_code": true,
  "data_url_output": "out/captcha_data_url.txt",

  "code_length": 6,
  "random_seed": 12345,
  "fixed_code": null,

  "ascii_chars": "$@B%8&WM# ",

  "text_to_ascii": {
    "font_path": null,
    "font_size": 40,
    "scale": 2
  },

  "render": {
    "font_path": null,
    "font_size": 9,
    "spacing": 1,
    "noise_lines": 24,
    "blur_shapes": 40,
    "apply_blur": true,
    "extra_noise_shapes": 30,
    "pixel_noise_density": 0.04,
    "jitter": 1,
    "gaussian_blur_radius": 1.1,
    "shape_blur_radius": 2.0
  }
}
```

**Notes (plain English):**
- `random_seed` → lock output for tests (remove in prod)
- `fixed_code` → force a known CAPTCHA (debug only)
- `ascii_chars` → **DARK → LIGHT** mapping
- `render.font_size` → **DO NOT USE MORE THAN ~20** or readability drops
- More noise = harder for bots (and heavier)

---

## Use in Python

```python
from captcha import generate_image, to_data_url

img, code = generate_image(length=6, seed=42)
img.save("captcha.png")
print("solution:", code)

# handy for <img src="...">
data_url = to_data_url(img)
```

### FastAPI demo

```python
import io
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from captcha import generate_image

app = FastAPI()
store = {}  # replace with Redis/DB in production

@app.get("/captcha.png")
def new_captcha():
    img, code = generate_image(length=6)
    store["demo"] = code  # bind to session/request id in real apps
    buf = io.BytesIO()
    img.save(buf, format="PNG"); buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

@app.post("/verify")
def verify(code: str):
    if not store.get("demo"):
        raise HTTPException(400, "No captcha in store")
    ok = code.strip().upper() == store["demo"].upper()
    store.pop("demo", None)  # one-time use
    return {"ok": ok}
```

---

## Tips

- Prefer a **monospace** `font_path`; keep `render.spacing = 1`
- If the image is too messy: lower `pixel_noise_density` / `blur_shapes`
- If too clean: increase `noise_lines` / `extra_noise_shapes`
- Pair with rate limiting + session binding + short expiry

---

## License & Contributing

MIT.
