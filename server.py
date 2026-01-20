"""手机语音输入同步到电脑光标 - GUI版"""

import asyncio
import io
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler
from tkinter import messagebox, ttk

import pyautogui
import pyperclip
import qrcode
from PIL import Image, ImageTk
import websockets
import pystray
from pystray import MenuItem as item

VERSION = "0.1.5"
GITHUB_REPO = "chxcodepro/VoiceSync"

SYSTEM = platform.system()

HTML_PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>语音输入</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html, body { height: 100%; overflow: hidden; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', sans-serif;
            background: #F2F2F7;
            display: flex;
            flex-direction: column;
            padding: 20px;
        }
        .header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 16px;
            flex-shrink: 0;
        }
        .theme-toggle {
            width: 36px;
            height: 36px;
            border: none;
            border-radius: 50%;
            background: rgba(0, 0, 0, 0.05);
            font-size: 18px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
            flex-shrink: 0;
        }
        .theme-toggle:active {
            transform: scale(0.9);
        }
        .status {
            flex: 1;
            text-align: center;
            padding: 10px 16px;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 600;
            flex-shrink: 0;
            transition: all 0.2s ease;
            letter-spacing: -0.08px;
        }
        .status.connected {
            background: #34C759;
            color: white;
        }
        .status.disconnected {
            background: #FF3B30;
            color: white;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.8; }
        }
        textarea {
            flex: 1;
            width: 100%;
            padding: 16px;
            font-size: 17px;
            line-height: 1.47;
            border: none;
            border-radius: 12px;
            resize: none;
            outline: none;
            background: white;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
            transition: box-shadow 0.2s ease;
            letter-spacing: -0.41px;
        }
        textarea:focus {
            box-shadow: 0 0 0 4px rgba(0, 122, 255, 0.15);
        }
        textarea::placeholder { color: #8E8E93; }
        .btn-group {
            display: flex;
            gap: 12px;
            margin-top: 16px;
            flex-shrink: 0;
        }
        .btn {
            flex: 1;
            padding: 13px;
            font-size: 17px;
            font-weight: 600;
            border: none;
            border-radius: 10px;
            transition: all 0.2s ease;
            cursor: pointer;
            letter-spacing: -0.41px;
        }
        .btn:active {
            transform: scale(0.96);
            opacity: 0.8;
        }
        .btn-send {
            background: #007AFF;
            color: white;
        }
        .btn-clear {
            background: #E5E5EA;
            color: #000;
        }
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.4);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1000;
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.3s ease;
        }
        .modal-overlay.show {
            opacity: 1;
            visibility: visible;
        }
        .modal {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(40px);
            padding: 24px;
            border-radius: 14px;
            width: 90%;
            max-width: 300px;
            text-align: center;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
            transform: scale(0.95);
            transition: transform 0.3s ease;
        }
        .modal-overlay.show .modal {
            transform: scale(1);
        }
        .modal h3 {
            margin-bottom: 6px;
            font-size: 17px;
            font-weight: 600;
            color: #000;
            letter-spacing: -0.41px;
        }
        .modal p {
            margin-bottom: 20px;
            font-size: 13px;
            color: #8E8E93;
            letter-spacing: -0.08px;
        }
        .modal-btns {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .modal-btn {
            width: 100%;
            padding: 13px;
            font-size: 17px;
            font-weight: 600;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s ease;
            letter-spacing: -0.41px;
        }
        .modal-btn:active {
            transform: scale(0.96);
            opacity: 0.8;
        }
        .modal-btn.primary {
            background: #007AFF;
            color: white;
        }
        .modal-btn.secondary {
            background: #E5E5EA;
            color: #000;
        }
        body[data-theme="dark"] {
            background: #000000;
        }
        body[data-theme="dark"] .theme-toggle {
            background: rgba(255, 255, 255, 0.1);
        }
        body[data-theme="dark"] textarea {
            background: #1C1C1E;
            color: #FFFFFF;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
        }
        body[data-theme="dark"] textarea::placeholder {
            color: #636366;
        }
        body[data-theme="dark"] .btn-clear {
            background: #2C2C2E;
            color: #FFFFFF;
        }
        body[data-theme="dark"] .modal {
            background: rgba(28, 28, 30, 0.95);
        }
        body[data-theme="dark"] .modal h3 {
            color: #FFFFFF;
        }
        body[data-theme="dark"] .modal-btn.secondary {
            background: #2C2C2E;
            color: #FFFFFF;
        }
    </style>
</head>
<body>
    <div class="header">
        <button class="theme-toggle" id="themeToggle">🌙</button>
        <div class="status disconnected" id="status">连接中...</div>
    </div>
    <textarea id="input" placeholder="点击这里，使用语音输入..."></textarea>
    <div class="btn-group">
        <button class="btn btn-send" id="sendBtn">发送</button>
        <button class="btn btn-clear" id="clearBtn">清空</button>
    </div>

    <div class="modal-overlay" id="modalOverlay">
        <div class="modal">
            <h3>窗口已切换</h3>
            <p id="modalMsg">检测到目标窗口已改变</p>
            <div class="modal-btns">
                <button class="modal-btn secondary" id="newConvBtn">新对话</button>
                <button class="modal-btn primary" id="switchBackBtn">返回程序</button>
            </div>
        </div>
    </div>

    <script>
        // 主题切换
        const themeToggle = document.getElementById('themeToggle');
        const savedTheme = localStorage.getItem('theme');
        const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const currentTheme = savedTheme || (systemDark ? 'dark' : 'light');

        function setTheme(theme) {
            document.body.setAttribute('data-theme', theme);
            themeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
            localStorage.setItem('theme', theme);
        }

        setTheme(currentTheme);
        themeToggle.addEventListener('click', () => {
            const newTheme = document.body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            setTheme(newTheme);
        });

        const wsUrl = `ws://${location.hostname}:${parseInt(location.port) + 1}`;
        let ws = null, sendTimer = null;
        let syncedText = '';
        let syncedCursor = 0;
        let pendingText = '';
        let windowSwitchSyncedText = '';  // 记录窗口切换时已同步的文本
        const statusEl = document.getElementById('status');
        const inputEl = document.getElementById('input');
        const clearBtn = document.getElementById('clearBtn');
        const modalOverlay = document.getElementById('modalOverlay');
        const modalMsg = document.getElementById('modalMsg');
        const newConvBtn = document.getElementById('newConvBtn');
        const switchBackBtn = document.getElementById('switchBackBtn');

        function optimizeText(text) {
            // 去除语气词
            text = text.replace(/[，。、]*(嗯+|啊+|呃+|哦+|诶+)[，。、]*/g, '');
            text = text.replace(/那个+/g, '');
            text = text.replace(/这个+/g, '');
            text = text.replace(/就是说+/g, '');
            text = text.replace(/然后+/g, '然后');

            // 去除重复字词
            text = text.replace(/(.)\1{2,}/g, '$1');
            text = text.replace(/(\\S{2,})\\1+/g, '$1');

            // 常见错误词纠正
            const corrections = {
                '在在': '在', '的的': '的', '了了': '了',
                '因为所以': '因为', '虽然但是': '虽然',
                '应该应该': '应该', '可以可以': '可以'
            };
            for (const [wrong, right] of Object.entries(corrections)) {
                text = text.replace(new RegExp(wrong, 'g'), right);
            }

            // 清理多余空格
            text = text.replace(/\\s+/g, ' ').trim();

            return text;
        }

        function connect() {
            ws = new WebSocket(wsUrl);
            ws.onopen = () => {
                statusEl.textContent = '已连接';
                statusEl.className = 'status connected';
            };
            ws.onclose = () => {
                statusEl.textContent = '已断开，重连中...';
                statusEl.className = 'status disconnected';
                setTimeout(connect, 2000);
            };
            ws.onerror = () => ws.close();
            ws.onmessage = handleServerMessage;
        }

        function send(msg) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify(msg));
            }
        }

        function handleServerMessage(event) {
            const data = JSON.parse(event.data);
            if (data.type === 'window_status') {
                if (data.changed) {
                    const name = data.window_name || '其他程序';
                    modalMsg.textContent = `当前窗口: ${name}`;
                    windowSwitchSyncedText = syncedText;  // 记录此时已同步的文本
                    modalOverlay.classList.add('show');
                } else {
                    doSend(pendingText, false);
                }
            } else if (data.type === 'switched_back') {
                if (data.success) {
                    setTimeout(() => doSend(pendingText, false), 100);
                }
            }
        }

        function doSend(text, newWindow) {
            if (!text) return;
            // 自动优化文本
            text = optimizeText(text);
            inputEl.value = text;

            // 新对话时用窗口切换时记录的已同步文本计算增量
            const baseText = newWindow ? windowSwitchSyncedText : syncedText;
            const newText = text.slice(baseText.length);
            if (newText) {
                send({type: 'confirm_send', text: newText, new_window: newWindow});
            }
            if (newWindow) {
                // 新对话：更新同步状态，但保留输入框内容
                syncedText = text;
                syncedCursor = inputEl.selectionStart;
                windowSwitchSyncedText = text;
            } else {
                syncedText = text;
                syncedCursor = inputEl.selectionStart;
            }
            modalOverlay.classList.remove('show');
        }

        function processChange() {
            const text = inputEl.value;
            const cursor = inputEl.selectionStart;

            if (text === syncedText && cursor === syncedCursor) return;

            if (text.length < syncedText.length) {
                // 只处理末尾删除：检查是否是 syncedText 的前缀
                if (syncedText.startsWith(text)) {
                    const deleteCount = syncedText.length - text.length;
                    send({type: 'delete', count: deleteCount});
                }
                // 非末尾删除不同步，只更新本地状态
                syncedText = text;
                syncedCursor = cursor;
                return;
            }

            if (text.length > syncedText.length) {
                if (!text.startsWith(syncedText)) {
                    // 文本被修改，找到公共前缀并重置
                    let i = 0;
                    while (i < syncedText.length && i < text.length && text[i] === syncedText[i]) i++;
                    syncedText = text.slice(0, i);
                }
                pendingText = text;
                send({type: 'check_window'});
            }
        }

        inputEl.addEventListener('input', () => {
            clearTimeout(sendTimer);
            sendTimer = setTimeout(processChange, 400);
        });

        inputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                clearTimeout(sendTimer);
                processChange();
            }
        });

        document.getElementById('sendBtn').addEventListener('click', () => {
            send({type: 'press_enter'});
        });

        clearBtn.addEventListener('click', () => {
            inputEl.value = '';
            syncedText = '';
            syncedCursor = 0;
            windowSwitchSyncedText = '';
        });

        newConvBtn.addEventListener('click', () => {
            doSend(pendingText, true);
        });

        switchBackBtn.addEventListener('click', () => {
            send({type: 'switch_back'});
        });

        connect();
    </script>
