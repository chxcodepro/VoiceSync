# 手机语音输入同步工具

通过局域网将手机上的语音输入实时同步到电脑光标位置。

## 功能

- 手机扫码连接，无需安装 App
- 语音输入实时同步到电脑任意光标位置
- 自动识别终端，使用正确的粘贴快捷键
- 窗口切换检测，支持多窗口输入
- 多网卡支持，可选择连接的网络
- 自动检测更新，一键升级到最新版本

## 使用方法

```bash
# 安装依赖
pip install -r requirements.txt

# 启动
python server.py
```

手机扫描二维码，在网页中使用语音输入即可。

## 下载

前往 [Releases](../../releases) 下载 Windows 可执行文件，无需安装 Python 环境。

## 平台支持

仅支持 Windows 平台。

## 技术栈

- **核心**: Python 3.11+
- **GUI**: tkinter
- **通信**: WebSocket (websockets) + HTTP Server
- **依赖**: pyautogui, pyperclip, qrcode, Pillow, psutil, pywin32

## 开发

```bash
# 克隆项目
git clone https://github.com/chxcodepro/device_voice_input.git
cd device_voice_input

# 安装依赖
pip install -r requirements.txt

# 运行
python server.py

# 构建可执行文件
pyinstaller --onefile --windowed --name "VoiceInput" --icon icon.ico server.py
```

构建产物位于 `dist/VoiceInput.exe`。
