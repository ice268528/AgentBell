# AgentBell UI 重设计目标文档

> 目标：把当前 Windows 默认 MessageBox / QMenu 风格的 AgentBell，重做成一个接近 Claude / Anthropic 暖黑色系的后台通知中心。本文档用于发给 Codex 作为实现目标。

---

## 0. 当前问题

当前 AgentBell 的 UI 主要问题：

1. **最近事件窗口太丑**：现在像 Windows 默认 `QMessageBox`，有蓝色 info 图标、白底窗口、系统默认按钮，不符合 AgentBell / Claude Code 工具气质。
2. **托盘菜单太系统默认**：右键菜单是白底默认菜单，和前面设计的 Claude 暖黑色 Toast 完全不统一。
3. **托盘图标太弱**：当前图标像系统默认 info 提示，不像一个独立应用，也没有状态区分。
4. **信息展示太粗糙**：最近事件只有两行文本，无法清楚区分 session、事件类型、时间、状态和来源。
5. **视觉体系不统一**：Toast、最近事件、托盘菜单、托盘图标之间没有统一 Theme Token。

本轮不要求新增复杂功能，重点是 **UI 收口 + 图标重做 + 最近事件面板重做 + 托盘菜单重做**。

---

## 1. 设计定位

AgentBell 不是 Claude Code 本体，也不是桌面版 Claude Code。它的定位是：

> Claude Code CLI 的本地后台提醒中心。

它应该像一个常驻托盘小工具：

- 静默常驻后台；
- 接收 Claude Code hooks 事件；
- 用 Toast 提醒用户；
- 在托盘里提供最近事件列表；
- 不抢焦点；
- 不伪造“打开 Claude Code / 自动授权 / 查看结果”这种本工具没有的能力。

视觉关键词：

- Claude / Anthropic 暖色系；
- 深色、克制、开发者工具感；
- 低饱和橙色强调；
- 卡片式事件列表；
- 不使用 Windows 默认 MessageBox；
- 不使用大面积蓝色 info 图标；
- 不使用系统默认白底 QMenu。

---

## 2. 参考依据

### 2.1 Claude Code hooks 事件依据

Claude Code hooks 支持 command hook 和 HTTP hook。官方文档说明：command hook 的输入通过 `stdin` 传入，HTTP hook 的输入作为 POST body 传入。hook lifecycle 中也包含 `PermissionRequest`、`Notification`、`TaskCompleted`、`Stop` 等事件。

实现时要保持此前确定的架构：

- `agentbell daemon` 常驻；
- hook 事件进入 daemon；
- daemon 统一管理 toast / tray / recent events；
- 不要让 hook 每次直接启动完整 UI。

参考：

- https://code.claude.com/docs/en/hooks

### 2.2 Claude / Anthropic 配色依据

使用 Anthropic brand style 里这组颜色：

```css
--claude-dark: #141413;
--claude-light: #faf9f5;
--claude-mid-gray: #b0aea5;
--claude-light-gray: #e8e6dc;
--claude-orange: #d97757;
--claude-blue: #6a9bcc;
--claude-green: #788c5d;
```

参考：

- https://github.com/anthropics/skills/blob/main/skills/brand-guidelines/SKILL.md

---

## 3. 总体 UI 架构

当前项目大概率已有这些模块：

```text
src/agentbell/daemon.py
src/agentbell/hook_sender.py
src/agentbell/tray.py
src/agentbell/toast_renderer.py
src/agentbell/cli.py
```

本轮建议新增或重构：

```text
src/agentbell/ui/theme.py
src/agentbell/ui/icons.py
src/agentbell/ui/recent_events_window.py
src/agentbell/ui/tray_menu.py
src/agentbell/ui/components.py
src/agentbell/ui/assets/
```

如果项目暂时不想新增这么多文件，可以合并实现，但必须保持以下原则：

- 所有颜色、字号、圆角、阴影集中到 theme；
- 托盘图标统一从 `icons.py` 或 `assets` 获取；
- 最近事件窗口不能使用 `QMessageBox`；
- 托盘菜单不能继续使用默认白底系统菜单作为主要 UI。

---

## 4. Theme Token

新增统一主题文件，例如：

```text
src/agentbell/ui/theme.py
```

示例：

