from __future__ import annotations

from pathlib import Path

import pytest
from forge.tools.builtins.filesystem import list_directory, read_file, search_files, write_file

ALLOWED_BASE = Path("/tmp/forge-test-fs")


@pytest.fixture(autouse=True)
def setup_fs(monkeypatch):
    monkeypatch.setattr("forge.tools.builtins.filesystem._ALLOWED_BASE", ALLOWED_BASE)
    ALLOWED_BASE.mkdir(parents=True, exist_ok=True)
    yield
    import shutil
    shutil.rmtree(ALLOWED_BASE, ignore_errors=True)


def test_write_and_read_file():
    result = write_file("hello.txt", "Hello, Forge!")
    assert "written" in result

    content = read_file("hello.txt")
    assert content == "Hello, Forge!"


def test_read_nonexistent_file():
    result = read_file("nonexistent.txt")
    assert "not found" in result


def test_write_nested_directories():
    result = write_file("nested/deep/file.txt", "deep content")
    assert "written" in result

    content = read_file("nested/deep/file.txt")
    assert content == "deep content"


def test_list_directory():
    (ALLOWED_BASE / "alpha.txt").write_text("alpha")
    (ALLOWED_BASE / "beta.txt").write_text("beta")
    (ALLOWED_BASE / "subdir").mkdir()
    (ALLOWED_BASE / "subdir" / "gamma.txt").write_text("gamma")

    result = list_directory("")
    assert "alpha.txt" in result
    assert "beta.txt" in result
    assert "subdir/" in result


def test_search_files():
    (ALLOWED_BASE / "main.py").write_text("code")
    (ALLOWED_BASE / "sub").mkdir(parents=True)
    (ALLOWED_BASE / "sub" / "helper.py").write_text("helper code")
    (ALLOWED_BASE / "data.json").write_text("{}")

    result = search_files("*.py")
    assert "main.py" in result
    assert "helper.py" in result
    assert "data.json" not in result


def test_access_denied_outside_allowed():
    result = read_file("/etc/passwd")
    assert "Access denied" in result

    result = list_directory("/etc")
    assert "Access denied" in result

    result = write_file("/etc/evil.txt", "bad")
    assert "Access denied" in result
