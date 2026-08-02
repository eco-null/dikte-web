"""The one-heavy-job-at-a-time manager the routes run on."""

import time
import unittest

import app.jobs as jobs_module


class Jobs(unittest.TestCase):
    def setUp(self):
        self.manager = jobs_module.JobManager(max_jobs=2)

    def test_a_job_runs_and_records_result(self):
        job_id = self.manager.submit("t", lambda emit: {"ok": True})
        job = self.manager.get(job_id)
        self.assertEqual(job.status, "done")
        self.assertEqual(job.result, {"ok": True})

    def test_a_failure_is_recorded(self):
        def boom(emit):
            raise RuntimeError("nope")
        job_id = self.manager.submit("t", boom)
        job = self.manager.get(job_id)
        self.assertEqual(job.status, "failed")
        self.assertIn("nope", job.error)

    def test_only_one_at_a_time(self):
        started = {}

        def work(emit):
            started["go"] = True
            time.sleep(0.2)
            return 1

        job_id = self.manager.submit("t", work)
        started["go"] = False
        with self.assertRaises(jobs_module.BusyError):
            self.manager.submit("t", work)
        time.sleep(0.3)
        second = self.manager.submit("t", lambda emit: 2)
        self.assertEqual(self.manager.get(second).status, "done")

    def test_emit_updates_the_stage(self):
        def work(emit):
            emit("halfway")
            return 1

        job_id = self.manager.submit("t", work)
        self.assertEqual(self.manager.get(job_id).stage, "halfway")

    def test_finished_jobs_over_the_limit_are_pruned(self):
        first = self.manager.submit("t", lambda emit: 1)
        second = self.manager.submit("t", lambda emit: 2)
        third = self.manager.submit("t", lambda emit: 3)
        time.sleep(0.3)
        # The next submit is when the overflow is noticed.
        fourth = self.manager.submit("t", lambda emit: 4)
        self.assertIsNone(self.manager.get(first))
        self.assertIsNotNone(self.manager.get(second))
        self.assertIsNotNone(self.manager.get(third))
        self.assertIsNotNone(self.manager.get(fourth))


if __name__ == "__main__":
    unittest.main()