```python
CLAUDE_THEME = {
    "dark": "#141413",
    "bg": "#181816",
    "bg_elevated": "#20201d",
    "bg_card": "rgba(250, 249, 245, 0.055)",
    "light": "#faf9f5",
    "text_primary": "#faf9f5",
    "text_secondary": "#b0aea5",
    "text_muted": "rgba(250, 249, 245, 0.58)",
    "border": "rgba(250, 249, 245, 0.12)",
    "border_soft": "rgba(250, 249, 245, 0.08)",
    "orange": "#d97757",
    "orange_hover": "#e38a6b",
    "orange_pressed": "#c76645",
    "green": "#788c5d",
    "blue": "#6a9bcc",
    "red": "#c45f4f",
}

RADIUS = {
    "window": 18,
    "card": 14,
    "button": 10,
    "icon": 12,
    "pill": 999,
}

SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
}
```

字体建议：

```python
FONT_STACK = 'Inter, "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif'
```

Windows 下可以优先使用：

- `Segoe UI`：英文和系统 UI；
- `Microsoft YaHei UI`：中文；
- 不要强制依赖用户未安装的字体。

---

## 5. 托盘图标设计

### 5.1 目标

当前托盘图标像系统默认 info 图标，必须替换。

新图标应该表达：

- AgentBell；
- 后台提醒；
- Claude Code 开发者工具；
- 有事件时可显示 badge。

### 5.2 图标方案

推荐图标：

```text
深色圆角方块 + Claude 橙色铃铛 / 终端符号 >_
```

默认态：

- 背景：`#141413` 或透明；
- 主图形：Claude Orange `#d97757`；
- 细节：`#faf9f5`；
- 外形：圆角方块或圆形；
- 尺寸：16x16、24x24、32x32、48x48、256x256；
- Windows 打包建议生成 `.ico`。

有未读事件态：

- 右上角显示小圆点 / 数字 badge；
- badge 背景：`#d97757`；
- 数字颜色：`#faf9f5`；
- 1-9 显示数字，超过 9 显示 `9+`。

静音态：

- 图标透明度降低；
- 或显示斜杠铃铛；
- 不要用系统灰色默认图标。

### 5.3 图标实现建议

优先使用代码生成图标，避免外部资源丢失。

建议在 `src/agentbell/ui/icons.py` 中生成 `QIcon`：

- 使用 `QPixmap` + `QPainter`；
- 绘制圆角背景；
- 绘制铃铛或 `>_`；
- 根据 unread_count 绘制 badge；
- 输出 `QIcon` 给 `QSystemTrayIcon`。

不要继续使用：

- Windows 默认 information icon；
- 蓝色 info icon；
- 白底图标；
- 图片加载失败后的空白占位。

---

## 5.4 图标视觉参考（来自设计图）

图片中的托盘图标在任务栏中显示为一个小型橙色图形，辨识度高。在托盘菜单 Header 中，图标为橙色圆角方块背景上的白色 `>_` 终端符号，具体：

- 图标底板：橙色 `#d97757` 圆角方块（约 28x28px）；
- 图形：白色 `>_` 终端提示符，线条粗细约 2px；
- 整体风格：简洁、开发者工具感，与 Claude Code 终端文化一致；
- 任务栏小尺寸（16x16）时只保留图形轮廓，底板不可见；
- 任务栏大尺寸（24x24+）时底板和图形均可见。

---

## 6. 托盘菜单设计

### 6.1 当前问题

现在托盘菜单是系统默认白底：

```text
最近事件
静音 30 分钟
退出 AgentBell
```

这个太像普通 Windows 程序，和 AgentBell 的 Claude 暖黑主题不一致。

### 6.2 推荐做法

有两个实现方案。

#### 方案 A：自定义无边框 Popup，推荐

不要依赖 `QMenu` 的系统绘制。右键托盘时显示一个自定义 `QWidget` / `QFrame` Popup。

优点：

- 可完全控制背景、圆角、阴影、hover；
- 可以加 header、状态点、badge；
- 与 Toast / Recent Events Window 风格一致。

#### 方案 B：QMenu + QSS，备选

如果短期必须用 `QMenu`，至少用 QSS 统一为深色菜单。但 Windows 上原生菜单有时不完全受控，所以最终还是推荐方案 A。

### 6.3 自定义托盘菜单布局

尺寸：

```text
width: 260px
min-height: 280px
border-radius: 16px
padding: 10px
```

结构：

```text
┌──────────────────────────────────────┐
│ [orange >_ icon] AgentBell  ● 运行中  │
├──────────────────────────────────────┤
│ [clipboard icon]  最近事件     [2]   │
│ [bell-off icon]   静音 30 分钟       │
├──────────────────────────────────────┤
│ [gear icon]       设置               │
│ [question icon]   关于 AgentBell      │
├──────────────────────────────────────┤
│ [power icon]      退出 AgentBell      │
└──────────────────────────────────────┘
```

图标细节（来自设计图）：

