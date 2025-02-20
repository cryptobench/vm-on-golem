import sys
import threading
import time
import itertools

class Spinner:
    """A simple spinner class for CLI progress indication."""
    def __init__(self, message="", delay=0.1):
        self.spinner = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
        self.delay = delay
        self.busy = False
        self.spinner_visible = False
        self.message = message
        sys.stdout.write('\033[?25l')  # Hide cursor

    def write_next(self):
        """Write the next spinner frame."""
        with self._screen_lock:
            if not self.spinner_visible:
                sys.stdout.write(f"\r{next(self.spinner)} {self.message}")
                self.spinner_visible = True
                sys.stdout.flush()

    def remove_spinner(self, cleanup=False):
        """Remove the spinner from the terminal."""
        with self._screen_lock:
            if self.spinner_visible:
                sys.stdout.write('\r')
                sys.stdout.write(' ' * (len(self.message) + 2))
                sys.stdout.write('\r')
                if cleanup:
                    sys.stdout.write('\033[?25h')  # Show cursor
                sys.stdout.flush()
                self.spinner_visible = False

    def spinner_task(self):
        """Animate the spinner."""
        while self.busy:
            self.write_next()
            time.sleep(self.delay)
            self.remove_spinner()

    def __enter__(self):
        """Start the spinner."""
        self._screen_lock = threading.Lock()
        self.busy = True
        self.thread = threading.Thread(target=self.spinner_task)
        self.thread.daemon = True
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop the spinner and show completion."""
        self.busy = False
        time.sleep(self.delay)
        self.remove_spinner(cleanup=True)
        if exc_type is None:
            # Show checkmark on success
            sys.stdout.write(f"\r✓ {self.message}\n")
        else:
            # Show X on failure
            sys.stdout.write(f"\r✗ {self.message}\n")
        sys.stdout.flush()

def step(message):
    """Decorator to add a spinning progress indicator to a function."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            with Spinner(message):
                return await func(*args, **kwargs)
        return wrapper
    return decorator
