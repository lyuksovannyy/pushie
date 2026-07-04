import unittest
import os
import shutil
import tempfile
from app.storage import Macro, ActionSpec, save_macro, delete_macro, load_macros, get_storage_dir

class TestStorage(unittest.TestCase):
    def setUp(self):
        # Redirect home for isolated storage testing
        self.temp_dir = tempfile.mkdtemp()
        self.original_home = os.environ.get("HOME")
        os.environ["HOME"] = self.temp_dir

    def tearDown(self):
        if self.original_home:
            os.environ["HOME"] = self.original_home
        shutil.rmtree(self.temp_dir)

    def test_save_and_load_individual_macros(self):
        # Create config directory manually to test normal path first
        os.makedirs(os.path.join(self.temp_dir, ".config"))
        
        press_actions = [
            ActionSpec("key_press", {"key": "x"}),
            ActionSpec("delay", {"milliseconds": 50})
        ]
        release_actions = [
            ActionSpec("key_release", {"key": "x"})
        ]
        macro = Macro(
            "macro_1", "Test Macro", "Description", "Super+Space",
            work_only_pressed=False, loop_while_held=True, active=True,
            press_actions=press_actions, release_actions=release_actions
        )
        
        save_macro(macro)
        
        # Verify file path is within .config/pushie
        expected_path = os.path.join(self.temp_dir, ".config", "pushie", "macro_1.yaml")
        self.assertTrue(os.path.exists(expected_path))
        
        loaded = load_macros()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].id, "macro_1")
        self.assertEqual(loaded[0].name, "Test Macro")
        self.assertEqual(loaded[0].hotkey, "Super+Space")
        self.assertFalse(loaded[0].work_only_pressed)
        self.assertTrue(loaded[0].loop_while_held)
        self.assertEqual(len(loaded[0].press_actions), 2)
        self.assertEqual(loaded[0].press_actions[0].type, "key_press")
        self.assertEqual(loaded[0].press_actions[0].properties["key"], "x")
        self.assertEqual(len(loaded[0].release_actions), 1)
        self.assertEqual(loaded[0].release_actions[0].type, "key_release")
        
        # Test deletion
        delete_macro("macro_1")
        self.assertFalse(os.path.exists(expected_path))
        self.assertEqual(len(load_macros()), 0)

    def test_fallback_storage_dir(self):
        macro = Macro("macro_fallback", "Fallback")
        save_macro(macro)
        
        expected_path = os.path.join(self.temp_dir, ".pushie", "macro_fallback.yaml")
        self.assertTrue(os.path.exists(expected_path))
        
        loaded = load_macros()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].id, "macro_fallback")

if __name__ == '__main__':
    unittest.main()
