"""Tests for verification cache (RunCache) and default cache path."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from heisenberg.playground.discover.cache import RunCache, get_default_cache_path
from heisenberg.playground.discover.models import CACHE_TTL_DAYS

# =============================================================================
# RUN CACHE TESTS
# =============================================================================


class TestRunCache:
    """Tests for RunCache - caching verified run results."""

    def test_run_cache_class_exists(self):
        """RunCache class should be importable."""
        assert RunCache is not None

    def test_run_cache_get_returns_none_for_unknown_run(self):
        """get() should return None for runs not in cache."""
        cache = RunCache()
        result = cache.get("unknown-run-id")

        assert result is None

    def test_run_cache_set_and_get(self):
        """set() should store value, get() should retrieve it."""
        cache = RunCache()
        cache.set("run-123", 5, datetime.now().isoformat())

        result = cache.get("run-123")

        assert result == 5

    def test_run_cache_stores_zero_failures(self):
        """Should correctly store and retrieve 0 failures (not None)."""
        cache = RunCache()
        cache.set("run-456", 0, datetime.now().isoformat())

        result = cache.get("run-456")

        assert result == 0
        assert result is not None


class TestRunCacheTTL:
    """Tests for RunCache TTL (90 days from run creation on GitHub)."""

    def test_cache_expires_when_run_older_than_90_days(self):
        """Entries for runs older than 90 days should return None."""
        cache = RunCache()

        old_run_date = datetime.now() - timedelta(days=91)
        cache._data["runs"]["old-run"] = {
            "failure_count": 3,
            "run_created_at": old_run_date.isoformat(),
        }

        result = cache.get("old-run")

        assert result is None  # Expired - GitHub artifacts gone

    def test_cache_valid_when_run_within_90_days(self):
        """Entries for recent runs should be returned."""
        cache = RunCache()

        recent_run_date = datetime.now() - timedelta(days=30)
        cache._data["runs"]["recent-run"] = {
            "failure_count": 7,
            "run_created_at": recent_run_date.isoformat(),
        }

        result = cache.get("recent-run")

        assert result == 7

    def test_cache_entry_at_89_days_is_valid(self):
        """Entry for run at 89 days should still be valid (just under TTL)."""
        cache = RunCache()

        boundary_date = datetime.now() - timedelta(days=89)
        cache._data["runs"]["boundary-run"] = {
            "failure_count": 2,
            "run_created_at": boundary_date.isoformat(),
        }

        result = cache.get("boundary-run")

        assert result == 2


class TestRunCacheTimezoneAware:
    """Tests for RunCache handling timezone-aware ISO strings from GitHub."""

    def test_get_handles_utc_suffix(self):
        """get() should handle GitHub-style UTC timestamps ('Z' suffix)."""
        cache = RunCache()
        utc_date = "2026-01-15T10:30:00Z"
        cache._data["runs"]["tz-run"] = {
            "failure_count": 5,
            "run_created_at": utc_date,
        }

        result = cache.get("tz-run")

        assert result == 5

    def test_get_handles_utc_offset(self):
        """get() should handle timestamps with explicit +00:00 offset."""
        cache = RunCache()
        utc_date = "2026-01-15T10:30:00+00:00"
        cache._data["runs"]["tz-run"] = {
            "failure_count": 3,
            "run_created_at": utc_date,
        }

        result = cache.get("tz-run")

        assert result == 3

    def test_prune_handles_utc_suffix(self, tmp_path):
        """_prune() should handle GitHub-style UTC timestamps without crashing."""
        cache_file = tmp_path / "cache.json"

        old_date = "2024-01-01T00:00:00Z"  # Well past 90 days
        recent_date = datetime.now(UTC).isoformat()

        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "runs": {
                        "old-run": {"failure_count": 5, "run_created_at": old_date},
                        "recent-run": {"failure_count": 3, "run_created_at": recent_date},
                    },
                }
            )
        )

        cache = RunCache(cache_path=cache_file)

        assert "old-run" not in cache._data["runs"]
        assert "recent-run" in cache._data["runs"]

    def test_set_and_get_with_github_timestamp(self):
        """Full round-trip: set() with GitHub timestamp, get() returns value."""
        cache = RunCache()
        github_ts = "2026-01-28T10:30:00Z"

        cache.set("gh-run", 7, github_ts)

        assert cache.get("gh-run") == 7

    def test_mixed_naive_and_aware_timestamps(self, tmp_path):
        """Cache with both naive and aware timestamps should load correctly."""
        cache_file = tmp_path / "cache.json"

        naive_date = datetime.now().isoformat()
        aware_date = datetime.now(UTC).isoformat()

        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "runs": {
                        "naive-run": {"failure_count": 1, "run_created_at": naive_date},
                        "aware-run": {"failure_count": 2, "run_created_at": aware_date},
                    },
                }
            )
        )

        cache = RunCache(cache_path=cache_file)

        assert cache.get("naive-run") == 1
        assert cache.get("aware-run") == 2


class TestRunCachePersistence:
    """Tests for RunCache persistence to JSON file."""

    def test_cache_save_creates_json_file(self, tmp_path):
        """save() should create JSON file at specified path."""
        cache_file = tmp_path / ".cache" / "verified_runs.json"
        cache = RunCache(cache_path=cache_file)
        cache.set("run-123", 5, datetime.now().isoformat())
        cache.save()

        assert cache_file.exists()

    def test_cache_save_creates_parent_directory(self, tmp_path):
        """save() should create parent .cache directory if needed."""
        cache_file = tmp_path / ".cache" / "verified_runs.json"
        cache = RunCache(cache_path=cache_file)
        cache.set("run-123", 5, datetime.now().isoformat())
        cache.save()

        assert (tmp_path / ".cache").is_dir()

    def test_cache_load_reads_existing_file(self, tmp_path):
        """load() should read data from existing JSON file."""
        cache_file = tmp_path / "cache.json"
        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "runs": {
                        "existing-run": {
                            "failure_count": 10,
                            "run_created_at": datetime.now().isoformat(),
                        }
                    },
                }
            )
        )

        cache = RunCache(cache_path=cache_file)

        result = cache.get("existing-run")

        assert result == 10

    def test_cache_handles_missing_file(self, tmp_path):
        """Should handle missing cache file gracefully."""
        cache_file = tmp_path / "nonexistent.json"
        cache = RunCache(cache_path=cache_file)

        result = cache.get("any-run")

        assert result is None

    def test_cache_handles_corrupt_json(self, tmp_path):
        """Should handle corrupt JSON file gracefully."""
        cache_file = tmp_path / "corrupt.json"
        cache_file.write_text("not valid json {{{")

        cache = RunCache(cache_path=cache_file)

        result = cache.get("any-run")

        assert result is None


class TestRunCacheSchemaVersion:
    """Tests for cache schema versioning."""

    def test_cache_includes_schema_version(self, tmp_path):
        """Saved cache should include schema_version."""
        cache_file = tmp_path / "cache.json"
        cache = RunCache(cache_path=cache_file)
        cache.set("run-1", 3, datetime.now().isoformat())
        cache.save()

        data = json.loads(cache_file.read_text())

        assert "schema_version" in data
        assert data["schema_version"] == 1

    def test_cache_ignores_old_schema_version(self, tmp_path):
        """Should ignore cache with older schema version."""
        cache_file = tmp_path / "cache.json"
        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": 0,
                    "runs": {
                        "old-run": {
                            "failure_count": 5,
                            "run_created_at": datetime.now().isoformat(),
                        }
                    },
                }
            )
        )

        cache = RunCache(cache_path=cache_file)

        result = cache.get("old-run")

        assert result is None


class TestVerifyWithCache:
    """Tests for integration of cache with verification."""

    @patch("heisenberg.playground.discover.analysis.download_and_check_failures")
    def test_verify_uses_cache_hit(self, mock_download):
        """verify_has_failures should use cached result if available."""
        from heisenberg.playground.discover.analysis import verify_has_failures_cached

        cache = RunCache()
        run_created_at = datetime.now().isoformat()
        cache.set("123", 5, run_created_at)

        result = verify_has_failures_cached("owner/repo", "123", "artifact", cache, run_created_at)

        mock_download.assert_not_called()
        assert result is True

    @patch("heisenberg.playground.discover.analysis.download_and_check_failures")
    def test_verify_downloads_on_cache_miss(self, mock_download):
        """verify_has_failures should download if not in cache."""
        from heisenberg.playground.discover.analysis import verify_has_failures_cached

        mock_download.return_value = 3

        cache = RunCache()
        run_created_at = datetime.now().isoformat()
        result = verify_has_failures_cached("owner/repo", "999", "artifact", cache, run_created_at)

        mock_download.assert_called_once()
        assert result is True

    @patch("heisenberg.playground.discover.analysis.download_and_check_failures")
    def test_verify_stores_result_in_cache(self, mock_download):
        """verify_has_failures should store result in cache after download."""
        from heisenberg.playground.discover.analysis import verify_has_failures_cached

        mock_download.return_value = 7

        cache = RunCache()
        run_created_at = datetime.now().isoformat()
        verify_has_failures_cached("owner/repo", "new-run", "artifact", cache, run_created_at)

        assert cache.get("new-run") == 7

    @patch("heisenberg.playground.discover.analysis.download_and_check_failures")
    def test_verify_caches_zero_failures(self, mock_download):
        """Should cache 0 failures (important for NO_FAILURES status)."""
        from heisenberg.playground.discover.analysis import verify_has_failures_cached

        mock_download.return_value = 0

        cache = RunCache()
        run_created_at = datetime.now().isoformat()
        result = verify_has_failures_cached(
            "owner/repo", "zero-run", "artifact", cache, run_created_at
        )

        assert result is False
        assert cache.get("zero-run") == 0


class TestRunCacheThreadSafety:
    """Tests for thread-safe RunCache with auto-save."""

    def test_cache_has_lock(self):
        """RunCache should have a threading lock (reentrant for nested calls)."""
        import threading

        cache = RunCache()

        assert hasattr(cache, "_lock")
        assert isinstance(cache._lock, type(threading.RLock()))

    def test_cache_auto_saves_on_set(self, tmp_path):
        """set() should automatically save to disk."""
        cache_file = tmp_path / "cache.json"
        cache = RunCache(cache_path=cache_file)

        cache.set("run-1", 5, datetime.now().isoformat())

        assert cache_file.exists()

        cache2 = RunCache(cache_path=cache_file)
        assert cache2.get("run-1") == 5

    def test_cache_thread_safe_concurrent_writes(self, tmp_path):
        """Multiple threads writing should not corrupt cache."""
        import threading

        cache_file = tmp_path / "cache.json"
        cache = RunCache(cache_path=cache_file)
        run_created_at = datetime.now().isoformat()

        errors = []

        def write_entry(i):
            try:
                cache.set(f"run-{i}", i, run_created_at)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_entry, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        for i in range(20):
            assert cache.get(f"run-{i}") == i

    def test_cache_get_uses_lock(self, tmp_path):
        """get() should use lock for thread-safe reads."""
        import threading

        cache_file = tmp_path / "cache.json"
        cache = RunCache(cache_path=cache_file)
        run_created_at = datetime.now().isoformat()

        for i in range(10):
            cache.set(f"run-{i}", i, run_created_at)

        errors = []
        results = []

        def read_and_write(i):
            try:
                cache.get(f"run-{i % 10}")
                cache.set(f"new-run-{i}", i, run_created_at)
                result = cache.get(f"new-run-{i}")
                results.append((i, result))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_and_write, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        for i, result in results:
            assert result == i

    def test_cache_save_uses_lock(self, tmp_path):
        """save() should use lock to prevent file corruption."""
        import threading

        cache_file = tmp_path / "cache.json"
        cache = RunCache(cache_path=cache_file)
        run_created_at = datetime.now().isoformat()

        errors = []

        def write_and_save(i):
            try:
                cache._data["runs"][f"direct-{i}"] = {
                    "failure_count": i,
                    "run_created_at": run_created_at,
                }
                cache.save()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_and_save, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        cache2 = RunCache(cache_path=cache_file)
        assert cache2._data["schema_version"] == 1


class TestRunCachePruning:
    """Tests for automatic cleanup of expired cache entries."""

    def test_cache_prunes_expired_entries_on_load(self, tmp_path):
        """Expired entries should be removed when cache is loaded."""
        cache_file = tmp_path / "cache.json"

        old_date = (datetime.now() - timedelta(days=CACHE_TTL_DAYS + 10)).isoformat()
        recent_date = datetime.now().isoformat()

        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "runs": {
                        "old-run": {"failure_count": 5, "run_created_at": old_date},
                        "recent-run": {"failure_count": 3, "run_created_at": recent_date},
                    },
                }
            )
        )

        cache = RunCache(cache_path=cache_file)

        assert "old-run" not in cache._data["runs"]
        assert "recent-run" in cache._data["runs"]

    def test_cache_prunes_corrupt_entries(self, tmp_path):
        """Entries with invalid dates should be pruned."""
        cache_file = tmp_path / "cache.json"

        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "runs": {
                        "corrupt-run": {"failure_count": 5, "run_created_at": "not-a-date"},
                        "missing-date-run": {"failure_count": 3},
                        "valid-run": {
                            "failure_count": 1,
                            "run_created_at": datetime.now().isoformat(),
                        },
                    },
                }
            )
        )

        cache = RunCache(cache_path=cache_file)

        assert "corrupt-run" not in cache._data["runs"]
        assert "missing-date-run" not in cache._data["runs"]
        assert "valid-run" in cache._data["runs"]

    def test_cache_saves_after_pruning(self, tmp_path):
        """Cache should save to disk after pruning expired entries."""
        cache_file = tmp_path / "cache.json"

        old_date = (datetime.now() - timedelta(days=CACHE_TTL_DAYS + 10)).isoformat()
        recent_date = datetime.now().isoformat()

        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "runs": {
                        "old-run": {"failure_count": 5, "run_created_at": old_date},
                        "recent-run": {"failure_count": 3, "run_created_at": recent_date},
                    },
                }
            )
        )

        RunCache(cache_path=cache_file)

        data = json.loads(cache_file.read_text())
        assert "old-run" not in data["runs"]
        assert "recent-run" in data["runs"]

    def test_cache_no_save_if_nothing_pruned(self, tmp_path):
        """Cache should not save if no entries were pruned."""
        import time

        cache_file = tmp_path / "cache.json"
        recent_date = datetime.now().isoformat()

        original_content = json.dumps(
            {
                "schema_version": 1,
                "runs": {
                    "run-1": {"failure_count": 5, "run_created_at": recent_date},
                },
            }
        )
        cache_file.write_text(original_content)
        original_mtime = cache_file.stat().st_mtime

        time.sleep(0.01)

        RunCache(cache_path=cache_file)

        assert cache_file.stat().st_mtime == original_mtime


class TestDefaultCachePath:
    """Tests for XDG-compliant default cache path."""

    def test_default_cache_path_is_absolute(self):
        """DEFAULT_CACHE_PATH should be an absolute path in user's home."""
        path = get_default_cache_path()

        assert path.is_absolute()

    def test_default_cache_path_in_user_cache_dir(self):
        """Default cache should be in ~/.cache/heisenberg/."""
        from pathlib import Path

        path = get_default_cache_path()

        assert str(Path.home()) in str(path)
        assert "heisenberg" in str(path)

    def test_default_cache_path_filename(self):
        """Default cache filename should be verified_runs.json."""
        path = get_default_cache_path()

        assert path.name == "verified_runs.json"
