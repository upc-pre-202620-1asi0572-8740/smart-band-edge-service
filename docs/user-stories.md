# Technical Stories — Smart Band Edge Service

## Overview

This document captures the technical stories for the Smart Band Edge Service,
an IoT edge application that receives telemetry from smart-band devices through
HTTP endpoints. In this context, interactions are unattended: each device
submits health records autonomously, without direct end-user participation at
the moment of transmission.

The stories are written from the perspective of a smart-band device maker. This
perspective emphasizes the integration contract on which the device and its
firmware depend, including authentication, telemetry validation, timestamp
handling, persistence guarantees, and service readiness.

The acceptance criteria focus on observable edge-service behavior rather than
user interface details. They reflect the current implemented scope of the
solution and align with the Domain-Driven Design approach used in the project,
particularly the Health and IAM bounded contexts and their domain,
application, infrastructure, and interface layers.

## Requirements Traceability Matrix (RTX)

| Story ID   | Title                                      | Bounded Context                                                                         | Related Implementation Elements                                                                                                                                                                                                                                                              |
|------------|--------------------------------------------|-----------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| TS-SBE-001 | Ingest an Authenticated Health Record      | Health; IAM (device authentication)                                                     | `health/interfaces/services.py`: `HealthRecordCreateRequest`, `health_api`; `health/application/services.py`: `HealthRecordApplicationService`; `health/integration/iam_anti_corruption_layer.py`: `IamAntiCorruptionLayer`; `health/infrastructure/repositories.py`: idempotent persistence |
| TS-SBE-002 | Enforce Device Authentication by API Key   | IAM; Health (authenticated ingestion)                                                   | `iam/interfaces/services.py`: `AuthRequest`, `iam_api`; `iam/application/services.py`: `AuthApplicationService.authenticate`; `iam/domain/entities.py`: `Device.authenticate`; `health/integration/iam_anti_corruption_layer.py`: `IamAntiCorruptionLayer`                                   |
| TS-SBE-003 | Validate BPM Domain Rules                  | Health                                                                                  | `health/interfaces/services.py`: `HealthRecordCreateRequest`; `health/domain/value_objects.py`: `HeartRateBpm`; `health/domain/entities.py`: `HealthRecord.record`                                                                                                                           |
| TS-SBE-004 | Normalize Device Timestamps to UTC         | Health                                                                                  | `health/interfaces/services.py`: timestamp parsing in `HealthRecordCreateRequest`; `health/domain/value_objects.py`: `RecordedAt`; `health/domain/entities.py`: `HealthRecord.record`                                                                                                        |
| TS-SBE-005 | Persist Accepted Health Records            | Health; IAM (device authentication)                                                     | `health/application/services.py`: `HealthRecordApplicationService`; `health/domain/repositories.py`: `HealthRecordRepository`, `HealthRecordSaveResult`; `health/infrastructure/repositories.py`: `HealthRecordRepository`; `health/infrastructure/models.py`: `HealthRecord`                |
| TS-SBE-006 | Bootstrap Database Before Serving Requests | Application bootstrap; shared infrastructure; IAM (optional development-device seeding) | `app.py`: `create_app`; `config.py`: `load_config`; `shared/infrastructure/database.py`: `configure_database`, `init_db`; `iam/application/services.py`: `get_or_create_test_device`                                                                                                         |

### TS-SBE-001 — Ingest an Authenticated Health Record
As a smart-band device maker, I want each device to submit heart-rate readings autonomously to the health ingestion endpoint so that the edge service validates and persists each record reliably.

Acceptance criteria:
- Scenario: Successful create
  - Given a smart-band device submits a `POST` request to `/api/v1/health-monitoring/data-records`
  - And the request includes the required telemetry attributes
  - And the request includes valid device credentials
  - When the edge service validates and persists the health record
  - Then the edge service returns a response with status `201 Created`
  - And the response includes the created record with `id`, `device_id`, `bpm`, and `created_at`
  - And the record includes the submitted device-generated `event_id`

- Scenario: Retry the same telemetry after an uncertain delivery
  - Given a device submits a valid record with a stable `event_id`
  - And the device does not receive the original response
  - When the device resubmits the same event ID and telemetry
  - Then the edge service returns the original record with status `200 OK`
  - And the edge service does not create a duplicate record

- Scenario: Reuse an event ID for different telemetry
  - Given a device has already submitted a record with an `event_id`
  - When the device submits different telemetry using that same event ID
  - Then the edge service returns `409 Conflict`
  - And the original record remains unchanged

