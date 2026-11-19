"""Deterministic three-mode harness: normal, web fullscreen, element fullscreen.

The real live page currently only exposes a native fullscreen control; this
harness verifies the userscript's mode-independent behavior (fixed body button,
CSS hiding, and re-parenting when the fullscreen element is not <body>).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "douyin-live-gift-toggle.user.js"
PAGE = ROOT / "test" / "modes.html"
OUT = ROOT / "test" / "evidence"
CHROME = os.environ.get(
    "DY_CHROME",
    str(Path(os.environ["LOCALAPPDATA"]) / "ms-playwright" / "chromium-1255" / "chrome-win64" / "chrome.exe"),
)

checks: list[dict] = []


def check(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + (f" :: {detail}" if detail is not None else ""))
    if not ok:
        raise AssertionError(name)


def snap(page):
    return page.evaluate(
        """() => {
          const bar=document.querySelector('#BottomLayout');
          const btn=document.querySelector('#dygt-gift-toggle');
          const br=btn.getBoundingClientRect();
          const fs=document.fullscreenElement;
          return {
            flag:document.documentElement.getAttribute('data-dygt-gifts'),
            bar:bar?{display:getComputedStyle(bar).display, h:bar.getBoundingClientRect().height}:null,
            button:btn?{text:btn.innerText.trim(), parent:btn.parentElement.id||btn.parentElement.tagName, visible:getComputedStyle(btn).display!=='none'&&br.width>0&&br.height>0, rect:[br.x,br.y,br.width,br.height].map(Math.round)}:null,
            fullscreen:fs?{tag:fs.tagName,id:fs.id}:null,
            bodyClass:document.body.className,
          };
        }"""
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 1000}, locale="zh-CN")
        ctx.add_init_script(path=str(SCRIPT))
        page = ctx.new_page()
        page.goto(PAGE.as_uri(), wait_until="load", timeout=30_000)
        page.wait_for_selector("#dygt-gift-toggle", state="visible", timeout=10_000)
        page.wait_for_timeout(300)

        s = snap(page)
        check("普通观看：按钮可见且礼物栏显示", s["button"]["visible"] and s["bar"]["display"] != "none" and s["bar"]["h"] > 20, s)
        page.screenshot(path=str(OUT / "10-synthetic-normal.png"))

        page.click("#dygt-gift-toggle")
        page.wait_for_timeout(200)
        s = snap(page)
        check("普通观看：点击后礼物栏隐藏", s["flag"] == "off" and s["bar"]["display"] == "none", s)

        page.click("#web-toggle")
        page.wait_for_timeout(300)
        s = snap(page)
        check("网页全屏：布局切换后按钮仍可见", "web-fullscreen" in s["bodyClass"] and s["button"]["visible"], s)
        check("网页全屏：隐藏状态继续生效", s["flag"] == "off" and s["bar"]["display"] == "none", s)
        page.screenshot(path=str(OUT / "11-synthetic-web-fullscreen.png"))

        # 再退回普通（模拟抖音自己的“退出网页全屏”），并显示礼物栏，准备进入原生全屏。
        page.evaluate("() => document.body.classList.remove('web-fullscreen')")
        page.click("#dygt-gift-toggle")
        page.wait_for_timeout(300)
        s = snap(page)
        check("退出网页全屏：礼物栏恢复", s["flag"] == "on" and s["bar"]["display"] != "none" and s["bar"]["h"] > 20, s)

        # 元素级原生全屏：按钮应被重新挂到全屏元素内部。
        page.click("#native-toggle")
        page.wait_for_timeout(700)
        s = snap(page)
        check("原生全屏：全屏元素为播放器容器", s["fullscreen"] and s["fullscreen"]["id"] == "LeftBackgroundLayout", s)
        check("原生全屏：按钮已挂到全屏元素内", s["button"]["parent"] == "LeftBackgroundLayout", s)
        check("原生全屏：按钮仍可见", s["button"]["visible"], s)
        page.screenshot(path=str(OUT / "12-synthetic-element-fullscreen.png"))

        page.click("#dygt-gift-toggle")
        page.wait_for_timeout(300)
        s = snap(page)
        check("原生全屏：切换后礼物栏隐藏", s["flag"] == "off" and s["bar"]["display"] == "none", s)
        page.screenshot(path=str(OUT / "13-synthetic-element-fullscreen-hidden.png"))

        if s["fullscreen"]:
            page.evaluate("() => document.exitFullscreen()")
            page.wait_for_timeout(500)
        s = snap(page)
        check("退出原生全屏：按钮回到 body", s["fullscreen"] is None and s["button"]["parent"] == "BODY", s)

        browser.close()

    result = {"passed": len(checks), "failed": 0, "checks": checks}
    (OUT / "synthetic-report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(checks)} passed, 0 failed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("TEST ERROR:", exc)
        (OUT / "synthetic-report.json").write_text(json.dumps({"error": str(exc), "checks": checks}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
