# Claude Code Hooks 授权提醒弹窗设计文档

> 版本：v1.0  
> 目标：让 Claude Code hooks 授权提醒弹窗更接近 Claude / Anthropic 官方暖色系视觉风格，并且适合开发者长期使用。  
> 官方配色参考：Anthropic skills brand-guidelines 中的颜色 token：Dark `#141413`、Light `#faf9f5`、Mid Gray `#b0aea5`、Light Gray `#e8e6dc`、Orange `#d97757`、Blue `#6a9bcc`、Green `#788c5d`。  
> 来源：https://github.com/anthropics/skills/blob/main/skills/brand-guidelines/SKILL.md

---

## 0. 项目背景

当前项目是一个 Claude Code hooks 弹窗提醒工具。现有弹窗类似系统默认通知，存在以下问题：

- 视觉过于简陋，像 Windows 默认消息框。
- 图标、背景、文字层级不符合 Claude Code 的产品气质。
- 提醒内容不够明确，用户不能快速理解“为什么弹出”和“需要做什么”。
- 弹窗容易打断输入，不适合长时间编码场景。
- 后续如果要给别人安装使用，需要更专业、更可信的 UI。

本次目标是重设计 Claude Code hooks 授权提醒弹窗，使其接近 Claude / Anthropic 官方暖色系视觉风格，并且适合开发者长期使用。

---

# 1. 设计目标

## 1.1 一句话目标

实现一个 **Claude 官方配色风格、右下角非打扰、可展开查看详情的 hooks 授权提醒 Toast**。

## 1.2 核心体验

用户正在写代码或使用 Claude Code 时，如果 Claude Code 需要用户授权工具调用，弹窗应：

1. 出现在屏幕右下角。
2. 不抢输入焦点。
3. 有轻微声音或动画提示。
4. 清晰展示“Claude Code 需要授权”。
5. 提供“打开 Claude Code / 查看详情 / 忽略”操作。
6. 自动收起或保持，具体根据事件严重程度决定。
7. 整体视觉应像 Claude Code 的官方辅助工具，而不是普通系统通知。

---

# 2. 设计原则

## 2.1 非打扰优先

这是开发者工具，不是营销弹窗。

弹窗不能：

- 抢占键盘焦点。
- 阻塞当前输入。
- 自动把窗口置顶到影响用户操作。
- 使用强烈闪烁动画。
- 使用过高饱和度颜色。

弹窗应该：

- 默认在右下角静默出现。
- 只用一次轻微滑入动画。
- 授权类事件可以播放短提示音。
- 用户无操作时保持 8-12 秒后自动变为折叠状态。
- 如果需要用户确认，可以保留一个小型悬浮胶囊入口。

## 2.2 Claude / Anthropic 风格

视觉关键词：

- Warm
- Minimal
- Developer-focused
- Calm
- Premium
- Trustworthy
- Dark but not pure black
- Orange accent, not purple/blue

不要做成：

- 赛博霓虹紫蓝风。
- Windows 默认气泡。
- 过度玻璃拟态。
- 大面积高亮渐变。
- 过于圆润的卡通风。

## 2.3 信息层级清晰

用户看到弹窗后，3 秒内应该知道：

- 谁在提醒：Claude Code Hooks
- 为什么提醒：需要授权工具调用
- 当前状态：等待用户处理
- 下一步：回到 Claude Code 授权

---

# 3. 官方配色 Token

## 3.1 基础色

```css
:root {
  --claude-dark: #141413;
  --claude-light: #faf9f5;
  --claude-mid-gray: #b0aea5;
  --claude-light-gray: #e8e6dc;
  --claude-orange: #d97757;
  --claude-blue: #6a9bcc;
  --claude-green: #788c5d;
}
```

## 3.2 深色弹窗扩展色

