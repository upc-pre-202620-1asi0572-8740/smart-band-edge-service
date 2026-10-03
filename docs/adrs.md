# Architecture Decision Records

This document records decisions that shape the Smart Band Edge Service. The
records are intentionally concise and focus on decisions that affect system
boundaries, integration contracts, or operational behavior.

These records were documented retrospectively from the implementation and
project history. New records should be appended rather than rewriting an
accepted decision. If a decision changes, add a new ADR that supersedes the
earlier record and links the two records.

## ADR format

Each record includes:

- **Status**: `Accepted`, `Superseded`, or `Deprecated`
- **Date**: the date the decision was made or, for retrospective records, the
  date the decision first became clear in project history
- **Context**: the problem and constraints
- **Decision**: the chosen approach
- **Consequences**: important benefits and trade-offs
- **Alternatives considered**: credible options that were not selected

## ADR-0001: Organize the service around DDD-inspired bounded contexts

- **Status**: Accepted
- **Date**: 2025-06-04

### Context

Authentication and health telemetry have different business responsibilities
and are expected to evolve independently. Mixing them in a single technical
module would make device identity concerns leak into the telemetry model.

### Decision

Structure the service as two bounded contexts:

- **IAM** owns device identity and API-key authentication.
- **Health** owns heart-rate validation and health-record persistence.

Each context uses domain, application, infrastructure, and interface layers.
The Health application service may ask IAM to validate a device, but Health
does not own authentication rules.

### Consequences

- Business responsibilities and ownership are explicit.
- Domain code remains independent of Flask and Peewee.
- Cross-context calls must remain small and intentional.
- The structure adds more modules than a single-module Flask application.

### Alternatives considered

- A single application module containing routes, validation, and persistence.
- A purely technical package structure organized only by framework layer.

## ADR-0002: Use SQLite with Peewee for local edge persistence

- **Status**: Accepted
- **Date**: 2025-06-04

### Context

The service needs durable local storage for device registrations and incoming
health records while remaining lightweight for development and small edge
deployments.

### Decision

Use SQLite as the local database and Peewee as the ORM. Keep ORM models and
repository implementations in the infrastructure layer so domain entities
and protocols do not depend on either technology.

### Consequences

- Local setup has no external database service dependency.
- The repository boundary allows the persistence technology to be replaced.
- SQLite is appropriate for the current scope but is not a default choice for
  high-write concurrency or centralized multi-instance workloads.
- A production deployment may require migration, backup, locking, and
  concurrency policies that are not yet implemented.

### Alternatives considered

- PostgreSQL for stronger multi-client and operational capabilities.
- An in-memory store, which would not provide durable telemetry.

## ADR-0003: Authenticate devices with a paired API key

- **Status**: Accepted
- **Date**: 2025-06-05

### Context

Unattended smart-band requests need a simple credential that firmware can send
without an interactive user session. The edge service must reject unknown
devices before accepting telemetry.

### Decision

Require the device identifier in the JSON request body and its paired secret
in the `X-API-Key` header. IAM validates the pair against the registered
device repository. IAM exposes a focused HTTP authentication endpoint for
clients that need an IAM response; other in-process bounded contexts call the
IAM application use case through their own integration components. Device
registration, credential rotation, and revocation are not exposed as HTTP
operations.

### Consequences

- Device-to-service integration is straightforward and explicit.
- Authentication behavior is shared through the IAM application use case,
  while HTTP adapters remain independent of in-process integration.
- API keys must be provisioned, rotated, stored, and transmitted securely.
- The seeded development credential is not suitable for production.

### Alternatives considered

- User-oriented sessions or OAuth, which do not fit unattended device
  ingestion.
- Client certificates or signed requests, which provide stronger guarantees
  but require more device provisioning and lifecycle infrastructure.

## ADR-0004: Validate request payloads at the HTTP boundary with Pydantic

- **Status**: Accepted
- **Date**: 2026-09-27

### Context

Malformed JSON and invalid field values should be rejected before the
application service runs. The API contract includes required fields, numeric
types, and a BPM range.

