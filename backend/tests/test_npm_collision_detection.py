"""Tests for the npm/pnpm node_modules collision detection heuristic.

The heuristic used in AutoScape.bat:
  - npm-created node_modules: .package-lock.json present, .modules.yaml absent → needs removal
  - pnpm-created node_modules: .modules.yaml present → ok
  - no node_modules directory at all → ok
"""

import pathlib


def needs_npm_removal(frontend_dir: pathlib.Path) -> bool:
    """Return True if frontend/node_modules looks npm-created and must be removed.

    Mirrors the bat heuristic:
      if .package-lock.json exists AND .modules.yaml does NOT exist → True
    """
    node_modules = frontend_dir / "node_modules"
    package_lock = node_modules / ".package-lock.json"
    modules_yaml = node_modules / ".modules.yaml"
    return package_lock.exists() and not modules_yaml.exists()


def test_npm_style_needs_removal(tmp_path: pathlib.Path) -> None:
    """npm-created layout: .package-lock.json present, .modules.yaml absent."""
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / ".package-lock.json").write_text("{}")
    assert needs_npm_removal(tmp_path) is True


def test_pnpm_style_is_ok(tmp_path: pathlib.Path) -> None:
    """pnpm-created layout: .modules.yaml present → no removal needed."""
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / ".modules.yaml").write_text("lockfileVersion: '6.0'\n")
    (node_modules / ".package-lock.json").write_text("{}")
    assert needs_npm_removal(tmp_path) is False


def test_no_node_modules_is_ok(tmp_path: pathlib.Path) -> None:
    """No node_modules directory at all → no removal needed."""
    assert needs_npm_removal(tmp_path) is False
