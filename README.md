# AgentBell

Windows 通知工具，用于 Claude Code CLI hooks。当 Claude Code 需要你授权工具调用或完成回复时，发送右下角 Toast 通知 + 系统提示音。

## 功能

- Claude Code 需要授权时：右下角 Toast 通知 + 提示音
- Claude Code 完成回复时：右下角 Toast 通知 + 提示音
- 不抢焦点，不打断键盘输入
- 多个 Claude Code 会话同时触发不会互相阻塞

## 安装 uv

如果还没有安装 uv，请先安装：

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

或参考 [uv 官方文档](https://docs.astral.sh/uv/getting-started/installation/)。

## 快速开始

### 1. 克隆或下载项目

```bash
cd AgentBell
```

### 2. 同步依赖

```bash
uv sync
```

### 3. 测试通知

```bash
uv run agentbell test
```

如果看到通知并听到提示音，说明工作正常。

### 4. 全局安装（可选）

```bash
uv tool install .
```

安装后可以直接使用 `agentbell` 命令，无需 `uv run`。

### 5. 安装 Claude Code hooks

```bash
uv run agentbell install-claude-hooks
```

这会修改 `%USERPROFILE%\.claude\settings.json`，安装前会自动备份。

### 6. 验证 hooks

在 Claude Code 中运行 `/hooks`，应该能看到 AgentBell 的 hooks。

## 卸载

### 卸载 Claude Code hooks

```bash
uv run agentbell uninstall-claude-hooks
```

### 回滚 settings.json

如果需要手动回滚，使用安装时自动创建的备份：

```cmd
copy "%USERPROFILE%\.claude\settings.backup.<timestamp>.json" "%USERPROFILE%\.claude\settings.json"
```

备份文件位于 `%USERPROFILE%\.claude\` 目录下，文件名格式为 `settings.backup.<时间戳>.json`。

## CLI 命令

| 命令 | 说明 |
|------|------|
| `agentbell test` | 发送测试通知 |
| `agentbell notify --title "..." --message "..." --kind permission` | 发送授权提醒 |
| `agentbell notify --title "..." --message "..." --kind done` | 发送完成提醒 |
| `agentbell install-claude-hooks` | 安装 Claude Code hooks |
| `agentbell uninstall-claude-hooks` | 卸载 Claude Code hooks |

## 常见问题

### Q: 没有通知出现？

1. 检查 Windows 通知设置是否开启
2. 检查专注助手 / 免打扰是否关闭
3. 查看日志：`%USERPROFILE%\.agentbell\logs\agentbell.log`

### Q: 没有声音？

1. 检查系统音量是否静音
2. 运行 `uv run agentbell test` 测试
3. 虚拟机或 RDP 环境可能不支持 `winsound`

### Q: PowerShell 报错？

AgentBell **不使用 PowerShell**。如果看到 PowerShell 错误，来自其他工具。

### Q: `/hooks` 看不到 AgentBell hooks？

1. 重新运行 `uv run agentbell install-claude-hooks`
2. 重启 Claude Code
3. 检查 `%USERPROFILE%\.claude\settings.json` 内容

### Q: 多个 Claude Code 会话同时触发会冲突吗？

不会。每个 hook 调用在独立进程中运行，通知会堆叠在 Windows 通知中心，不会互相阻塞。

### Q: 为什么不用 Stop hook？

Stop hook 会在每次 Claude Code 回复后触发，太频繁。AgentBell 使用 `Notification + idle_prompt`，只在 Claude Code 真正等待输入时才触发，提供有意义的提醒而不是噪音。

## 许可证

MIT License
