"""The tiny Signal that replaced pyqtSignal; only connect/emit/disconnect."""

import unittest

from app.vendor.dikte import signals


class SignalTests(unittest.TestCase):
    def test_emit_calls_every_connected_slot(self):
        s = signals.Signal()
        seen = []
        s.connect(lambda *a: seen.append(a))
        s.connect(lambda *a: seen.append(a))
        s.emit(1, "x")
        self.assertEqual(seen, [(1, "x"), (1, "x")])

    def test_emit_without_slots_is_a_noop(self):
        signals.Signal().emit(1, 2, 3)

    def test_disconnect_stops_delivery(self):
        s = signals.Signal()
        seen = []
        s.connect(seen.append)
        s.disconnect(seen.append)
        s.emit("y")
        self.assertEqual(seen, [])

    def test_disconnect_missing_slot_is_a_noop(self):
        s = signals.Signal()
        s.disconnect(lambda: None)

    def test_slots_see_snapshot_of_connections(self):
        s = signals.Signal()
        calls = []

        def first(*a):
            calls.append("first")
            s.disconnect(first)

        s.connect(first)
        s.connect(lambda *a: calls.append("second"))
        s.emit()
        # A slot that disconnects itself mid-emit must not break the rest.
        self.assertEqual(calls, ["first", "second"])


if __name__ == "__main__":
    unittest.main()
