#!/usr/bin/env python3
"""
DeepSeek Harness MCP Bridge
---------------------------
Connects Claude Desktop (Executive Technical Manager & Lead Architect)
to the live DeepSeek Harness Web UI running on http://127.0.0.1:3080.

Features:
- Live Web UI synchronization (watch DeepSeek work in your browser).
- Complete untruncated responses with reasoning traces & tool execution reporting.
- Smart Model Routing: choose between DeepSeek-V4.1-Flash and DeepSeek-V4-Pro.
- Configurable reasoning efforts: off, low, high, max.
- Automatic clean session renaming in the browser sidebar.
- Non-blocking 40-second async handoff (Claude Desktop never hits the 4-minute crash barrier).
- Workspace directory binding.
- Dynamic credential resolution from ~/.dsh/.credentials.yaml with HMAC-SHA256 cookie signing.
- Zero copy-paste code enforcement for Manager persona.
"""

import os
import sys
import json
import time
import uuid
import hmac
import hashlib
import base64
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    import yaml
except ImportError:
    yaml = None

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer

MANAGER_INSTRUCTIONS = """
[CRITICAL SYSTEM ARCHITECTURE DIRECTIVE: EXECUTIVE ENGINEERING MANAGER]
You are operating as the Executive Technical Manager and Lead Architect.
You do NOT implement code yourself. You do NOT output raw code blocks or code diffs in chat for the user to copy-paste.

DeepSeek Harness is your Autonomous Engineering Team executing live in the local browser Web UI (http://127.0.0.1:3080).
Your job is to:
1. Brainstorm, analyze requirements, and create a comprehensive Project Specification and Milestone Plan.
2. Delegate each technical implementation phase to DeepSeek Harness using `delegate_to_deepseek`.
   - SMART MODEL ROUTING:
     * Use `model="deepseek-flash"` with `reasoning_effort="low"` or `"off"` for fast file searches, simple refactors, documentation, and routine edits.
     * Use `model="deepseek-v4-pro"` with `reasoning_effort="high"` or `"max"` for complex algorithmic architecture, complex bugs, and large refactors.
3. Inform the user that they can watch DeepSeek execute live in their web browser at http://127.0.0.1:3080.
4. When tasks take longer than 40 seconds, use `inspect_deepseek_session` to monitor progress.
5. Review the execution results and provide feedback via `send_feedback_to_deepseek`.
6. Enforce modern UI/UX design standards (mobile-first, clean color palettes, Tailwind, responsive layouts).
"""

app = MCPServer(
    "deepseek-bridge",
    instructions=MANAGER_INSTRUCTIONS
)

# Configuration & Paths
HOME = Path.home()
CREDENTIALS_FILE = HOME / ".dsh" / ".credentials.yaml"
DSH_HOST = os.environ.get("DSH_HOST", "127.0.0.1:3080")
DSH_URL = f"http://{DSH_HOST}"
LOG_FILE = Path(__file__).parent / "bridge.log"

_CACHED_COOKIE: Optional[str] = None
_COOKIE_EXPIRY: float = 0