```css
:root {
  --toast-bg: #181816;
  --toast-bg-elevated: #20201d;
  --toast-border: rgba(250, 249, 245, 0.12);
  --toast-border-strong: rgba(217, 119, 87, 0.42);

  --text-primary: #faf9f5;
  --text-secondary: #b0aea5;
  --text-muted: rgba(250, 249, 245, 0.58);

  --accent-primary: #d97757;
  --accent-primary-hover: #e38a6b;
  --accent-primary-pressed: #c76645;

  --code-bg: rgba(250, 249, 245, 0.06);
  --code-border: rgba(250, 249, 245, 0.1);

  --shadow-soft: 0 18px 48px rgba(0, 0, 0, 0.38);
  --shadow-orange: 0 0 32px rgba(217, 119, 87, 0.18);
}
```

## 3.3 颜色使用比例

推荐比例：

- 70%：深色背景 `#141413 / #181816`
- 20%：灰色文本与边框 `#b0aea5 / #e8e6dc`
- 10%：Claude 橙色 `#d97757`

不要大面积使用橙色。橙色只用于：

- 状态点
- 主按钮
- 图标强调
- 关键命令高亮
- 活跃边框

---

# 4. 字体规范

## 4.1 字体栈

如果项目是 Web / Electron / Tauri：

```css
font-family:
  Inter,
  ui-sans-serif,
  system-ui,
  -apple-system,
  BlinkMacSystemFont,
  "Segoe UI",
  "PingFang SC",
  "Microsoft YaHei",
  sans-serif;
```

如果项目是 Python 桌面应用：

- Windows：优先 `Microsoft YaHei UI`
- macOS：优先 `PingFang SC`
- Linux：优先 `Noto Sans CJK SC`
- 英文与数字：可用系统 UI 字体

## 4.2 字号

```css
--font-title: 15px;
--font-body: 13px;
--font-meta: 12px;
--font-code: 12px;
```

## 4.3 字重

- 标题：600
- 正文：400 / 450
- 命令文本：500
- 按钮：600

---

# 5. 弹窗布局

## 5.1 默认位置

弹窗默认固定在屏幕右下角。

```css
right: 24px;
bottom: 24px;
```

如果检测到任务栏在右侧或底部，应自动避让。

## 5.2 尺寸

### 紧凑态 Compact Toast

```css
width: 360px;
min-height: 96px;
border-radius: 16px;
padding: 16px;
```

适合普通授权提醒。

### 展开态 Expanded Toast

```css
width: 420px;
min-height: 220px;
border-radius: 18px;
padding: 18px;
```

适合显示工具名、命令、项目路径、详情。

### 折叠态 Mini Pill

```css
width: auto;
height: 36px;
border-radius: 999px;
padding: 0 14px;
```

用户长时间未处理时，自动变成右下角小胶囊。

---

# 6. 组件结构

## 6.1 Compact Toast 结构

```text
┌────────────────────────────────────────────┐
│ [Claude Icon]  Claude Code 需要授权    [×] │
│              需要你确认工具调用            │
│                                            │
│              [查看详情]  [打开授权]        │
└────────────────────────────────────────────┘
```

## 6.2 Expanded Toast 结构

```text
┌────────────────────────────────────────────┐
│ [Icon] Claude Code 需要授权            [×] │
│       Claude Code 正在等待你确认工具调用   │
│                                            │
│ ┌────────────────────────────────────────┐ │
│ │ 将执行以下操作                         │ │
│ │ 运行 shell 命令                        │ │
│ │ ls -la /Users/username/project         │ │
│ └────────────────────────────────────────┘ │
│                                            │
│ □ 本次会话不再提醒低风险操作              │
│                                            │
│              [忽略]  [打开 Claude Code]   │
└────────────────────────────────────────────┘
```

## 6.3 Mini Pill 结构

```text
[橙色状态点] Claude Code 等待授权
```

点击 Mini Pill 后恢复为 Expanded Toast。

---

# 7. 视觉细节

## 7.1 背景

