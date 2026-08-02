import os
import unittest
from app.window_detector import (
    get_distro_info,
    has_command,
    get_process_name_from_pid,
    get_active_window_process_name,
)

class TestWindowDetector(unittest.TestCase):
    def test_get_distro_info(self):
        info = get_distro_info()
        self.assertIsInstance(info, dict)
        self.assertIn("id", info)
        self.assertIn("name", info)

    def test_lru_cache_distro_info(self):
        info1 = get_distro_info()
        info2 = get_distro_info()
        self.assertIs(info1, info2)

    def test_has_command(self):
        self.assertTrue(has_command("ls"))
        self.assertFalse(has_command("non_existent_command_xyz_123"))

    def test_get_process_name_from_pid(self):
        pid = os.getpid()
        name = get_process_name_from_pid(pid)
        self.assertIsNotNone(name)
        self.assertIsInstance(name, str)

    def test_get_active_window_process_name(self):
        result = get_active_window_process_name()
        self.assertTrue(result is None or isinstance(result, str))

if __name__ == "__main__":
    unittest.main()
