import os
import glob
from typing import TypedDict, Any, Optional
from collections.abc import Sequence
import yaml

class ActionDict(TypedDict):
    type: str
    properties: dict[str, Any]

class MacroDict(TypedDict):
    id: str
    name: str
    description: str
    xdg_hotkey: str
    evdev_hotkey: str
    bind_method: str
    evdev_pass_through: bool
    work_only_pressed: bool
    loop_while_held: bool
    active: bool
    press_actions: list[ActionDict]
    release_actions: list[ActionDict]

class ActionSpec:
    def __init__(self, type_: str, properties: Optional[dict[str, Any]] = None) -> None:
        self.type: str = type_
        self.properties: dict[str, Any] = properties or {}

    def to_dict(self) -> ActionDict:
        return {"type": self.type, "properties": self.properties}

class Macro:
    def __init__(
        self, 
        id_: str, 
        name: str, 
        description: str = "", 
        hotkey: str = "", 
        work_only_pressed: bool = True, 
        loop_while_held: bool = False, 
        active: bool = True, 
        press_actions: Optional[list[ActionSpec]] = None, 
        release_actions: Optional[list[ActionSpec]] = None,
        bind_method: str = "xdg",
        evdev_pass_through: bool = False,
        xdg_hotkey: str = "",
        evdev_hotkey: str = ""
    ) -> None:
        self.id: str = id_
        self.name: str = name
        self.description: str = description
        self.work_only_pressed: bool = work_only_pressed
        self.loop_while_held: bool = loop_while_held
        self.active: bool = active
        self.press_actions: list[ActionSpec] = press_actions or []
        self.release_actions: list[ActionSpec] = release_actions or []
        self.bind_method: str = bind_method
        self.evdev_pass_through: bool = evdev_pass_through

        if hotkey:
            if bind_method == "evdev":
                self.evdev_hotkey: str = evdev_hotkey or hotkey
                self.xdg_hotkey: str = xdg_hotkey
            else:
                self.xdg_hotkey: str = xdg_hotkey or hotkey
                self.evdev_hotkey: str = evdev_hotkey
        else:
            self.xdg_hotkey: str = xdg_hotkey
            self.evdev_hotkey: str = evdev_hotkey

    @property
    def hotkey(self) -> str:
        if self.bind_method == "evdev":
            return self.evdev_hotkey
        return self.xdg_hotkey

    @hotkey.setter
    def hotkey(self, value: str) -> None:
        if self.bind_method == "evdev":
            self.evdev_hotkey = value
        else:
            self.xdg_hotkey = value

    def to_dict(self) -> MacroDict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "xdg_hotkey": self.xdg_hotkey,
            "evdev_hotkey": self.evdev_hotkey,
            "bind_method": self.bind_method,
            "evdev_pass_through": self.evdev_pass_through,
            "work_only_pressed": self.work_only_pressed,
            "loop_while_held": self.loop_while_held,
            "active": self.active,
            "press_actions": [a.to_dict() for a in self.press_actions],
            "release_actions": [a.to_dict() for a in self.release_actions]
        }

def get_storage_dir() -> str:
    home = os.environ.get("HOME", os.path.expanduser("~"))
    config_dir = os.path.join(home, ".config")
    if os.path.isdir(config_dir):
        path = os.path.join(config_dir, "pushie")
    else:
        path = os.path.join(home, ".pushie")
    os.makedirs(path, exist_ok=True)
    return path

def save_macro(macro: Macro) -> None:
    directory = get_storage_dir()
    filepath = os.path.join(directory, f"{macro.id}.yaml")
    data = macro.to_dict()
    with open(filepath, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False)

def delete_macro(macro_id: str) -> None:
    directory = get_storage_dir()
    filepath = os.path.join(directory, f"{macro_id}.yaml")
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            print(f"Error deleting macro file {filepath}: {e}")

def load_macros() -> list[Macro]:
    directory = get_storage_dir()
    macros: list[Macro] = []
    
    # List all YAML config files
    pattern = os.path.join(directory, "*.yaml")
    files = glob.glob(pattern)
    
    for filepath in files:
        # Ignore main configuration if upgrade path was used
        if os.path.basename(filepath) == "macros.yaml":
            continue
            
        try:
            with open(filepath, "r") as f:
                d = yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading macro from {filepath}: {e}")
            continue
            
        if not isinstance(d, dict):
            continue
            
        press_actions: list[ActionSpec] = []
        raw_press = d.get("press_actions", d.get("actions", []))
        if isinstance(raw_press, list):
            for a in raw_press:
                if isinstance(a, dict) and "type" in a:
                    press_actions.append(ActionSpec(a["type"], a.get("properties")))
        
        release_actions: list[ActionSpec] = []
        raw_release = d.get("release_actions", [])
        if isinstance(raw_release, list):
            for a in raw_release:
                if isinstance(a, dict) and "type" in a:
                    release_actions.append(ActionSpec(a["type"], a.get("properties")))

        macros.append(Macro(
            d.get("id", ""),
            d.get("name", "Unnamed Macro"),
            d.get("description", ""),
            d.get("hotkey", ""),
            d.get("work_only_pressed", True),
            d.get("loop_while_held", False),
            d.get("active", True),
            press_actions,
            release_actions,
            bind_method=d.get("bind_method", "xdg"),
            evdev_pass_through=d.get("evdev_pass_through", False),
            xdg_hotkey=d.get("xdg_hotkey", ""),
            evdev_hotkey=d.get("evdev_hotkey", "")
        ))
    return macros
