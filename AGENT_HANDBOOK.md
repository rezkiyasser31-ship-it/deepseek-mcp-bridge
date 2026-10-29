# DeepSeek Harness Agent Handbook & Architecture

**Target Audience:** AI Agents & Developers  
**Purpose:** Explains the architecture, RPC protocol, authentication, and safeguards of the Claude-to-DeepSeek Harness MCP Bridge.

---

## 1. System Architecture

```
+-------------------------------------------------------------+
|                   Claude Desktop (Manager)                  |
|          Lead Architect: Plans, delegates, reviews          |
+------------------------------+------------------------------+
                               | Model Context Protocol (stdio)
                               v
+-------------------------------------------------------------+
|             DeepSeek MCP Bridge (server.py)                 |
|     - Mints HMAC-SHA256 Auth Cookies dynamically            |
|     - Enforces 40s Async Safe Return (Anti-Crash)           |
|     - Binds tasks to target workspace directory             |
+------------------------------+------------------------------+
                               | Typert RPC (HTTP /api)
                               v
+-------------------------------------------------------------+
|              DeepSeek Harness Web Server                    |
|             (http://127.0.0.1:3080 / dsh web)               |
|     - Executes tools, modifies files, runs bash commands    |
|     - Renders live progress in user's web browser           |
+-------------------------------------------------------------+
```

---

## 2. Solved Edge Cases & Safeguards

### A. The 40-Second Non-Blocking Ceiling (Claude Timeout Fix)
* **The Problem:** Claude Desktop has a hardcoded network timeout of roughly 4 minutes for MCP tool calls. DeepSeek coding tasks can easily take 5 to 10 minutes. If the tool blocks until completion, Claude crashes with "Server disconnected".
* **The Solution:** `server.py` polls DeepSeek's `session/list` and `session/projections` every 1.5 seconds. If the task finishes within 40 seconds, it returns `status: completed`. If the task takes longer, it safely hands control back to Claude after 40 seconds with `status: still_running`. Claude is instructed to poll using `inspect_deepseek_session` to check final results without risking a crash.

### B. Dynamic Browser Authentication (HMAC-SHA256)
* **The Mechanism:** `dsh web` protects its `/api` endpoint with loopback browser authentication. 
* **The Solution:** The bridge reads the secret from `~/.dsh/.credentials.yaml` (`client-connection/browser-session.payload.secret`), computes the authority hash for `127.0.0.1:3080`, and mints a valid `dsh-auth-<hash>` cookie signed with HMAC-SHA256. This grants the bridge full owner permissions without requiring manual token logins.

### C. Workspace Routing & Isolation
* **The Mechanism:** When `delegate_to_deepseek` is invoked, it calls `session/create` with `{"cwd": workspace_path}` and attaches an explicit architectural directive forcing DeepSeek to operate strictly within the target workspace.

### D. Safe Config Merging
* Windows PowerShell 5.1 corrupts `claude_desktop_config.json` with BOM headers. `install_bridge.ps1` executes an inline Python script with `utf-8-sig` to safely merge `deepseek` into `mcpServers` alongside existing tools (like `antigravity`).

---

## 3. Remote Typert Endpoints Used

All requests use HTTP POST to `http://127.0.0.1:3080/api/<endpoint>` with JSON payload:
```json
{
  "type": "client-request",
  "rpcId": "<uuid>",
  "method": "<endpoint>",
  "payload": {
    "args": { ... }
  }
}
```

1. **`session/create`**:
   - `args.request.cwd`: Working directory path.
   - Returns: `sessionId`.
2. **`session/prompt`**:
   - `args.request.sessionId`: Target session ID.
   - `args.request.mode`: `"queue"` (or `"steer"`).
   - `args.request.content`: Array of content blocks (`[{"type": "text", "text": "..."}]`).
3. **`session/list`**:
   - Returns array of active sessions with their `running: boolean` status and metadata.
4. **`session/projections`**:
   - `args.request.sessionId`: Target session ID.
   - Returns `turnOutline` (prompts and assistant responses), `sessionStats` (steps, turns, LLM ms, tool ms).
5. **`session/cancel`**:
   - Aborts an ongoing session.

---

## 4. Troubleshooting Guide

1. **"Cannot connect to DeepSeek Harness on http://127.0.0.1:3080"**:
   - Run `dsh web` in a terminal window to start the Web UI server.
2. **"DeepSeek Harness credentials file not found"**:
   - Verify `~/.dsh/.credentials.yaml` exists. If not, running `dsh web` for the first time will generate it automatically.
3. **Claude UI says "Server disconnected"**:
   - Ensure `dsh web` did not crash, and restart Claude Desktop to reset the MCP connection.
