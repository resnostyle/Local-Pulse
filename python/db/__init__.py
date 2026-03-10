"""Database connection and event insert logic.

When inserting events: store all timestamps in UTC, and always provide
a non-null fingerprint for deduplication.
"""
