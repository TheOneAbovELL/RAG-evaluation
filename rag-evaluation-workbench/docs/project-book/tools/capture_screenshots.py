"""Capture full-page screenshots of the running Streamlit app for the project book.

Requires the app to be running locally (``uv run streamlit run streamlit_app.py``) and Google Chrome or
Microsoft Edge. Uses the Chrome DevTools Protocol directly (the ``websockets`` package is already a
Streamlit dependency), waits until Streamlit reports that the script has finished and no loading
skeletons remain, then captures the whole page in light mode.

    uv run python scripts/seed_demo_runs.py --pages docs/project-book/tools/screenshot_pages.json
    uv run python docs/project-book/tools/capture_screenshots.py \n        --pages docs/project-book/tools/screenshot_pages.json --out docs/project-book/screenshots

Only http://localhost URLs are visited.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets

BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "google-chrome", "chromium", "msedge",
]
VIEWPORT_HEIGHT = 2800
READY_JS = """
(() => {
  const app = document.querySelector('[data-testid="stApp"]');
  if (!app) return false;
  if (document.querySelector('[data-testid="stSkeleton"]')) return false;
  const status = document.querySelector('[data-testid="stStatusWidget"]');
  if (status && /running/i.test(status.innerText)) return false;
  if (document.querySelectorAll('[data-testid="stMarkdownContainer"]').length === 0) return false;
  // A fingerprint of the rendered page; capture only once it has stopped changing.
  return document.body.innerText.length + ':' + document.querySelectorAll('*').length;
})()
"""
STABLE_SECONDS = 3.0


def find_browser() -> str:
    for candidate in BROWSERS:
        if Path(candidate).is_file() or shutil.which(candidate):
            return candidate
    raise SystemExit("Chrome or Edge not found")


class CDP:
    def __init__(self, ws):
        self.ws, self.next_id = ws, 0

    async def call(self, method: str, **params):
        self.next_id += 1
        my_id = self.next_id
        await self.ws.send(json.dumps({"id": my_id, "method": method, "params": params}))
        while True:
            message = json.loads(await self.ws.recv())
            if message.get("id") == my_id:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})


async def capture(pages: list[tuple[str, str]], base: str, out_dir: Path, port: int, width: int) -> None:
    targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
    page = next(t for t in targets if t["type"] == "page")
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=50_000_000) as ws:
        cdp = CDP(ws)
        await cdp.call("Page.enable")
        await cdp.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "light"}])
        # One tall, fixed viewport for every page: resizing between pages re-triggers the sidebar animation.
        await cdp.call("Emulation.setDeviceMetricsOverride", width=width, height=VIEWPORT_HEIGHT, deviceScaleFactor=1,
                       mobile=False)
        for name, path in pages:
            assert path.startswith("/"), path
            await cdp.call("Page.navigate", url=base + path)
            deadline = time.time() + 60
            ready_since, last = None, None
            while time.time() < deadline:
                await asyncio.sleep(0.5)
                result = await cdp.call("Runtime.evaluate", expression=READY_JS, returnByValue=True)
                value = result.get("result", {}).get("value")
                if value and value == last:
                    ready_since = ready_since or time.time()
                    if time.time() - ready_since >= STABLE_SECONDS:
                        break
                else:
                    ready_since = None
                last = value
            else:
                print(f"warning: {name} did not stabilise within 60 s")
            shot = await cdp.call("Page.captureScreenshot", format="png")
            target = out_dir / f"{name}.png"
            target.write_bytes(base64.b64decode(shot["data"]))
            size = trim_bottom(target)
            print(f"{name}: {target.stat().st_size:,} bytes, {size[0]}x{size[1]}")


def trim_bottom(path: Path, margin: int = 40) -> tuple[int, int]:
    """Crop the empty area below the last content row (the viewport is deliberately taller than the page)."""
    from PIL import Image, ImageChops

    with Image.open(path) as img:
        rgb = img.convert("RGB")
        # Ignore the sidebar (left 300 px), whose background runs the full height.
        main = rgb.crop((300, 0, rgb.width, rgb.height))
        background = Image.new("RGB", main.size, main.getpixel((main.width - 5, main.height - 5)))
        box = ImageChops.difference(main, background).getbbox()
        bottom = min(rgb.height, (box[3] if box else rgb.height) + margin)
        rgb.crop((0, 0, rgb.width, bottom)).save(path, optimize=True)
        return rgb.width, bottom


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=Path, required=True, help="JSON list of [name, path] pairs")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base", default="http://localhost:8501")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--port", type=int, default=9333)
    args = parser.parse_args()
    if not args.base.startswith(("http://localhost", "http://127.0.0.1")):
        raise SystemExit("only local URLs are captured")
    pages = json.loads(args.pages.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    profile = tempfile.mkdtemp(prefix="ragwb-shots-")
    proc = subprocess.Popen([find_browser(), "--headless=new", "--disable-gpu", "--no-first-run",
                             "--hide-scrollbars", f"--remote-debugging-port={args.port}", f"--user-data-dir={profile}",
                             "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{args.port}/json/version", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        asyncio.run(capture(pages, args.base, args.out, args.port, args.width))
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    main()
