# DeepSeek Harness <-> Claude Desktop MCP Bridge

A high-performance Model Context Protocol (MCP) bridge linking **Claude Desktop** (acting as Executive Technical Manager & Lead Architect) to the live **DeepSeek Harness Web UI** (`dsh web`).

---

## Features

- **Live Browser Observation:** Watch DeepSeek think, edit files, and execute commands in real time in your web browser at `http://127.0.0.1:3080`.
- **40-Second Non-Blocking Ceiling:** Eliminates Claude Desktop's 4-minute crash limit by safely handing control back with `still_running` for long tasks.
- **Dynamic Credential Discovery:** Automatically reads `~/.dsh/.credentials.yaml` and signs `dsh-auth` cookies using HMAC-SHA256.
- **Strict Manager Persona:** Instructs Claude to plan architecture and milestones, enforce modern UI/UX design standards, and delegate without copy-pasting code.
- **Multi-Server Compatible:** Runs harmoniously alongside the Antigravity bridge in Claude Desktop.

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

- `delegate_to_deepseek(task_description, workspace_path, acceptance_criteria)`: Starts a new session in DeepSeek bound to the specified directory.
- `send_feedback_to_deepseek(session_id, feedback)`: Sends review notes or next-step orders to an existing session.
- `inspect_deepseek_session(session_id)`: Checks progress, step count, tool timing, and latest output.
- `cancel_deepseek_session(session_id)`: Aborts a running task.