弹窗背景使用深色暖黑，不要纯黑。

推荐：

```css
background:
  radial-gradient(circle at 12% 0%, rgba(217, 119, 87, 0.14), transparent 32%),
  linear-gradient(180deg, #20201d 0%, #181816 100%);
```

## 7.2 边框

```css
border: 1px solid rgba(250, 249, 245, 0.12);
```

当事件为“等待授权”时，使用轻微橙色边框：

```css
box-shadow:
  0 18px 48px rgba(0, 0, 0, 0.38),
  0 0 32px rgba(217, 119, 87, 0.16);

border-color: rgba(217, 119, 87, 0.42);
```

## 7.3 圆角

```css
border-radius: 16px;
```

不建议超过 22px，否则会显得像移动端卡片，不够开发者工具。

## 7.4 阴影

```css
box-shadow:
  0 18px 48px rgba(0, 0, 0, 0.38),
  0 1px 0 rgba(250, 249, 245, 0.06) inset;
```

## 7.5 图标

不要使用 Windows 默认蓝色 info 图标。

推荐图标方案：

1. 左侧使用 Claude 风格橙色圆角盾牌 / 终端图标。
2. 图标底色使用 `#d97757` 到 `#c76645` 的轻微渐变。
3. 图标内部使用浅色 `#faf9f5`。
4. 图标尺寸：
   - Compact：36 x 36
   - Expanded：42 x 42
   - Mini Pill：8 x 8 状态点

图标可以先用简单 SVG 实现，避免依赖图片资源。

示例 SVG 方向：

- 外形：圆角方块或盾牌
- 内部：`>_` 终端符号
- 右下角可加一个小圆点表示 hook/event

---

# 8. 文案规范

## 8.1 标题

推荐标题：

```text
Claude Code 需要授权
```

不要写：

```text
Claude Code 授权提醒
```

原因：  
“需要授权”更像当前状态，“授权提醒”更像通知分类。

## 8.2 副标题

推荐：

```text
Claude Code 正在等待你确认工具调用。
```

或者更短：

```text
需要你确认工具调用以继续执行。
```

## 8.3 操作卡片文案

```text
将执行以下操作
运行 shell 命令
ls -la /Users/username/project
```

如果没有具体命令，则显示：

```text
工具调用详情暂不可用
请回到 Claude Code 查看完整授权信息。
```

## 8.4 按钮文案

主按钮：

```text
打开 Claude Code
```

次按钮：

```text
查看详情
```

弱按钮：

```text
忽略
```

关闭按钮：

```text
×
```

不要使用：

```text
立即授权
```

原因：  
弹窗工具本身通常不能真正替用户授权，只能引导用户回到 Claude Code。写“立即授权”容易造成误解。

---

# 9. 交互状态

## 9.1 初始出现

当 hook 收到授权等待事件：

1. 弹窗从右下角滑入。
2. 透明度从 0 到 1。
3. 位移从 `translateY(12px)` 到 `translateY(0)`。
4. 动画时长 180ms。
5. 播放一次短提示音，可配置关闭。

```css
animation: toast-in 180ms ease-out;
```

## 9.2 自动收起

如果用户 10 秒内没有操作：

- Compact Toast 自动变成 Mini Pill。
- Mini Pill 保持在右下角。
- Mini Pill 不闪烁，只保留橙色状态点。

可配置：

```json
{
  "autoCollapseMs": 10000,
  "autoDismiss": false
}
```

授权类提醒不要完全自动消失，避免用户错过。

## 9.3 点击主按钮

点击“打开 Claude Code”：

- 如果可以定位 Claude Code 所在终端窗口，则激活该窗口。
- 如果无法激活，则显示提示：

```text
请回到 Claude Code 终端完成授权。
```

- 不要在未确认的情况下自动执行任何授权行为。

## 9.4 点击查看详情

Compact Toast 展开为 Expanded Toast。

展示信息：

