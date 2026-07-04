#!/usr/bin/env python3
import evdev
import time
import threading
import queue
import subprocess
import random
from typing import List, Dict, Set, Callable

__out = subprocess.check_output(['xdotool', 'getdisplaygeometry'], text=True)
display_width, display_height = map(int, __out.split())

# ====================== CONFIG ======================
DEVICE_NAME = ("gsr-ui virtual keyboard", "Compx 2.4G Wireless Receiver", "Razer Razer Naga V2 HyperSpeed")

# Format: "key1 key2": [actions...]
# Prefix with '!' for TOGGLE mode (press to start, press again to stop)
BINDS: Dict[str, List[str | int | list | tuple[int, int] | tuple[float, int, float, int]] | Callable] = {
    "x": ["+1", 0.01, "-1"], # hold 'x' button to start simple and fast auto clicker and unhold to stop
    # "!ctrl x": ["h", "e", "l", "l", "o", "space", "w", "o", "r", "l", "d", "space", 1000,], # press combo 'ctrl + x' button to toggle this macro
    "!n": [(0, 50, 0.5, -20), 10, "1",
           (0.5, 0, 0.6, 0), 10, [10, "1", 25],
           (0, 50, 0.5, 55), 10, "1",
           (0.5, 0, 0.6, 0), 10, [11, "1", 100]],
    # "!v": [(0.55, 0, 0.9, 0), 10, '1', (0.5, 0, 0.65, 0), 300, '1', (0.532, 0, 0.9, 0), [55, '1', 100]],
    # "!key1 key2": ['a', 'b']      # TOGGLE Combo: Press key1+key2 to toggle
}

# ====================== XDOTOOL SIMULATOR ======================
def simulate_action(action):
    if isinstance(action, Callable):
        return action()
    
    elif isinstance(action, int):
        time.sleep(action / 1000.0)
        return
        
    elif isinstance(action, list):
        actions = action.copy()
        times = actions.pop(0)
        
        for i in range(times):
            for v in actions:
                try:
                    simulate_action(v)
                except:
                    pass
    
    elif isinstance(action, tuple):
        if len(action) == 2:
            wait = random.randint(*action)
            time.sleep(wait / 1000.0)

        elif len(action) == 4:
            xp, x, yp, y = action

            abs_x = int(display_width*xp + x)
            abs_y = int(display_height*yp + y)
            print(abs_x, abs_y)

            subprocess.run(['ydotool', 'mousemove', '--absolute', '0', '0'], check=False)
            subprocess.run(['ydotool', 'mousemove', str(abs_x), str(abs_y)], check=False)
            
        return

    elif isinstance(action, str):
        hold = action[0] == '+' and 'down' or 'up' if action[0] in '-+' else ''
        key = action[1:] if hold != '' else action
        mouse = key.isdigit()

        rule = None
        if mouse:
            rule = 'mouse' + hold if hold != '' else 'click'
        else:
            rule = 'key' + hold

        subprocess.run(['xdotool', rule, key], check=False)

# ====================== COMBO ENGINE ======================
class ContinuousComboEngine:
    def __init__(self, binds: Dict[str, List[str | int]]):
        self.binds = binds
        self.active_keys: Set[str] = set()
        self.lock = threading.Lock()
        
        self.running_combo: str | None = None # The combo currently executing in the thread
        self.toggled_combo: str | None = None # The combo set to "Always On" state
        
        self.worker_thread = None
        self.stop_event = threading.Event()

    def update_keys(self, key: str, pressed: bool):
        with self.lock:
            # 1. Update Physical State
            if pressed:
                self.active_keys.add(key)
            else:
                self.active_keys.discard(key)

            physical_chord = " ".join(sorted(self.active_keys))
            toggle_check_name = "!" + physical_chord

            # 2. Check for Toggle Triggers (Only on Key Down)
            if pressed and toggle_check_name in self.binds:
                if self.toggled_combo == toggle_check_name:
                    print(f"[{toggle_check_name}] Toggled OFF")
                    self.toggled_combo = None
                else:
                    print(f"[{toggle_check_name}] Toggled ON")
                    self.toggled_combo = toggle_check_name
                
                # We processed a toggle command, decide what runs below
            
            # 3. Determine what should be running
            target_combo = None

            # Priority 1: Physical Hold matches a bind (Overrides toggles)
            if physical_chord in self.binds:
                target_combo = physical_chord
            
            # Priority 2: Active Toggle (if no physical hold overrides it)
            elif self.toggled_combo:
                target_combo = self.toggled_combo

            # 4. State Transition
            if target_combo != self.running_combo:
                self.stop_worker() # Stop whatever was running
                
                if target_combo:
                    self.start_worker(target_combo)

    def start_worker(self, combo_name: str):
        self.running_combo = combo_name
        self.stop_event.clear()
        self.worker_thread = threading.Thread(
            target=self._combo_worker,
            args=(self.binds[combo_name],),
            daemon=True
        )
        self.worker_thread.start()

    def stop_worker(self):
        self.stop_event.set()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=0.2)
        self.running_combo = None

    def _combo_worker(self, actions: List[str | int]):
        print(f"STARTED Loop: {self.running_combo}")
        while not self.stop_event.is_set():
            for action in actions:
                if self.stop_event.is_set():
                    break
                simulate_action(action)
        print(f"STOPPED Loop: {self.running_combo}")

    def shutdown(self):
        self.stop_worker()

# ====================== INPUT HANDLING ======================
def find_devices() -> List[str]:
    paths = []
    try:
        for path in evdev.list_devices():
            dev = evdev.InputDevice(path)
            if dev.name in DEVICE_NAME:
                paths.append(path)
                print(f"Found: {dev.name} → {path}")
    except Exception as e:
        print(f"Error listing devices: {e}")
    return paths

def reader_thread(path: str, q: queue.Queue):
    try:
        dev = evdev.InputDevice(path)
        print(f"Listening on {dev.name}")
        for event in dev.read_loop():
            if event.type == evdev.ecodes.EV_KEY and event.value in (0, 1):
                q.put((path, event))
    except Exception as e:
        print(f"Device disconnected or error: {path} - {e}")

# ====================== MAIN ======================
def main():
    paths = find_devices()
    if not paths:
        print("No matching devices found. Exiting.")
        return

    q: queue.Queue = queue.Queue()
    engine = ContinuousComboEngine(BINDS)

    for p in paths:
        threading.Thread(target=reader_thread, args=(p, q), daemon=True).start()

    # Pre-calculate allowed keys for the filter
    allowed_keys = set()
    for combo in BINDS.keys():
        clean_combo = combo.replace('!', '')
        for k in clean_combo.split(' '):
            allowed_keys.add(k)

    print("Macro engine running...")
    print(f"Monitoring keys: {allowed_keys}")
    print("Press Ctrl+C to quit.\n")

    try:
        while True:
            _, event = q.get()
            if event.value not in (0, 1):
                continue

            keycode = event.code
            keyname = evdev.ecodes.KEY.get(keycode)
            if not keyname:
                continue

            key = keyname.removeprefix("KEY_").lower()
            pressed = bool(event.value)

            if key not in allowed_keys:
                continue

            print(f"{'DOWN' if pressed else 'UP  '} {key.upper():<10}", end="\r")
            engine.update_keys(key, pressed)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        engine.shutdown()

if __name__ == "__main__":
    main()
