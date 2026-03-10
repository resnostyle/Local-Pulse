"""Generate deterministic fingerprints for event deduplication."""

import hashlib


def compute_fingerprint(title: str, start_time: str, source_url: str) -> str:
    """Compute a SHA-256 fingerprint for deduplication.

    Args:
        title: Event title
        start_time: ISO 8601 start time string
        source_url: URL of the event source

    Returns:
        64-char hex string matching VARCHAR(64)
    """
    # Use length-prefixed fields to avoid collision if inputs contain the delimiter
    payload = f"{len(title)}:{title}{len(start_time)}:{start_time}{len(source_url)}:{source_url}"
    return hashlib.sha256(payload.encode()).hexdigest()
