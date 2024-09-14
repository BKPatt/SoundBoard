import contextlib

@contextlib.contextmanager
def silence_pygame():
    with contextlib.redirect_stdout(None), contextlib.redirect_stderr(None):
        yield
        
CHUNK = 1024
SOUNDS_DIR = "sounds"
CONFIG_FILE = "config.json"