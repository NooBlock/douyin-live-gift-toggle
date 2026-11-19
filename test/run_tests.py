"""End-to-end checks for the userscript against the real Douyin live page.

The browser context is isolated (no user profile, no login, no cookies). Only DOM
inspection and the script's own toggle button are clicked; no gift, recharge,
game or login control is activated.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "douyin-live-gift-toggle.user.js"
OUT = ROOT / "test" / "evidence"
URL = os.environ.get("DY_URL", "https://live.douyin.com/543221183540")
CHROME = os.environ.get(
    "DY_CHROME",
    str(Path(os.environ["LOCALAPPDATA"]) / "ms-playwright" / "chromium-1255" / "chrome-win64" / "chrome.exe"),
)

results: list[dict] = []


def check(name: str, condition: bool, detail=None):
    results.append({"check": name, "ok": bool(condition), "detail": detail})
    print(("PASS " if condition else "FAIL ") + name + (f" :: {detail}" if detail is not None else ""))
    if not condition:
        raise AssertionError(name + (f" :: {detail}" if detail is not None else ""))


def snapshot(page):
    return page.evaluate(
        """() => {
          const bar = document.querySelector('#BottomLayout');
          const gifts = document.querySelector('[data-e2e="gifts-container"]');
          const btn = document.querySelector('#dygt-gift-toggle');
          const b = btn ? btn.getBoundingClientRect() : null;
          const s = btn ? getComputedStyle(btn) : null;
          const labelEl = btn ? btn.querySelector('.dygt-label') : null;
          const ls = labelEl ? getComputedStyle(labelEl) : null;
          const lr = labelEl ? labelEl.getBoundingClientRect() : null;
          const fs = document.fullscreenElement;
          return {
            flag: document.documentElement.getAttribute('data-dygt-gifts'),
            bar: bar ? {display:getComputedStyle(bar).display, rect:[bar.getBoundingClientRect().x,bar.getBoundingClientRect().y,bar.getBoundingClientRect().width,bar.getBoundingClientRect().height].map(Math.round)} : null,
            gifts: gifts ? {display:getComputedStyle(gifts).display, rect:[gifts.getBoundingClientRect().x,gifts.getBoundingClientRect().y,gifts.getBoundingClientRect().width,gifts.getBoundingClientRect().height].map(Math.round)} : null,
            button: btn ? {text:(btn.innerText||'').trim(), off:btn.getAttribute('data-off'), pressed:btn.getAttribute('aria-pressed'), label:btn.getAttribute('aria-label'), parent:btn.parentElement && btn.parentElement.tagName, visible:s.display!=='none'&&b.width>0&&b.height>0, rect:[b.x,b.y,b.width,b.height].map(Math.round), width:Math.round(b.width), opacity:Number(s.opacity), background:s.backgroundColor, labelOpacity:ls?Number(ls.opacity):null, labelWidth:lr?Math.round(lr.width):null} : null,
            fullscreen: fs ? {tag:fs.tagName, id:fs.id, cls:typeof fs.className==='string'?fs.className:''} : null,
            styleCount: document.querySelectorAll('#dygt-gift-toggle-style').length,
            buttonCount: document.querySelectorAll('#dygt-gift-toggle').length,
            inner:[innerWidth,innerHeight],
          };
        }"""
    )


def wait_ready(page):
    page.wait_for_selector("#BottomLayout", state="attached", timeout=60_000)
    page.wait_for_selector("#dygt-gift-toggle", state="visible", timeout=60_000)
    page.wait_for_timeout(1600)
    if page.evaluate("() => document.documentElement.getAttribute('data-dygt-gifts')") == "off":
        return
    wait_bar_visible(page)


def wait_bar_visible(page):
    # 直播页是异步布局：底栏先以 0 高度挂载，等礼物容器真正出现后再断言。
    page.wait_for_function(
        """() => {
          const bar = document.querySelector('#BottomLayout');
          const gifts = document.querySelector('[data-e2e="gifts-container"]');
          if (!bar || !gifts) return false;
          const r = bar.getBoundingClientRect();
          return r.height > 20 && r.width > 100;
        }""",
        timeout=60_000,
    )
    page.wait_for_timeout(1000)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME,
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            viewport={"width": 1600, "height": 1000},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        ctx.add_init_script(path=str(SCRIPT))
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
        wait_ready(page)

        s0 = snapshot(page)
        check("normal: 页面加载后按钮存在且只有一个", s0["button"] and s0["buttonCount"] == 1, s0["button"])
        check("normal: 样式只注入一次", s0["styleCount"] == 1, s0["styleCount"])
        check("normal: 默认显示礼物栏", s0["flag"] == "on" and s0["bar"]["display"] != "none" and s0["bar"]["rect"][3] > 20 and s0["gifts"] and s0["gifts"]["rect"][3] > 20, s0)
        check("normal: 默认只显示 logo、插件名隐藏", s0["button"]["width"] <= 32 and s0["button"]["labelOpacity"] == 0 and "礼物栏开关" in s0["button"]["text"], s0["button"])
        check("normal: 默认半透明且无底色", s0["button"]["opacity"] < 0.8 and s0["button"]["background"] in ("rgba(0, 0, 0, 0)", "transparent"), s0["button"])
        check("normal: aria 动作为隐藏", s0["button"]["label"] == "隐藏抖音底部礼物栏" and s0["button"]["pressed"] == "false", s0["button"])
        page.screenshot(path=str(OUT / "01-normal-visible.png"))

        page.hover("#dygt-gift-toggle")
        page.wait_for_timeout(350)
        sh = snapshot(page)
        check("hover: 展开显示插件名", sh["button"]["width"] >= 100 and sh["button"]["labelWidth"] >= 30 and sh["button"]["labelOpacity"] > 0.9, sh["button"])
        check("hover: 出现底色并恢复不透明", sh["button"]["background"] not in ("rgba(0, 0, 0, 0)", "transparent") and sh["button"]["opacity"] > 0.9, sh["button"])
        page.screenshot(path=str(OUT / "01b-hover-expanded.png"))
        page.mouse.move(700, 500)
        page.wait_for_timeout(350)
        sc = snapshot(page)
        check("hover 结束: 收回纯 logo", sc["button"]["width"] <= 32 and sc["button"]["labelOpacity"] == 0, sc["button"])

        page.click("#dygt-gift-toggle")
        page.wait_for_timeout(700)
        s1 = snapshot(page)
        check("click: 礼物栏被隐藏", s1["flag"] == "off" and s1["bar"]["display"] == "none", s1["bar"])
        check("click: aria 变为显示、状态正确", s1["button"]["label"] == "显示抖音底部礼物栏" and s1["button"]["pressed"] == "true", s1["button"])
        check("click: 按钮仍在视口内", s1["button"]["visible"], s1["button"])
        control = page.evaluate(
            """() => { const e=document.querySelector('#PlayerControlLayout'); if(!e) return null;
              const s=getComputedStyle(e); const r=e.getBoundingClientRect();
              return {display:s.display, h:Math.round(r.height), w:Math.round(r.width)}; }"""
        )
        check("click: 播放器控制层未被误隐藏", control and control["display"] != "none" and control["h"] > 100, control)
        page.mouse.move(700, 500)
        page.wait_for_timeout(250)
        page.screenshot(path=str(OUT / "02-normal-hidden.png"))

        page.reload(wait_until="domcontentloaded", timeout=60_000)
        wait_ready(page)
        s2 = snapshot(page)
        check("reload: 当前标签页保持隐藏", s2["flag"] == "off" and s2["bar"]["display"] == "none", s2)
        check("reload: 按钮状态保持显示动作", s2["button"]["label"] == "显示抖音底部礼物栏" and "礼物栏开关" in s2["button"]["text"], s2["button"])
        page.screenshot(path=str(OUT / "03-reload-hidden.png"))

        page.click("#dygt-gift-toggle")
        page.wait_for_timeout(500)
        page.mouse.move(700, 500)
        wait_bar_visible(page)
        s3 = snapshot(page)
        check("restore: 点击后礼物栏恢复", s3["flag"] == "on" and s3["bar"]["display"] != "none" and s3["bar"]["rect"][3] > 20, s3["bar"])

        # 原生全屏：点真实的播放器全屏图标（不是送礼/充值按钮）。
        page.mouse.move(700, 500)
        page.wait_for_timeout(500)
        fs_point = page.evaluate(
            """() => {
              const tips = Array.from(document.querySelectorAll('.douyin-player-tooltips.douyin-player-fullscreen'))
                .filter(e => e.textContent.includes('进入全屏'))
                .map(e => { const r = e.getBoundingClientRect(); return {x:r.x + r.width/2, y:r.y + r.height/2, w:r.width, h:r.height}; })
                .filter(p => p.w > 0 && p.h > 0 && p.y > 0 && p.y < innerHeight);
              return tips[0] || null;
            }"""
        )
        check("native fullscreen: 找到播放器全屏按钮", fs_point is not None, fs_point)
        page.mouse.move(fs_point["x"], fs_point["y"])
        page.wait_for_timeout(350)
        page.mouse.click(fs_point["x"], fs_point["y"])
        page.wait_for_timeout(1800)
        s4 = snapshot(page)
        check("native fullscreen: 浏览器进入全屏", s4["fullscreen"] is not None, s4["fullscreen"])
        check("native fullscreen: 按钮仍可见", s4["button"]["visible"], s4["button"])
        check("native fullscreen: 按钮在全屏元素内或 body 内", s4["button"]["parent"] in ("BODY", "DIV"), s4["button"])
        page.screenshot(path=str(OUT / "04-native-fullscreen.png"))

        page.click("#dygt-gift-toggle")
        page.wait_for_timeout(700)
        s5 = snapshot(page)
        check("native fullscreen: 切换后礼物栏隐藏", s5["flag"] == "off" and s5["bar"]["display"] == "none", s5)
        check("native fullscreen: 按钮仍可见", s5["button"]["visible"], s5["button"])
        page.screenshot(path=str(OUT / "05-native-fullscreen-hidden.png"))

        if s5["fullscreen"]:
            page.evaluate("() => document.fullscreenElement && document.exitFullscreen()")
            page.wait_for_timeout(800)
        s6 = snapshot(page)
        check("exit fullscreen: 已退出全屏", s6["fullscreen"] is None, s6["fullscreen"])
        check("exit fullscreen: 隐藏状态仍生效", s6["flag"] == "off" and s6["bar"]["display"] == "none", s6)

        # 多标签页独立：同一浏览器上下文新开一页，必须是默认显示。
        page2 = ctx.new_page()
        page2.goto(URL, wait_until="domcontentloaded", timeout=60_000)
        wait_ready(page2)
        p2 = snapshot(page2)
        check("multi-tab: 新标签页默认显示礼物栏", p2["flag"] == "on" and p2["bar"]["display"] != "none", p2)
        check("multi-tab: 新标签页按钮可见", p2["button"]["visible"], p2["button"])
        page2.click("#dygt-gift-toggle")
        page2.wait_for_timeout(500)
        p2b = snapshot(page2)
        check("multi-tab: 新标签页可独立隐藏", p2b["flag"] == "off" and p2b["bar"]["display"] == "none", p2b)
        p1 = snapshot(page)
        check("multi-tab: 原标签页状态不被新标签页改写", p1["flag"] == "off", p1["flag"])
        page2.screenshot(path=str(OUT / "06-second-tab-hidden.png"))

        # 视口变化（网页全屏/F11 的等价几何变化）：按钮固定定位应仍可见。
        page2.set_viewport_size({"width": 1366, "height": 768})
        page2.wait_for_timeout(600)
        p2c = snapshot(page2)
        check("viewport: 缩小后按钮仍可见", p2c["button"]["visible"], p2c["button"])
        check("viewport: 缩小时按钮不超出视口", p2c["button"]["rect"][0] >= 0 and p2c["button"]["rect"][1] >= 0 and p2c["button"]["rect"][0] + p2c["button"]["rect"][2] <= 1366 and p2c["button"]["rect"][1] + p2c["button"]["rect"][3] <= 768, p2c["button"])
        page2.screenshot(path=str(OUT / "07-small-viewport.png"))

        browser.close()

    summary = {
        "url": URL,
        "elapsed_seconds": round(time.time() - started, 2),
        "passed": sum(1 for r in results if r["ok"]),
        "failed": sum(1 for r in results if not r["ok"]),
        "checks": results,
    }
    (OUT / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{summary['passed']} passed, {summary['failed']} failed in {summary['elapsed_seconds']}s")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("\nTEST ERROR:", exc)
        (OUT / "report.json").write_text(
            json.dumps({"error": str(exc), "checks": results}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        raise
