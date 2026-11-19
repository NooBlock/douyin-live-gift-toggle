// ==UserScript==
// @name         抖音直播礼物栏一键隐藏
// @name:en      Douyin Live Gift Bar Toggle
// @namespace    https://local.dygt/
// @version      1.1.2
// @description  一键隐藏/显示抖音直播底部的礼物栏、充值和游戏入口，支持普通/网页全屏/原生全屏；纯本地修改，不影响账号。
// @description:en One-click toggle for Douyin Live's gift bar, recharge and game entries. Works in normal, web and native fullscreen. Local-only, no account access.
// @author       local
// @license      MIT
// @match        https://live.douyin.com/*
// @run-at       document-start
// @grant        none
// @noframes
// ==/UserScript==

(() => {
  'use strict';

  /*
   * 设计约束：
   * 1. 不调用任何抖音接口、不读 Cookie、不发请求、不模拟送礼/充值/登录。
   * 2. 只做两件事：给 <html> 打一个本地属性，用 CSS 隐藏底栏；加一个悬浮按钮。
   * 3. 隐藏状态只存在当前标签页的 sessionStorage：刷新保留，新标签页互不影响。
   * 4. 不用轮询、不用长期 MutationObserver；底栏是 React 动态渲染的，CSS 选择器会自动命中。
   * 5. 按钮固定在视口左侧，原生全屏时若全屏元素不是 <body>，会重新挂载进全屏元素。
   */

  const STATE_KEY = 'dygt.giftDock.hidden.v1';
  const HTML_FLAG = 'data-dygt-gifts';
  const BUTTON_ID = 'dygt-gift-toggle';

  const CSS = `
    /* 只隐藏“底部礼物栏”这一块，不动播放器、弹幕、聊天和顶部信息。 */
    html[${HTML_FLAG}="off"] #BottomLayout,
    html[${HTML_FLAG}="off"] #giftPanelEntrance,
    html[${HTML_FLAG}="off"] [data-e2e="gifts-container"],
    html[${HTML_FLAG}="off"] [data-e2e="gifts-switch"],
    html[${HTML_FLAG}="off"] [data-e2e="recharge-btn"] {
      display: none !important;
    }

    #${BUTTON_ID} {
      all: initial !important;
      position: fixed !important;
      left: max(14px, env(safe-area-inset-left, 0px)) !important;
      bottom: 142px !important;
      z-index: 2147483647 !important;
      box-sizing: border-box !important;
      display: inline-flex !important;
      align-items: center !important;
      justify-content: flex-start !important;
      width: 30px !important;
      height: 30px !important;
      padding: 0 0 0 6px !important;
      border: 1px solid transparent !important;
      border-radius: 50% !important;
      background: transparent !important;
      box-shadow: none !important;
      color: #fff !important;
      font: 600 12px/1 -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif !important;
      letter-spacing: 0.01em !important;
      white-space: nowrap !important;
      cursor: pointer !important;
      user-select: none !important;
      -webkit-user-select: none !important;
      -webkit-tap-highlight-color: transparent !important;
      overflow: hidden !important;
      opacity: 0.58 !important;
      transition: width 0.18s ease, background-color 0.18s ease, border-color 0.18s ease,
                  border-radius 0.18s ease, opacity 0.18s ease, box-shadow 0.18s ease !important;
    }

    #${BUTTON_ID}:hover,
    #${BUTTON_ID}:focus-visible {
      width: 118px !important;
      padding: 0 10px 0 6px !important;
      border-color: rgba(255, 255, 255, 0.2) !important;
      border-radius: 999px !important;
      background: rgba(18, 18, 22, 0.9) !important;
      box-shadow: 0 6px 18px rgba(0, 0, 0, 0.3) !important;
      opacity: 1 !important;
      outline: none !important;
    }

    #${BUTTON_ID}:focus-visible {
      border-color: rgba(254, 44, 85, 0.8) !important;
      box-shadow: 0 0 0 2px rgba(254, 44, 85, 0.45), 0 6px 18px rgba(0, 0, 0, 0.3) !important;
    }

    #${BUTTON_ID}[data-off="true"] {
      color: #ff5d75 !important;
    }

    #${BUTTON_ID} .dygt-icon {
      display: block !important;
      width: 18px !important;
      height: 18px !important;
      flex: 0 0 18px !important;
      color: currentColor !important;
      filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.65)) !important;
      pointer-events: none !important;
    }

    #${BUTTON_ID} .dygt-label {
      display: inline-block !important;
      max-width: 0 !important;
      margin-left: 0 !important;
      overflow: hidden !important;
      color: #fff !important;
      opacity: 0 !important;
      font: inherit !important;
      pointer-events: none !important;
      transition: max-width 0.18s ease, margin-left 0.18s ease, opacity 0.12s ease !important;
    }

    #${BUTTON_ID}:hover .dygt-label,
    #${BUTTON_ID}:focus-visible .dygt-label {
      max-width: 82px !important;
      margin-left: 6px !important;
      opacity: 1 !important;
    }

    #${BUTTON_ID} .dygt-gift-off {
      display: none !important;
    }

    #${BUTTON_ID}[data-off="true"] .dygt-gift-on {
      display: none !important;
    }

    #${BUTTON_ID}[data-off="true"] .dygt-gift-off {
      display: block !important;
    }
  `;

  let hidden = false;
  try {
    hidden = sessionStorage.getItem(STATE_KEY) === '1';
  } catch (_) {
    // 隐私模式/存储被禁用时退回当前页面内存状态，不影响功能。
  }

  function paintFlag() {
    document.documentElement.setAttribute(HTML_FLAG, hidden ? 'off' : 'on');
  }

  function installCss() {
    const style = document.createElement('style');
    style.id = 'dygt-gift-toggle-style';
    style.textContent = CSS;
    (document.head || document.documentElement).appendChild(style);
  }

  // 尽早打标记，避免刷新后礼物栏先闪一下再消失。
  // @run-at document-start 时（尤其自动化注入）<html> 可能还没创建，等它出现即可。
  function start() {
    if (!document.documentElement) {
      const observer = new MutationObserver(() => {
        if (!document.documentElement) return;
        observer.disconnect();
        start();
      });
      observer.observe(document, { childList: true });
      return;
    }

    paintFlag();
    installCss();

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', boot, { once: true });
    } else {
      boot();
    }
  }

  const GIFT_ON = `
    <svg class="dygt-icon dygt-gift-on" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4.2 10.2h15.6v9.2H4.2z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
      <path d="M3.1 7.2h17.8v3H3.1z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
      <path d="M12 7.2v12.2" stroke="currentColor" stroke-width="1.7"/>
      <path d="M11.9 7.2C10.7 4.5 7 4.7 7 6.5c0 1 .7 1.5 1.8 1.5h3.1Z"
            stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
      <path d="M12.1 7.2C13.3 4.5 17 4.7 17 6.5c0 1-.7 1.5-1.8 1.5h-3.1Z"
            stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
    </svg>`;

  const GIFT_OFF = `
    <svg class="dygt-icon dygt-gift-off" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4.2 10.2h15.6v9.2H4.2z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" opacity=".72"/>
      <path d="M3.1 7.2h17.8v3H3.1z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" opacity=".72"/>
      <path d="M12 7.2v12.2" stroke="currentColor" stroke-width="1.7" opacity=".72"/>
      <path d="M11.9 7.2C10.7 4.5 7 4.7 7 6.5c0 1 .7 1.5 1.8 1.5h3.1Z"
            stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" opacity=".72"/>
      <path d="M12.1 7.2C13.3 4.5 17 4.7 17 6.5c0 1-.7 1.5-1.8 1.5h-3.1Z"
            stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" opacity=".72"/>
      <path d="M4.3 19.7 19.7 4.3" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"/>
    </svg>`;

  let button = null;
  let bootTries = 0;

  function makeButton() {
    const btn = document.createElement('button');
    btn.id = BUTTON_ID;
    btn.type = 'button';
    btn.setAttribute('data-dygt-role', 'gift-dock-toggle');
    btn.innerHTML = `${GIFT_ON}${GIFT_OFF}<span class="dygt-label"></span>`;

    btn.addEventListener('pointerdown', (event) => {
      // 防止抖音把点击当成“暂停/播放”或触发全屏手势。
      event.stopPropagation();
    });

    btn.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      hidden = !hidden;
      paintFlag();
      syncButton();
      try {
        sessionStorage.setItem(STATE_KEY, hidden ? '1' : '0');
      } catch (_) {
        // 存不了就只在当前页面生效。
      }
    });

    btn.addEventListener('dblclick', (event) => {
      event.preventDefault();
      event.stopPropagation();
    });

    return btn;
  }

  function syncButton() {
    if (!button) return;
    button.dataset.off = hidden ? 'true' : 'false';
    button.setAttribute('aria-pressed', hidden ? 'true' : 'false');
    button.setAttribute('aria-label', hidden ? '显示抖音底部礼物栏' : '隐藏抖音底部礼物栏');
    button.title = hidden ? '显示底部礼物栏（仅当前标签页）' : '隐藏底部礼物栏（仅当前标签页）';
    const label = button.querySelector('.dygt-label');
    if (label) label.textContent = '礼物栏开关';
  }

  function mountButton() {
    if (!button) return;
    const fs = document.fullscreenElement;
    // 原生全屏时浏览器只绘制全屏元素及其子树；<video> 不能 append，保持 body 兜底。
    const host = fs && fs !== document.documentElement && fs.tagName !== 'VIDEO' && typeof fs.appendChild === 'function'
      ? fs
      : document.body;
    if (host && button.parentNode !== host) host.appendChild(button);
  }

  function boot() {
    if (button) return;
    if (!document.body) {
      // 极少数情况下 DOMContentLoaded 时 body 还没挂上；最多等 2 秒，不无限轮询。
      if (bootTries++ < 25) window.setTimeout(boot, 80);
      return;
    }
    button = makeButton();
    syncButton();
    mountButton();
    document.addEventListener('fullscreenchange', mountButton, true);
    document.addEventListener('webkitfullscreenchange', mountButton, true);
  }

  start();
})();