### Decision

Use Pydantic request models in the Flask interface layer. The interface maps
validation failures to `400 Bad Request`; domain services remain responsible
for business invariants that apply beyond this particular transport.

### Consequences

- HTTP contracts are explicit and errors are handled close to the boundary.
- Application and domain services can be called without depending on Flask
  request objects.
- Validation rules may need coordination when additional transports are
  introduced.
- Pydantic becomes a runtime dependency.

### Alternatives considered

- Manual dictionary checks in each route.
- Relying only on domain validation after transport parsing.

## ADR-0005: Normalize accepted timestamps to UTC

- **Status**: Accepted
- **Date**: 2025-06-05

### Context

Devices may report timestamps with different local offsets, while persisted
telemetry must be comparable across devices and deployments.

### Decision

Accept ISO 8601 timestamps, convert offset-aware values to UTC, and generate
the current UTC time when `created_at` is omitted. Persist and return the
normalized value.

### Consequences

- Queries and downstream processing use one consistent time basis.
- Original device offset information is not retained separately.
- Device clocks and malformed timestamps remain input-quality concerns.

### Alternatives considered

- Persisting each device's local timestamp and offset unchanged.
- Requiring every device to normalize to UTC before sending.

## ADR-0006: Bootstrap storage on the first request

- **Status**: Superseded by ADR-0007
- **Date**: 2025-06-05

### Context

The lightweight service should start without a manual database preparation
step. The development environment also needs a known test device.

### Decision

Use Flask's `before_request` hook with a process-local guard to initialize the
SQLite database, create missing tables, and seed the development device once
before the first handled request.

### Consequences

- Local startup is straightforward and setup is idempotent for the current process.
- The first request bears initialization latency.
- Initialization is coupled with request handling and does not provide a
  migration or readiness lifecycle for production.
- Multi-worker startup behavior requires care because each worker has its own
  process-local guard.

### Alternatives considered

- An explicit startup or deployment command.
- Flask application-factory initialization before serving requests.
- A migration framework and managed provisioning workflow.

## ADR-0007: Initialize through an application factory

- **Status**: Accepted
- **Date**: 2026-09-27

### Context

Initialization tied to the first request delayed failures until traffic arrived,
used a process-local flag, and behaved inconsistently across workers. Database
connections also need a predictable Flask lifecycle.

### Decision

Create the Flask application through `create_app()`. Configure the database
from `DATABASE_PATH`, initialize tables before the application serves requests,
and close the Peewee connection in `teardown_appcontext`. Development-device
seeding is controlled explicitly by `SEED_TEST_DEVICE` and
`TEST_DEVICE_API_KEY`.

### Consequences

- Configuration and initialization failures occur during application creation.
- Database cleanup follows Flask's application-context lifecycle.
- The application is easier to test and deploy with different settings.
- Schema migrations and multi-process coordination still require a dedicated
  migration/deployment mechanism.

### Alternatives considered

- Retaining the first-request flag and adding locking around it.
- Running a separate manual initialization command without application-factory
  integration.

## ADR-0008: Isolate Health from IAM with an anti-corruption adapter

- **Status**: Accepted
- **Date**: 2026-09-27

### Context

Health needs to confirm that a submitting device is authorized, but directly
depending on IAM's repository and credential model couples Health use cases to
another bounded context's internals.

### Decision

Define a Health-owned `SubmittingDevice` domain concept and a Health
`IamAntiCorruptionLayer` that delegates credential verification to IAM's
application service. When IAM accepts the credentials, the layer translates
that result into a `SubmittingDevice`; otherwise it returns no Health device.
The application factory composes the layer into the Health application
service. The Health HTTP interface handles Health-owned request and response
semantics and does not invoke IAM routes or helpers.

### Consequences

- Health application code no longer imports IAM repositories or domain types.
- IAM implementation details are contained in one anti-corruption layer.
- The boundary can be replaced with another identity provider without changing
  Health use cases.
- Health works with its own domain concept rather than IAM's `Device` model or
  an IAM-specific authentication result.

### Alternatives considered

