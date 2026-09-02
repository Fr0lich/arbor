import queue
import threading

class BackgroundWorker:
    def __init__(self):
        self.task_queue = queue.Queue()
        self.root = None
        self._polling = False
        self._lock = threading.Lock()

    def start(self, root):
        """Starts the main-thread polling loop using root.after()"""
        with self._lock:
            if self._polling:
                return
            self.root = root
            self._polling = True
        self._poll()

    def stop(self):
        """Stops the main-thread polling loop and drains any pending tasks."""
        with self._lock:
            self._polling = False
            self.root = None
        # Drain the task queue
        try:
            while True:
                self.task_queue.get_nowait()
        except queue.Empty:
            pass

    def _poll(self):
        with self._lock:
            if not self._polling or not self.root:
                return
            root_ref = self.root

        try:
            if not root_ref.winfo_exists():
                self.stop()
                return
        except Exception:
            self.stop()
            return

        try:
            while True:
                task = self.task_queue.get_nowait()
                if callable(task):
                    try:
                        task()
                    except Exception as e:
                        print(f"Background task callback error: {e}")
        except queue.Empty:
            pass
        finally:
            with self._lock:
                should_reschedule = self._polling and self.root is not None
            if should_reschedule:
                try:
                    if root_ref.winfo_exists():
                        root_ref.after(100, self._poll)
                    else:
                        self.stop()
                except Exception:
                    self.stop()

    def run_in_background(self, func, callback=None, error_callback=None):
        """
        Runs func in a background thread.
        When finished, it puts the callback on the task_queue to be executed on the main thread.
        If root is not yet initialized, executes callback directly.
        """
        def _wrapper():
            result = None
            err = None
            try:
                result = func()
            except Exception as e:
                err = e
                print(f"Background task error: {e}")

            with self._lock:
                is_active = self.root is not None and self._polling

            if is_active:
                if err is not None and error_callback:
                    self.task_queue.put(lambda: error_callback(err))
                elif callback:
                    self.task_queue.put(lambda: callback(result))
            else:
                # Direct invocation fallback (e.g. in tests)
                if err is not None and error_callback:
                    try:
                        error_callback(err)
                    except Exception:
                        pass
                elif callback:
                    try:
                        callback(result)
                    except Exception:
                        pass

        threading.Thread(target=_wrapper, daemon=True).start()

# Global singleton worker
app_worker = BackgroundWorker()

