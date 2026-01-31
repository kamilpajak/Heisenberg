"""Tests for quarantine cache (QuarantineCache) and default quarantine path."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from heisenberg.discovery.cache import QuarantineCache, get_default_quarantine_path
from heisenberg.discovery.models import DISCOVERY_SCHEMA_VERSION, QUARANTINE_TTL_HOURS

# =============================================================================
# QUARANTINE CACHE TESTS
# =============================================================================


class TestQuarantineCache:
    """Tests for QuarantineCache - caching incompatible repos."""

    def test_is_quarantined_returns_false_for_unknown_repo(self):
        """is_quarantined() should return False for repos not in cache."""
        cache = QuarantineCache()

        result = cache.is_quarantined("unknown/repo")

        assert result is False

    def test_set_and_is_quarantined(self):
        """set() should store value, is_quarantined() should return True."""
        cache = QuarantineCache()
        cache.set("owner/repo", "no_artifacts")

        result = cache.is_quarantined("owner/repo")

        assert result is True

    def test_stores_status_value(self):
        """set() should store the status string in the entry."""
        cache = QuarantineCache()
        cache.set("owner/repo", "no_failed_runs")

        entry = cache._data["repos"]["owner/repo"]

        assert entry["status"] == "no_failed_runs"


class TestQuarantineTTL:
    """Tests for QuarantineCache TTL (24 hours wall-clock)."""

    def test_expires_after_24_hours(self):
        """Entries older than 24 hours should not be quarantined."""
        cache = QuarantineCache()

        old_time = datetime.now() - timedelta(hours=25)
        cache._data["repos"]["owner/repo"] = {
            "status": "no_artifacts",
            "quarantined_at": old_time.isoformat(),
        }

        result = cache.is_quarantined("owner/repo")

        assert result is False

    def test_valid_within_24_hours(self):
        """Entries within 24 hours should be quarantined."""
        cache = QuarantineCache()

        recent_time = datetime.now() - timedelta(hours=12)
        cache._data["repos"]["owner/repo"] = {
            "status": "no_artifacts",
            "quarantined_at": recent_time.isoformat(),
        }

        result = cache.is_quarantined("owner/repo")

        assert result is True

    def test_at_23_hours_is_valid(self):
        """Entry at 23 hours should still be quarantined (just under TTL)."""
        cache = QuarantineCache()

        boundary_time = datetime.now() - timedelta(hours=23)
        cache._data["repos"]["owner/repo"] = {
            "status": "no_artifacts",
            "quarantined_at": boundary_time.isoformat(),
        }

        result = cache.is_quarantined("owner/repo")

        assert result is True


class TestQuarantinePersistence:
    """Tests for QuarantineCache persistence to JSON file."""

    def test_save_creates_json_file(self, tmp_path):
        """save() should create JSON file at specified path."""
        cache_file = tmp_path / ".cache" / "quarantined_repos.json"
        cache = QuarantineCache(cache_path=cache_file)
        cache.set("owner/repo", "no_artifacts")
        cache.save()

        assert cache_file.exists()

    def test_save_creates_parent_directory(self, tmp_path):
        """save() should create parent directory if needed."""
        cache_file = tmp_path / ".cache" / "quarantined_repos.json"
        cache = QuarantineCache(cache_path=cache_file)
        cache.set("owner/repo", "no_artifacts")
        cache.save()

        assert (tmp_path / ".cache").is_dir()

    def test_load_reads_existing_file(self, tmp_path):
        """load() should read data from existing JSON file."""
        cache_file = tmp_path / "quarantine.json"
        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": DISCOVERY_SCHEMA_VERSION,
                    "repos": {
                        "owner/repo": {
                            "status": "no_artifacts",
                            "quarantined_at": datetime.now().isoformat(),
                        }
                    },
                }
            )
        )

        cache = QuarantineCache(cache_path=cache_file)

        assert cache.is_quarantined("owner/repo") is True

    def test_handles_missing_file(self, tmp_path):
        """Should handle missing cache file gracefully."""
        cache_file = tmp_path / "nonexistent.json"
        cache = QuarantineCache(cache_path=cache_file)

        result = cache.is_quarantined("any/repo")

        assert result is False

    def test_handles_corrupt_json(self, tmp_path):
        """Should handle corrupt JSON file gracefully."""
        cache_file = tmp_path / "corrupt.json"
        cache_file.write_text("not valid json {{{")

        cache = QuarantineCache(cache_path=cache_file)

        result = cache.is_quarantined("any/repo")

        assert result is False


class TestQuarantineSchemaVersion:
    """Tests for quarantine cache schema versioning."""

    def test_includes_schema_version(self, tmp_path):
        """Saved cache should include schema_version."""
        cache_file = tmp_path / "quarantine.json"
        cache = QuarantineCache(cache_path=cache_file)
        cache.set("owner/repo", "no_artifacts")
        cache.save()

        data = json.loads(cache_file.read_text())

        assert "schema_version" in data
        assert data["schema_version"] == DISCOVERY_SCHEMA_VERSION

    def test_ignores_old_schema_version(self, tmp_path):
        """Should ignore cache with older schema version."""
        cache_file = tmp_path / "quarantine.json"
        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": 0,
                    "repos": {
                        "owner/repo": {
                            "status": "no_artifacts",
                            "quarantined_at": datetime.now().isoformat(),
                        }
                    },
                }
            )
        )

        cache = QuarantineCache(cache_path=cache_file)

        assert cache.is_quarantined("owner/repo") is False


class TestQuarantinePruning:
    """Tests for automatic cleanup of expired quarantine entries."""

    def test_prunes_expired_entries_on_load(self, tmp_path):
        """Expired entries should be removed when cache is loaded."""
        cache_file = tmp_path / "quarantine.json"

        old_time = (datetime.now() - timedelta(hours=QUARANTINE_TTL_HOURS + 10)).isoformat()
        recent_time = datetime.now().isoformat()

        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": DISCOVERY_SCHEMA_VERSION,
                    "repos": {
                        "old/repo": {"status": "no_artifacts", "quarantined_at": old_time},
                        "recent/repo": {"status": "no_artifacts", "quarantined_at": recent_time},
                    },
                }
            )
        )

        cache = QuarantineCache(cache_path=cache_file)

        assert "old/repo" not in cache._data["repos"]
        assert "recent/repo" in cache._data["repos"]

    def test_prunes_corrupt_entries(self, tmp_path):
        """Entries with invalid dates should be pruned."""
        cache_file = tmp_path / "quarantine.json"

        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": DISCOVERY_SCHEMA_VERSION,
                    "repos": {
                        "corrupt/repo": {"status": "no_artifacts", "quarantined_at": "not-a-date"},
                        "missing/date": {"status": "no_artifacts"},
                        "valid/repo": {
                            "status": "no_artifacts",
                            "quarantined_at": datetime.now().isoformat(),
                        },
                    },
                }
            )
        )

        cache = QuarantineCache(cache_path=cache_file)

        assert "corrupt/repo" not in cache._data["repos"]
        assert "missing/date" not in cache._data["repos"]
        assert "valid/repo" in cache._data["repos"]

    def test_saves_after_pruning(self, tmp_path):
        """Cache should save to disk after pruning expired entries."""
        cache_file = tmp_path / "quarantine.json"

        old_time = (datetime.now() - timedelta(hours=QUARANTINE_TTL_HOURS + 10)).isoformat()
        recent_time = datetime.now().isoformat()

        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": DISCOVERY_SCHEMA_VERSION,
                    "repos": {
                        "old/repo": {"status": "no_artifacts", "quarantined_at": old_time},
                        "recent/repo": {"status": "no_artifacts", "quarantined_at": recent_time},
                    },
                }
            )
        )

        QuarantineCache(cache_path=cache_file)

        data = json.loads(cache_file.read_text())
        assert "old/repo" not in data["repos"]
        assert "recent/repo" in data["repos"]

    def test_no_save_if_nothing_pruned(self, tmp_path):
        """Cache should not save if no entries were pruned."""
        import time

        cache_file = tmp_path / "quarantine.json"
        recent_time = datetime.now().isoformat()

        original_content = json.dumps(
            {
                "schema_version": DISCOVERY_SCHEMA_VERSION,
                "repos": {
                    "valid/repo": {"status": "no_artifacts", "quarantined_at": recent_time},
                },
            }
        )
        cache_file.write_text(original_content)
        original_mtime = cache_file.stat().st_mtime

        time.sleep(0.01)

        QuarantineCache(cache_path=cache_file)

        assert cache_file.stat().st_mtime == original_mtime


class TestQuarantineThreadSafety:
    """Tests for thread-safe QuarantineCache with auto-save."""

    def test_has_lock(self):
        """QuarantineCache should have a threading lock (reentrant)."""
        import threading

        cache = QuarantineCache()

        assert hasattr(cache, "_lock")
        assert isinstance(cache._lock, type(threading.RLock()))

    def test_auto_saves_on_set(self, tmp_path):
        """set() should automatically save to disk."""
        cache_file = tmp_path / "quarantine.json"
        cache = QuarantineCache(cache_path=cache_file)

        cache.set("owner/repo", "no_artifacts")

        assert cache_file.exists()

        cache2 = QuarantineCache(cache_path=cache_file)
        assert cache2.is_quarantined("owner/repo") is True

    def test_thread_safe_concurrent_writes(self, tmp_path):
        """Multiple threads writing should not corrupt cache."""
        import threading

        cache_file = tmp_path / "quarantine.json"
        cache = QuarantineCache(cache_path=cache_file)

        errors = []

        def write_entry(i):
            try:
                cache.set(f"owner/repo-{i}", "no_artifacts")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_entry, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        for i in range(20):
            assert cache.is_quarantined(f"owner/repo-{i}") is True


class TestQuarantineRemove:
    """Tests for removing repos from quarantine."""

    def test_remove_existing_entry(self):
        """remove() should remove a quarantined repo."""
        cache = QuarantineCache()
        cache.set("owner/repo", "no_artifacts")

        cache.remove("owner/repo")

        assert cache.is_quarantined("owner/repo") is False

    def test_remove_nonexistent_is_noop(self):
        """remove() on a non-quarantined repo should be a no-op."""
        cache = QuarantineCache()

        cache.remove("unknown/repo")  # Should not raise

        assert cache.is_quarantined("unknown/repo") is False


class TestDefaultQuarantinePath:
    """Tests for XDG-compliant default quarantine path."""

    def test_path_is_absolute(self):
        """Default quarantine path should be absolute."""
        path = get_default_quarantine_path()

        assert path.is_absolute()

    def test_path_in_user_cache_dir(self):
        """Default quarantine path should be in ~/.cache/heisenberg/."""
        from pathlib import Path

        path = get_default_quarantine_path()

        assert str(Path.home()) in str(path)
        assert "heisenberg" in str(path)

    def test_filename_is_quarantined_repos_json(self):
        """Default quarantine filename should be quarantined_repos.json."""
        path = get_default_quarantine_path()

        assert path.name == "quarantined_repos.json"
