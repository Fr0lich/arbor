"""
ui/tutorials/database_tutorial.py

Action-driven interactive tutorial for creating new databases and adding new specimen objects.
Operates strictly in an isolated in-memory sandbox without mutating real user files.
"""

from .sandbox_manager import SandboxManager
from .tutorial_runner import TutorialRunner, ActionStep


def start_database_tutorial(ui, on_complete=None):
    """Initializes sandbox and starts the Database & Object Creation tutorial."""
    SandboxManager().enter_sandbox(ui, mock_type="review")

    initial_count = len(ui.app.df_reg) if ui.app.df_reg is not None else 0

    steps = [
        ActionStep(
            step_id="open_db_wizard",
            title="Create a New Database",
            instruction="You can generate clean database templates with standard botanical sheets using the New Database Wizard (accessible via File -> New Database).",
            action_hint="Inspect wizard setup options or click Skip Step."
        ),
        ActionStep(
            step_id="add_new_object",
            title="Add a New Specimen Record",
            instruction="Press Ctrl+N (or right-click the specimen list and select 'New Object') to add a new record to the database.",
            target_id="search_entry",
            action_hint="Press Ctrl+N to add a new object.",
            validator=lambda u: bool(
                u.app.df_reg is not None and len(u.app.df_reg) > initial_count
            )
        ),
        ActionStep(
            step_id="enter_specimen_data",
            title="Enter Specimen Information",
            instruction="Click into the Registration Data panel fields and enter identification properties (e.g. Genus, Species, Locality).",
            target_id="object_editor_frame",
            action_hint="Type data into any registration field."
        ),
        ActionStep(
            step_id="database_complete",
            title="Tutorial Complete",
            instruction="You have learned how to create databases and add new objects. Click Finish to exit sandbox mode and return to your workspace.",
            action_hint="Click 'Finish' below to exit sandbox."
        )
    ]

    return TutorialRunner(ui, steps, tutorial_name="Databases & New Objects", on_complete=on_complete)