- event 类型
- tool 名称
- command / file path / operation
- project path
- timestamp
- session id，可选

## 9.5 点击忽略

忽略当前弹窗，但不影响 Claude Code 本身的授权等待。

行为：

- 当前 Toast 消失。
- 3 秒内相同事件不要重复弹出。
- 如果 hook 再次收到新事件，可以重新弹出。

## 9.6 关闭按钮

关闭按钮与忽略类似，但语义是关闭 UI。

---

# 10. 事件类型设计

当前重点是授权提醒，但以后可能扩展更多 hooks 类型。

## 10.1 permission_required

授权等待。

视觉：

- 橙色状态点
- 橙色主按钮
- 标题：Claude Code 需要授权

## 10.2 task_done

任务完成。

视觉：

- 绿色状态点
- 标题：Claude Code 任务完成
- 主按钮：查看结果

## 10.3 error

执行失败。

视觉：

- 暗红色状态点
- 标题：Claude Code 执行失败
- 主按钮：查看错误

## 10.4 info

普通信息。

视觉：

- 灰色或蓝色状态点
- 标题：Claude Code 通知

---

# 11. CSS / UI Token 建议

请在项目中建立统一 token 文件，而不是把颜色散落在组件里。

推荐文件：

```text
src/ui/theme/claudeTheme.ts
```

或：

```text
src/ui/theme/claude-theme.css
```

## 11.1 TypeScript Token 示例

```ts
export const claudeTheme = {
  colors: {
    dark: "#141413",
    light: "#faf9f5",
    midGray: "#b0aea5",
    lightGray: "#e8e6dc",
    orange: "#d97757",
    blue: "#6a9bcc",
    green: "#788c5d",

    toastBg: "#181816",
    toastBgElevated: "#20201d",
    toastBorder: "rgba(250, 249, 245, 0.12)",
    toastBorderStrong: "rgba(217, 119, 87, 0.42)",

    textPrimary: "#faf9f5",
    textSecondary: "#b0aea5",
    textMuted: "rgba(250, 249, 245, 0.58)",

    accentPrimary: "#d97757",
    accentPrimaryHover: "#e38a6b",
    accentPrimaryPressed: "#c76645"
  },

  radius: {
    toast: 16,
    card: 12,
    button: 10,
    pill: 999
  },

  shadow: {
    toast: "0 18px 48px rgba(0, 0, 0, 0.38)",
    orange: "0 0 32px rgba(217, 119, 87, 0.16)"
  }
};
```

---

# 12. HTML / CSS 参考结构

如果项目使用 WebView / Electron / Tauri，可以按这个结构实现。

```html
<div class="cc-toast cc-toast--permission">
  <button class="cc-toast__close" aria-label="关闭">×</button>

  <div class="cc-toast__header">
    <div class="cc-toast__icon">
      <span class="cc-toast__terminal">&gt;_</span>
    </div>

    <div class="cc-toast__title-wrap">
      <div class="cc-toast__eyebrow">
        <span class="cc-toast__dot"></span>
        Claude Code Hooks
      </div>
      <h2 class="cc-toast__title">Claude Code 需要授权</h2>
      <p class="cc-toast__desc">需要你确认工具调用以继续执行。</p>
    </div>
  </div>

  <div class="cc-toast__detail">
    <div class="cc-toast__detail-title">将执行以下操作</div>
    <div class="cc-toast__detail-subtitle">运行 shell 命令</div>
    <code class="cc-toast__code">ls -la /Users/username/project</code>
  </div>

  <div class="cc-toast__actions">
    <button class="cc-button cc-button--ghost">忽略</button>
    <button class="cc-button cc-button--primary">打开 Claude Code</button>
  </div>
</div>
```

