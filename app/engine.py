import subprocess
import threading
import time
import logging
from typing import Optional, Any
from collections.abc import Sequence, Mapping
from app.storage import Macro, ActionSpec

logger = logging.getLogger("pushie.engine")

def run_cmd(*args: str) -> str:
    try:
        cp = subprocess.run(args, capture_output=True, text=True, check=True)
        return cp.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(args)} - {e}")
        return ""

class PulseAudioHelper:
    @staticmethod
    def get_default_source() -> str:
        return run_cmd("pactl", "get-default-source")

    @staticmethod
    def toggle_mic(source: str, state: bool) -> None:
        # State: True = Unmuted (mute=0), False = Muted (mute=1)
        logger.debug(f"{'Unmuting' if state else 'Muting'} mic: {source}")
        run_cmd("pactl", "set-source-mute", source, "0" if state else "1")

    @staticmethod
    def set_source_volume(source: str, volume: str) -> None:
        logger.debug(f"Setting source volume for {source} to {volume}")
        run_cmd("pactl", "set-source-volume", source, volume)

    @staticmethod
    def get_app_sources() -> list[tuple[str, str, str]]:
        output = run_cmd("pactl", "list", "source-outputs")
        if not output:
            return []
        sources = output.split("Source Output")
        app_sources: list[tuple[str, str, str]] = []
        for source in sources:
            index: Optional[str] = None
            name: Optional[str] = None
            binary: Optional[str] = None
            for line in source.splitlines():
                line = line.strip()
                if line.startswith("object.serial"):
                    index = line.split(" = ")[1].replace('"', '').strip()
                elif line.startswith("application.name") or line.startswith("node.name"):
                    name = line.split(" = ")[1].replace('"', '').strip()
                elif line.startswith("application.process.binary"):
                    binary = line.split(" = ")[1].replace('"', '').strip()
            binary = binary or "unknown*"
            if index is None or name is None:
                continue
            app_sources.append((index, name, binary))
        return app_sources

    @classmethod
    def apply_rules(cls, rules: Sequence[str], source: str, volume: str) -> None:
        logger.debug(f"=== Applying rules: {rules} to source '{source}' (vol: {volume}) ===")
        muted_apps: dict[str, bool] = {}
        allowed_apps: dict[str, bool] = {}
        for item in rules:
            item = item.strip()
            if item.startswith("!"):
                target = item[1:].lower()
                muted_apps[target] = True
            else:
                target = item.lower()
                allowed_apps[target] = True
        
        app_sources = cls.get_app_sources()
        if not app_sources:
            return
        
        for index, app_name, app_binary in app_sources:
            app_lc = app_name.lower()
            binary_lc = app_binary.lower()
            
            def _name_matches(name_lc: str, rules_dict: Mapping[str, bool]) -> bool:
                return any(k in name_lc for k in rules_dict if k != "all")

            if "all" in allowed_apps or _name_matches(app_lc, allowed_apps) or _name_matches(binary_lc, allowed_apps):
                vol = volume
            elif "all" in muted_apps or _name_matches(app_lc, muted_apps) or _name_matches(binary_lc, muted_apps):
                vol = "0.0"
            else:
                vol = volume
            
            run_cmd("pactl", "set-source-output-volume", index, vol)

