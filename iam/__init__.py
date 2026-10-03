"""Identity and Access Management (IAM) bounded context package.

Handles device registration, look-up, and API-key-based authentication for
smart band devices, following a Domain-Driven Design layered architecture:

- **domain**: ``Device`` aggregate root and ``ApiCredential`` value object
  with authentication, rotation, and revocation behavior.
- **application**: ``AuthApplicationService`` that orchestrates device
  lifecycle and authentication use-cases.
- **infrastructure**: Peewee ORM models and repository implementations for
  persisting device data.
- **interfaces**: Flask Blueprint and HTTP request handling for IAM routes.
"""
