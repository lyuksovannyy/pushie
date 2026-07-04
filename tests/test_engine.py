import unittest
import time
from app.storage import Macro, ActionSpec
from app.engine import MacroEngine

class TestEngine(unittest.TestCase):
    def test_engine_activation(self):
        engine = MacroEngine()
        
        # Create a macro with clean actions
        press_actions = [
            ActionSpec("delay", {"milliseconds": 10})
        ]
        macro = Macro(
            "test_macro", "Test Exec", "Desc", "F13",
            work_only_pressed=True, loop_while_held=False,
            press_actions=press_actions
        )
        
        # Activate macro
        engine.handle_activate(macro)
        
        # Verify thread is running or tracked
        self.assertIn("test_macro", engine._running_actions)
        
        # Let it finish or stop it
        time.sleep(0.05)
        # Deactivate
        engine.handle_deactivate(macro)
        self.assertNotIn("test_macro", engine._running_actions)

if __name__ == '__main__':
    unittest.main()
