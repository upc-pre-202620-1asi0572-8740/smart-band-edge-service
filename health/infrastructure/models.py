"""Peewee ORM model for the Health bounded context.

Defines the ``health_records`` database table structure used to persist
:class:`~health.domain.entities.HealthRecord` domain entities.  This module
belongs to the infrastructure layer and must not be referenced directly from
the domain or application layers; access is mediated through the repository.
"""
from peewee import BooleanField, Model, AutoField, FloatField, CharField, DateTimeField

from shared.infrastructure.database import db


class HealthRecord(Model):
    """ORM mapping for the ``health_records`` table.

    Each row represents a single heart-rate reading submitted by a registered
    smart band device.

    Attributes:
        id (AutoField): Auto-incrementing integer primary key assigned by the
            database on insert.
        device_id (CharField): Foreign reference to the device that produced
            the reading.  Stored as a plain string (not a FK constraint) to
            keep the bounded contexts loosely coupled.
        event_id (CharField): Device-scoped idempotency key. ``NULL`` only for
            records written before idempotency was introduced.
        bpm (FloatField): Heart-rate measurement in beats per minute.
        created_at (DateTimeField): UTC timestamp of when the reading was
            captured by the device.
        timestamp_supplied (BooleanField): Whether the device supplied the
            timestamp or the service generated it.
    """

    id = AutoField()
    device_id = CharField()
    event_id = CharField(null=True, max_length=128)
    bpm = FloatField()
    created_at = DateTimeField()
    timestamp_supplied = BooleanField(default=True)

    class Meta:
        """Peewee metadata: binds the model to the shared database and names the table."""

        database = db
        table_name = 'health_records'