每个菜单项左侧有一个图标，样式为简单线性图标，颜色默认 `#b0aea5`，hover 时变 `#d97757`：

| 菜单项 | 图标 | 图标描述 |
|--------|------|----------|
| Header | `>_` | 橙色圆角方块背景 + 白色终端提示符，非菜单项图标 |
| 最近事件 | 剪贴板/列表 | 两个重叠矩形，表示事件列表 |
| 静音 30 分钟 | 带斜线的铃铛 | 铃铛 + 一条斜杠，表示静音 |
| 设置 | 齿轮 | 六齿齿轮轮廓 |
| 关于 AgentBell | 问号圆圈 | 圆圈内含 `?` |
| 退出 AgentBell | 电源 | 经典电源符号（圆 + 竖线） |

Header 区域：

- 左侧：橙色圆角方块 `>_` 图标（约 28x28px）；
- 中间：标题 `AgentBell`，白色，14px，字重 600；
- 右侧：绿色圆点 `●` + `运行中`，绿色 `#788c5d`，12px；
- 未读状态：绿色圆点变为橙色 badge 数字（如 `2`），背景 `#d97757`，白色数字。

视觉：

- 背景：`#181816`；
- Header 背景：`#141413` 或透明；
- hover 背景：`rgba(250,249,245,0.065)`；
- active item 背景：`rgba(217,119,87,0.12)`；
- 分割线：`rgba(250,249,245,0.10)`；
- 图标颜色：默认 `#b0aea5`，hover 用 `#d97757`；
- 运行中状态点：`#788c5d`；
- 未读 badge：`#d97757`；
- 阴影：`0 8px 32px rgba(0,0,0,0.4)`。

菜单项高度：

```text
item height: 42px
icon: 18px
font-size: 13px
```

### 6.4 交互

- 左键点击托盘图标：打开 / 关闭最近事件面板；
- 右键点击托盘图标：打开自定义托盘菜单；
- 点击“最近事件”：打开最近事件面板；
- 点击“静音 30 分钟”：切换静音状态，并更新菜单显示为“已静音 · 剩余 xx 分钟”；
- 点击“退出 AgentBell”：正常退出 daemon / tray；
- 点击菜单外部：菜单自动关闭。

---

## 7. 最近事件窗口设计

### 7.1 当前问题

当前最近事件窗口像这样：

```text
AgentBell 最近事件
蓝色 info 图标
[等待授权] MyProject - PermissionRequest
[等待授权] ClaudeBell - PermissionRequest
确定
```

这不能接受。

必须删除：

- `QMessageBox`；
- 蓝色 info icon；
- 白底系统窗口；
- 默认“确定”按钮；
- 纯文本堆叠列表。

### 7.2 新窗口定位

最近事件窗口是 AgentBell 的轻量通知中心，不是系统弹窗。

它应该：

- 使用深色 Claude Theme；
- 靠近右下角托盘区域显示；
- 不抢焦点或尽量减少打扰；
- 可关闭；
- 支持事件分组；
- 支持空状态；
- 支持最多展示最近 20 条事件；
- 后续可扩展设置入口。

### 7.3 窗口尺寸

默认尺寸：

```text
width: 460px
height: 360px
border-radius: 18px
padding: 16px
```

如果事件较少，可以自适应高度，但不要小于：

```text
min-height: 220px
```

位置：

- 默认显示在右下角；
- 距离屏幕右边 24px；
- 距离任务栏上方 24px；
- 多显示器时使用当前托盘所在屏幕或主屏幕。

### 7.4 窗口结构

```text
┌────────────────────────────────────────────┐
│ [bell] AgentBell 最近事件              [×] │
│ 运行中 · 2 个事件 · 14:32                 │
├────────────────────────────────────────────┤
│ ┌────────────────────────────────────────┐ │
│ │ ● 等待授权                    14:32:18 │ │
│ │ MyProject · PermissionRequest          │ │
│ │ 请回到 Claude Code 终端手动确认工具调用 │ │
│ └────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────┐ │
│ │ ● 等待授权                    14:32:05 │ │
│ │ ClaudeBell · PermissionRequest         │ │
│ │ 请回到 Claude Code 终端手动确认工具调用 │ │
│ └────────────────────────────────────────┘ │
├────────────────────────────────────────────┤
│ [查看全部]                         [设置] │
└────────────────────────────────────────────┘
```

### 7.5 Header 设计

Header 内容：

- 左侧：铃铛 icon；
- 标题：`AgentBell 最近事件`；
- 副标题：`运行中 · 2 个事件 · 14:32`；
- 右侧：关闭按钮。

样式：

