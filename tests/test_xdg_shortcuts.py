import unittest
import sys
from PySide6.QtCore import QCoreApplication
from app.xdg_shortcuts import XDGShortcutsClient

class TestXDGShortcuts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize Qt App context if not already created
        cls.app = QCoreApplication.instance()
        if cls.app is None:
            cls.app = QCoreApplication(sys.argv)

    def test_initialization(self):
        client = XDGShortcutsClient()
        self.assertIsNotNone(client.bus)
        # Verify the GLib thread is started
        self.assertTrue(client.dbus_thread.is_alive())

if __name__ == '__main__':
    unittest.main()
