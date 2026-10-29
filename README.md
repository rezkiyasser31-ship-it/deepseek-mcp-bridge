# DeepSeek Harness <-> Claude Desktop MCP Bridge

A high-performance Model Context Protocol (MCP) bridge linking **Claude Desktop** (acting as Executive Technical Manager & Lead Architect) to the live **DeepSeek Harness Web UI** (`dsh web`).

---

## Features

- **Live Browser Observation:** Watch DeepSeek think, edit files, and execute commands in real time in your web browser at `http://127.0.0.1:3080`.
- **Full Untruncated Telemetry:** Bypasses the 120-character summary truncation via `session/page`, delivering 100% of markdown outputs and reasoning traces.
- **Tool Execution Auditing:** Captures and reports exact tool calls (`pwsh`, `write`, `read`) executed by DeepSeek for accountability.
- **Dynamic Model & Reasoning Routing:** Easily switch between `deepseek-flash` (fast speed) and `deepseek-v4-pro` (complex reasoning) with adjustable effort (`off`, `low`, `high`, `max`).
- **Autonomous Multi-Step Chaining:** Enables hands-free execution across multi-step milestones without manual user prompts.
- **Active Wait Relay:** Automatically bridges tasks taking longer than 45 seconds via `inspect_deepseek_session` without disconnecting Claude or dropping message turns.
- **Dynamic Credential Discovery:** Automatically reads `~/.dsh/.credentials.yaml` and signs `dsh-auth` cookies using HMAC-SHA256 with 24h session caching.
- **Multi-Account Protection:** Installs across all 6 Claude Desktop configuration locations (including custom data directories and Claude Multi-Account profiles).

---

## Quick Setup

1. **Start DeepSeek Harness Web UI:**
   ```powershell
   dsh web
   ```
   *(Keep this terminal open or run it in the background).*

2. **Install the Bridge:**
   ```powershell
   cd C:\Users\yasser\.gemini\deepseek-mcp-bridge
   powershell.exe -ExecutionPolicy Bypass -File .\install_bridge.ps1
   ```

3. **Restart Claude Desktop:**
   Completely quit Claude Desktop from the system tray and open it again.

---

## MCP Tools Available in Claude

- `delegate_to_deepseek(task_description, workspace_path, acceptance_criteria, model, reasoning_effort, timeout_seconds)`: Starts a new session in DeepSeek bound to the specified directory.
- `send_feedback_to_deepseek(session_id, feedback, timeout_seconds)`: Sends review notes or next-step orders to an existing session.
- `inspect_deepseek_session(session_id, wait_seconds)`: Checks progress, step count, tool timing, and actively waits for completion.
- `cancel_deepseek_session(session_id)`: Aborts a running task.
