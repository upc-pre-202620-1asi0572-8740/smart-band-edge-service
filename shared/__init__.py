"""Shared kernel package for the Smart Band Edge Service.

Contains cross-cutting infrastructure components that are shared across
all bounded contexts (IAM, Health, etc.), such as the database connection
singleton and initialization helpers.

This package intentionally has no domain logic; it only provides
technical plumbing required by the application.
"""