class MacroEngine:
    def __init__(self) -> None:
        self._running_actions: dict[str, tuple[threading.Thread, threading.Event]] = {}  # macro_id -> (thread, stop_event)
        self._toggled_states: dict[str, bool] = {}   # macro_id -> bool
        self._active_macros: dict[str, Macro] = {}   # macro_id -> Macro
        self.lock = threading.Lock()
        self._held_keys: dict[str, set[str]] = {}
        self._held_keys_thread = threading.Thread(target=self._keep_keys_pressed_loop, daemon=True)
        self._held_keys_thread.start()

    def _keep_keys_pressed_loop(self) -> None:
        while True:
            time.sleep(0.1)
            keys_to_press = set()
            with self.lock:
                for keys_set in self._held_keys.values():
                    keys_to_press.update(keys_set)
            for key in keys_to_press:
                if key:
                    subprocess.run(["xdotool", "keydown", key], check=False)

    def handle_activate(self, macro: Macro) -> None:
        if not macro.active:
            return
        
        if macro.work_only_pressed:
            with self.lock:
                if macro.id in self._running_actions:
                    return
        
        logger.info(f"Activating macro: {macro.name} (ID: {macro.id})")
        with self.lock:
            self._active_macros[macro.id] = macro
            if macro.work_only_pressed:
                # Hold mode: run press actions in loop or once
                self._stop_macro_thread_locked(macro.id)
                self._start_macro_thread_locked(macro, macro.press_actions, loop=macro.loop_while_held)
            else:
                # Toggle mode: toggle current state
                current_state = self._toggled_states.get(macro.id, False)
                new_state = not current_state
                self._toggled_states[macro.id] = new_state
                
                self._stop_macro_thread_locked(macro.id)
                if new_state:
                    self._start_macro_thread_locked(macro, macro.press_actions, loop=macro.loop_while_held)
                else:
                    self._start_macro_thread_locked(macro, macro.release_actions, loop=False)

    def handle_deactivate(self, macro: Macro) -> None:
        if not macro.active:
            return
        
        if macro.work_only_pressed:
            logger.info(f"Deactivating macro: {macro.name} (ID: {macro.id})")
            with self.lock:
                self._active_macros[macro.id] = macro
                self._stop_macro_thread_locked(macro.id)
                self._start_macro_thread_locked(macro, macro.release_actions, loop=False)

    def _start_macro_thread_locked(self, macro: Macro, actions: Sequence[ActionSpec], loop: bool = False) -> None:
        if not actions:
            return
            
        logger.debug(f"Starting action sequence thread for macro ID: {macro.id} (loop={loop})")
        stop_event = threading.Event()
        t = threading.Thread(
            target=self._execute_actions_loop,
            args=(macro.id, actions, loop, stop_event),
            daemon=True
        )
        self._running_actions[macro.id] = (t, stop_event)
        t.start()

    def _stop_macro_thread_locked(self, macro_id: str) -> None:
        if macro_id in self._running_actions:
            logger.debug(f"Stopping action sequence thread for macro ID: {macro_id}")
            t, stop_event = self._running_actions[macro_id]
            stop_event.set()
            t.join(timeout=0.1)
            del self._running_actions[macro_id]

        if macro_id in self._held_keys:
            released_keys = list(self._held_keys[macro_id])
            for key in released_keys:
                subprocess.run(["xdotool", "keyup", key], check=False)
            del self._held_keys[macro_id]

    def _execute_actions_loop(self, macro_id: str, actions: Sequence[ActionSpec], loop: bool, stop_event: threading.Event) -> None:
        display_w, display_h = 1920, 1080
        try:
            geometry = run_cmd("xdotool", "getdisplaygeometry")
            if geometry:
                parts = geometry.split()
                if len(parts) >= 2:
                    display_w, display_h = int(parts[0]), int(parts[1])
        except Exception:
            pass

        while not stop_event.is_set():
            for action in actions:
                if stop_event.is_set():
                    break
                
                atype = action.type
                props = action.properties
                
                if atype == "key_press":
                    key = props.get("key", "")
                    logger.debug(f"Action done: press key '{key}'")
                    subprocess.run(["xdotool", "keydown", key], check=False)
                    with self.lock:
                        if macro_id not in self._held_keys:
                            self._held_keys[macro_id] = set()
                        self._held_keys[macro_id].add(key)
                elif atype == "key_release":
                    key = props.get("key", "")
                    logger.debug(f"Action done: release key '{key}'")
                    subprocess.run(["xdotool", "keyup", key], check=False)
                    with self.lock:
                        if macro_id in self._held_keys:
                            self._held_keys[macro_id].discard(key)
                elif atype == "key_tap":
                    key = props.get("key", "")
                    logger.debug(f"Action done: tap key '{key}'")
                    subprocess.run(["xdotool", "key", key], check=False)
                elif atype == "mouse_click":
                    btn = props.get("button", 1)
                    logger.debug(f"Action done: click mouse button {btn}")
                    subprocess.run(["xdotool", "click", str(btn)], check=False)
                elif atype == "mouse_move":
                    xp = float(props.get("xp", 0.0))
                    x = int(props.get("x", 0))
                    yp = float(props.get("yp", 0.0))
                    y = int(props.get("y", 0))
                    abs_x = int(display_w * xp + x)
                    abs_y = int(display_h * yp + y)
                    logger.debug(f"Action done: move mouse to ({abs_x}, {abs_y})")
                    subprocess.run(['ydotool', 'mousemove', '--absolute', '0', '0'], check=False)
                    subprocess.run(['ydotool', 'mousemove', str(abs_x), str(abs_y)], check=False)
                elif atype == "delay":
                    ms = props.get("milliseconds", 0)
                    logger.debug(f"Action done: delay {ms}ms")
                    time.sleep(ms / 1000.0)
                elif atype == "mic_toggle":
                    unmute = props.get("unmute", True)
                    src = PulseAudioHelper.get_default_source()
                    if src:
                        logger.debug(f"Action doing: mic_toggle target_unmute={unmute}")
                        PulseAudioHelper.toggle_mic(src, unmute)
                elif atype == "mic_rules":
                    rules = props.get("rules", [])
                    vol = str(props.get("volume", "1.0"))
                    src = PulseAudioHelper.get_default_source()
                    if src:
                        logger.debug(f"Action doing: mic_rules volume={vol} rules={rules}")
                        PulseAudioHelper.set_source_volume(src, vol)
                        PulseAudioHelper.apply_rules(rules, src, vol)

            if not loop:
                break

    def stop_all(self) -> None:
        logger.info("Stopping all macros...")
        with self.lock:
            # Capture currently running/held macros
            running_macro_ids = list(self._running_actions.keys())
            
            # Stop all running action threads
            for mid in running_macro_ids:
                self._stop_macro_thread_locked(mid)
            
            self._toggled_states.clear()
            
            # For each macro that was running, run its release sequence if available
            threads_to_join = []
            for mid in running_macro_ids:
                macro = self._active_macros.get(mid)
                if macro and macro.release_actions:
                    self._start_macro_thread_locked(macro, macro.release_actions, loop=False)
                    if macro.id in self._running_actions:
                        t, _ = self._running_actions[macro.id]
                        threads_to_join.append(t)
            
            # Wait for all release sequence threads to finish execution before returning
            for t in threads_to_join:
                t.join(timeout=2.0)
