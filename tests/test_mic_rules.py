import unittest
from unittest import mock
from app.engine import PulseAudioHelper

SOURCES = """Source #61
	State: SUSPENDED
	Name: alsa_output.pci-0000_00_1f.3.analog-stereo.monitor
	Properties:
		device.class = "monitor"

Source #63
	State: RUNNING
	Name: alsa_input.usb-mic-0005.analog-stereo
"""

# #150: OBS capturing the mic. #151: OBS capturing desktop audio from the
# sink monitor (screencast audio). #152: Discord capturing the mic.
SOURCE_OUTPUTS = """Source Output #150
	Driver: Pipewire
	Source: 63
	object.serial = "150"
	Properties:
		application.name = "OBS"
		application.process.binary = "obs"

Source Output #151
	Driver: Pipewire
	Source: 61
	object.serial = "151"
	Properties:
		application.name = "OBS"
		application.process.binary = "obs"

Source Output #152
	Driver: Pipewire
	Source: 63
	object.serial = "152"
	Properties:
		application.name = "Discord"
		application.process.binary = "discord"
"""


class TestMicRules(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def fake_run_cmd(*args):
            if args[:3] == ("pactl", "list", "source-outputs"):
                return SOURCE_OUTPUTS
            if args[:3] == ("pactl", "list", "sources"):
                return SOURCES
            self.calls.append(args)
            return ""

        self.patcher = mock.patch("app.engine.run_cmd", side_effect=fake_run_cmd)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def _vol_calls(self):
        return {c[2]: c[3] for c in self.calls if c[:2] == ("pactl", "set-source-output-volume")}

    def test_mic_rules_skip_desktop_audio_streams(self):
        """Mic rules must never mute monitor streams that carry other apps'
        sounds for screen recorders (OBS, Discord, ...) - only the mic itself."""
        PulseAudioHelper.apply_rules(["!obs"], "alsa_input.usb-mic-0005.analog-stereo", "1.0")
        vols = self._vol_calls()
        self.assertNotIn("151", vols, "desktop-audio monitor stream must never be touched")
        self.assertEqual(vols["150"], "0.0")

    def test_unmute_reaches_all_mic_capture_streams(self):
        """Unmute applies to every app capturing from the mic."""
        PulseAudioHelper.apply_rules(["all"], "alsa_input.usb-mic-0005.analog-stereo", "1.0")
        vols = self._vol_calls()
        self.assertNotIn("151", vols)
        self.assertEqual(vols, {"150": "1.0", "152": "1.0"})

    def test_explicit_mute_wins_over_all_allow(self):
        """Placeholder combo '!vesktop, discord, all': vesktop stays muted."""
        PulseAudioHelper.apply_rules(["!vesktop", "discord", "all"], "alsa_input.usb-mic-0005.analog-stereo", "1.0")
        vols = self._vol_calls()
        self.assertEqual(vols, {"150": "1.0", "152": "1.0"})

    def test_named_allow_wins_over_mute_all(self):
        """'discord, !all' is push-to-talk for Discord only: everyone else muted."""
        PulseAudioHelper.apply_rules(["discord", "!all"], "alsa_input.usb-mic-0005.analog-stereo", "1.0")
        vols = self._vol_calls()
        self.assertEqual(vols, {"150": "0.0", "152": "1.0"})

    def test_named_mute_wins_over_allow_all(self):
        """'all, !discord' talks to everyone except Discord."""
        PulseAudioHelper.apply_rules(["all", "!discord"], "alsa_input.usb-mic-0005.analog-stereo", "1.0")
        vols = self._vol_calls()
        self.assertEqual(vols, {"150": "1.0", "152": "0.0"})

    def test_mute_all(self):
        PulseAudioHelper.apply_rules(["!all"], "alsa_input.usb-mic-0005.analog-stereo", "1.0")
        self.assertEqual(self._vol_calls(), {"150": "0.0", "152": "0.0"})


if __name__ == "__main__":
    unittest.main()
