import unittest
import subprocess as real_subprocess
from unittest import mock
from app.storage import Macro, ActionSpec
from app.engine import MacroEngine


class TestPressReleaseState(unittest.TestCase):
    """Regression tests: a skipped release (active-window detection miss while
    a target-app gated macro is held in a fullscreen game like Arc Raiders)
    must never leave the macro stuck "pressed" - which swallowed the next key
    press and forced a double press for the bind to do anything."""

    def setUp(self):
        self.engine = MacroEngine()
        self.pactl_calls = []
        self.taps = []
        self.releases = []

        def fake_run_cmd(*args):
            if args[:2] == ("pactl", "get-default-source"):
                return "mic"
            if args[:2] == ("pactl", "set-source-mute"):
                self.pactl_calls.append(args[3])
                return ""
            return ""

        def fake_subprocess_run(cmd, **kwargs):
            if cmd and cmd[0] == "xdotool":
                if cmd[1] == "key":
                    self.taps.append(cmd[2])
                elif cmd[1] == "keyup":
                    self.releases.append(cmd[2])
                return mock.Mock()
            return real_subprocess.run(cmd, **kwargs)

        patcher = mock.patch("app.engine.run_cmd", side_effect=fake_run_cmd)
        patcher.start()
        self.addCleanup(patcher.stop)
        spatcher = mock.patch("app.engine.subprocess.run", side_effect=fake_subprocess_run)
        spatcher.start()
        self.addCleanup(spatcher.stop)
        self.addCleanup(self.engine.stop_all_fast)

    def _macro(self):
        return Macro(
            "arc_ptt", "Arc PTT", "", "F13",
            work_only_pressed=True, loop_while_held=True, active=True,
            press_actions=[ActionSpec("mic_toggle", {"unmute": True})],
            release_actions=[ActionSpec("mic_toggle", {"unmute": False})],
            target_apps=["arc raiders"],
        )

    def test_release_processed_even_when_app_detection_misses(self):
        macro = self._macro()

        self.engine.handle_activate(macro, "arc raiders")
        self.assertTrue(self.engine._pressed_states.get("arc_ptt", False))
        self.assertIn("0", self.pactl_calls)  # press: mic unmuted

        # Key released while the active-window cache is mid-poll/blank
        # (fullscreen game focus flicker). Release must still be processed.
        self.engine.handle_deactivate(macro, "")
        self.assertFalse(
            self.engine._pressed_states.get("arc_ptt", False),
            "release must clear pressed state even if current app detection missed",
        )
        self.assertIn("1", self.pactl_calls)  # release: mic muted again

        # The next press must NOT be swallowed by the re-entry guard
        self.engine.handle_activate(macro, "arc raiders")
        self.assertTrue(self.engine._pressed_states.get("arc_ptt", False))
        self.engine.handle_deactivate(macro, "arc raiders")

    def test_spurious_release_without_press_is_ignored(self):
        macro = self._macro()
        self.engine.handle_deactivate(macro, "arc raiders")
        self.assertFalse(self.engine._pressed_states.get("arc_ptt", False))
        self.assertEqual(self.pactl_calls, [])  # no release actions ran

    def test_press_outside_target_apps_is_still_ignored(self):
        macro = self._macro()
        self.engine.handle_activate(macro, "firefox")
        self.assertFalse(self.engine._pressed_states.get("arc_ptt", False))
        self.assertEqual(self.pactl_calls, [])

    def test_fire_and_forget_runs_on_every_press(self):
        """work_only_pressed=False = fire-and-forget: press actions run once
        per activation, release actions are never used, and releases are no-ops.
        Every consecutive press must fire - no alternating/toggling behavior."""
        macro = Macro(
            "tap_k", "F16 -> K", "", "F16",
            work_only_pressed=False, active=True,
            press_actions=[ActionSpec("key_tap", {"key": "K"})],
            release_actions=[ActionSpec("key_release", {"key": "K"})],
            target_apps=["gamethread"],
        )
        self.engine.handle_activate(macro, "gamethread")
        self.engine.handle_deactivate(macro, "gamethread")  # fire-and-forget: no-op
        self.engine.handle_activate(macro, "gamethread")
        # Press actions fired on BOTH presses (release actions never ran)
        self.assertEqual(self.taps, ["K", "K"])
        self.assertEqual(self.releases, [])


if __name__ == "__main__":
    unittest.main()
