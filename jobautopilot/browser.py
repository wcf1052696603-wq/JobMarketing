# -*- coding: utf-8 -*-
"""浏览器管理：常驻 Edge + CDP 端口，多个脚本复用同一个浏览器窗口。

这样用户可以随时在同一个窗口里手动操作，登录态也不会丢。
"""
import json
import os
import subprocess
import time
import urllib.request

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN','zh','en']});
Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
window.chrome = window.chrome || {runtime: {}};
const origQuery = window.navigator.permissions && window.navigator.permissions.query;
if (origQuery) {
  window.navigator.permissions.query = (p) => (
    p && p.name === 'notifications'
      ? Promise.resolve({state: Notification.permission})
      : origQuery(p)
  );
}
"""


def find_browser():
    for p in EDGE_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def cdp_alive(port):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/json/version" % port, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def ensure_browser(port=9222, profile=None):
    """确保带调试端口的浏览器已启动，返回是否新启动。"""
    if cdp_alive(port):
        return False
    exe = find_browser()
    if not exe:
        raise RuntimeError("未找到 Edge/Chrome，请修改 browser.py 中的路径")
    cmd = [
        exe,
        "--remote-debugging-port=%d" % port,
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        "--start-maximized",
        "--disable-popup-blocking",
        "about:blank",
    ]
    if profile:
        os.makedirs(profile, exist_ok=True)
        cmd.insert(2, "--user-data-dir=%s" % profile)
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        time.sleep(1)
        if cdp_alive(port):
            return True
    raise RuntimeError("浏览器启动失败，CDP 端口 %d 无响应" % port)


def connect(port=9222):
    """返回 (pw, browser, context)。"""
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp("http://127.0.0.1:%d" % port)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    try:
        ctx.add_init_script(STEALTH_JS)
    except Exception:
        pass
    return pw, browser, ctx


def list_targets(port=9222):
    with urllib.request.urlopen("http://127.0.0.1:%d/json/list" % port, timeout=5) as r:
        return json.load(r)


class Session:
    """连接上下文管理器。"""

    def __init__(self, port=9222, profile=None, target_host=None):
        self.port = port
        self.profile = profile
        self.target_host = target_host
        self.pw = None
        self.browser = None
        self.ctx = None
        self.page = None

    def __enter__(self):
        ensure_browser(self.port, self.profile)
        self.pw, self.browser, self.ctx = connect(self.port)
        self.page = self._pick_page()
        return self

    def _pick_page(self):
        if self.target_host:
            for pg in self.ctx.pages:
                if self.target_host in (pg.url or ""):
                    return pg
        for pg in self.ctx.pages:
            if (pg.url or "").startswith("http"):
                return pg
        return self.ctx.new_page()

    def __exit__(self, *a):
        try:
            self.browser.close()
        except Exception:
            pass
        try:
            self.pw.stop()
        except Exception:
            pass