```css
.cc-toast {
  width: 380px;
  padding: 16px;
  border-radius: 16px;
  color: #faf9f5;
  background:
    radial-gradient(circle at 12% 0%, rgba(217, 119, 87, 0.14), transparent 34%),
    linear-gradient(180deg, #20201d 0%, #181816 100%);
  border: 1px solid rgba(250, 249, 245, 0.12);
  box-shadow:
    0 18px 48px rgba(0, 0, 0, 0.38),
    0 0 32px rgba(217, 119, 87, 0.16),
    0 1px 0 rgba(250, 249, 245, 0.06) inset;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 99999;
  animation: cc-toast-in 180ms ease-out;
}

.cc-toast__close {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  color: rgba(250, 249, 245, 0.58);
  background: transparent;
  cursor: pointer;
}

.cc-toast__close:hover {
  color: #faf9f5;
  background: rgba(250, 249, 245, 0.08);
}

.cc-toast__header {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding-right: 28px;
}

.cc-toast__icon {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  color: #faf9f5;
  background: linear-gradient(145deg, #e38a6b, #c76645);
  box-shadow: 0 8px 20px rgba(217, 119, 87, 0.28);
  flex: 0 0 auto;
}

.cc-toast__terminal {
  font-weight: 700;
  font-size: 14px;
  letter-spacing: -0.04em;
}

.cc-toast__eyebrow {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #b0aea5;
  font-size: 12px;
  line-height: 1.2;
  margin-bottom: 4px;
}

.cc-toast__dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #d97757;
  box-shadow: 0 0 14px rgba(217, 119, 87, 0.7);
}

.cc-toast__title {
  margin: 0;
  font-size: 15px;
  line-height: 1.35;
  font-weight: 650;
  color: #faf9f5;
}

.cc-toast__desc {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: #b0aea5;
}

.cc-toast__detail {
  margin-top: 14px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(250, 249, 245, 0.055);
  border: 1px solid rgba(250, 249, 245, 0.1);
}

.cc-toast__detail-title {
  font-size: 13px;
  font-weight: 600;
  color: #faf9f5;
}

.cc-toast__detail-subtitle {
  margin-top: 3px;
  font-size: 12px;
  color: rgba(250, 249, 245, 0.58);
}

.cc-toast__code {
  display: block;
  margin-top: 8px;
  color: #d97757;
  font-size: 12px;
  line-height: 1.45;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
}

.cc-toast__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}

.cc-button {
  height: 34px;
  padding: 0 14px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.cc-button--ghost {
  color: #faf9f5;
  background: rgba(250, 249, 245, 0.04);
  border: 1px solid rgba(250, 249, 245, 0.12);
}

.cc-button--ghost:hover {
  background: rgba(250, 249, 245, 0.08);
}

.cc-button--primary {
  color: #faf9f5;
  background: #d97757;
  border: 1px solid rgba(250, 249, 245, 0.1);
  box-shadow: 0 8px 22px rgba(217, 119, 87, 0.24);
}

.cc-button--primary:hover {
  background: #e38a6b;
}

@keyframes cc-toast-in {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.985);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
```

---

# 13. Python 桌面实现建议

如果项目是 Python + uv 管理，推荐使用以下方案之一：

## 13.1 推荐方案：PySide6

适合做高质量自定义弹窗。

优点：

- 可以做无边框窗口。
- 可以设置不抢焦点。
- 可以做圆角、阴影、透明背景。
- 跨平台能力较好。
- 后续可以扩展设置页、历史记录页。

建议窗口参数：

- Frameless window
- Always on top 可配置
- Tool window
- 不抢焦点
- 透明背景
- 右下角定位
- 支持多显示器

伪代码方向：

```python
class PermissionToast(QWidget):
    def __init__(self, event):
        super().__init__()
        self.setWindowFlags(
            Qt.Tool |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.build_ui(event)
        self.move_to_bottom_right()
        self.animate_in()
```

## 13.2 备选方案：Tkinter

如果项目想保持轻量，可以用 Tkinter。

缺点：

- 高级视觉效果较弱。
- 圆角、阴影、透明背景处理麻烦。
- 高级动画体验不如 PySide6。

