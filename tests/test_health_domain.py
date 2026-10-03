import unittest
from datetime import UTC, datetime, timedelta

from health.domain.entities import HealthRecord, SubmittingDevice
from health.domain.value_objects import HeartRateBpm, RecordedAt, TelemetryEventId


class HeartRateBpmTestCase(unittest.TestCase):
    def test_accepts_range_boundaries_and_normalizes_to_float(self):
        self.assertEqual(HeartRateBpm(0).value, 0.0)
        self.assertEqual(HeartRateBpm(200).value, 200.0)

    def test_rejects_non_finite_or_out_of_range_values(self):
        for value in (-1, 201, float("nan"), float("inf"), True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    HeartRateBpm(value)


class TelemetryEventIdTestCase(unittest.TestCase):
    def test_rejects_empty_and_overlong_event_ids(self):
        for event_id in ("", "  ", "x" * 129):
            with self.subTest(event_id=event_id):
                with self.assertRaises(ValueError):
                    TelemetryEventId(event_id)


class RecordedAtTestCase(unittest.TestCase):
    def test_normalizes_offset_aware_time_to_utc(self):
        recorded_at = RecordedAt(datetime.fromisoformat("2026-09-27T15:00:00-05:00"))
        self.assertEqual(recorded_at.value.utcoffset(), timedelta(0))
        self.assertEqual(recorded_at.value.hour, 20)

    def test_rejects_naive_time(self):
        with self.assertRaises(ValueError):
            RecordedAt(datetime(2026, 9, 27, 15))


class HealthRecordTestCase(unittest.TestCase):
    def test_factory_creates_record_with_domain_values(self):
        source_time = datetime.fromisoformat("2026-09-27T15:00:00-05:00")
        record = HealthRecord.record(
            SubmittingDevice("smart-band-001"), "event-42", 72, source_time
        )

        self.assertEqual(record.bpm, 72.0)
        self.assertEqual(record.created_at.isoformat(), "2026-09-27T20:00:00+00:00")
        self.assertTrue(record.timestamp_supplied)
        self.assertIsNone(record.id)
        self.assertEqual(record.with_persistence_id(1).id, 1)

    def test_omitted_timestamp_is_marked_as_service_generated(self):
        record = HealthRecord.record(
            SubmittingDevice("smart-band-001"), "event-43", 72, None
        )

        self.assertFalse(record.timestamp_supplied)
        self.assertEqual(record.created_at.utcoffset(), timedelta(0))

    def test_rejects_invalid_direct_aggregate_construction(self):
        with self.assertRaises(TypeError):
            HealthRecord(SubmittingDevice("smart-band-001"), 72, RecordedAt.now())

    def test_rejects_empty_device_identity(self):
        with self.assertRaises(ValueError):
            SubmittingDevice(" ")


if __name__ == "__main__":
    unittest.main()
