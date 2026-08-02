"""pyqtSignal yerine geçen küçük Signal; yalnızca connect/emit yeter."""
import contextlib


class Signal:
    def __init__(self, *_types):
        self._slots = []

    def connect(self, slot):
        self._slots.append(slot)

    def disconnect(self, slot):
        with contextlib.suppress(ValueError):
            self._slots.remove(slot)

    def emit(self, *args):
        for slot in list(self._slots):
            slot(*args)