如果使用 Tkinter，也必须避免系统默认 MessageBox 风格，需要完全自绘 Frame。

---

# 14. 声音设计

授权提醒可以播放轻提示音，但必须可关闭。

## 14.1 默认声音

声音应该：

- 短，100-250ms。
- 柔和。
- 不刺耳。
- 不连续重复。

不要使用：

- Windows 默认错误音。
- 高音蜂鸣。
- 连续响铃。
- 游戏通知音。

## 14.2 配置项

```json
{
  "sound": {
    "enabled": true,
    "volume": 0.45,
    "permissionRequired": "soft-pop"
  }
}
```

---

# 15. 配置项设计

建议支持用户配置：

```json
{
  "theme": "claude-dark",
  "position": "bottom-right",
  "alwaysOnTop": true,
  "stealFocus": false,
  "playSound": true,
  "autoCollapseMs": 10000,
  "maxVisibleToasts": 3,
  "dedupeWindowMs": 3000,
  "showCommandPreview": true,
  "showProjectPath": true
}
```

必须默认：

```json
{
  "stealFocus": false
}
```

这是项目核心体验，不能打断用户键盘输入。

---

# 16. Hook 事件数据结构

建议 UI 层接收统一事件对象。

```ts
type ClaudeHookToastEvent = {
  id: string;
  type: "permission_required" | "task_done" | "error" | "info";
  title?: string;
  message?: string;
  toolName?: string;
  command?: string;
  projectPath?: string;
  sessionId?: string;
  timestamp: number;
  priority?: "low" | "normal" | "high";
};
```

Python 可对应为：

```python
@dataclass
class ClaudeHookToastEvent:
    id: str
    type: Literal["permission_required", "task_done", "error", "info"]
    title: str | None = None
    message: str | None = None
    tool_name: str | None = None
    command: str | None = None
    project_path: str | None = None
    session_id: str | None = None
    timestamp: float = field(default_factory=time.time)
    priority: Literal["low", "normal", "high"] = "normal"
```

---

# 17. 多弹窗堆叠规则

如果短时间内多个 Claude Code 会话同时触发 hooks：

1. 最多显示 3 个 Toast。
2. 新 Toast 从右下角往上堆叠。
3. 同一个 session + 同一个 type + 同一个 command 在 3 秒内去重。
4. 超过 3 个后合并成一个摘要 Toast。

摘要 Toast 文案：

```text
Claude Code 有 4 个事件等待处理
其中 2 个需要授权。
```

按钮：

```text
查看全部
```

---

# 18. 可访问性要求

必须满足：

- 文本对比度足够。
- 主按钮能用键盘访问，但弹窗默认不抢焦点。
- 鼠标悬停状态明显。
- 关闭按钮有 `aria-label` 或等价描述。
- 命令过长时省略，但展开详情能看到完整内容。
- 不用颜色作为唯一信息来源，状态也要有文字说明。

---

# 19. 不要实现的内容

本轮只做 UI 与交互，不要做以下事情：

- 不要自动替用户点击 Claude Code 授权。
- 不要修改 Claude Code 的权限模型。
- 不要引入复杂账号系统。
- 不要做完整通知中心。
- 不要做大而全的设置面板。
- 不要把弹窗做成居中阻塞 Modal。
- 不要使用紫色、蓝色作为主视觉。
- 不要使用系统默认 MessageBox。
- 不要让弹窗抢键盘焦点。

---

# 20. 实现任务拆分

## Task 1：建立 Claude Theme Token

新增统一主题 token 文件。

验收标准：

- 所有颜色从 token 引用。
- 没有散落的硬编码主色。
- 支持后续扩展 light theme。

## Task 2：实现 PermissionToast 组件

实现默认授权提醒弹窗。

验收标准：

