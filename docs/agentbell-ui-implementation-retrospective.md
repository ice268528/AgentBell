# AgentBell UI 实现复盘

> 生成日期：2026-06-10

---

## 1. 最终实现了什么

- **Event Store 持久化**：JSON 文件存储（`~/.agentbell/events.json`），daemon 重启后事件不丢失
- **自定义托盘菜单**：深色 Claude Theme，Header 橙色 `>_` 图标 + "AgentBell" + 运行状态
- **自定义最近事件窗口**：深色卡片式事件列表，三行结构（状态+时间 / session·event / 描述）
- **自定义托盘图标**：橙色圆角方块 + 白色 `>_`，支持 default/badge/muted 三种状态
- **Toast 通知**：左侧图标 + 标题 + 描述 + project pill + 按钮，8 秒自动消失
- **preview-ui 命令**：展示所有 toast 类型的验收工具

---

## 2. 踩过的坑和弯路

### 2.1 PowerShell 失败
- Windows 受限语言模式阻止 WinRT 类型 → 改用 ctypes Shell_NotifyIconW → 再改用自定义 GDI 窗口

### 2.2 窗口不可见
- SetWindowPos 从 WNDPROC 调用返回 0 → 改用 MoveWindow

### 2.3 输入中断
- 缺少 WS_EX_NOACTIVATE → 添加窗口扩展样式

### 2.4 白色方块
- 系统默认背景穿透 → 填充整个窗口背景 + NULL_PEN

### 2.5 RLock 死锁
- SessionRegistry.update() 调用 get_or_create()，两者都获取 threading.Lock() → 改用 RLock

### 2.6 声音不播放
- daemon 线程在进程退出时被杀死 → 将声音播放移入子进程

---

## 3. 错误做法记录

| 错误做法 | 正确做法 |
|----------|----------|
| 用 notify 绕过 daemon 直接弹窗 | hooks 必须走 hook-sender → daemon |
| 用 QMessageBox 做最近事件 | 自定义 GDI 深色窗口 |
| 用默认 QMenu / 蓝色 info 图标 | 自定义深色菜单 + 橙色 `>_` 图标 |
| 写假按钮（"打开 Claude Code"、"立即授权"） | 只放有真实 handler 的按钮 |
| 把 Stop 当任务完成 | Stop 不显示任务完成 |
| 只做测试 UI，没接真实 Event Store | EventStore 持久化 + daemon 统一管理 |

---

## 4. 最终正确架构

```
Claude Code hooks
  ↓ (stdin JSON)
hook-sender
  ↓ (HTTP POST)
agentbell daemon (127.0.0.1:37371)
  ├── EventRouter → 路由事件
  ├── EventStore → 持久化存储（JSON）
  ├── SessionRegistry → 实时状态
  ├── EventLogger → JSONL 日志
  ├── Toast → pythonw.exe 子进程
  ├── TrayIcon → 自定义 GDI 图标
  ├── TrayMenu → 自定义 GDI 菜单
  └── RecentEventsWindow → 自定义 GDI 窗口
```

---

## 5. UI 后续维护规则

1. 所有颜色集中到 `ui/theme.py`，不要硬编码
2. 不使用 QMessageBox、QMenu 等系统默认控件
3. 不使用蓝色 info 图标
4. 所有按钮必须有真实 handler
5. Stop 事件不能显示任务完成
6. 新事件类型必须在 EventRouter 中注册
7. Toast 去重窗口 5 秒

---

## 6. 本地验证命令

```bash
# 启动 daemon（带托盘图标）
uv run agentbell daemon

# 发送测试 toast
uv run agentbell test --style permission
uv run agentbell test --style waiting_input
uv run agentbell test --style done
uv run agentbell test --style error

# 预览所有 UI
uv run agentbell preview-ui

# 通过 hook-sender 模拟真实事件
echo '{"hook_event_name":"PermissionRequest","session_id":"test","cwd":"E:/test"}' | uv run agentbell hook-sender
```

---

## 7. 修改文件列表

| 文件 | 变更 |
|------|------|
| `src/agentbell/event_store.py` | **新增** - Event Store 持久化 |
| `src/agentbell/ui/theme.py` | **新增** - 统一 Claude 色板 |
| `src/agentbell/ui/icons.py` | **新增** - 自定义托盘图标 |
| `src/agentbell/ui/tray_menu.py` | **新增** - 自定义托盘菜单 |
| `src/agentbell/ui/recent_events_window.py` | **新增** - 自定义最近事件窗口 |
| `src/agentbell/daemon.py` | **修改** - 集成 EventStore，去重 5s |
| `src/agentbell/tray.py` | **修改** - 使用新 UI 组件 |
| `src/agentbell/toast_renderer.py` | **修改** - 添加 project pill |
| `src/agentbell/cli.py` | **修改** - 添加 preview-ui 命令 |

---

## 8. 仍未完成的限制

1. **托盘图标多尺寸**：当前仅 16x16，24/32/48 需要 .ico 生成支持
2. **卡片 hover 效果**：GDI 实现 hover 需要跟踪鼠标位置，当前为静态
3. **Toast 动画**：滑入/滑出动画需要 WM_TIMER + MoveWindow 实现
4. **设置/关于菜单**：暂未实现，菜单项已隐藏
