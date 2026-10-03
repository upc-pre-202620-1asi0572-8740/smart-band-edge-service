# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project intends to follow [Semantic Versioning](https://semver.org/)
for published releases. Changes are grouped by user-visible or
maintainer-relevant impact; implementation-only commits are consolidated
instead of being listed individually.

## [1.0.0] - 2026-09-27

### Added

- IAM exposes a focused device-authentication endpoint backed by the
  application use case; it does not expose device lifecycle management.
- Architecture decision records in [`docs/adrs.md`](docs/adrs.md), covering
  the service boundaries, persistence, authentication, validation, time
  handling, and startup lifecycle.

### Changed

- Application configuration now loads environment-specific dotenv files,
  gives process environment variables precedence without mutating process
  state, reads environment settings from those files, and enforces safe
  production settings.
- Health ingestion now requires device-scoped event IDs, returns the original
  record for identical retries, and rejects conflicting reuse with `409`.
- Existing Health databases receive an additive event-ID migration and unique
  `(device_id, event_id)` index; historical records keep a null event ID.
- Health records now enforce BPM, device identity, and UTC timestamp invariants
  through domain value objects and a domain-owned record factory.
- IAM devices now own authentication, credential rotation, and revocation
  behavior; stored API credentials use salted PBKDF2 verifiers with a legacy
  plaintext migration.
- Health now uses a DDD anti-corruption layer to translate IAM authentication
  into its own `SubmittingDevice` concept, removing direct repository and
  HTTP-helper dependencies across the bounded-context boundary.
- Application initialization now uses a Flask application factory with
  environment-configured database lifecycle and teardown.
- Development test-device seeding is opt-in and requires an explicitly
  configured API key.
- API validation distinguishes malformed requests from authentication failures,
  rejects unknown Health payload fields, and requires timezone-aware timestamps.
- Added standard-library regression tests for authenticated ingestion and
  request error semantics.
- Removed the unused direct `python-dateutil` dependency.
- Domain entities are immutable frozen dataclasses with explicit type hints.
- Repository dependencies are expressed through domain protocols and injected
  into application services, improving separation from Peewee and testability.
- Request payloads are validated with Pydantic at the HTTP boundary, including
  the `0..200` BPM constraint.
- Repository methods use instance-bound collaborators consistently.
- Dependency versions were refreshed and Pydantic was added to the runtime
  requirements.
- Module and project documentation was clarified to describe the implemented
  IoT edge scope and DDD-inspired structure.

## Initial implementation - 2025-06-05

### Added

- Initial smart-band edge API for authenticated heart-rate ingestion.
- IAM and Health bounded contexts with domain, application, infrastructure,
  and interface layers.
- `POST /api/v1/health-monitoring/data-records` endpoint.
- Device authentication using `device_id` and the `X-API-Key` header.
- SQLite persistence through Peewee for devices and health records.
- UTC normalization for ISO 8601 telemetry timestamps.
- First-request database initialization and development-device seeding.
- Project README, technical stories, class diagram, and MIT license.
