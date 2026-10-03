"""One logical automation owner; guardian is notification-only."""
from contextlib import contextmanager
import threading
from fgoSchedule import ScriptStop

NETWORK_ERROR_EVENT=threading.Event()
GUARDIAN_STOP=threading.Event()

class AutomationOwner:
    def __init__(self):self._lock=threading.RLock();self._state=threading.Lock();self._thread=None;self._depth=0
    def isOwner(self):
        with self._state:return self._thread==threading.get_ident()
    @contextmanager
    def claim(self):
        if not self._lock.acquire(blocking=False):raise ScriptStop('Another automation worker owns the device')
        with self._state:self._thread=threading.get_ident();self._depth+=1
        try:yield
        finally:
            with self._state:
                self._depth-=1
                if not self._depth:self._thread=None
            self._lock.release()

automationOwner=AutomationOwner()
