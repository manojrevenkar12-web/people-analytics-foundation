"""Screenshots of the built console. Serve it first: python -m http.server 4176 -d web/dist"""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
URL = "http://127.0.0.1:4176/"
SHOTS = [
    ("console", (1440, 900), "light", True, 1),
    ("console-dark", (1440, 900), "dark", False, 2),
    ("console-phone", (390, 844), "light", False, 2),
]


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-proxy-server"])
        for name, (w, h), theme, full, scale in SHOTS:
            ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=scale, color_scheme=theme)
            page = await ctx.new_page()
            await page.goto(URL)
            await page.wait_for_selector("figure")
            await page.wait_for_timeout(3000)  # let the decode replay finish
            await page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
            await ctx.close()
        ctx = await b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page = await ctx.new_page()
        await page.goto(URL)
        await page.wait_for_timeout(3000)
        el = await page.query_selector("section[aria-labelledby=pilots]")
        if el:
            await el.screenshot(path=str(OUT / "pilots.png"))
        await b.close()


asyncio.run(main())
