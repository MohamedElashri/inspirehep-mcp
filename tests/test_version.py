"""Tests for package version metadata."""

from importlib.metadata import version as installed_version

from inspirehep_mcp import __version__


def test_runtime_version_comes_from_package_metadata():
    assert __version__ == installed_version("inspirehep-mcp")
