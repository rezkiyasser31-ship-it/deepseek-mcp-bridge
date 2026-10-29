#!/usr/bin/env python3
"""
DeepSeek MCP Bridge - Universal Cross-Platform Installer
-------------------------------------------------------
Automatically locates all Claude Desktop configuration files on Windows, macOS, or Linux,
and registers the DeepSeek Harness MCP server without overwriting existing servers.
"""

import sys
import os
import json
import glob
from pathlib import Path


def get_candidate_configs():
    """Discover all Claude Desktop configuration files across all platforms."""
    home = Path.home()
    candidates = []

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        localappdata = os.environ.get("LOCALAPPDATA")

        # Standard Windows config path
        if appdata:
            candidates.append(Path(appdata) / "Claude" / "claude_desktop_config.json")

        # Windows Store / Package paths
        if localappdata:
            pkg_pattern = os.path.join(localappdata, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude", "claude_desktop_config.json")
            candidates.extend([Path(p) for p in glob.glob(pkg_pattern)])
            pkg_3p_pattern = os.path.join(localappdata, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude-3p", "claude_desktop_config.json")
            candidates.extend([Path(p) for p in glob.glob(pkg_3p_pattern)])

            # Custom user-data-dir paths (Claude-Data)
            claude_data = Path(localappdata) / "Claude-Data"
            if claude_data.exists():
                candidates.extend(claude_data.rglob("claude_desktop_config.json"))

        # Claude Multi-Account profile directories
        multi_profiles = home / ".claude_multi" / "native_profiles"
        if multi_profiles.exists():
            candidates.extend(multi_profiles.rglob("claude_desktop_config.json"))

    elif sys.platform == "darwin":  # macOS
        mac_config = home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        candidates.append(mac_config)

    else:  # Linux
        linux_config = home / ".config" / "Claude" / "claude_desktop_config.json"
        candidates.append(linux_config)

    # De-duplicate while preserving order
    seen = set()
    unique_candidates = []
    for c in candidates:
        resolved = str(c.resolve()) if c.exists() else str(c)
        if resolved not in seen:
            seen.add(resolved)
            unique_candidates.append(c)

    return unique_candidates


def install():
    bridge_dir = Path(__file__).parent.resolve()
    server_path = str(bridge_dir / "server.py")
    python_exe = sys.executable

    print("==================================================")
    print("  DeepSeek Harness <-> Claude Desktop MCP Bridge  ")
    print("==================================================")
    print(f"[+] Python Executable: {python_exe}")
    print(f"[+] Server Path:       {server_path}")
    print()

    # Discover candidate paths
    candidates = get_candidate_configs()
    if not candidates:
        print("[-] No Claude Desktop configuration directories found.")
        print("    Please ensure Claude Desktop is installed on this machine.")
        return 1

    success_count = 0
    for config_path in candidates:
        config_path = Path(config_path)
        config_dir = config_path.parent

        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            config = {}
            if config_path.exists():
                try:
                    with open(config_path, "r", encoding="utf-8-sig") as f:
                        content = f.read().strip()
                        if content:
                            config = json.loads(content)
                except Exception as e:
                    print(f"[-] Warning parsing {config_path}: {e}")

            if "mcpServers" not in config:
                config["mcpServers"] = {}

            config["mcpServers"]["deepseek"] = {
                "command": python_exe,
                "args": [server_path]
            }

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)

            print(f"[+] Registered in: {config_path}")
            success_count += 1
        except Exception as e:
            print(f"[-] Failed to update {config_path}: {e}")

    print()
    if success_count > 0:
        print(f"[SUCCESS] Successfully registered DeepSeek MCP bridge in {success_count} config file(s)!")
        print("Next step: Restart Claude Desktop, ensure 'dsh web' is running on port 3080, and enjoy!")
        return 0
    else:
        print("[-] Could not write to any Claude configuration file.")
        return 1


if __name__ == "__main__":
    sys.exit(install())
