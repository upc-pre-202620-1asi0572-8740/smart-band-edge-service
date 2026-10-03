"""`Health` bounded-context package.

Provides health monitoring functionality following the Domain-Driven Design
(DDD) approach, structured into domain, application, infrastructure, and
interface layers, with a context integration layer for interactions with
other bounded contexts.

- **domain**: The ``HealthRecord`` aggregate and value objects that enforce
  telemetry invariants.
- **application**: Coordinates Health use cases, aggregate behavior, context
  integration, and repository persistence.
- **infrastructure**: Peewee ORM models and repository implementations for
  persisting health records.
- **integration**: Anti-corruption layers that translate external bounded
  context concepts into Health's domain language.
- **interfaces**: Flask Blueprint exposing the REST API endpoints for this
  bounded context.
"""