- 标题字号：16px；
- 标题字重：600；
- 副标题字号：12px；
- 副标题颜色：`#b0aea5`；
- 关闭按钮：透明背景，hover 时 `rgba(250,249,245,0.08)`。

### 7.6 事件卡片设计

每条事件使用卡片，不要纯文本列表。

卡片尺寸：

```text
width: 100%
min-height: 82px
padding: 12px
border-radius: 14px
```

卡片背景：

```css
background: rgba(250, 249, 245, 0.055);
border: 1px solid rgba(250, 249, 245, 0.10);
```

hover：

```css
background: rgba(250, 249, 245, 0.075);
border-color: rgba(217, 119, 87, 0.22);
```

卡片内容（三行结构）：

```text
● 等待授权                         14:32:18
MyProject · PermissionRequest
请回到 Claude Code 终端手动确认工具调用。
```

行详细说明：

**第一行 — 状态 + 时间（同一行，两端对齐）**

- 左侧：状态圆点 `●` + 状态文案（如 `等待授权`）；
- 右侧：时间戳（如 `14:32:18`），等宽字体，右对齐；
- 状态圆点颜色与状态类型对应（见下方状态颜色表）；
- 状态文案字号 13px，字重 600，颜色 `#faf9f5`；
- 时间字号 12px，颜色 `#b0aea5`。

**第二行 — Session · Event**

- 格式：`{session_label} · {hook_event_name}`；
- 中间用居中点 `·` 分隔（Unicode U+00B7），不要用 `-` 或 `|`；
- 字号 12px，颜色 `#b0aea5`；
- session_label 取值优先级：`session_title` > `cwd basename` > `session_id[:6]`。

**第三行 — 描述**

- 内容：normalized message 或 fallback 文案；
- 字号 12px，颜色 `rgba(250,249,245,0.58)`（text_muted）；
- 单行截断，超出显示 `...`；
- 不要换行。

字段来源：

- 状态：normalized event type；
- session label：`session_title > cwd basename > session_id[:6]`；
- event name：`hook_event_name`；
- 时间：本地时间，HH:MM:SS 格式；
- 描述：normalized message 或 fallback。

状态颜色（状态圆点颜色）：

```text
permission_required: #d97757  (橙色)
waiting_input: #6a9bcc        (蓝色)
task_completed: #788c5d       (绿色)
error: #c45f4f                (红色)
info: #b0aea5                 (灰色)
```

### 7.7 空状态

没有事件时，不要显示空白系统窗口。

空状态：

```text
[bell icon]
暂无最近事件
AgentBell 正在后台运行。Claude Code 需要你注意时会在这里显示。
```

按钮：

```text
[知道了]
```

### 7.8 Footer 设计

Footer 操作：

- `查看全部`：打开更完整历史列表，短期可以禁用或隐藏；
- `设置`：如果设置页没实现，可以隐藏；
- `清空`：可选，实现后清空 recent events；
- 不要放没有 handler 的按钮。

如果没有真实功能，不要显示按钮。

---

## 7.9 最近事件窗口视觉参考（来自设计图）

图片中最近事件窗口的关键视觉特征：

- 整体为深色圆角卡片，背景 `#181816`，圆角约 18px；
- 窗口有细微边框，`rgba(250,249,245,0.12)`；
- 窗口有外部阴影，营造浮起感；
- Header 区域标题 `AgentBell 最近事件` 为白色粗体；
- 每个事件卡片之间有约 8px 间距；
- 卡片背景比窗口背景稍浅，形成层次感；
- 状态圆点 `●` 为实心圆形，颜色鲜明，一眼可识别事件类型；
- Footer 区域与卡片区域有分割线，`rgba(250,249,245,0.10)`；
- Footer 按钮为 ghost 样式，不抢视觉焦点。

---

## 7A. Toast 通知设计

### 7A.1 定位

Toast 是 AgentBell 的即时提醒方式，用于在 Claude Code 需要用户注意时短暂弹出。

### 7A.2 窗口尺寸

```text
width: 340px
border-radius: 14px
padding: 14px
```

位置：

- 右下角，距离屏幕右边 24px；
- 距离任务栏上方 24px；
- 多个 Toast 垂直堆叠，间距 8px。

### 7A.3 窗口结构

```text
┌──────────────────────────────────────┐
│ ┌────┐                               │
│ │ >_ │  Claude Code 需要授权          │
│ └────┘  需要你确认工具调用以继续执行。 │
│                                      │
│  ┌──────────┐  ┌──────────────┐      │
│  │ MyProject│  │ 查看详情  我知道了│      │
│  └──────────┘  └──────────────┘      │
└──────────────────────────────────────┘
```

