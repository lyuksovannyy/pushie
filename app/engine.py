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
    def get_source_index(source: str) -> Optional[str]:
        """Resolve a source name (e.g. the default mic) to its pactl index."""
        output = run_cmd("pactl", "list", "sources")
        if not output:
            return None
        current_index: Optional[str] = None
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith("Source #"):
                current_index = stripped[len("Source #"):].strip()
            elif stripped.startswith("Name:") and current_index is not None:
                name = stripped[len("Name:"):].strip().replace('"', '')
                if name == source:
                    return current_index
        return None

    @staticmethod
    def get_app_sources() -> list[tuple[str, str, str, str]]:
        """Returns (index, app_name, binary, attached_source_index) tuples.

        attached_source_index is "" when it cannot be determined.
        """
        output = run_cmd("pactl", "list", "source-outputs")
        if not output:
            return []
        sources = output.split("Source Output")
        app_sources: list[tuple[str, str, str, str]] = []
        for source in sources:
            index: Optional[str] = None
            name: Optional[str] = None
            binary: Optional[str] = None
            attached_source: str = ""
            for line in source.splitlines():
                line = line.strip()
                if line.startswith("Source:"):
                    attached_source = line.split(":", 1)[1].strip()
                elif line.startswith("object.serial"):
                    index = line.split(" = ")[1].replace('"', '').strip()
                elif line.startswith("application.name") or line.startswith("node.name"):
                    name = line.split(" = ")[1].replace('"', '').strip()
                elif line.startswith("application.process.binary"):
                    binary = line.split(" = ")[1].replace('"', '').strip()
            binary = binary or "unknown*"
            if index is None or name is None:
                continue
            app_sources.append((index, name, binary, attached_source))
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

        # Only ever touch capture streams attached to the mic itself. Streams
        # from other sources (e.g. sink monitors) belong to screen recorders
        # like OBS/Discord capturing desktop audio - those carry other apps'
        # sounds and must never be modified by mic rules.
        mic_index = cls.get_source_index(source)
        app_sources = cls.get_app_sources()
        if not app_sources:
            return

        for index, app_name, app_binary, attached_source in app_sources:
            if mic_index and attached_source and attached_source != mic_index:
                logger.debug(f"Skipping source-output {index} ({app_name}): not capturing from mic '{source}'")
                continue

            app_lc = app_name.lower()
            binary_lc = app_binary.lower()
            
            def _name_matches(name_lc: str, rules_dict: Mapping[str, bool]) -> bool:
                return any(k in name_lc for k in rules_dict if k != "all")

            # A rule naming the app beats the catch-all "all" / "!all", so
            # "discord, !all" unmutes only Discord and "!vesktop, all" mutes
            # only vesktop. If an app is both muted and allowed by name, the
            # mute wins. Apps no rule covers are left unmuted.
            if _name_matches(app_lc, muted_apps) or _name_matches(binary_lc, muted_apps):
                vol = "0.0"
            elif _name_matches(app_lc, allowed_apps) or _name_matches(binary_lc, allowed_apps):
                vol = volume
            elif "all" in muted_apps:
                vol = "0.0"
            else:
                vol = volume

            run_cmd("pactl", "set-source-output-volume", index, vol)

