"""Optional local vision-LLM probe via Ollama or LM Studio (OpenAI-compatible).

Useful for qualitative triage: count visible circles, note tramlines vs formation,
describe complexity, flag watermarks. NOT a substitute for biophysical lab work.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
from pathlib import Path

import requests

DEFAULT_PROMPT = """You are assisting a crop-circle geometry research lab.
Describe this aerial photo briefly and factually:
1) Approximate number of distinct flattened circles/arcs visible
2) Overall motif (spiral, fractal, helix, pictogram, simple circles, 3D cube, etc.)
3) Presence of tractor tramlines and whether the formation respects/crosses them
4) Photo quality issues (watermarks, low res, oblique angle, shadows)
5) Anything that looks unusually precise or unusually crude
Keep it under 200 words. Do not claim aliens or hoaxes — observe only."""


def _b64_image(path: Path) -> tuple[str, str]:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return mime, data


def ask_ollama(path: Path, model: str, host: str = "http://localhost:11434", prompt: str = DEFAULT_PROMPT) -> dict:
    mime, data = _b64_image(path)
    url = f"{host.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [data],
            }
        ],
    }
    # Newer Ollama vision models prefer images as base64 in message; some want /api/generate
    r = requests.post(url, json=payload, timeout=300)
    if r.status_code >= 400:
        # Fallback to generate endpoint
        payload2 = {
            "model": model,
            "prompt": prompt,
            "images": [data],
            "stream": False,
        }
        r = requests.post(f"{host.rstrip('/')}/api/generate", json=payload2, timeout=300)
        r.raise_for_status()
        body = r.json()
        return {"backend": "ollama", "model": model, "response": body.get("response", body)}
    r.raise_for_status()
    body = r.json()
    msg = body.get("message", {})
    return {"backend": "ollama", "model": model, "response": msg.get("content", body)}


def ask_lmstudio(path: Path, model: str, host: str = "http://localhost:1234", prompt: str = DEFAULT_PROMPT) -> dict:
    mime, data = _b64_image(path)
    url = f"{host.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
                ],
            }
        ],
        "temperature": 0.2,
    }
    r = requests.post(url, json=payload, timeout=300)
    r.raise_for_status()
    body = r.json()
    content = body["choices"][0]["message"]["content"]
    return {"backend": "lmstudio", "model": model, "response": content}


def main() -> None:
    ap = argparse.ArgumentParser(description="Local vision model probe for crop-circle photos")
    ap.add_argument("image")
    ap.add_argument("--backend", choices=["ollama", "lmstudio"], default="ollama")
    ap.add_argument("--model", default="llava")
    ap.add_argument("--host", default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    path = Path(args.image)
    if args.backend == "ollama":
        host = args.host or "http://localhost:11434"
        result = ask_ollama(path, model=args.model, host=host)
    else:
        host = args.host or "http://localhost:1234"
        result = ask_lmstudio(path, model=args.model, host=host)
    result["path"] = str(path)
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)


if __name__ == "__main__":
    main()
