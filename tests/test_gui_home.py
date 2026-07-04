import unittest
import sys
from PySide6.QtCore import QCoreApplication
from app.storage import Macro
from app.gui_home import HomePage

class TestGuiHome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance()
        if cls.app is None:
            cls.app = QCoreApplication(sys.argv)

    def test_homepage_population(self):
        home = HomePage()
        macros = [
            Macro("macro_1", "Test PTT", "Desc 1", "F13"),
            Macro("macro_2", "Test Clicker", "Desc 2", "F14")
        ]
        
        home.populate_macros(macros)
        
        # Verify cards are stored internally
        self.assertIn("macro_1", home.cards)
        self.assertIn("macro_2", home.cards)
        self.assertEqual(home.cards["macro_1"].macro.name, "Test PTT")

if __name__ == '__main__':
    unittest.main()
