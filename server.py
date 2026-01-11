"""手机语音输入同步到电脑光标 - GUI版"""

import asyncio
import io
import json
import platform
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from http.server import HTTPServer, SimpleHTTPRequestHandler
from tkinter import ttk

import pyautogui
import pyperclip
import qrcode
from PIL import Image, ImageTk
import websockets

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
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: #f5f5f5;
            display: flex;
            flex-direction: column;
            padding: 15px;
        }
        .status {
            text-align: center;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 15px;
            font-size: 14px;
            flex-shrink: 0;
        }
        .status.connected { background: #d4edda; color: #155724; }
        .status.disconnected { background: #f8d7da; color: #721c24; }
        textarea {
            flex: 1;
            width: 100%;
            padding: 15px;
            font-size: 18px;
            border: 2px solid #ddd;
            border-radius: 12px;
            resize: none;
            outline: none;
        }
        textarea:focus { border-color: #007bff; }
        .clear-btn {
            margin-top: 10px;
            padding: 12px;
            font-size: 16px;
            background: #6c757d;
            color: white;
            border: none;
            border-radius: 8px;
            flex-shrink: 0;
        }
    </style>
</head>
<body>
    <div class="status disconnected" id="status">连接中...</div>
    <textarea id="input" placeholder="点击这里，使用语音输入..."></textarea>
    <button class="clear-btn" id="clearBtn">清空并开始新输入</button>
    <script>
        const wsUrl = `ws://${location.hostname}:${parseInt(location.port) + 1}`;
        let ws = null, sendTimer = null;
        let syncedText = '';
        let syncedCursor = 0;
        const statusEl = document.getElementById('status');
        const inputEl = document.getElementById('input');
        const clearBtn = document.getElementById('clearBtn');

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
        }

        function send(msg) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify(msg));
            }
        }

        function processChange() {
            const text = inputEl.value;
            const cursor = inputEl.selectionStart;

            if (text === syncedText && cursor === syncedCursor) return;

            if (text.length > syncedText.length && text.startsWith(syncedText)) {
                const newText = text.slice(syncedText.length);
                send({type: 'insert', text: newText});
                syncedText = text;
                syncedCursor = cursor;
            } else if (text.length < syncedText.length && syncedText.startsWith(text)) {
                const deleteCount = syncedText.length - text.length;
                const deleteFromEnd = syncedCursor - cursor;
                if (deleteFromEnd >= 0 && deleteFromEnd <= deleteCount) {
                    const moveLeft = syncedText.length - syncedCursor;
                    send({type: 'delete', move: moveLeft, count: deleteCount});
                    syncedText = text;
                    syncedCursor = cursor;
                }
            } else {
                const newText = text.slice(syncedText.length);
                if (newText && text.startsWith(syncedText)) {
                    send({type: 'insert', text: newText});
                    syncedText = text;
                    syncedCursor = cursor;
                }
            }
        }

        inputEl.addEventListener('input', () => {
            clearTimeout(sendTimer);
            sendTimer = setTimeout(processChange, 600);
        });

        clearBtn.addEventListener('click', () => {
            inputEl.value = '';
            syncedText = '';
            syncedCursor = 0;
        });

        connect();
    </script>
</body>
</html>"""


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


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


def delete_text(move_left: int, count: int):
    """删除文字：先移动光标到指定位置，再执行退格"""
    if move_left > 0:
        for _ in range(move_left):
            pyautogui.press('right')
    for _ in range(count):
        pyautogui.press('backspace')


def handle_message(message: str):
    """处理 WebSocket 消息"""
    try:
        data = json.loads(message)
        msg_type = data.get('type')
        if msg_type == 'insert':
            type_text(data.get('text', ''))
        elif msg_type == 'delete':
            delete_text(data.get('move', 0), data.get('count', 0))
    except json.JSONDecodeError:
        type_text(message)


class HttpHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode("utf-8"))

    def log_message(self, format, *args):
        pass


class VoiceInputApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("语音输入")
        self.root.resizable(False, False)

        self.port_http = find_available_port(8765)
        self.port_ws = self.port_http + 1
        self.local_ip = get_local_ip()
        self.url = f"http://{self.local_ip}:{self.port_http}"

        self.connected_clients = 0
        self.ws_server = None
        self.http_server = None

        self._setup_ui()
        self._start_servers()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_ui(self):
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack()

        title_label = ttk.Label(main_frame, text="手机扫码连接", font=("", 14, "bold"))
        title_label.pack(pady=(0, 15))

        qr_frame = ttk.Frame(main_frame)
        qr_frame.pack()

        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(self.url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        img_byte_arr = io.BytesIO()
        qr_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        pil_img = Image.open(img_byte_arr)
        self.qr_photo = ImageTk.PhotoImage(pil_img)

        qr_label = ttk.Label(qr_frame, image=self.qr_photo)
        qr_label.pack()

        url_label = ttk.Label(main_frame, text=self.url, font=("", 10))
        url_label.pack(pady=(10, 5))

        self.status_var = tk.StringVar(value="等待连接...")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, font=("", 11))
        self.status_label.pack(pady=(10, 0))

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
                handle_message(message)
        finally:
            self.connected_clients -= 1
            self._update_status()

    def _update_status(self):
        if self.connected_clients > 0:
            text = f"已连接 ({self.connected_clients} 台设备)"
        else:
            text = "等待连接..."
        self.root.after(0, lambda: self.status_var.set(text))

    def _on_close(self):
        if self.http_server:
            self.http_server.shutdown()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    app = VoiceInputApp()
    app.run()


if __name__ == "__main__":
    main()
