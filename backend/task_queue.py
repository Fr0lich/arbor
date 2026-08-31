import queue
import threading

class BackgroundWorker:
    def __init__(self):
        self.task_queue = queue.Queue()
        self.root = None
        self._polling = False

    def start(self, root):
        """Starts the main-thread polling loop using root.after()"""
        if self._polling:
            return
        self.root = root
        self._polling = True
        self._poll()

    def _poll(self):
        if not self._polling or not self.root:
            return

        try:
            while True:
                task = self.task_queue.get_nowait()
                if callable(task):
                    task()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._poll)

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

            if self.root and self._polling:
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

