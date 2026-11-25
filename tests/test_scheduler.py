import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from airport_scheduler import RunwayScheduler, to_minutes


class SchedulerTests(unittest.TestCase):
    def make_scheduler(self):
        scheduler = RunwayScheduler()
        scheduler.set_runways([
            {"name": "09L", "mode": "mixed", "windows": [(0, 1440)]},
            {"name": "27", "mode": "departure", "windows": [(0, 1440)]},
        ])
        return scheduler

    def test_emergency_is_scheduled_first(self):
        scheduler = self.make_scheduler()
        scheduler.add_flight("LOW1", "arrival", 400, 1)
        scheduler.add_flight("EMG1", "arrival", 500, 5, emergency=True)
        self.assertEqual(scheduler.schedule_next().id, "EMG1")

    def test_bookings_never_overlap(self):
        scheduler = self.make_scheduler()
        for index in range(20):
            scheduler.add_flight(f"A{index:02}", "arrival", 360, 3)
        scheduler.schedule_all()
        for runway in scheduler.runways:
            for left, right in zip(runway.bookings, runway.bookings[1:]):
                self.assertLessEqual(left.end, right.start)

    def test_departure_only_runway_never_gets_arrival(self):
        scheduler = self.make_scheduler()
        scheduler.add_flight("AR01", "arrival", 360, 3)
        scheduler.schedule_all()
        self.assertFalse(next(r for r in scheduler.runways if r.name == "27").bookings)

    def test_to_minutes(self):
        self.assertEqual(to_minutes("06:40"), 400)


if __name__ == "__main__":
    unittest.main()
