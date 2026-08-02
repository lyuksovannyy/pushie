import json
import logging
import os
import platform
import re
import shutil
import socket
import subprocess
import time
from functools import lru_cache
from typing import Callable, Optional

logger = logging.getLogger("pushie.window_detector")

# ==========================================
# 1. Distro Detection & LRU Cached Helpers
# ==========================================

@lru_cache(maxsize=1)
def get_distro_info() -> dict:
    """Retrieve OS/distro information (cached)."""
    info = {"id": "linux", "name": "Linux", "pretty_name": "Linux"}
    if hasattr(platform, "freedesktop_os_release"):
        try:
            os_rel = platform.freedesktop_os_release()
            info["id"] = os_rel.get("ID", "linux")
            info["name"] = os_rel.get("NAME", "Linux")
            info["pretty_name"] = os_rel.get("PRETTY_NAME", info["name"])
            return info
        except Exception as e:
            logger.debug("freedesktop_os_release error: %s", e)

    if os.path.exists("/etc/os-release"):
        try:
            with open("/etc/os-release", "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        info[k.lower()] = v.strip("\"'\n")
        except Exception as e:
            logger.debug("Failed reading /etc/os-release: %s", e)
    return info


@lru_cache(maxsize=32)
def has_command(cmd: str) -> bool:
    """Check if a CLI tool is available on PATH (cached)."""
    return shutil.which(cmd) is not None


@lru_cache(maxsize=256)
def get_process_name_from_pid(pid: int) -> Optional[str]:
    """Resolve PID to executable process name via /proc (cached)."""
    if not pid or pid <= 0:
        return None
    try:
        with open(f"/proc/{pid}/comm", "r", encoding="utf-8") as f:
            comm = f.read().strip()
            if comm:
                return comm
    except Exception:
        pass
    try:
        with open(f"/proc/{pid}/cmdline", "r", encoding="utf-8") as f:
            cmd = f.read().split("\0")[0]
            if cmd:
                return os.path.basename(cmd)
    except Exception:
        pass
    return None


# ==========================================
# 2. Active Window Detection Logic
# ==========================================

