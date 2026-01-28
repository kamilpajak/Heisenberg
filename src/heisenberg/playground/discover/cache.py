"""Verification cache for discovered run results."""

from __future__ import annotations

import json

from .models import CACHE_SCHEMA_VERSION, CACHE_TTL_DAYS


def get_default_cache_path():
    """Get the default cache path (XDG-compliant).

    Returns:
        Path to ~/.cache/heisenberg/verified_runs.json
    """
    from pathlib import Path

    cache_dir = Path.home() / ".cache" / "heisenberg"
    return cache_dir / "verified_runs.json"


class RunCache:
    """Cache for verified run results with TTL.

    Stores run_id -> failure_count mappings to avoid re-downloading
    large artifacts on subsequent runs. Entries expire after 90 days
    to ensure users can still view runs on GitHub.

    Thread-safe: uses a lock for concurrent access and auto-saves on write.
    """

    def __init__(self, cache_path: str | None = None):
        """Initialize cache.

        Args:
            cache_path: Path to cache JSON file. If None, uses in-memory only.
        """
        import threading
        from pathlib import Path

        self._path = Path(cache_path) if cache_path else None
        self._data: dict = {"schema_version": CACHE_SCHEMA_VERSION, "runs": {}}
        # Use RLock (reentrant) because set() calls save() while holding lock
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        """Load cache from disk if it exists, then prune expired entries."""
        if not self._path or not self._path.exists():
            return

        try:
            data = json.loads(self._path.read_text())
            # Ignore old schema versions
            if data.get("schema_version") != CACHE_SCHEMA_VERSION:
                return
            self._data = data
            # Prune expired/corrupt entries
            self._prune()
        except (json.JSONDecodeError, OSError):
            # Corrupt or unreadable file - start fresh
            pass

    def _prune(self) -> None:
        """Remove expired and corrupt entries from cache.

        Called during load to prevent unbounded cache growth.
        Saves to disk if any entries were pruned.
        """
        from datetime import datetime, timedelta

        now = datetime.now()
        cutoff = timedelta(days=CACHE_TTL_DAYS)
        expired_ids = []

        for run_id, entry in self._data["runs"].items():
            try:
                created_at = datetime.fromisoformat(entry["run_created_at"])
                if now - created_at > cutoff:
                    expired_ids.append(run_id)
            except (KeyError, ValueError):
                # Missing or invalid date - prune corrupt entry
                expired_ids.append(run_id)

        for run_id in expired_ids:
            del self._data["runs"][run_id]

        # Save if we pruned anything
        if expired_ids:
            self.save()

    def save(self) -> None:
        """Save cache to disk (thread-safe)."""
        if not self._path:
            return

        with self._lock:
            # Create parent directory if needed
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, indent=2))

    def get(self, run_id: str) -> int | None:
        """Get cached failure count for a run (thread-safe).

        Returns None if not in cache or if run is older than 90 days
        (GitHub artifacts would have expired).
        """
        from datetime import datetime, timedelta

        with self._lock:
            entry = self._data["runs"].get(run_id)
            if not entry:
                return None

            # Check TTL based on when the RUN was created (not when we cached it)
            # This ensures artifacts are still available on GitHub for demo users
            try:
                run_created_at = datetime.fromisoformat(entry["run_created_at"])
                run_age = datetime.now() - run_created_at
                if run_age > timedelta(days=CACHE_TTL_DAYS):
                    return None  # Expired - GitHub artifacts gone
                return entry["failure_count"]
            except (KeyError, ValueError):
                return None

    def set(self, run_id: str, failure_count: int, run_created_at: str) -> None:
        """Store failure count for a run and auto-save to disk.

        Thread-safe: uses lock for concurrent access.

        Args:
            run_id: GitHub workflow run ID
            failure_count: Number of test failures
            run_created_at: ISO timestamp of when the run was created on GitHub
        """
        with self._lock:
            self._data["runs"][run_id] = {
                "failure_count": failure_count,
                "run_created_at": run_created_at,
            }
            self.save()  # Auto-save to prevent data loss on crash
