import os
import sys
import random

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def simulate_button_mashing(main_window, num_actions=100, on_finished=None):
    """
    Simulates rapid erratic user interactions (navigation, undo, redo, mark reviewed,
    layout presets, search indexing) on the desktop Tkinter event loop.
    Catches unhandled TclErrors, thread synchronization faults, and race conditions.
    """
    print(f"Beginning desktop UI button mashing ({num_actions} simulated interactions)...")
    actions = [
        ("navigate_forward", lambda: main_window.navigate_object(1)),
        ("navigate_backward", lambda: main_window.navigate_object(-1)),
        ("mark_reviewed", lambda: main_window.mark_current_as_reviewed()),
        ("push_undo", lambda: main_window.push_undo_state()),
        ("undo", lambda: main_window.undo_shortcut()),
        ("redo", lambda: main_window.redo_shortcut()),
        ("refresh_list", lambda: main_window.refresh_list()),
        ("toggle_preset", lambda: main_window._apply_layout_preset({
            "show_list": random.choice([True, False]),
            "show_search": random.choice([True, False])
        })),
    ]

    action_counts = {name: 0 for name, _ in actions}

    def do_step(step_num):
        if step_num >= num_actions:
            print(f"[PASS] UI button mashing stress test passed ({num_actions} actions) without any TclErrors or crashes!")
            print(f"Action distribution: {action_counts}")
            if on_finished:
                on_finished()
            return

        name, action = random.choice(actions)
        action_counts[name] += 1
        try:
            action()
        except Exception as exc:
            print(f"CRASH ON STEP {step_num} ({name}): {exc}")
            raise exc

        # Schedule next action with tight 5ms interval to stress test debounce & race guards
        main_window.root.after(5, lambda: do_step(step_num + 1))

    main_window.root.after(50, lambda: do_step(0))