### 7A.4 左侧图标

图标位于 Toast 左上角：

- 底板：橙色 `#d97757` 圆角方块，尺寸约 36x36px，圆角 10px；
- 图形：白色 `>_` 终端提示符，线条粗细约 2.5px；
- 与托盘菜单 Header 中的图标风格一致，但尺寸更大。

不同事件类型使用不同图标底板颜色：

```text
permission_required: #d97757 (橙色)
waiting_input: #6a9bcc       (蓝色)
task_completed: #788c5d      (绿色)
error: #c45f4f               (红色)
info: #b0aea5                (灰色)
```

### 7A.5 文字区域

图标右侧为文字区域：

**标题行**

- 内容：事件标题（如 `Claude Code 需要授权`）；
- 字号：14px；
- 字重：600；
- 颜色：`#faf9f5`（白色）。

**描述行**

- 内容：事件描述（如 `需要你确认工具调用以继续执行。`）；
- 字号：12px；
- 字重：400；
- 颜色：`#b0aea5`（灰色）；
- 单行，超出截断。

### 7A.6 项目标签（Project Pill）

文字区域下方显示项目来源标签：

- 内容：session_label 或 project 名（如 `MyProject`）；
- 样式：pill 形状，圆角 6px；
- 背景：透明；
- 边框：`1px solid rgba(250,249,245,0.15)`；
- 字号：11px；
- 颜色：`#b0aea5`；
- padding：2px 8px；
- 位置：紧跟在描述行下方，靠左对齐。

### 7A.7 按钮区域

项目标签右侧（或下方，取决于宽度）放置操作按钮：

- 按钮水平排列，间距 8px；
- 按钮靠右对齐。

按钮样式：

**查看详情（Ghost）**

```css
background: rgba(250,249,245,0.04);
border: 1px solid rgba(250,249,245,0.12);
color: #faf9f5;
border-radius: 8px;
height: 30px;
padding: 0 10px;
font-size: 12px;
```

**我知道了（Soft Orange，主要动作）**

```css
background: rgba(217,119,87,0.14);
border: 1px solid rgba(217,119,87,0.28);
color: #faf9f5;
border-radius: 8px;
height: 30px;
padding: 0 10px;
font-size: 12px;
```

### 7A.8 Toast 背景与边框

```css
background: #1a1a18;
border: 1px solid rgba(250, 249, 245, 0.10);
border-radius: 14px;
```

阴影：

```css
box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
```

### 7A.9 Toast 动画

- 出现：从右侧滑入 + 淡入，时长 250ms；
- 消失：向右滑出 + 淡出，时长 200ms；
- 自动消失：8 秒后自动关闭；
- 手动关闭：点击 `我知道了` 或关闭按钮立即消失。

### 7A.10 关闭按钮

- 位置：Toast 右上角；
- 样式：`×` 符号，透明背景；
- hover 背景：`rgba(250,249,245,0.08)`；
- 尺寸：20x20px；
- 颜色：`#b0aea5`。

---

## 8. Toast 与最近事件的统一

Toast 和 Recent Events Window 应该使用同一套视觉语言。

Toast：

- 适合即时提醒；
- 8 秒后自动消失；
- 不再缩成 mini pill；
- 不长期占右下角。

Recent Events Window：

- 由托盘打开；
- 显示最近事件；
- 不自动弹出，除非用户点击托盘；
- 是 Toast 消失后的回看入口。

两者统一：

- 同一色板；
- 同一图标系统；
- 同一状态文案；
- 同一 session label 规则；
- 同一按钮规则。

---

## 9. 按钮规则

继续坚持：没有真实能力的按钮不要出现。

禁止：

- `打开 Claude Code`：除非真的实现并验证了打开对应终端；
- `立即授权`：工具不能替用户授权；
- `查看结果`：除非 payload 里有真实 resultPath/logPath 且代码真的打开；
- 没有 handler 的按钮；
- disabled 但占主要位置的假按钮。

允许：

- `我知道了`：关闭当前 Toast / 窗口；
- `查看详情`：展开真实 event 信息；
- `复制提示`：复制提示文字；
- `清空`：清空本地 recent events；
- `设置`：仅在设置页已实现时显示。

按钮样式：

```css
height: 32px;
padding: 0 12px;
border-radius: 9px;
font-size: 12px;
```

Ghost：

```css
background: rgba(250,249,245,0.04);
border: 1px solid rgba(250,249,245,0.12);
color: #faf9f5;
```

Soft Orange：

```css
background: rgba(217,119,87,0.14);
border: 1px solid rgba(217,119,87,0.28);
color: #faf9f5;
```