</body>
</html>"""


def _parse_semver(version: str) -> tuple[int, int, int] | None:
    version = (version or "").strip().lstrip("v").strip()
    parts = version.split(".")
    if len(parts) != 3:
        return None
    try:
        major, minor, patch = (int(p) for p in parts)
    except ValueError:
        return None
    return major, minor, patch


def _is_newer_version(latest: str, current: str) -> bool:
    latest_parsed = _parse_semver(latest)
    current_parsed = _parse_semver(current)
    if latest_parsed is None or current_parsed is None:
        return (latest or "").strip() != (current or "").strip()
    return latest_parsed > current_parsed


def _fetch_latest_release(repo: str, timeout_s: float = 3.5) -> dict | None:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"VoiceSync/{VERSION}",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            if resp.status != 200:
                return None
            data = resp.read().decode("utf-8", errors="replace")
            return json.loads(data)
    except urllib.error.HTTPError as e:
        try:
            if e.code == 403 and e.headers.get("X-RateLimit-Remaining") == "0":
                return None
        except Exception:
            return None
        return None
    except Exception:
        return None


def _find_exe_asset(release: dict) -> dict | None:
    assets = release.get("assets") or []
    for asset in assets:
        name = (asset.get("name") or "").strip().lower()
        if name == "voicesync.exe":
            return asset
    for asset in assets:
        name = (asset.get("name") or "").strip().lower()
        if name.endswith(".exe"):
            return asset
    return None


def _download_file(url: str, dest_path: str, progress_cb=None, timeout_s: float = 60.0):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": f"VoiceSync/{VERSION}",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp, open(dest_path, "wb") as f:
        total = resp.headers.get("Content-Length")
        total_size = int(total) if total and total.isdigit() else 0
        downloaded = 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if progress_cb:
                progress_cb(downloaded, total_size)


def _write_update_bat(bat_path: str, pid: int, target_exe: str, new_exe: str):
    content = rf"""@echo off
