# AgentBell

Windows 系统托盘通知工具，为 Claude Code CLI 提供桌面通知、状态监控和 hooks 配置管理。

当 Claude Code 需要你授权工具调用、等待输入或完成任务时，AgentBell 在系统托盘弹出暖色系 Toast 通知并播放提示音。

## 功能

- **系统托盘常驻**：橙色 >_ 图标常驻托盘，实时显示运行状态
- **Toast 弹窗通知**：授权提醒、等待输入、任务完成、错误通知四种类型
- **最近事件面板**：左键点击托盘图标查看最近 20 条事件记录
- **右键菜单**：最近事件、静音 30 分钟、设置、关于、重启、退出
- **设置管理**：一键安装/卸载 Claude Code hooks，可视化编辑 settings.json
- **配置状态检测**：自动检测 hooks 配置状态，未配置时显示红色"待配置"
- **多会话聚合**：多个 Claude Code 会话同时触发时合并通知
- **暗色主题 UI**：Claude/Anthropic 暖色系设计语言，圆角暗色面板

## 快速开始（推荐）

### 1. 下载

从 [GitHub Release](https://github.com/ice268528/AgentBell/releases/tag/v1.0.0) 下载 `AgentBell-v1.0.0-win64.zip`，解压到任意目录。

解压后目录结构：
```
AgentBell/
├── AgentBell.exe        ← 主程序（托盘守护进程）
├── AgentBellCLI.exe     ← 命令行工具
└── _internal/           ← 依赖文件（不要删除）
```

### 2. 启动

双击 `AgentBell.exe`，系统托盘出现橙色 >_ 图标：
- **左键点击**：打开最近事件面板
- **右键点击**：打开菜单

首次启动时状态显示红色"待配置"，表示尚未安装 hooks。

### 3. 安装 hooks

右键菜单 → 设置 → 点击"安装 Hooks"。

安装前自动备份 `~/.claude/settings.json`，安装后状态变为绿色"已配置"。

### 4. 完成

之后使用 Claude Code 时，AgentBell 会自动弹出通知提醒。无需手动启动 daemon——安装 hooks 后，Claude Code 触发事件时会自动启动 AgentBell（如果未运行）。

### 测试通知

右键菜单 → 设置 → 命令行运行：
```bash
AgentBellCLI.exe test
```
看到 Toast 弹窗并听到提示音即表示工作正常。

## 从源码安装

需要 Python 3.10+ 和 [uv](https://docs.astral.sh/uv/)：

```bash
git clone git@github.com:ice268528/AgentBell.git
cd AgentBell
uv sync

# 启动
uv run agentbell daemon

# 安装 hooks
uv run agentbell install-claude-hooks

# 测试
uv run agentbell test
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `AgentBellCLI.exe daemon` | 启动托盘守护进程 |
| `AgentBellCLI.exe test` | 发送测试通知 |
| `AgentBellCLI.exe test --style done` | 测试完成风格 |
| `AgentBellCLI.exe test --style error` | 测试错误风格 |
| `AgentBellCLI.exe test --style waiting_input` | 测试等待输入风格 |
| `AgentBellCLI.exe install-claude-hooks` | 安装 Claude Code hooks |
| `AgentBellCLI.exe uninstall-claude-hooks` | 卸载 Claude Code hooks |

## 托盘菜单

| 菜单项 | 说明 |
|--------|------|
| 最近事件 | 查看最近 20 条事件，红点显示待授权数量 |
| 静音 30 分钟 | 暂停所有通知 |
| 设置 | 安装/卸载 hooks，编辑 settings.json |
| 关于 AgentBell | 版本和项目信息 |
| 重启 | 重启 AgentBell 守护进程 |
| 退出 AgentBell | 关闭托盘图标和守护进程 |

## 设置窗口

右键菜单 → 设置，可以：
- 查看 hooks 配置状态（绿色"已配置" / 红色"未配置"）
- 一键安装或卸载 hooks
- 可编辑、可滚动的 settings.json 编辑器
- 修改后点击"保存"，自动验证 JSON 格式

## 设计风格

使用 Anthropic 官方配色：

| 颜色 | 用途 |
|------|------|
| `#141413` / `#181816` | 深色背景 |
| `#d97757` | 橙色强调 |
| `#faf9f5` | 浅色文字 |
| `#b0aea5` | 灰色次要文字 |
| `#788c5d` | 绿色（已完成/运行中） |
| `#c45f4f` | 红色（错误/待配置） |
| `#6a9bcc` | 蓝色（等待输入） |

## 项目结构

```
AgentBell/
├── src/agentbell/
│   ├── __main__.py          # python -m agentbell 入口
│   ├── cli.py               # CLI 命令（click）
│   ├── daemon.py            # HTTP 服务 + 事件路由
│   ├── tray.py              # 系统托盘图标
│   ├── toast_renderer.py    # Toast 弹窗渲染
│   ├── event_store.py       # 事件持久化存储
│   ├── hook_sender.py       # Claude Code hook 转发器
│   ├── claude_hooks.py      # hooks 安装/卸载
│   ├── theme.py             # 设计 token
│   └── ui/
│       ├── tray_menu.py     # 右键菜单面板
│       ├── recent_events_window.py  # 最近事件窗口
│       ├── settings_window.py       # 设置/关于窗口
│       ├── icons.py         # 托盘图标生成
│       └── theme.py         # UI 常量和颜色
├── scripts/                 # 构建脚本和入口
├── docs/                    # 文档
├── pyproject.toml
└── README.md
```

## 常见问题

### 没有通知出现？

1. 检查 Windows 通知设置是否开启
2. 检查专注助手 / 免打扰是否关闭
3. 确认 hooks 已安装：右键菜单 → 设置 → 查看状态
4. 查看日志：`%USERPROFILE%\.agentbell\logs\`

### 托盘图标不显示？

1. 确认 `AgentBell.exe` 正在运行（任务管理器查看进程）
2. 检查 Windows 任务栏设置中是否隐藏了图标

### 需要手动启动 AgentBell 吗？

首次使用需要手动启动 `AgentBell.exe` 并安装 hooks。安装 hooks 后，Claude Code 触发事件时会自动启动 AgentBell（如果未运行），无需手动管理。已运行时不会重复启动。

## 许可证

MIT License