不再使用大面积实心橙色按钮，除非这是明确的主要可执行动作。

---

## 10. 事件文案规则

### 10.1 permission_required

状态：

```text
等待授权
```

标题：

```text
Claude Code 需要授权
```

描述：

```text
请回到正在运行 Claude Code 的终端，手动确认工具调用。
```

### 10.2 waiting_input

状态：

```text
等待输入
```

标题：

```text
Claude Code 等待输入
```

描述：

```text
本轮响应已结束，请回到终端继续操作。
```

### 10.3 task_completed

状态：

```text
已完成
```

标题：

```text
Claude Code 任务完成
```

描述：

```text
任务已标记完成。请回到终端查看输出或继续操作。
```

注意：不要从 `Stop` 显示任务完成。

### 10.4 error

状态：

```text
执行失败
```

标题：

```text
Claude Code 执行失败
```

描述：显示真实错误摘要；没有就显示：

```text
发生错误。请回到 Claude Code 终端查看详细信息。
```

---

## 11. PySide6 实现建议

如果项目使用 PySide6，请按以下方式实现。

### 11.1 不要使用 QMessageBox

最近事件不要再用：

```python
QMessageBox.information(...)
```

也不要用：

```python
QMessageBox(...)
```

请实现：

```python
class RecentEventsWindow(QWidget):
    ...
```

窗口 flags：

```python
Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
```

属性：

```python
Qt.WA_TranslucentBackground
```

### 11.2 使用自绘圆角窗口

外层透明，内层 Card 做背景和圆角。

伪结构：

```python
class RecentEventsWindow(QWidget):
    def __init__(self, event_store):
        super().__init__()
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.build_ui()
        self.apply_theme()
```

### 11.3 QSS 示例

```css
#RecentEventsCard {
  background-color: #181816;
  border: 1px solid rgba(250, 249, 245, 0.12);
  border-radius: 18px;
}

QLabel#Title {
  color: #faf9f5;
  font-size: 16px;
  font-weight: 600;
}

QLabel#Subtitle {
  color: #b0aea5;
  font-size: 12px;
}

QFrame#EventCard {
  background-color: rgba(250, 249, 245, 0.055);
  border: 1px solid rgba(250, 249, 245, 0.10);
  border-radius: 14px;
}

QPushButton#GhostButton {
  background-color: rgba(250, 249, 245, 0.04);
  border: 1px solid rgba(250, 249, 245, 0.12);
  color: #faf9f5;
  border-radius: 9px;
  min-height: 32px;
  padding-left: 12px;
  padding-right: 12px;
}

QPushButton#GhostButton:hover {
  background-color: rgba(250, 249, 245, 0.08);
}

/* Toast */
#ToastCard {
  background-color: #1a1a18;
  border: 1px solid rgba(250, 249, 245, 0.10);
  border-radius: 14px;
}

#ToastTitle {
  color: #faf9f5;
  font-size: 14px;
  font-weight: 600;
}

#ToastMessage {
  color: #b0aea5;
  font-size: 12px;
}

#ProjectPill {
  background-color: transparent;
  border: 1px solid rgba(250, 249, 245, 0.15);
  border-radius: 6px;
  color: #b0aea5;
  font-size: 11px;
  padding: 2px 8px;
}

#SoftOrangeButton {
  background-color: rgba(217, 119, 87, 0.14);
  border: 1px solid rgba(217, 119, 87, 0.28);
  color: #faf9f5;
  border-radius: 8px;
  min-height: 30px;
  padding-left: 10px;
  padding-right: 10px;
  font-size: 12px;
}

#SoftOrangeButton:hover {
  background-color: rgba(217, 119, 87, 0.22);
}
```

注意：Qt QSS 对 `rgba()` 的支持与环境有关，如果出现问题，可以改用 `QColor` / palette 或十六进制近似色。

---

## 12. 数据模型要求

最近事件必须从真实 event store 读取，不要写死示例。

事件模型建议：

```python
@dataclass
class AgentBellEvent:
    id: str
    timestamp: float
    session_id: str | None
    session_label: str
    cwd: str | None
    hook_event_name: str
    notification_type: str | None
    kind: Literal[
        "permission_required",
        "waiting_input",
        "task_completed",
        "error",
        "info",
    ]
    title: str
    message: str
    tool_name: str | None = None
    command: str | None = None
    project_path: str | None = None
    raw_payload: dict | None = None
```

Recent Events Window 只展示最近 20 条。

排序：

```text
timestamp desc
```

聚合：

- 默认按时间显示；
- 后续可选按 session 分组；
- 多会话聚合 Toast 不影响最近事件列表，列表里仍要能看到每个 session。