- Scenario: Missing required fields
  - Given a smart-band device submits a `POST` request to `/api/v1/health-monitoring/data-records`
  - And the request omits a required telemetry attribute such as `event_id` or `bpm`
  - When the edge service validates the payload
  - Then the edge service returns a response with status `400 Bad Request`
  - And the response includes an error payload indicating an invalid health-record request

---

### TS-SBE-002 — Enforce Device Authentication by API Key
As a smart-band device maker, I want each device request to be authenticated with an API key so that only registered devices can submit telemetry to the edge service.

Acceptance criteria:
- Scenario: Missing authentication data
  - Given a smart-band device submits a request to `/api/v1/health-monitoring/data-records`
  - And the request omits `device_id` or `X-API-Key`
  - When the edge service validates the request
  - Then the edge service returns a response with status `401 Unauthorized`
  - And the response identifies the missing `device_id` or `X-API-Key`

- Scenario: Invalid credential pair
  - Given a smart-band device submits a request to `/api/v1/health-monitoring/data-records`
  - And the device identifier and API key do not match any registered device
  - When the edge service executes IAM authentication
  - Then the edge service returns a response with status `401 Unauthorized`
  - And the response indicates an invalid device ID or API key

---

### TS-SBE-003 — Validate BPM Domain Rules
As a smart-band device maker, I want the service to validate BPM values sent by each device against domain constraints so that invalid physiological data is rejected before persistence.

Acceptance criteria:
- Scenario: BPM outside the accepted range
  - Given a smart-band device submits a `POST` request to `/api/v1/health-monitoring/data-records`
  - And the `bpm` value is outside the range `0..200`
  - When the HTTP request model and Health domain value object validate the
    value
  - Then the edge service returns a response with status `400 Bad Request`
  - And the response includes an error payload indicating an invalid health-record request

- Scenario: BPM is not numeric
  - Given a smart-band device submits a `POST` request to `/api/v1/health-monitoring/data-records`
  - And the `bpm` value is not numeric
  - When the HTTP request model attempts to parse `bpm`
  - Then the edge service returns a response with status `400 Bad Request`
  - And the response includes an error payload indicating an invalid health-record request

---

### TS-SBE-004 — Normalize Device Timestamps to UTC
As a smart-band device maker, I want the service to normalize timestamps sent by each device to UTC so that stored telemetry remains consistent across device time zones.

Acceptance criteria:
- Scenario: Timestamp provided with time-zone offset
  - Given a smart-band device submits a `POST` request to `/api/v1/health-monitoring/data-records`
  - And the `created_at` value is provided in valid ISO 8601 format with an offset
  - When the HTTP request model parses the timestamp and the Health domain
    normalizes it
  - Then the value is converted and stored as UTC
  - And the response includes the normalized `created_at` value

- Scenario: Timestamp omitted
  - Given a smart-band device submits a `POST` request to `/api/v1/health-monitoring/data-records`
  - And the request omits `created_at`
  - When the edge service creates the health record through the domain factory
  - Then `created_at` is set using the current UTC time
  - And the record is persisted with that generated timestamp

---

### TS-SBE-005 — Persist Accepted Health Records
As a smart-band device maker, I want each accepted telemetry record from a device to become durable and identifiable so that ingestion remains reliable and traceable.

Acceptance criteria:
- Scenario: Accepted record becomes durable
  - Given the edge service holds a valid `HealthRecord` domain entity without an `id`
  - When the edge service completes persistence
  - Then the record is stored in local persistence
  - And the returned domain entity includes the assigned `id`

- Scenario: Application service orchestrates domain and persistence
  - Given a smart-band device submits a valid authenticated request
  - And the request contains accepted `bpm` and timestamp values
  - When the edge service executes the create-health-record use case
  - Then the Health-to-IAM anti-corruption layer asks the IAM application
    service to authenticate the device
  - And it creates a `HealthRecord` through the domain factory using validated
    value objects
  - And it persists the record idempotently through the Health repository

---

### TS-SBE-006 — Bootstrap a Database Before Serving Requests
As a smart-band device maker, I want the edge service to prepare its local storage before serving requests so that a device can begin sending records without manual database preparation.

Acceptance criteria:
- Scenario: Application startup bootstraps storage
  - Given the edge service creates its Flask application
  - When the application factory configures and initializes local storage
  - Then local storage is initialized
  - And the `devices` and `health_records` tables are created if missing
  - And existing device and telemetry schemas are migrated additively
  - And a test device is created only when development seeding is enabled and
    the device is absent

- Scenario: Requests do not trigger bootstrap work
  - Given the Flask application has been created and initialized
  - When the edge service receives an HTTP request
  - Then request handling does not rerun database initialization or schema migrations