setlocal enableextensions

set "PID={pid}"
set "TARGET={target_exe}"
set "NEWFILE={new_exe}"
set "MAX_RETRIES=10"
set "RETRY_COUNT=0"

timeout /t 1 /nobreak >NUL
taskkill /F /PID %PID% >NUL 2>&1
timeout /t 2 /nobreak >NUL

:retry
move /Y "%NEWFILE%" "%TARGET%" >NUL 2>&1
if errorlevel 1 (
  set /a RETRY_COUNT+=1
  if %RETRY_COUNT% LSS %MAX_RETRIES% (
    timeout /t 2 /nobreak >NUL
    goto retry
  )
  echo Update failed: cannot replace "%TARGET%".
  echo Please download the latest version from GitHub Releases.
  del "%NEWFILE%" >NUL 2>&1
  pause
  exit /b 1
)

start "" "%TARGET%"
del "%~f0" >NUL 2>&1
"""
    with open(bat_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(content)


def get_all_ips() -> list[tuple[str, str]]:
    """获取所有网卡的 IP 地址，返回 [(name, ip), ...]"""
    import psutil
    result = []
    default_ip = None

    # 获取默认路由 IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        default_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    # 获取网卡状态
    stats = psutil.net_if_stats()

    for name, addrs in psutil.net_if_addrs().items():
        # 检查网卡是否启用
        if name in stats and not stats[name].isup:
            continue

        for addr in addrs:
            if addr.family != socket.AF_INET:
                continue
            ip = addr.address
            # 只过滤本地回环
            if ip.startswith("127."):
                continue
            result.append((name, ip))

    # 默认路由的 IP 排在最前面
    if default_ip:
        result.sort(key=lambda x: (x[1] != default_ip, x[0]))

    return result if result else [("localhost", "127.0.0.1")]


def find_available_port(start_port: int, count: int = 2) -> int:
    """查找连续可用的端口"""
    for port in range(start_port, 65535):
        available = True
        for offset in range(count):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port + offset)) == 0:
                    available = False
                    break
        if available:
            return port
    return start_port


def get_terminal_processes() -> set:
    """获取终端进程名集合"""
    common = {"code", "cursor"}
    if SYSTEM == "Windows":
        return common | {
            "windowsterminal.exe", "cmd.exe", "powershell.exe", "pwsh.exe",
            "wezterm-gui.exe", "alacritty.exe", "hyper.exe", "terminus.exe",
            "conemu64.exe", "conemu.exe", "mintty.exe", "gitbash.exe",
            "code.exe", "cursor.exe",
        }
    elif SYSTEM == "Darwin":
        return common | {
            "terminal", "iterm2", "alacritty", "hyper", "wezterm-gui", "kitty",
        }
    else:
        return common | {
            "gnome-terminal", "konsole", "xfce4-terminal", "terminator",
            "alacritty", "kitty", "wezterm", "hyper", "tilix", "xterm",
        }


def get_active_process_name() -> str:
    """获取当前活动窗口的进程名（跨平台）"""
    try:
        if SYSTEM == "Windows":
            import win32gui
            import win32process
            import psutil
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return psutil.Process(pid).name().lower()
        elif SYSTEM == "Darwin":
            script = 'tell application "System Events" to get name of first process whose frontmost is true'
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            return result.stdout.strip().lower()
        else:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowpid"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                import psutil
                pid = int(result.stdout.strip())
                return psutil.Process(pid).name().lower()
    except Exception:
        pass
    return ""


def get_window_handle():
    """获取当前活动窗口句柄"""
    try:
        if SYSTEM == "Windows":
            import win32gui
            return win32gui.GetForegroundWindow()
        elif SYSTEM == "Darwin":
            script = '''
            tell application "System Events"
                set frontApp to first application process whose frontmost is true
                return {name of frontApp, id of frontApp}
            end tell
            '''
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            return result.stdout.strip()
        else:
            result = subprocess.run(["xdotool", "getactivewindow"], capture_output=True, text=True)
            if result.returncode == 0:
                return int(result.stdout.strip())
    except Exception:
        pass
    return None


def get_window_title(handle) -> str:
    """获取窗口标题"""
    if handle is None:
        return ""
    try:
        if SYSTEM == "Windows":
            import win32gui
            return win32gui.GetWindowText(handle)
        elif SYSTEM == "Darwin":
            return str(handle).split(",")[0] if handle else ""
        else:
            result = subprocess.run(
                ["xdotool", "getwindowname", str(handle)],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
    except Exception:
        pass
    return ""


def activate_window(handle) -> bool:
    """激活指定窗口"""
    if handle is None:
        return False
    try:
        if SYSTEM == "Windows":
            import win32gui
            import win32con
            win32gui.ShowWindow(handle, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(handle)
            return True
        elif SYSTEM == "Darwin":
            app_name = str(handle).split(",")[0] if handle else ""
            if app_name:
                script = f'tell application "{app_name}" to activate'
                subprocess.run(["osascript", "-e", script])
                return True
        else:
            subprocess.run(["xdotool", "windowactivate", str(handle)])
            return True
    except Exception:
        pass
    return False


def type_text(text: str):
    """将文字输入到光标位置，自动适配终端"""
    pyperclip.copy(text)
    time.sleep(0.1)
    process_name = get_active_process_name()
    terminals = get_terminal_processes()

    is_terminal = any(t in process_name for t in terminals)

    if SYSTEM == "Darwin":
        key = "command"
    else:
        key = "ctrl"

    if is_terminal:
        pyautogui.hotkey(key, "shift", "v")
    else:
        pyautogui.hotkey(key, "v")


def delete_text(count: int):
    """从末尾删除指定数量的字符"""
    for _ in range(count):
        pyautogui.press('backspace')


class HttpHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode("utf-8"))

    def log_message(self, format, *args):
        pass


class VoiceSyncApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("VoiceSync")
        self.root.resizable(False, False)
        self.root.configure(bg='#F5F5F7')

        self.port_http = find_available_port(8765)
        self.port_ws = self.port_http + 1
        self.all_ips = get_all_ips()
        self.current_ip_index = 0

        self.connected_clients = 0
        self.ws_server = None
        self.http_server = None
        self.last_window_handle = None
        self.tray_icon = None
        self.config_file = os.path.join(os.path.expanduser("~"), ".voicesync_config.json")
        self.config = self._load_config()

        self._setup_ui()
        self._start_servers()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._start_update_check()

    def _start_update_check(self):
        if SYSTEM != "Windows":
            return
        threading.Thread(target=self._check_updates_on_startup, daemon=True).start()

    def _check_updates_on_startup(self):
        release = _fetch_latest_release(GITHUB_REPO)
        if not release:
            return

        tag_name = (release.get("tag_name") or "").strip()
        latest_version = tag_name.lstrip("v").strip()
        if not latest_version:
            return

        if not _is_newer_version(latest_version, VERSION):
            return

        body = (release.get("body") or "").strip()
        snippet = body[:200] if body else "(无)"
        release_url = (release.get("html_url") or "").strip() or f"https://github.com/{GITHUB_REPO}/releases/latest"

        def prompt():
            msg = (
                f"发现新版本，是否更新？\n\n"
                f"当前版本：{VERSION}\n"
                f"最新版本：{latest_version}\n\n"
                f"更新说明（节选）：\n{snippet}"
            )
            if messagebox.askyesno("发现更新", msg):
                self._start_update_flow(release, latest_version, release_url)

        self.root.after(0, prompt)

    def _start_update_flow(self, release: dict, latest_version: str, release_url: str):
        if not getattr(sys, "frozen", False):
            messagebox.showinfo(
                "手动更新",
                f"当前为源码运行模式，无法自动替换可执行文件。\n\n请前往：\n{release_url}",
            )
            return

        asset = _find_exe_asset(release)
        if not asset:
            messagebox.showerror("更新失败", f"未找到可下载的 VoiceSync.exe。\n\n请前往：\n{release_url}")
            return

        download_url = (asset.get("browser_download_url") or "").strip()
        if not download_url:
            messagebox.showerror("更新失败", f"下载链接缺失。\n\n请前往：\n{release_url}")
            return

        target_exe = os.path.abspath(sys.executable)
        tmp_dir = tempfile.gettempdir()
        new_exe = os.path.join(tmp_dir, f"VoiceSync-{latest_version}.exe")
        bat_path = os.path.join(tmp_dir, f"VoiceSync-update-{os.getpid()}.bat")

        def progress(downloaded: int, total: int):
            if total > 0:
                percent = int(downloaded * 100 / total)
                text = f"正在下载更新... {percent}%"
            else:
                text = f"正在下载更新... {downloaded // 1024} KB"
            self.root.after(0, lambda: self.status_var.set(text))

        def run():
            try:
                _download_file(download_url, new_exe, progress_cb=progress)
                if not os.path.exists(new_exe) or os.path.getsize(new_exe) <= 0:
                    raise RuntimeError("downloaded file is empty")
                # 校验PE文件头
                with open(new_exe, "rb") as f:
                    header = f.read(2)
                    if header != b"MZ":
                        raise RuntimeError("invalid PE file")
            except Exception:
                # 清理临时文件
                if os.path.exists(new_exe):
                    try:
                        os.remove(new_exe)
                    except Exception:
                        pass
                self.root.after(0, lambda: messagebox.showerror("下载失败", f"下载更新失败，请手动更新：\n{release_url}"))
                self.root.after(0, lambda: self._update_status())
                return

            try:
                _write_update_bat(bat_path, os.getpid(), target_exe, new_exe)
                subprocess.Popen(
                    ["cmd.exe", "/c", bat_path],
                    cwd=tmp_dir,
                    creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                )
            except Exception:
                # 清理临时文件
                if os.path.exists(new_exe):
                    try:
                        os.remove(new_exe)
                    except Exception:
                        pass
                self.root.after(0, lambda: messagebox.showerror("更新失败", f"无法启动更新脚本，请手动更新：\n{release_url}"))
                self.root.after(0, lambda: self._update_status())
                return

            os._exit(0)

        threading.Thread(target=run, daemon=True).start()

    def _get_current_url(self) -> str:
        _, ip = self.all_ips[self.current_ip_index]
        return f"http://{ip}:{self.port_http}"

    def _setup_ui(self):
        style = ttk.Style()
        style.configure('Title.TLabel', font=('SF Pro Display', 20, 'bold'), background='#F5F5F7', foreground='#1D1D1F')
        style.configure('Url.TLabel', font=('SF Mono', 11), background='#F5F5F7', foreground='#007AFF')
        style.configure('Status.TLabel', font=('SF Pro Text', 13), background='#F5F5F7')
        style.configure('Main.TFrame', background='#F5F5F7')
        style.configure('QR.TFrame', background='white')

        main_frame = ttk.Frame(self.root, padding=40, style='Main.TFrame')
        main_frame.pack()

        title_label = ttk.Label(main_frame, text="扫码连接", style='Title.TLabel')
        title_label.pack(pady=(0, 20))

        # 网卡选择下拉框
        if len(self.all_ips) > 1:
            ip_frame = tk.Frame(main_frame, bg='#F5F5F7')
            ip_frame.pack(pady=(0, 20))
            tk.Label(ip_frame, text="网卡:", bg='#F5F5F7', font=('SF Pro Text', 11), fg='#1D1D1F').pack(side=tk.LEFT)
            self.ip_var = tk.StringVar()
            ip_options = [f"{name} ({ip})" for name, ip in self.all_ips]
            self.ip_var.set(ip_options[0])
            ip_menu = ttk.Combobox(ip_frame, textvariable=self.ip_var, values=ip_options,
                                   state='readonly', width=30)
            ip_menu.pack(side=tk.LEFT, padx=(5, 0))
            ip_menu.bind('<<ComboboxSelected>>', self._on_ip_change)

        self.qr_container = tk.Frame(main_frame, bg='white', padx=16, pady=16,
                                     highlightbackground='#D1D1D6', highlightthickness=1)
        self.qr_container.pack()

        self.qr_label = tk.Label(self.qr_container, bg='white')
        self.qr_label.pack()
        self._update_qr()

        self.url_var = tk.StringVar(value=self._get_current_url())
        url_label = ttk.Label(main_frame, textvariable=self.url_var, style='Url.TLabel')
        url_label.pack(pady=(20, 12))

        self.status_var = tk.StringVar(value="等待连接...")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, style='Status.TLabel')
        self.status_label.pack(pady=(12, 0))

    def _update_qr(self):
        url = self._get_current_url()
        qr = qrcode.QRCode(box_size=7, border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="#1D1D1F", back_color="white")

        img_byte_arr = io.BytesIO()
        qr_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        pil_img = Image.open(img_byte_arr)
        self.qr_photo = ImageTk.PhotoImage(pil_img)
        self.qr_label.configure(image=self.qr_photo)

    def _on_ip_change(self, event):
        self.current_ip_index = event.widget.current()
        self._update_qr()
        self.url_var.set(self._get_current_url())

    def _start_servers(self):
        threading.Thread(target=self._run_http_server, daemon=True).start()
        threading.Thread(target=self._run_ws_server, daemon=True).start()

    def _run_http_server(self):
        self.http_server = HTTPServer(("0.0.0.0", self.port_http), HttpHandler)
        self.http_server.serve_forever()

    def _run_ws_server(self):
        asyncio.run(self._ws_main())

    async def _ws_main(self):
        async with websockets.serve(self._handle_ws, "0.0.0.0", self.port_ws) as server:
            self.ws_server = server
            await asyncio.Future()

    async def _handle_ws(self, websocket):
        self.connected_clients += 1
        self._update_status()
        try:
            async for message in websocket:
                await self._process_message(message, websocket)
        finally:
            self.connected_clients -= 1
            self._update_status()

    async def _process_message(self, message: str, websocket):
        """处理 WebSocket 消息"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')

            if msg_type == 'check_window':
                current_handle = get_window_handle()
                changed = (self.last_window_handle is not None and
                          current_handle != self.last_window_handle)
                window_title = get_window_title(current_handle) if changed else ""
                await websocket.send(json.dumps({
                    'type': 'window_status',
                    'changed': changed,
                    'window_name': window_title
                }))

            elif msg_type == 'confirm_send':
                text = data.get('text', '')
                new_window = data.get('new_window', False)
                if text:
                    if new_window or self.last_window_handle is None:
                        self.last_window_handle = get_window_handle()
                    type_text(text)

            elif msg_type == 'switch_back':
                success = activate_window(self.last_window_handle)
                time.sleep(0.2)
                await websocket.send(json.dumps({
                    'type': 'switched_back',
                    'success': success
                }))

            elif msg_type == 'delete':
                if self.last_window_handle:
                    current_handle = get_window_handle()
                    if current_handle != self.last_window_handle:
                        activate_window(self.last_window_handle)
                        time.sleep(0.1)
                delete_text(data.get('count', 0))

            elif msg_type == 'press_enter':
                pyautogui.press('enter')

        except json.JSONDecodeError:
            type_text(message)

    def _update_status(self):
        if self.connected_clients > 0:
            text = f"已连接 ({self.connected_clients} 台设备)"
            color = '#34C759'
        else:
            text = "等待连接..."
            color = '#8E8E93'
        self.root.after(0, lambda: self._set_status(text, color))

    def _set_status(self, text, color):
        self.status_var.set(text)
        self.status_label.configure(foreground=color)

    def _load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {"default_close_action": None}

    def _save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _show_close_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("退出确认")
        dialog.geometry("340x180")
        dialog.resizable(False, False)
        dialog.configure(bg='#F5F5F7')
        dialog.transient(self.root)
        dialog.grab_set()

        x = self.root.winfo_x() + (self.root.winfo_width() - 340) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 180) // 2
        dialog.geometry(f"+{x}+{y}")

        result = {"action": None}

        main_frame = tk.Frame(dialog, bg='#F5F5F7', padx=30, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        title = tk.Label(main_frame, text="选择操作", font=('SF Pro Display', 17, 'bold'),
                        bg='#F5F5F7', fg='#1D1D1F')
        title.pack(pady=(0, 20))

        btn_frame = tk.Frame(main_frame, bg='#F5F5F7')
        btn_frame.pack(pady=(0, 15))

        def on_minimize():
            result["action"] = "minimize"
            dialog.destroy()

        def on_exit():
            result["action"] = "exit"
            dialog.destroy()

        minimize_btn = tk.Button(btn_frame, text="最小化到托盘", font=('SF Pro Text', 13, 'bold'),
                                bg='#007AFF', fg='white', relief=tk.FLAT, cursor='hand2',
                                padx=20, pady=10, command=on_minimize, bd=0)
        minimize_btn.pack(side=tk.LEFT, padx=5)

        exit_btn = tk.Button(btn_frame, text="退出程序", font=('SF Pro Text', 13, 'bold'),
                            bg='#FF3B30', fg='white', relief=tk.FLAT, cursor='hand2',
                            padx=20, pady=10, command=on_exit, bd=0)
        exit_btn.pack(side=tk.LEFT, padx=5)

        skip_var = tk.BooleanVar()
        skip_check = tk.Checkbutton(main_frame, text="记住我的选择，下次不再询问",
                                    variable=skip_var, bg='#F5F5F7', font=('SF Pro Text', 11),
                                    fg='#8E8E93', selectcolor='#F5F5F7')
        skip_check.pack()

        dialog.wait_window()

        if skip_var.get() and result["action"]:
            self.config["default_close_action"] = result["action"]
            self._save_config()

        return result["action"]

    def _create_tray_icon(self):
        icon_path = "icon.ico"
        if os.path.exists(icon_path):
            icon_image = Image.open(icon_path)
        else:
            icon_image = Image.new('RGB', (64, 64), color='blue')

        menu = pystray.Menu(
            item('显示窗口', self._show_window, default=True),
            item('退出', self._quit_app)
        )
        self.tray_icon = pystray.Icon("VoiceSync", icon_image, "语音输入", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _show_window(self):
        def show():
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        self.root.after(0, show)

    def _quit_app(self):
        if self.tray_icon:
            self.tray_icon.stop()
        if self.http_server:
            self.http_server.shutdown()
        self.root.after(0, self.root.destroy)

    def _on_close(self):
        default_action = self.config.get("default_close_action")

        if default_action:
            action = default_action
        else:
            action = self._show_close_dialog()

        if action == "minimize":
            self.root.withdraw()
            if not self.tray_icon:
                self._create_tray_icon()
        elif action == "exit":
            if self.http_server:
                self.http_server.shutdown()
            self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    app = VoiceSyncApp()
    app.run()


if __name__ == "__main__":
    main()