- Directly injecting IAM's device repository into the Health service.
- Calling IAM's HTTP endpoint, adding avoidable network and serialization
  overhead for an in-process modular monolith.
- Duplicating credential validation in Health.

## ADR-0009: Protect Health record invariants with domain value objects

- **Status**: Accepted
- **Date**: 2026-09-27

### Context

Health telemetry validation was concentrated in a service that accepted raw
transport-like values, while callers could directly construct a record with
invalid BPM or a naive timestamp.

### Decision

Represent BPM and observation time as immutable `HeartRateBpm` and `RecordedAt`
value objects. Create records through the `HealthRecord.record` domain factory,
which requires the Health-local `SubmittingDevice`, validates BPM, and applies
UTC timestamp rules. Parse timestamp strings at the HTTP boundary and pass
typed datetime values into the application layer.

### Consequences

- Invalid values cannot enter a HealthRecord through normal domain
  construction.
- Domain invariants can be tested without Flask, Pydantic, or a database.
- Persistence and HTTP layers map to/from the domain-owned value objects.
- The current plausible BPM range is explicit in the domain model and needs
  domain review if supported sensors or use cases change.

### Alternatives considered

- Keeping invariant checks in an application/domain service and allowing
  direct record construction.
- Relying only on request schema validation, which would not protect other
  record creation paths.

## ADR-0011: Make telemetry retries idempotent with device event IDs

- **Status**: Accepted
- **Date**: 2026-09-27

### Context

An IoT device may lose the response after the edge service commits a record.
Retrying a non-idempotent creation request can persist duplicate measurements.

### Decision

Require each device to supply a stable `event_id` and scope uniqueness to
`(device_id, event_id)`. A repeated event with matching BPM and timestamp
semantics returns the original record with `200 OK`; reusing the ID for
different telemetry returns `409 Conflict`. A unique database index enforces
the constraint across requests. An additive migration leaves event IDs null
for historical rows.

### Consequences

- Devices must persist and reuse event IDs until a submission is acknowledged.
- Identical retries return the original record without duplicate rows.
- Reusing an ID with changed input is explicitly rejected.
- Existing records remain available without assigning fabricated event IDs.
- Idempotency does not protect data lost before the device durably stores the
  event ID and payload.

### Alternatives considered

- Time-window deduplication, which can merge distinct readings or miss delayed
  retries.
- A separate HTTP idempotency header, which makes the device contract less
  explicit than a telemetry event identity.
- Globally unique event IDs, which require unnecessary coordination between
  independent devices.

## ADR-0010: Make the IAM device aggregate its own credential lifecycle

- **Status**: Accepted
- **Date**: 2026-09-27

### Context

IAM previously queried by both device ID and raw API key, and its domain
authentication service only converted repository presence into a boolean.
Device lifecycle rules such as credential rotation and revocation were not
represented in the domain model, and credentials were persisted in plaintext.

### Decision

Make `Device` responsible for authenticating credentials, rotating an active
device's credential, and revoking access. Represent stored credentials with an
`ApiCredential` value object that uses a salted PBKDF2 verifier and
constant-time comparison. Repositories load devices by ID and persist aggregate
state; the aggregate evaluates authentication policy. Application
startup adds the revocation column and migrates legacy plaintext credentials
to verifiers.

### Consequences

- The aggregate evaluates credential acceptance and active/revoked state together.
- Repository queries no longer include or compare raw credentials.
- Raw API keys are not returned from persistence or represented in `Device`.
- Startup performs a one-time data migration; application startup can take
  longer for a database with many legacy credentials.
- PBKDF2 adds per-authentication CPU cost; the work factor should be measured
  against expected edge-device capacity and threat model.
- Credential rotation and revocation are domain capabilities exposed through
  application services; no public management endpoints are added here.

### Alternatives considered

- Hashing credentials in repository code, which would leave credential policy
  outside the aggregate.
- Keeping lookup-by-ID-and-key, which embeds authentication policy in SQL.
- Adding a lifecycle state without persisting it, which would lose revocation on
  restart.