---

## 13. 交互细节

### 13.1 点击托盘图标

左键：

- 如果 Recent Events Window 未显示，则显示；
- 如果已显示，则隐藏。

右键：

- 显示自定义 Tray Menu。

### 13.2 点击事件卡片

短期可以：

- 展开详情；
- 或复制 session/cwd 信息；
- 如果没有真实 handler，点击不要做假跳转。

### 13.3 点击关闭

- Recent Events Window 隐藏，不退出 daemon；
- Toast 关闭只关闭当前 Toast；
- 托盘菜单“退出 AgentBell”才退出后台程序。

### 13.4 静音

静音 30 分钟：

- 不显示 Toast；
- 仍记录最近事件；
- 托盘图标可以显示 muted 状态；
- 菜单项显示剩余时间。

---

## 14. 不要做的事

本轮明确禁止：

1. 不要继续使用 `QMessageBox` 显示最近事件。
2. 不要继续使用蓝色 info 系统图标。
3. 不要使用系统默认白底 QMenu 作为主要托盘 UI。
4. 不要写死 `MyProject`、`ClaudeBell`、`PermissionRequest` 等假数据。
5. 不要显示没有真实 handler 的按钮。
6. 不要恢复 mini pill 常驻右下角。
7. 不要把 Stop 当成 task_done。
8. 不要通过 hook 直接创建完整 UI 进程。
9. 不要改变 Claude Code 的授权机制。
10. 不要实现自动授权。

---

## 15. 实现任务拆分

### Task 1：新增 UI Theme

新增：

```text
src/agentbell/ui/theme.py
```

验收：

- 颜色集中管理；
- Toast、Recent Events、Tray Menu 使用同一色板；
- 不再散落硬编码主色。

### Task 2：重做 Tray Icon

新增或修改：

```text
src/agentbell/ui/icons.py
src/agentbell/tray.py
```

验收：

- 托盘图标不再是蓝色 info；
- 有默认态、未读态、静音态；
- Windows 任务栏小尺寸下仍清晰。

### Task 3：实现自定义 Recent Events Window

新增：

```text
src/agentbell/ui/recent_events_window.py
```

验收：

- 不使用 QMessageBox；
- 深色 Claude Theme；
- 事件卡片展示，三行结构（状态+时间、session·event、描述）；
- 有空状态；
- 有关闭按钮；
- 数据来自真实 event store。

### Task 3A：重做 Toast 通知

修改：

```text
src/agentbell/toast_renderer.py
```

验收：

- 左侧橙色 `>_` 图标，不同事件类型不同颜色；
- 标题 + 描述 + 项目 pill + 按钮；
- 8 秒自动消失；
- 多个 Toast 排队不重叠；
- 与最近事件窗口风格一致。

### Task 4：实现自定义 Tray Menu

新增：

```text
src/agentbell/ui/tray_menu.py
```

验收：

- 不再显示默认白底菜单；
- 有 Header、运行状态、未读数；
- 有 最近事件 / 静音 / 设置 / 关于 / 退出；
- 点击外部关闭。

### Task 5：统一 Event Store

修改：

```text
src/agentbell/daemon.py
src/agentbell/tray.py
```

验收：

- Toast 和 Recent Events 使用同一份事件数据；
- 多会话 session label 正确；
- 最近事件不是硬编码。

### Task 6：验收截图

必须提供截图：

1. 新托盘图标默认态；
2. 新托盘图标未读态（带 badge）；
3. 自定义托盘菜单（含运行状态和未读 badge）；
4. 最近事件窗口有事件状态（三行卡片结构）；
5. 最近事件窗口空状态；
6. permission Toast（含图标、标题、描述、项目 pill、按钮）；
7. Toast 与最近事件窗口风格对比（色板一致）。

---

## 16. 最终验收标准

完成后必须满足：

1. 最近事件窗口不再是 Windows 默认 MessageBox。
2. 最近事件窗口不再出现蓝色 info 图标。
3. 最近事件窗口不再只有纯文本列表和“确定”按钮。
4. 托盘菜单不再是白底默认菜单，或至少已用深色 QSS 统一；优先自定义 Popup。
5. 托盘图标不再是系统默认 info，使用 AgentBell 自定义图标。
6. 未读事件时托盘图标有 badge 或状态提示。
7. 静音时托盘图标有 muted 状态。
8. 最近事件使用真实 event store，不写死假数据。
9. 所有按钮都有真实 handler，没有假按钮。
10. 所有 UI 使用统一 Claude Theme。
11. 不恢复 mini pill。
12. 不抢焦点，不影响正在输入代码。
13. daemon 架构保持不变：hook 事件进入 daemon，由 daemon 统一管理 UI。
14. 给出修改文件列表和本地验证命令。