def get_active_window_process_name() -> Optional[str]:
    """Returns the process name (e.g. 'firefox', 'code', 'kitty') of the active window on Linux."""
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

    # 1. Hyprland (hyprctl)
    if ("hyprland" in desktop or os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")) and has_command("hyprctl"):
        try:
            out = subprocess.check_output(
                ["hyprctl", "activewindow", "-j"], stderr=subprocess.DEVNULL
            )
            data = json.loads(out)
            pid = data.get("pid")
            if pid and pid > 0:
                pname = get_process_name_from_pid(pid)
                if pname:
                    return pname
            if data.get("initialClass"):
                return data["initialClass"]
            if data.get("class"):
                return data["class"]
        except Exception as e:
            logger.debug("Hyprland activewindow check failed: %s", e)

    # 2. Sway / i3 / wlroots (swaymsg)
    if ("sway" in desktop or os.environ.get("SWAYSOCK")) and has_command("swaymsg"):
        try:
            out = subprocess.check_output(
                ["swaymsg", "-t", "get_tree"], stderr=subprocess.DEVNULL
            )
            tree = json.loads(out)

            def _find_focused(node):
                if node.get("focused"):
                    return node
                for child in node.get("nodes", []) + node.get("floating_nodes", []):
                    res = _find_focused(child)
                    if res:
                        return res
                return None

            focused = _find_focused(tree)
            if focused:
                pid = focused.get("pid")
                if pid:
                    pname = get_process_name_from_pid(pid)
                    if pname:
                        return pname
                if focused.get("app_id"):
                    return focused["app_id"]
                win_props = focused.get("window_properties", {})
                if win_props.get("class"):
                    return win_props["class"]
        except Exception as e:
            logger.debug("Sway get_tree failed: %s", e)

    # 3. KDE Plasma Wayland (kdotool)
    if ("kde" in desktop or "plasma" in desktop) and has_command("kdotool"):
        try:
            win_id = (
                subprocess.check_output(
                    ["kdotool", "getactivewindow"], stderr=subprocess.DEVNULL
                )
                .decode()
                .strip()
            )
            if win_id:
                pid_out = (
                    subprocess.check_output(
                        ["kdotool", "getwindowpid", win_id],
                        stderr=subprocess.DEVNULL,
                    )
                    .decode()
                    .strip()
                )
                if pid_out.isdigit():
                    pname = get_process_name_from_pid(int(pid_out))
                    if pname:
                        return pname
                cls_name = (
                    subprocess.check_output(
                        ["kdotool", "getwindowclassName", win_id],
                        stderr=subprocess.DEVNULL,
                    )
                    .decode()
                    .strip()
                )
                if cls_name:
                    return cls_name
        except Exception as e:
            logger.debug("kdotool activewindow failed: %s", e)

    # 4. GNOME Wayland (gdbus Shell Introspect API)
    if "gnome" in desktop and has_command("gdbus"):
        try:
            out = subprocess.check_output(
                [
                    "gdbus",
                    "call",
                    "--session",
                    "--dest",
                    "org.gnome.Shell.Introspect",
                    "--object-path",
                    "/org/gnome/Shell/Introspect",
                    "--method",
                    "org.gnome.Shell.Introspect.GetWindows",
                ],
                stderr=subprocess.DEVNULL,
            ).decode()

            pid_match = re.search(
                r"'has-focus':\s*<true>.*?'pid':\s*<(\d+)>", out, re.DOTALL
            )
            if pid_match:
                pname = get_process_name_from_pid(int(pid_match.group(1)))
                if pname:
                    return pname
            class_match = re.search(
                r"'has-focus':\s*<true>.*?'wm-class':\s*<'([^']+)'",
                out,
                re.DOTALL,
            )
            if class_match:
                return class_match.group(1)
        except Exception as e:
            logger.debug("GNOME Introspect.GetWindows failed: %s", e)

    # 5. X11 / Xwayland fallback (xdotool)
    if has_command("xdotool"):
        try:
            pid_out = (
                subprocess.check_output(
                    ["xdotool", "getactivewindow", "getwindowpid"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
            if pid_out.isdigit():
                pname = get_process_name_from_pid(int(pid_out))
                if pname:
                    return pname
        except Exception as e:
            logger.debug("xdotool getactivewindow failed: %s", e)

    # 6. X11 / Xwayland fallback (xprop)
    if has_command("xprop"):
        try:
            root_out = subprocess.check_output(
                ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                stderr=subprocess.DEVNULL,
            ).decode()
            match = re.search(r"0x[0-9a-fA-F]+", root_out)
            if match:
                win_id = match.group(0)
                pid_out = subprocess.check_output(
                    ["xprop", "-id", win_id, "_NET_WM_PID"],
                    stderr=subprocess.DEVNULL,
                ).decode()
                pid_match = re.search(r"\d+", pid_out)
                if pid_match:
                    pname = get_process_name_from_pid(int(pid_match.group(0)))
                    if pname:
                        return pname

                class_out = subprocess.check_output(
                    ["xprop", "-id", win_id, "WM_CLASS"],
                    stderr=subprocess.DEVNULL,
                ).decode()
                classes = re.findall(r'"(.*?)"', class_out)
                if classes:
                    return classes[-1]
        except Exception as e:
            logger.debug("xprop active window lookup failed: %s", e)

    return None


# ==========================================
# 3. Event Listener / Poller Watcher
# ==========================================

def _listen_hyprland_socket(callback: Callable[[str], None]) -> bool:
    """Hyprland event socket connection."""
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if not signature or not runtime_dir:
        return False
    sock_path = f"{runtime_dir}/hypr/{signature}/.socket2.sock"
    if not os.path.exists(sock_path):
        return False

    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(sock_path)
        last_app = None
        buffer = ""
        while True:
            data = s.recv(4096).decode("utf-8", errors="ignore")
            if not data:
                break
            buffer += data
            lines = buffer.split("\n")
            buffer = lines.pop()
            for line in lines:
                if line.startswith("activewindow>>"):
                    current_app = get_active_window_process_name()
                    if current_app and current_app != last_app:
                        callback(current_app)
                        last_app = current_app
        return True
    except Exception as e:
        logger.debug("Hyprland socket event listener stopped: %s", e)
        return False


def _listen_xprop_spy(callback: Callable[[str], None]) -> bool:
    """X11 / Xwayland xprop -spy event listener."""
    if not has_command("xprop"):
        return False
    try:
        proc = subprocess.Popen(
            ["xprop", "-spy", "-root", "_NET_ACTIVE_WINDOW"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        last_app = None
        if proc.stdout:
            for _ in iter(proc.stdout.readline, ""):
                current_app = get_active_window_process_name()
                if current_app and current_app != last_app:
                    callback(current_app)
                    last_app = current_app
        return True
    except Exception as e:
        logger.debug("xprop -spy listener stopped: %s", e)
        return False


def watch_active_window(
    callback: Callable[[str], None], poll_interval: float = 1.0
):
    """
    Monitors active window changes. Attempts native event streams first;
    falls back to 1-second polling if events are unsupported.
    """
    # Try Hyprland event socket
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        if _listen_hyprland_socket(callback):
            return

    # Try X11 xprop -spy listener
    if os.environ.get("DISPLAY") and has_command("xprop"):
        if _listen_xprop_spy(callback):
            return

    # Fallback: 1-second Poller Loop
    last_app = None
    while True:
        current_app = get_active_window_process_name()
        if current_app and current_app != last_app:
            callback(current_app)
            last_app = current_app
        time.sleep(poll_interval)