- 右下角出现。
- 不抢焦点。
- 使用 Claude 暖黑 + 橙色强调。
- 标题、副标题、按钮层级清晰。
- 支持关闭、忽略、打开 Claude Code。

## Task 3：实现 Expanded 详情态

点击“查看详情”后展开。

验收标准：

- 展示 toolName、command、projectPath。
- command 使用 monospace。
- 长命令可截断，也可复制或展开查看。
- UI 不溢出屏幕。

## Task 4：实现 Mini Pill 折叠态

10 秒未操作后折叠。

验收标准：

- 折叠成小胶囊。
- 点击后恢复 Toast。
- 不闪烁，不打扰输入。

## Task 5：实现多事件去重与堆叠

验收标准：

- 同事件短时间不重复弹。
- 多事件最多显示 3 个。
- 超过 3 个合并摘要。

## Task 6：实现提示音配置

验收标准：

- 默认播放一次轻提示音。
- 可关闭。
- 不连续播放。
- 不使用刺耳系统错误音。

---

# 21. 最终验收标准

完成后，应该达到以下效果：

1. 弹窗看起来像 Claude Code 官方生态工具，而不是系统默认通知。
2. 主色为 Anthropic / Claude 风格暖橙，不使用紫蓝 AI 风。
3. 用户正在输入代码时不会被打断。
4. 授权提醒足够醒目，但不过度打扰。
5. 多个 Claude Code 会话同时触发 hooks 时不会刷屏。
6. 代码中存在统一主题 token，后续可以维护。
7. UI 支持 compact、expanded、mini pill 三种状态。
8. 弹窗可配置声音、位置、自动折叠时间。
9. 权限提醒不会误导用户，以“打开 Claude Code”代替“立即授权”。
10. 视觉、交互、代码结构都适合开源给别人安装使用。

---

# 22. 给 Claude Code 的实现要求

请先阅读当前项目结构，然后基于现有技术栈实现上述设计。不要盲目重构整个项目。

执行顺序：

1. 找到当前弹窗 UI 的实现位置。
2. 找到 hook event 到 UI 的数据流。
3. 新增或整理 theme token。
4. 替换旧弹窗样式。
5. 实现 compact / expanded / mini pill 状态。
6. 确保弹窗不抢焦点。
7. 增加多事件去重与堆叠。
8. 增加基础配置项。
9. 补充 README 截图说明或开发文档。
10. 给出本地运行与验证方法。

实现时请遵守：

- 不要影响已有 hooks 逻辑。
- 不要改变 Claude Code 的授权机制。
- 不要自动执行授权。
- 不要引入大型依赖，除非项目现有技术栈确实需要。
- 如果需要引入 PySide6 / WebView / Tauri / Electron，请先说明理由。
- 所有视觉 token 要集中维护。
- 最终给出修改文件列表和测试结果。

---

# 23. 可直接发送给 Claude Code 的精简 Prompt

下面这段可以单独复制给 Claude Code：

```text
请基于 docs/design/claude-code-hooks-toast-design.md 实现 Claude Code hooks 授权提醒弹窗重设计。

目标：做成 Claude / Anthropic 官方暖色系风格的右下角非打扰 Toast，而不是系统默认消息框。

重点要求：
1. 使用官方风格颜色：#141413、#faf9f5、#b0aea5、#e8e6dc、#d97757。
2. 弹窗默认右下角出现，不抢键盘焦点。
3. 实现 compact、expanded、mini pill 三种状态。
4. 授权类提醒不要自动完全消失，10 秒后可折叠为 mini pill。
5. 主按钮文案用“打开 Claude Code”，不要用“立即授权”。
6. 不要自动替用户授权，不要修改 Claude Code 权限机制。
7. 增加事件去重和最多 3 个 Toast 堆叠规则。
8. 视觉 token 集中维护，不要到处硬编码颜色。
9. 优先基于现有技术栈实现，不要盲目引入大型依赖。
10. 完成后给出修改文件列表、运行方法和验证结果。
```
