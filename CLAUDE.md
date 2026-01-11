# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

手机语音输入同步工具 - 通过局域网将手机上的语音输入实时同步到电脑光标位置。

## 技术架构

- 单文件架构: `server.py` 包含所有逻辑和内嵌 HTML
- HTTP Server (默认 8765): 提供移动端网页界面
- WebSocket Server (HTTP端口+1): 接收文本并通过剪贴板粘贴到光标位置
- 端口自动发现: 若默认端口被占用，自动查找连续可用端口
- 跨平台支持: Windows (pywin32), macOS (osascript), Linux (xdotool)

## 常用命令

```bash
# 安装依赖 (Python 3.11+)
pip install -r requirements.txt

# 启动服务
python server.py

# 本地构建可执行文件
pyinstaller --onefile --windowed --name "VoiceInput" server.py
# Linux 不加 --windowed，需先安装 xdotool
```

## 平台依赖

- Windows: pywin32 (自动安装)
- macOS: 无额外依赖
- Linux: `sudo apt-get install xdotool`

## CI/CD

GitHub Actions 自动构建 (`.github/workflows/build.yml`):
- 推送 `v*` 标签触发多平台构建
- 产物: Windows (.exe), macOS (.app), Linux (binary)

## 核心逻辑

- `VoiceInputApp`: 主应用类，管理 tkinter GUI 和双服务器生命周期
- `HTML_PAGE`: 内嵌移动端网页，600ms 防抖后通过 WebSocket 发送增量文本
- `type_text()`: 自动识别终端进程，终端用 Ctrl+Shift+V，普通窗口用 Ctrl+V
- 窗口切换检测: 记录 `last_window_handle`，切换时弹窗让用户选择"新对话"或"返回原窗口"
- `get_all_ips()`: 获取所有网卡 IP，默认路由 IP 排在最前

## WebSocket 消息协议

客户端 → 服务端:
- `{type: 'check_window'}`: 检查目标窗口是否切换
- `{type: 'confirm_send', text, new_window}`: 确认发送文本
- `{type: 'switch_back'}`: 请求切回原窗口
- `{type: 'insert', text}`: 直接插入文本
- `{type: 'delete', count}`: 删除末尾字符

服务端 → 客户端:
- `{type: 'window_status', changed, window_name}`: 窗口状态响应
- `{type: 'switched_back', success}`: 窗口切换结果
