import time
import importlib
import ui.main_window

# Mock app and config
class MockApp:
    def __init__(self):
        self.config = {
            "ui_sections": {
                "registration": [
                    {"name": f"Field{i}", "type": "text"} for i in range(100)
                ]
            }
        }

def test_current():
    app = MockApp()
    fields_to_render = [f"Field{i}" for i in range(50)]

    start_time = time.time()
    for _ in range(1000):
        for fname in fields_to_render:
            field = next((f for f in app.config["ui_sections"]["registration"] if f["name"] == fname), None)
            if not field:
                continue
    return time.time() - start_time

def test_optimized():
    app = MockApp()
    fields_to_render = [f"Field{i}" for i in range(50)]

    start_time = time.time()
    for _ in range(1000):
        # The optimized version
        reg_fields = {f["name"]: f for f in app.config["ui_sections"]["registration"]}
        for fname in fields_to_render:
            field = reg_fields.get(fname)
            if not field:
                continue
    return time.time() - start_time

print(f"Current: {test_current():.4f}s")
print(f"Optimized: {test_optimized():.4f}s")
