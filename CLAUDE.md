# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

手机语音输入同步工具 - 通过局域网将手机上的语音输入实时同步到电脑光标位置。

## 技术架构

- HTTP Server (端口 8765): 提供移动端网页界面
- WebSocket Server (端口 8766): 接收文本并通过剪贴板粘贴到光标位置
- 单文件架构: `server.py` 包含所有逻辑和内嵌 HTML

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python server.py

# 构建可执行文件
# Windows
pyinstaller --onefile --windowed --name "VoiceInput" server.py

# macOS
pyinstaller --onefile --windowed --name "VoiceInput" server.py

# Linux (需先安装 xdotool: sudo apt-get install xdotool)
pyinstaller --onefile --name "VoiceInput" server.py
```

## 关键依赖

- `websockets`: WebSocket 服务端
- `pyperclip` + `pyautogui`: 剪贴板操作和模拟按键
- `qrcode` + `Pillow`: 二维码生成和 GUI 显示
- `pywin32`: Windows 下获取活动窗口进程（仅 Windows）
- `psutil`: 跨平台进程信息获取

## 工作流程

1. 启动后在终端显示二维码
2. 手机扫码访问网页
3. 网页通过 WebSocket 连接服务端
4. 输入框内容在 600ms 无输入后自动发送
5. 服务端通过 pyperclip + pyautogui 粘贴到当前光标