def log(msg: str) -> None:
    """Append log messages with timestamp."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass


def get_auth_cookie() -> str:
    """
    Dynamically discover DeepSeek Harness browser session secret
    and mint a valid signed authentication cookie.
    """
    global _CACHED_COOKIE, _COOKIE_EXPIRY
    now = time.time()
    if _CACHED_COOKIE and now < _COOKIE_EXPIRY:
        return _CACHED_COOKIE

    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(f"DeepSeek Harness credentials file not found at {CREDENTIALS_FILE}")

    with open(CREDENTIALS_FILE, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    secret_b64 = None
    if yaml is not None:
        try:
            creds = yaml.safe_load(content)
            secret_b64 = creds["records"]["client-connection/browser-session"]["payload"]["secret"]
        except Exception:
            pass

    if not secret_b64:
        import re
        m = re.search(r"secret:\s*([A-Za-z0-9_-]+)", content)
        if m:
            secret_b64 = m.group(1)

    if not secret_b64:
        raise ValueError("Could not extract browser-session secret from ~/.dsh/.credentials.yaml")

    # Base64url decode secret
    secret = base64.urlsafe_b64decode(secret_b64 + "=" * (-len(secret_b64) % 4))
    cookie_name = "dsh-auth-" + base64.urlsafe_b64encode(hashlib.sha256(DSH_HOST.encode()).digest()).decode().rstrip("=")

    issued_at = int(now * 1000)
    # 7 day cookie lifetime
    expires_at = issued_at + (7 * 24 * 3600 * 1000)

    payload = {
        "version": 1,
        "authority": DSH_HOST,
        "issuedAt": issued_at,
        "expiresAt": expires_at
    }

    body_b64 = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode().rstrip("=")
    sig_b64 = base64.urlsafe_b64encode(hmac.new(secret, body_b64.encode("utf-8"), hashlib.sha256).digest()).decode().rstrip("=")

    _CACHED_COOKIE = f"{cookie_name}=v1.{body_b64}.{sig_b64}"
    _COOKIE_EXPIRY = now + (24 * 3600)  # Refresh daily
    return _CACHED_COOKIE


def rpc_call(endpoint: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a typed Typert RPC request against DeepSeek Harness Web API."""
    cookie = get_auth_cookie()
    rpc_id = str(uuid.uuid4())
    req_body = {
        "type": "client-request",
        "rpcId": rpc_id,
        "method": endpoint,
        "payload": {"args": args}
    }

    url = f"{DSH_URL}/api/{endpoint}"
    data = json.dumps(req_body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Cookie": cookie,
            "Content-Type": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if not res.get("result", {}).get("ok", False):
                err = res.get("result", {}).get("error", {})
                raise RuntimeError(f"DeepSeek RPC Error ({err.get('code')}): {err.get('message')}")
            return res.get("result", {}).get("value", {})
    except urllib.error.URLError as e:
        if "10061" in str(e) or "refused" in str(e).lower():
            raise ConnectionError(
                f"Cannot connect to DeepSeek Harness on {DSH_URL}. "
                "Please make sure 'dsh web' is running in a terminal."
            )
        raise


def get_session_turn_details(session_id: str, as_of_seq: int) -> Dict[str, Any]:
    """
    Retrieve untruncated final response, executed tools, and reasoning traces
    directly from the session event log.
    """
    if as_of_seq <= 0:
        return {"response": "", "reasoning": "", "tools_called": []}
    try:
        page = rpc_call("session/page", {
            "request": {
                "address": {"kind": "session", "sessionId": session_id},
                "throughSeq": as_of_seq,
                "maxMessages": 50
            }
        })
        records = page.get("records", [])
        tools_called = []
        assistant_text = ""
        reasoning_text = ""

        for r in records:
            ev = r.get("event", {})
            ev_type = ev.get("type")
            if ev_type == "tool/call":
                tname = ev.get("data", {}).get("name")
                if tname and tname not in tools_called:
                    tools_called.append(tname)
            elif ev_type == "assistant/message":
                msg = ev.get("data", {}).get("message", {})
                for part in msg.get("content", []):
                    if part.get("type") == "text":
                        assistant_text = part.get("text", "")
                    elif part.get("type") == "reasoning":
                        reasoning_text = part.get("text", "")

        return {
            "response": assistant_text,
            "reasoning": reasoning_text,
            "tools_called": tools_called
        }
    except Exception as e:
        log(f"Error reading turn details for {session_id}: {e}")
        return {"response": "", "reasoning": "", "tools_called": []}


def wait_for_session_turn(session_id: str, timeout_seconds: int = 40) -> Dict[str, Any]:
    """
    Poll session state until the model completes its current response turn,
    or until the strict 40-second non-blocking ceiling is reached.
    """
    deadline = time.time() + timeout_seconds
    log(f"Waiting for DeepSeek session {session_id} (timeout={timeout_seconds}s)")

    last_response = ""
    last_reasoning = ""
    tools_called = []
    stats = {}
    as_of_seq = 0

    while time.time() < deadline:
        try:
            # 1. Check if session is actively running
            res_list = rpc_call("session/list", {"_request": {}})
            sessions = res_list.get("sessions", [])
            target = next((s for s in sessions if s.get("sessionId") == session_id), None)
            is_running = target.get("running", False) if target else False

            # 2. Check projections for turn outline and seq
            res_proj = rpc_call("session/projections", {"request": {"sessionId": session_id}})
            as_of_seq = res_proj.get("asOfSeq", 0)
            vals = res_proj.get("values", {})
            stats = vals.get("sessionStats", {})
            outline = vals.get("turnOutline", [])

            if outline:
                latest_turn = outline[-1]
                resp = latest_turn.get("response", "")
                if resp:
                    last_response = resp

            # If agent is no longer running and we have reached a sequence point, fetch full untruncated content!
            if not is_running and last_response:
                details = get_session_turn_details(session_id, as_of_seq)
                full_resp = details["response"] or last_response
                full_reasoning = details["reasoning"]
                tools_called = details["tools_called"]

                log(f"Session {session_id} completed turn successfully. Tools: {tools_called}")
                return {
                    "status": "completed",
                    "session_id": session_id,
                    "agent_response": full_resp,
                    "reasoning_summary": full_reasoning or None,
                    "tools_executed": tools_called,
                    "stats": {
                        "turns": stats.get("turns", 0),
                        "steps": stats.get("steps", 0),
                        "llm_seconds": round(stats.get("llmMs", 0) / 1000, 1),
                        "tool_seconds": round(stats.get("toolMs", 0) / 1000, 1)
                    }
                }
        except Exception as e:
            log(f"Polling warning for {session_id}: {e}")

        time.sleep(1.5)

    # Reached the 40-second ceiling: return still_running to protect Claude Desktop from crashing
    log(f"Session {session_id} still running after {timeout_seconds}s. Handing off safely.")
    return {
        "status": "still_running",
        "session_id": session_id,
        "message": (
            "Task is actively running in DeepSeek Harness. You can watch it executing live in your browser at "
            f"{DSH_URL}. Please use `inspect_deepseek_session` in a few moments to review progress and final output."
        ),
        "partial_response": last_response or "DeepSeek is executing tools and reasoning...",
        "stats": stats
    }


# ==========================================
# MCP TOOLS EXPOSED TO CLAUDE DESKTOP
# ==========================================

@app.tool()
def delegate_to_deepseek(
    task_description: str,
    workspace_path: str,
    acceptance_criteria: Optional[str] = None,
    model: str = "deepseek-flash",
    reasoning_effort: str = "high",
    timeout_seconds: int = 45
) -> str:
    """[MANAGER TOOL] Delegate a technical task or implementation directive to DeepSeek Harness.
    
    Creates a new live session in DeepSeek Harness bound to the given workspace directory,
    sets the model and reasoning tier, names the session cleanly, and tracks execution.
    The user can watch execution live in their web browser at http://127.0.0.1:3080.
    
    AUTONOMOUS MULTI-STEP EXECUTION:
    When executing a multi-step plan, you have full executive authority to chain steps automatically.
    Do NOT pause to ask the user for confirmation between steps unless an unrecoverable failure occurs.
    Upon receiving a successful result for Step N, immediately call send_feedback_to_deepseek with Step N+1.
    Continue until the entire plan is complete and verified, then present the final summary to the user.
    
    Args:
        task_description: Clear, actionable implementation instructions.
        workspace_path: Absolute directory where code must be inspected or created.
        acceptance_criteria: Optional verification checklist.
        model: Model to use ('deepseek-flash' for speed, 'deepseek-v4-pro' for deep reasoning).
        reasoning_effort: Reasoning effort ('off', 'low', 'high', 'max').
        timeout_seconds: Optional timeout (internally capped to prevent Claude Desktop UI crashes).
    """
    log(f"delegate_to_deepseek called: workspace={workspace_path}, model={model}, reasoning={reasoning_effort}")

    # Validate workspace path
    wp = Path(workspace_path).expanduser().resolve()
    if not wp.exists():
        wp.mkdir(parents=True, exist_ok=True)

    # 1. Create a live session in DeepSeek Harness
    create_val = rpc_call("session/create", {"request": {"cwd": str(wp)}})
    session_id = create_val.get("sessionId")
    if not session_id:
        raise RuntimeError("DeepSeek Harness failed to return a valid sessionId.")

    log(f"Created DeepSeek session: {session_id}")

    # 2. Select Model and Reasoning Effort
    target_model = model if model in ["deepseek-flash", "deepseek-v4-pro"] else "deepseek-flash"
    target_effort = reasoning_effort if reasoning_effort in ["off", "low", "high", "max"] else "high"
    try:
        rpc_call("session/selectModel", {
            "request": {
                "sessionId": session_id,
                "provider": "deepseek-official",
                "model": target_model,
                "reasoningEffort": target_effort
            }
        })
        log(f"Configured model={target_model}, effort={target_effort} for {session_id}")
    except Exception as e:
        log(f"Model selection warning: {e}")

    # 3. Rename session for clean Web UI display
    try:
        clean_title = task_description.strip().split("\n")[0][:45]
        rpc_call("session/rename", {
            "request": {
                "sessionId": session_id,
                "title": clean_title
            }
        })
    except Exception as e:
        log(f"Session rename warning: {e}")

    # 4. Format managerial directive
    formatted_prompt = f"""[EXECUTIVE DIRECTIVE FROM LEAD ARCHITECT]
Workspace: {wp}
Task Description:
{task_description}
"""
    if acceptance_criteria:
        formatted_prompt += f"\nAcceptance Criteria / Verification:\n{acceptance_criteria}\n"

    formatted_prompt += (
        "\nCRITICAL DIRECTIVE:\n"
        f"1. You must work strictly inside the target project directory: {wp}.\n"
        "2. Do not leave the project directory or modify external files.\n"
        "3. Complete the task thoroughly and report back when finished."
    )

    # 5. Queue prompt
    rpc_call("session/prompt", {
        "request": {
            "requestId": str(uuid.uuid4()),
            "sessionId": session_id,
            "mode": "queue",
            "content": [{"type": "text", "text": formatted_prompt}]
        }
    })
    log(f"Queued prompt for {session_id}")

    # 6. Wait for response turn with safety timeout
    result = wait_for_session_turn(session_id, timeout_seconds=40)
    return json.dumps(result, indent=2)


@app.tool()
def send_feedback_to_deepseek(
    session_id: str,
    feedback: str,
    timeout_seconds: int = 45
) -> str:
    """[MANAGER TOOL] Send managerial review, follow-up feedback, or next-phase instructions to an existing DeepSeek session.
    
    AUTONOMOUS STEP ADVANCEMENT:
    When working through a multi-step plan, call this tool immediately to advance to the next step once the current step's acceptance criteria are met.
    Do NOT pause to ask the user for permission to proceed to subsequent steps. Execute all steps autonomously to completion.
    
    Args:
        session_id: The ID of the active DeepSeek session.
        feedback: The instructions, corrections, or follow-up prompt.
        timeout_seconds: Optional timeout parameter.
    """
    log(f"send_feedback_to_deepseek called: session={session_id}")

    rpc_call("session/prompt", {
        "request": {
            "requestId": str(uuid.uuid4()),
            "sessionId": session_id,
            "mode": "queue",
            "content": [{"type": "text", "text": feedback}]
        }
    })

    result = wait_for_session_turn(session_id, timeout_seconds=40)
    return json.dumps(result, indent=2)


@app.tool()
def inspect_deepseek_session(session_id: str) -> str:
    """[MANAGER TOOL] Inspect the live status, step count, and untruncated output of a running or completed DeepSeek session.
    
    Use this when a previous task returned 'still_running' to check if DeepSeek has finished.
    
    Args:
        session_id: The ID of the session to inspect.
    """
    log(f"inspect_deepseek_session called: session={session_id}")

    # Check running state from list
    res_list = rpc_call("session/list", {"_request": {}})
    sessions = res_list.get("sessions", [])
    target = next((s for s in sessions if s.get("sessionId") == session_id), None)
    is_running = target.get("running", False) if target else False

    # Check detailed projections
    res_proj = rpc_call("session/projections", {"request": {"sessionId": session_id}})
    as_of_seq = res_proj.get("asOfSeq", 0)
    vals = res_proj.get("values", {})
    stats = vals.get("sessionStats", {})
    outline = vals.get("turnOutline", [])
    title = vals.get("title", "")
    working_dir = vals.get("workingDirectory", "")

    status = "running" if is_running else "completed"

    # Get full untruncated response & tools executed
    details = get_session_turn_details(session_id, as_of_seq)
    full_response = details["response"]
    reasoning_summary = details["reasoning"]
    tools_called = details["tools_called"]

    if not full_response and outline:
        full_response = outline[-1].get("response", "")

    report = {
        "status": status,
        "session_id": session_id,
        "title": title,
        "working_directory": working_dir,
        "latest_response": full_response or ("Executing steps in browser..." if is_running else "No output recorded."),
        "reasoning_summary": reasoning_summary or None,
        "tools_executed": tools_called,
        "total_turns": len(outline),
        "steps_executed": stats.get("steps", 0),
        "llm_seconds": round(stats.get("llmMs", 0) / 1000, 1),
        "tool_seconds": round(stats.get("toolMs", 0) / 1000, 1),
        "web_ui_url": f"{DSH_URL}"
    }

    return json.dumps(report, indent=2)


@app.tool()
def cancel_deepseek_session(session_id: str) -> str:
    """[MANAGER TOOL] Abort or cancel an ongoing task in DeepSeek Harness."""
    log(f"cancel_deepseek_session called: session={session_id}")
    res = rpc_call("session/cancel", {"request": {"sessionId": session_id}})
    return json.dumps({"status": "cancelled", "session_id": session_id, "details": res}, indent=2)


if __name__ == "__main__":
    log("Starting DeepSeek Harness MCP Bridge...")
    app.run()