class MacroEngine:
    def __init__(self) -> None:
        self._running_actions: dict[str, tuple[threading.Thread, threading.Event]] = {}  # macro_id -> (thread, stop_event)
        self._toggled_states: dict[str, bool] = {}   # macro_id -> bool
        self._pressed_states: dict[str, bool] = {}   # macro_id -> bool
        self._active_macros: dict[str, Macro] = {}   # macro_id -> Macro
        self.lock = threading.Lock()
        self._held_keys: dict[str, set[str]] = {}
        self._held_mouse_buttons: dict[str, set[int]] = {}  # macro_id -> set of mouse buttons
        self._keep_alive_thread = threading.Thread(target=self._keep_inputs_pressed_loop, daemon=True)
        self._keep_alive_thread.start()

    def _keep_inputs_pressed_loop(self) -> None:
        """Keep keys and mouse buttons pressed by re-sending down commands every 50ms."""
        while True:
            time.sleep(0.05)  # 50ms = 20Hz refresh, prevents premature release
            keys_to_press = set()
            buttons_to_press = set()
            
            with self.lock:
                for keys_set in self._held_keys.values():
                    keys_to_press.update(keys_set)
                for buttons_set in self._held_mouse_buttons.values():
                    buttons_to_press.update(buttons_set)
            
            for key in keys_to_press:
                if key:
                    subprocess.run(["xdotool", "keydown", key], check=False)
            
            for btn in buttons_to_press:
                if btn:
                    subprocess.run(["xdotool", "mousedown", str(btn)], check=False)

    def handle_activate(self, macro: Macro, current_app: str = "") -> None:
        if not macro.active:
            return
        
        # Check target apps before execution
        if macro.target_apps:
            current_app_lower = current_app.lower() if current_app else ""
            target_apps_lower = [app.lower() for app in macro.target_apps]
            if current_app_lower not in target_apps_lower:
                logger.debug(f"Macro {macro.name} skipped: current app '{current_app}' not in target list {macro.target_apps}")
                return
        
        # Execution lock - prevents re-entry (e.g. portal auto-repeat)
        if macro.work_only_pressed:
            with self.lock:
                if self._pressed_states.get(macro.id, False):
                    logger.debug(f"Macro {macro.name} press swallowed: already pressed (missed release?)")
                    return
                self._pressed_states[macro.id] = True
        
        logger.info(f"Activating macro: {macro.name} (ID: {macro.id})")
        with self.lock:
            self._active_macros[macro.id] = macro
            if macro.work_only_pressed:
                # Hold mode: run press actions in loop or once
                self._stop_macro_thread_locked(macro.id)
                self._start_macro_thread_locked(macro, macro.press_actions, loop=macro.loop_while_held)
            else:
                # Fire-and-forget: run press actions once per activation.
                # Release actions are not used in this mode.
                self._stop_macro_thread_locked(macro.id)
                self._start_macro_thread_locked(macro, macro.press_actions, loop=False)

    def handle_deactivate(self, macro: Macro, current_app: str = "") -> None:
        if not macro.active:
            return
        
        if macro.work_only_pressed:
            # A physical key release must ALWAYS be processed. Gating this on
            # the active-window check leaves the macro stuck in "pressed"
            # state whenever app detection misses (fullscreen games, focus
            # flicker, Proton window classes): the next press is then
            # swallowed by the re-entry guard in handle_activate, forcing a
            # double press before anything happens, and release actions
            # (e.g. mic mute) never run. Target-app gating stays on activate
            # only - spurious releases are already ignored below.
            with self.lock:
                was_pressed = self._pressed_states.get(macro.id, False)
                self._pressed_states[macro.id] = False
            if not was_pressed:
                return
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
            t.join(timeout=0.05)  # Reduced from 0.1s to 0.05s
            del self._running_actions[macro_id]

        # Release all held keys
        if macro_id in self._held_keys:
            released_keys = list(self._held_keys[macro_id])
            for key in released_keys:
                subprocess.run(["xdotool", "keyup", key], check=False)
            del self._held_keys[macro_id]
        
        # Release all held mouse buttons
        if macro_id in self._held_mouse_buttons:
            released_buttons = list(self._held_mouse_buttons[macro_id])
            for btn in released_buttons:
                subprocess.run(["xdotool", "mouseup", str(btn)], check=False)
            del self._held_mouse_buttons[macro_id]

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
                elif atype == "mouse_press":
                    btn = props.get("button", 1)
                    logger.debug(f"Action done: press mouse button {btn}")
                    subprocess.run(["xdotool", "mousedown", str(btn)], check=False)
                    with self.lock:
                        if macro_id not in self._held_mouse_buttons:
                            self._held_mouse_buttons[macro_id] = set()
                        self._held_mouse_buttons[macro_id].add(btn)
                elif atype == "mouse_release":
                    btn = props.get("button", 1)
                    logger.debug(f"Action done: release mouse button {btn}")
                    subprocess.run(["xdotool", "mouseup", str(btn)], check=False)
                    with self.lock:
                        if macro_id in self._held_mouse_buttons:
                            self._held_mouse_buttons[macro_id].discard(btn)
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
            self._pressed_states.clear()
            
            # For each macro that was running, run its release sequence if available.
            # Only hold-mode macros have a release phase; fire-and-forget macros
            # intentionally have nothing to release.
            threads_to_join = []
            for mid in running_macro_ids:
                macro = self._active_macros.get(mid)
                if macro and macro.work_only_pressed and macro.release_actions:
                    self._start_macro_thread_locked(macro, macro.release_actions, loop=False)
                    if macro.id in self._running_actions:
                        t, _ = self._running_actions[macro.id]
                        threads_to_join.append(t)
            
            # Wait for all release sequence threads to finish execution before returning
            for t in threads_to_join:
                t.join(timeout=2.0)
    
    def stop_all_fast(self) -> None:
        """Fast shutdown without waiting for threads - for app exit."""
        logger.info("Fast shutdown: stopping all macros")
        with self.lock:
            # Signal all threads to stop (don't wait for them)
            for mid in list(self._running_actions.keys()):
                _, stop_event = self._running_actions[mid]
                stop_event.set()
            
            # Collect all held inputs
            all_keys = set()
            all_buttons = set()
            
            for keys_set in self._held_keys.values():
                all_keys.update(keys_set)
            
            for buttons_set in self._held_mouse_buttons.values():
                all_buttons.update(buttons_set)
            
            # Clear all state immediately
            self._running_actions.clear()
            self._held_keys.clear()
            self._held_mouse_buttons.clear()
            self._toggled_states.clear()
            self._pressed_states.clear()
            self._active_macros.clear()
        
        # Release inputs outside lock (non-blocking)
        for key in all_keys:
            subprocess.Popen(["xdotool", "keyup", key], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        for btn in all_buttons:
            subprocess.Popen(["xdotool", "mouseup", str(btn)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        logger.info("All macros stopped")