---

## 17. UI 背后的功能需求

每个 UI 组件背后需要对应的功能支撑，以下是必须实现的核心功能。

### 17.1 Event Store（事件存储）

所有 UI 组件的数据来源，必须实现：

- **写入**：hook 事件到达时，daemon 将事件写入 store；
- **读取**：Toast、最近事件窗口、托盘菜单 badge 均从同一 store 读取；
- **容量**：最多保留最近 100 条事件，超出自动淘汰最旧的；
- **持久化**：建议使用 JSON 文件持久化，daemon 重启后不丢失；
- **查询**：支持按时间倒序获取最近 N 条；
- **清除**：支持一键清空所有事件。

### 17.2 Toast 管理器

控制 Toast 的生命周期：

- **队列**：多个事件同时到达时，Toast 排队显示，不重叠；
- **去重**：相同 session + 相同 event 在 5 秒内不重复弹出；
- **自动消失**：8 秒后自动关闭；
- **手动关闭**：用户点击按钮后立即关闭；
- **静音**：静音期间不弹出 Toast，但事件仍写入 store；
- **位置**：多个 Toast 垂直堆叠，新 Toast 在最上方。

### 17.3 托盘图标管理

根据状态动态更新图标：

- **默认态**：无未读事件，显示普通图标；
- **未读态**：有未读事件，图标右上角显示数字 badge（1-9 显示数字，10+ 显示 `9+`）；
- **静音态**：图标透明度降至 50%，或显示斜杠标记；
- **更新时机**：新事件到达、用户打开最近事件窗口（清除未读）、静音状态切换。

### 17.4 托盘菜单功能

每个菜单项背后的功能：

| 菜单项 | 功能 | 实现要求 |
|--------|------|----------|
| 最近事件 | 打开/关闭最近事件窗口 | toggle 行为，已打开则关闭 |
| 静音 30 分钟 | 切换静音状态 | 30 分钟倒计时，到期自动解除；菜单文案变为 `已静音 · 剩余 xx 分钟` |
| 设置 | 打开设置页 | 短期可隐藏，不实现假入口 |
| 关于 AgentBell | 显示版本信息 | 可用简单 MessageBox 显示版本号 |
| 退出 AgentBell | 退出程序 | 关闭 daemon、tray、所有窗口 |

### 17.5 最近事件窗口功能

- **数据展示**：从 event store 读取最近 20 条，按时间倒序；
- **实时更新**：新事件到达时自动刷新列表（无需手动刷新）；
- **空状态**：无事件时显示空状态插画 + 文案；
- **关闭**：关闭按钮隐藏窗口，不退出 daemon；
- **定位**：默认显示在屏幕右下角，靠近托盘区域；
- **多显示器**：在当前托盘所在显示器显示。

### 17.6 Hook 事件处理

daemon 接收 hook 事件后的处理流程：

```text
hook 事件到达
  → 解析 payload
  → 归一化为 AgentBellEvent
  → 写入 Event Store
  → 判断是否弹出 Toast（静音则跳过）
  → 更新托盘图标 badge
  → 如果最近事件窗口已打开，刷新列表
```

### 17.7 进程架构

保持现有架构不变：

- `agentbell daemon`：常驻后台进程，管理所有状态；
- hook 事件通过 HTTP 或 stdin 传入 daemon；
- daemon 启动 tray icon + 事件监听；
- UI 组件（Toast、最近事件窗口、托盘菜单）由 daemon 按需创建和销毁；
- 不要让 hook 直接启动完整 UI 进程。

---

## 18. 给 Codex 的执行要求

请先阅读项目结构，确认当前 UI 技术栈和文件位置，再执行。不要盲目重构核心 hook 逻辑。

执行顺序：

1. 找到当前最近事件窗口实现，确认是否使用了 `QMessageBox`。
2. 找到当前托盘图标生成逻辑。
3. 找到当前托盘菜单实现。
4. 新增统一 theme token。
5. 替换托盘图标。
6. 替换最近事件窗口为自定义深色窗口。
7. 替换或美化托盘菜单。
8. 确认所有数据来自真实 event store。
9. 删除所有 fake UI / fake CTA。
10. 给出截图和验收报告。

交付报告必须包含：

- 是否仍使用 QMessageBox；
- 是否仍使用系统默认 info 图标；
- 是否仍使用默认白底 QMenu；
- 新增 / 修改文件列表；
- 本地运行命令；
- 截图路径；
- 当前已知限制。

