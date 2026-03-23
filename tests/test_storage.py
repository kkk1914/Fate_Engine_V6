"""Tests for core/storage.py — storage backend abstraction.

Phase 1.7: Tests LocalStorage operations (save, get, exists).
"""
import pytest
import os
import tempfile
from core.storage import LocalStorage


class TestLocalStorage:
    """LocalStorage filesystem operations."""

    def test_save_and_get(self, tmp_path):
        storage = LocalStorage(base_dir=str(tmp_path))
        path = storage.save_report("test_report.md", "# Test Report\nContent here.")
        assert os.path.exists(path)

        content = storage.get_report("test_report.md")
        assert content == "# Test Report\nContent here."

    def test_exists(self, tmp_path):
        storage = LocalStorage(base_dir=str(tmp_path))
        assert not storage.exists("nonexistent.md")

        storage.save_report("exists.md", "content")
        assert storage.exists("exists.md")

    def test_save_creates_dirs(self, tmp_path):
        storage = LocalStorage(base_dir=str(tmp_path / "deep" / "nested"))
        path = storage.save_report("report.md", "content")
        assert os.path.exists(path)

    def test_subdir(self, tmp_path):
        storage = LocalStorage(base_dir=str(tmp_path))
        path = storage.save_report("report.md", "content", subdir="2024")
        assert "2024" in path
        assert storage.exists("report.md", subdir="2024")

    def test_unicode_content(self, tmp_path):
        storage = LocalStorage(base_dir=str(tmp_path))
        content = "# ဗေဒင် အစီရင်ခံစာ\nMyanmar content: ကောင်းကင်"
        storage.save_report("burmese.md", content)
        retrieved = storage.get_report("burmese.md")
        assert retrieved == content

    def test_overwrite(self, tmp_path):
        storage = LocalStorage(base_dir=str(tmp_path))
        storage.save_report("report.md", "version 1")
        storage.save_report("report.md", "version 2")
        assert storage.get_report("report.md") == "version 2"
