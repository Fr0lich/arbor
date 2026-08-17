import utils
import time
import os

class DummyApp:
    def __init__(self):
        self.config = {
            "ui_sections": {
                "location": [
                    {"name": "Stored as", "type": "text"},
                    {"name": "Building", "type": "text"},
                    {"name": "Floor", "type": "text"},
                    {"name": "Cabinet", "type": "text"},
                    {"name": "Extra", "type": "text"},
                    {"name": "Loaned out", "type": "checkbox"},
                ],
                "registration": [
                    {"name": f"RegField{i}", "type": "text"} for i in range(100)
                ]
            }
        }

class MockWindow:
    def __init__(self):
        self.app = DummyApp()
        self.field_names_order = ["Stored as", "Building", "Floor", "Cabinet", "Extra"]
        self.fields_to_render = [f"RegField{i}" for i in range(100)]

    def baseline(self):
        start_time = time.perf_counter()
        for _ in range(1000):
            for name in self.field_names_order:
                field = next((f for f in self.app.config["ui_sections"]["location"] if f["name"] == name), None)
            loan_field = next((f for f in self.app.config["ui_sections"]["location"] if f["name"] == "Loaned out"), None)

            for fname in self.fields_to_render:
                field = next((f for f in self.app.config["ui_sections"]["registration"] if f["name"] == fname), None)
        return time.perf_counter() - start_time

    def optimized(self):
        start_time = time.perf_counter()
        for _ in range(1000):
            # Optimized dictionary lookups
            loc_dict = {f["name"]: f for f in self.app.config["ui_sections"]["location"]}
            for name in self.field_names_order:
                field = loc_dict.get(name)
            loan_field = loc_dict.get("Loaned out")

            reg_dict = {f["name"]: f for f in self.app.config["ui_sections"]["registration"]}
            for fname in self.fields_to_render:
                field = reg_dict.get(fname)
        return time.perf_counter() - start_time

if __name__ == "__main__":
    win = MockWindow()
    baseline_time = win.baseline()
    optimized_time = win.optimized()
    print(f"Baseline: {baseline_time:.6f}s")
    print(f"Optimized: {optimized_time:.6f}s")
    print(f"Improvement: {baseline_time / optimized_time:.2f}x faster")
