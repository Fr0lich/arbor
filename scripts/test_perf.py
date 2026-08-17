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
                    {"name": f"RegField{i}", "type": "text"} for i in range(20)
                ],
                "problems": [
                    {"name": f"ProbField{i}", "type": "checkbox"} for i in range(10)
                ]
            }
        }

    def config_lookup_test_baseline(self):
        start_time = time.perf_counter()
        field_names_order = ["Stored as", "Building", "Floor", "Cabinet", "Extra"]
        for _ in range(10000):
            for idx, name in enumerate(field_names_order):
                field = next((f for f in self.config["ui_sections"]["location"] if f["name"] == name), None)

            loan_field = next((f for f in self.config["ui_sections"]["location"] if f["name"] == "Loaned out"), None)

            for fname in [f"RegField{i}" for i in range(20)]:
                field = next((f for f in self.config["ui_sections"]["registration"] if f["name"] == fname), None)
        end_time = time.perf_counter()
        return end_time - start_time

    def config_lookup_test_optimized(self):
        start_time = time.perf_counter()
        field_names_order = ["Stored as", "Building", "Floor", "Cabinet", "Extra"]
        for _ in range(10000):
            loc_config_dict = {f["name"]: f for f in self.config["ui_sections"]["location"]}
            for idx, name in enumerate(field_names_order):
                field = loc_config_dict.get(name)

            loan_field = loc_config_dict.get("Loaned out")

            reg_config_dict = {f["name"]: f for f in self.config["ui_sections"]["registration"]}
            for fname in [f"RegField{i}" for i in range(20)]:
                field = reg_config_dict.get(fname)
        end_time = time.perf_counter()
        return end_time - start_time

if __name__ == "__main__":
    app = DummyApp()
    print(f"Baseline Time: {app.config_lookup_test_baseline():.6f} seconds")
    print(f"Optimized Time: {app.config_lookup_test_optimized():.6f} seconds")
