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
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            flex-direction: column;
            padding: 16px;
        }
        .status {
            text-align: center;
            padding: 12px 16px;
            border-radius: 12px;
            margin-bottom: 16px;
            font-size: 14px;
            font-weight: 500;
            flex-shrink: 0;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
        }
        .status.connected {
            background: rgba(72, 187, 120, 0.9);
            color: white;
            box-shadow: 0 4px 15px rgba(72, 187, 120, 0.4);
        }
        .status.disconnected {
            background: rgba(245, 101, 101, 0.9);
            color: white;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        textarea {
            flex: 1;
            width: 100%;
            padding: 16px;
            font-size: 17px;
            line-height: 1.5;
            border: none;
            border-radius: 16px;
            resize: none;
            outline: none;
            background: rgba(255, 255, 255, 0.95);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            transition: box-shadow 0.3s ease;
        }
        textarea:focus {
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15), 0 0 0 3px rgba(102, 126, 234, 0.5);
        }
        textarea::placeholder { color: #a0aec0; }
        .clear-btn {
            margin-top: 12px;
            padding: 14px;
            font-size: 15px;
            font-weight: 500;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 12px;
            flex-shrink: 0;
            backdrop-filter: blur(10px);
            transition: all 0.2s ease;
            cursor: pointer;
        }
        .clear-btn:active {
            transform: scale(0.97);
            background: rgba(255, 255, 255, 0.3);
        }
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(4px);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1000;
            opacity: 0;
            visibility: hidden;
            transition: all 0.25s ease;
        }
        .modal-overlay.show {
            opacity: 1;
            visibility: visible;
        }
        .modal {
            background: white;
            padding: 28px 24px;
            border-radius: 20px;
            width: 90%;
            max-width: 320px;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            transform: scale(0.9) translateY(20px);
            transition: transform 0.25s ease;
        }
        .modal-overlay.show .modal {
            transform: scale(1) translateY(0);
        }
        .modal h3 {
            margin-bottom: 8px;
            font-size: 18px;
            font-weight: 600;
            color: #1a202c;
        }
        .modal p {
            margin-bottom: 24px;
            font-size: 14px;
            color: #718096;
        }
        .modal-btns {
            display: flex;
            gap: 12px;
        }
        .modal-btn {
            flex: 1;
            padding: 14px;
            font-size: 15px;
            font-weight: 500;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .modal-btn:active { transform: scale(0.96); }
        .modal-btn.primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }
        .modal-btn.secondary {
            background: #edf2f7;
            color: #4a5568;
        }
    </style>
</head>
<body>
    <div class="status disconnected" id="status">连接中...</div>
    <textarea id="input" placeholder="点击这里，使用语音输入..."></textarea>
    <button class="clear-btn" id="clearBtn">清空并开始新输入</button>

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
            // 新对话时用窗口切换时记录的已同步文本计算增量
            const baseText = newWindow ? windowSwitchSyncedText : syncedText;
            const newText = text.slice(baseText.length);
            if (newText) {
                send({type: 'confirm_send', text: newText, new_window: newWindow});
            }
            if (newWindow) {
                // 新对话：清空输入框，重置状态
                inputEl.value = '';
                syncedText = '';
                syncedCursor = 0;
                inputEl.focus();
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
            sendTimer = setTimeout(processChange, 600);
        });

        clearBtn.addEventListener('click', () => {
            inputEl.value = '';
            syncedText = '';
            syncedCursor = 0;
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

    for name, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            ip = addr.address
            # 过滤 127.x.x.x 和 169.254.x.x (APIPA)
            if addr.family == socket.AF_INET and not ip.startswith("127.") and not ip.startswith("169.254."):
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


class VoiceInputApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("语音输入")
        self.root.resizable(False, False)
        self.root.configure(bg='#f8f9fa')

        self.port_http = find_available_port(8765)
        self.port_ws = self.port_http + 1
        self.all_ips = get_all_ips()
        self.current_ip_index = 0

        self.connected_clients = 0
        self.ws_server = None
        self.http_server = None
        self.last_window_handle = None

        self._setup_ui()
        self._start_servers()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _get_current_url(self) -> str:
        _, ip = self.all_ips[self.current_ip_index]
        return f"http://{ip}:{self.port_http}"

    def _setup_ui(self):
        style = ttk.Style()
        style.configure('Title.TLabel', font=('Segoe UI', 16, 'bold'), background='#f8f9fa', foreground='#1a202c')
        style.configure('Url.TLabel', font=('Consolas', 11), background='#f8f9fa', foreground='#667eea')
        style.configure('Status.TLabel', font=('Segoe UI', 12), background='#f8f9fa')
        style.configure('Main.TFrame', background='#f8f9fa')
        style.configure('QR.TFrame', background='white')

        main_frame = ttk.Frame(self.root, padding=30, style='Main.TFrame')
        main_frame.pack()

        title_label = ttk.Label(main_frame, text="手机扫码连接", style='Title.TLabel')
        title_label.pack(pady=(0, 15))

        # 网卡选择下拉框
        if len(self.all_ips) > 1:
            ip_frame = tk.Frame(main_frame, bg='#f8f9fa')
            ip_frame.pack(pady=(0, 15))
            tk.Label(ip_frame, text="网卡:", bg='#f8f9fa', font=('Segoe UI', 10)).pack(side=tk.LEFT)
            self.ip_var = tk.StringVar()
            ip_options = [f"{name} ({ip})" for name, ip in self.all_ips]
            self.ip_var.set(ip_options[0])
            ip_menu = ttk.Combobox(ip_frame, textvariable=self.ip_var, values=ip_options,
                                   state='readonly', width=30)
            ip_menu.pack(side=tk.LEFT, padx=(5, 0))
            ip_menu.bind('<<ComboboxSelected>>', self._on_ip_change)

        self.qr_container = tk.Frame(main_frame, bg='white', padx=12, pady=12,
                                     highlightbackground='#e2e8f0', highlightthickness=1)
        self.qr_container.pack()

        self.qr_label = tk.Label(self.qr_container, bg='white')
        self.qr_label.pack()
        self._update_qr()

        self.url_var = tk.StringVar(value=self._get_current_url())
        url_label = ttk.Label(main_frame, textvariable=self.url_var, style='Url.TLabel')
        url_label.pack(pady=(15, 8))

        self.status_var = tk.StringVar(value="等待连接...")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, style='Status.TLabel')
        self.status_label.pack(pady=(8, 0))

    def _update_qr(self):
        url = self._get_current_url()
        qr = qrcode.QRCode(box_size=7, border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="#1a202c", back_color="white")

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

            elif msg_type == 'insert':
                if self.last_window_handle is None:
                    self.last_window_handle = get_window_handle()
                type_text(data.get('text', ''))

            elif msg_type == 'delete':
                if self.last_window_handle:
                    activate_window(self.last_window_handle)
                    time.sleep(0.1)
                delete_text(data.get('count', 0))

        except json.JSONDecodeError:
            type_text(message)

    def _update_status(self):
        if self.connected_clients > 0:
            text = f"已连接 ({self.connected_clients} 台设备)"
            color = '#48bb78'
        else:
            text = "等待连接..."
            color = '#a0aec0'
        self.root.after(0, lambda: self._set_status(text, color))

    def _set_status(self, text, color):
        self.status_var.set(text)
        self.status_label.configure(foreground=color)

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
