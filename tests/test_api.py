import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

_test_directory = tempfile.TemporaryDirectory(prefix="smart-band-test-")
os.environ["APP_ENV"] = "development"
os.environ["DATABASE_PATH"] = os.path.join(_test_directory.name, "test.db")
os.environ["SEED_TEST_DEVICE"] = "1"
os.environ["TEST_DEVICE_API_KEY"] = "test-only-key"

from app import create_app
from health.domain.entities import SubmittingDevice
from health.infrastructure.models import HealthRecord as HealthRecordModel
from health.infrastructure.repositories import HealthRecordRepository
from health.integration.iam_anti_corruption_layer import IamAntiCorruptionLayer
from iam.infrastructure.models import Device as DeviceModel


class IamAntiCorruptionLayerTestCase(unittest.TestCase):
    def test_translates_iam_authentication_to_health_concept(self):
        class FakeIamAuthenticationService:
            credentials = None

            def authenticate(self, device_id, api_key):
                self.credentials = (device_id, api_key)
                return True

        iam_service = FakeIamAuthenticationService()
        layer = IamAntiCorruptionLayer(iam_service)

        self.assertEqual(
            layer.authenticated_submitting_device("band-42", "secret"),
            SubmittingDevice("band-42"),
        )
        self.assertEqual(iam_service.credentials, ("band-42", "secret"))

    def test_returns_no_health_concept_when_iam_rejects_credentials(self):
        class RejectingIamAuthenticationService:
            def authenticate(self, device_id, api_key):
                return False

        layer = IamAntiCorruptionLayer(RejectingIamAuthenticationService())

        self.assertIsNone(layer.authenticated_submitting_device("band-42", "invalid"))


class IamApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.testing = True

    def setUp(self):
        self.client = self.app.test_client()

    def test_authenticates_registered_device(self):
        response = self.client.post(
            "/api/v1/iam/authentications",
            json={"device_id": "smart-band-001"},
            headers={"X-API-Key": "test-only-key"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json,
            {"device_id": "smart-band-001", "authenticated": True},
        )

    def test_rejects_invalid_device_credentials(self):
        for device_id, api_key in (
            ("smart-band-001", "invalid-key"),
            ("unknown-device", "invalid-key"),
        ):
            with self.subTest(device_id=device_id):
                response = self.client.post(
                    "/api/v1/iam/authentications",
                    json={"device_id": device_id},
                    headers={"X-API-Key": api_key},
                )
                self.assertEqual(response.status_code, 401)

    def test_rejects_missing_api_key(self):
        response = self.client.post(
            "/api/v1/iam/authentications",
            json={"device_id": "smart-band-001"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json, {"error": "Missing X-API-Key"})

    def test_rejects_malformed_or_extra_request_fields(self):
        for body in ({}, {"device_id": "smart-band-001", "bpm": 70}):
            with self.subTest(body=body):
                response = self.client.post(
                    "/api/v1/iam/authentications",
                    json=body,
                    headers={"X-API-Key": "test-only-key"},
                )
                self.assertEqual(response.status_code, 400)

    def test_rejects_non_json_authentication_request(self):
        response = self.client.post(
            "/api/v1/iam/authentications",
            data="{}",
            content_type="text/plain",
            headers={"X-API-Key": "test-only-key"},
        )

        self.assertEqual(response.status_code, 415)

    def test_rejects_malformed_json(self):
        response = self.client.post(
            "/api/v1/iam/authentications",
            data="{",
            content_type="application/json",
            headers={"X-API-Key": "test-only-key"},
        )

        self.assertEqual(response.status_code, 400)


class HealthApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.testing = True

    def setUp(self):
        self.client = self.app.test_client()

    def test_creates_authenticated_record(self):
        response = self.client.post(
            "/api/v1/health-monitoring/data-records",
            json={
                "device_id": "smart-band-001",
                "event_id": "event-create-1",
                "bpm": 72,
                "created_at": "2026-09-27T15:00:00-05:00",
            },
            headers={"X-API-Key": "test-only-key"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["event_id"], "event-create-1")
        self.assertEqual(response.json["created_at"], "2026-09-27T20:00:00Z")

    def test_rejects_naive_timestamp(self):
        response = self.client.post(
            "/api/v1/health-monitoring/data-records",
            json={"device_id": "smart-band-001", "event_id": "event-naive", "bpm": 72, "created_at": "2026-09-27T15:00:00"},
            headers={"X-API-Key": "test-only-key"},
        )

        self.assertEqual(response.status_code, 400)

    def test_rejects_invalid_device_credentials(self):
        response = self.client.post(
            "/api/v1/health-monitoring/data-records",
            json={"device_id": "smart-band-001", "event_id": "event-auth", "bpm": 72},
            headers={"X-API-Key": "invalid-key"},
        )

        self.assertEqual(response.status_code, 401)

    def test_rejects_non_json_requests_with_unsupported_media_type(self):
        response = self.client.post(
            "/api/v1/health-monitoring/data-records",
            data="{}",
            content_type="text/plain",
            headers={"X-API-Key": "test-only-key"},
        )

        self.assertEqual(response.status_code, 415)

    def test_z_migrates_legacy_health_schema_additively(self):
        database = HealthRecordModel._meta.database
        original_count = HealthRecordModel.select().count()
        database.execute_sql(
            'DROP INDEX IF EXISTS "health_records_device_event_id_unique"'
        )
        database.execute_sql(
            'ALTER TABLE "health_records" DROP COLUMN "timestamp_supplied"'
        )
        database.execute_sql('ALTER TABLE "health_records" DROP COLUMN "event_id"')

        HealthRecordRepository().migrate_schema()

        columns = {
            column.name for column in database.get_columns("health_records")
        }
        indexes = {
            index.name for index in database.get_indexes("health_records")
        }
        self.assertIn("event_id", columns)
        self.assertIn("timestamp_supplied", columns)
        self.assertIn("health_records_device_event_id_unique", indexes)
        self.assertEqual(HealthRecordModel.select().count(), original_count)

    def test_device_lifecycle_changes_are_persisted(self):
        iam_service = self.app.extensions["iam_authentication_service"]
        iam_service.register_device("lifecycle-device", "first-secret")
        with self.assertRaises(ValueError):
            iam_service.register_device("lifecycle-device", "duplicate-secret")

        self.assertTrue(iam_service.authenticate("lifecycle-device", "first-secret"))
        iam_service.rotate_api_key("lifecycle-device", "second-secret")
        self.assertFalse(iam_service.authenticate("lifecycle-device", "first-secret"))
        self.assertTrue(iam_service.authenticate("lifecycle-device", "second-secret"))
        iam_service.revoke_device("lifecycle-device")
        self.assertFalse(iam_service.authenticate("lifecycle-device", "second-secret"))

        stored = DeviceModel.get_by_id("lifecycle-device").credential_verifier
        self.assertNotEqual(stored, "second-secret")

    def test_idempotent_retry_returns_original_record(self):
        payload = {
            "device_id": "smart-band-001",
            "event_id": "retry-event-42",
            "bpm": 72,
            "created_at": "2026-09-27T15:00:00-05:00",
        }
        headers = {"X-API-Key": "test-only-key"}

        first = self.client.post(
            "/api/v1/health-monitoring/data-records", json=payload, headers=headers
        )
        retry = self.client.post(
            "/api/v1/health-monitoring/data-records", json=payload, headers=headers
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json["id"], first.json["id"])
        self.assertEqual(
            HealthRecordModel.select()
            .where(HealthRecordModel.event_id == "retry-event-42")
            .count(),
            1,
        )

    def test_idempotent_retry_without_timestamp_returns_original_time(self):
        payload = {
            "device_id": "smart-band-001",
            "event_id": "retry-without-time",
            "bpm": 72,
        }
        headers = {"X-API-Key": "test-only-key"}

        first = self.client.post(
            "/api/v1/health-monitoring/data-records", json=payload, headers=headers
        )
        retry = self.client.post(
            "/api/v1/health-monitoring/data-records", json=payload, headers=headers
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json["id"], first.json["id"])
        self.assertEqual(retry.json["created_at"], first.json["created_at"])

    def test_concurrent_retries_create_one_record(self):
        payload = {
            "device_id": "smart-band-001",
            "event_id": "concurrent-event-42",
            "bpm": 72,
            "created_at": "2026-09-27T15:00:00-05:00",
        }

        def submit():
            with self.app.test_client() as client:
                return client.post(
                    "/api/v1/health-monitoring/data-records",
                    json=payload,
                    headers={"X-API-Key": "test-only-key"},
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda _: submit(), range(2)))

        self.assertEqual(sorted(response.status_code for response in responses), [200, 201])
        self.assertEqual(responses[0].json["id"], responses[1].json["id"])
        self.assertEqual(
            HealthRecordModel.select()
            .where(HealthRecordModel.event_id == "concurrent-event-42")
            .count(),
            1,
        )

    def test_rejects_event_id_reuse_with_different_telemetry(self):
        headers = {"X-API-Key": "test-only-key"}
        base = {
            "device_id": "smart-band-001",
            "event_id": "conflicting-event-42",
            "bpm": 72,
            "created_at": "2026-09-27T15:00:00-05:00",
        }
        self.client.post(
            "/api/v1/health-monitoring/data-records", json=base, headers=headers
        )
        conflicting = self.client.post(
            "/api/v1/health-monitoring/data-records",
            json={**base, "bpm": 73},
            headers=headers,
        )

        self.assertEqual(conflicting.status_code, 409)

    def test_same_event_id_is_scoped_to_device(self):
        iam_service = self.app.extensions["iam_authentication_service"]
        iam_service.register_device("second-device", "second-device-secret")
        payload = {"event_id": "device-local-event", "bpm": 72}

        responses = [
            self.client.post(
                "/api/v1/health-monitoring/data-records",
                json={**payload, "device_id": device_id},
                headers={"X-API-Key": api_key},
            )
            for device_id, api_key in (
                ("smart-band-001", "test-only-key"),
                ("second-device", "second-device-secret"),
            )
        ]

        self.assertEqual([response.status_code for response in responses], [201, 201])

    def test_missing_event_id_is_rejected(self):
        response = self.client.post(
            "/api/v1/health-monitoring/data-records",
            json={"device_id": "smart-band-001", "bpm": 72},
            headers={"X-API-Key": "test-only-key"},
        )

        self.assertEqual(response.status_code, 400)

    def test_migrates_legacy_plaintext_credentials(self):
        DeviceModel.create(
            device_id="legacy-device",
            credential_verifier="legacy-secret",
            created_at=datetime.now(UTC),
            revoked_at=None,
        )

        iam_service = self.app.extensions["iam_authentication_service"]
        DeviceModel._meta.database.execute_sql(
            'ALTER TABLE "devices" DROP COLUMN "revoked_at"'
        )
        iam_service.device_repository.migrate_schema()

        self.assertTrue(iam_service.authenticate("legacy-device", "legacy-secret"))
        columns = {
            column.name
            for column in DeviceModel._meta.database.get_columns("devices")
        }
        self.assertIn("revoked_at", columns)
        self.assertTrue(
            DeviceModel.get_by_id("legacy-device").credential_verifier.startswith(
                "pbkdf2_sha256$"
            )
        )


if __name__ == "__main__":
    unittest.main()
