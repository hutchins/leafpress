"""Detect package version from common manifest files."""

from __future__ import annotations

import json
from pathlib import Path

_VCS_MARKERS = frozenset({".git", ".svn"})


def _candidate_dirs(start: Path) -> list[Path]:
    """Walk up from start, stopping at a VCS root (.git / .svn) or filesystem root."""
    dirs: list[Path] = []
    current = start.resolve()
    while True:
        dirs.append(current)
        if any((current / marker).exists() for marker in _VCS_MARKERS):
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    return dirs


def detect_package_version(project_dir: Path) -> str | None:
    """Return the package version from the first recognised manifest file.

    Searches project_dir and its parents up to the VCS root (.git or .svn).

    Manifest priority (checked in each directory before moving up):
      1. pyproject.toml  — [project] version  or  [tool.poetry] version
      2. Cargo.toml      — [package] version
      3. package.json    — .version
      4. pom.xml         — <version> (Maven)
      5. composer.json   — .version (PHP)
      6. pubspec.yaml    — version: (Dart/Flutter)
      7. *.csproj        — <Version> (.NET)

    Returns None if no manifest is found or none contains a version.
    """
    fns = (
        _from_pyproject,
        _from_cargo,
        _from_package_json,
        _from_pom_xml,
        _from_composer_json,
        _from_pubspec_yaml,
        _from_csproj,
    )
    for directory in _candidate_dirs(project_dir):
        for fn in fns:
            ver = fn(directory)
            if ver:
                return ver
    return None


def _load_toml(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            return None
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _from_pyproject(project_dir: Path) -> str | None:
    data = _load_toml(project_dir / "pyproject.toml")
    if data is None:
        return None
    ver = data.get("project", {}).get("version")
    if ver:
        return str(ver)
    ver = data.get("tool", {}).get("poetry", {}).get("version")
    return str(ver) if ver else None


def _from_cargo(project_dir: Path) -> str | None:
    data = _load_toml(project_dir / "Cargo.toml")
    if data is None:
        return None
    ver = data.get("package", {}).get("version")
    return str(ver) if ver else None


def _from_package_json(project_dir: Path) -> str | None:
    path = project_dir / "package.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ver = data.get("version")
        return str(ver) if ver else None
    except Exception:
        return None


def _from_pom_xml(project_dir: Path) -> str | None:
    path = project_dir / "pom.xml"
    if not path.exists():
        return None
    try:
        import xml.etree.ElementTree as ET

        tree = ET.parse(path)
        root = tree.getroot()
        # pom.xml uses a default namespace
        ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
        prefix = f"{{{ns}}}" if ns else ""
        ver_el = root.find(f"{prefix}version")
        if ver_el is not None and ver_el.text:
            return ver_el.text.strip()
    except Exception:
        pass
    return None


def _from_composer_json(project_dir: Path) -> str | None:
    path = project_dir / "composer.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ver = data.get("version")
        return str(ver) if ver else None
    except Exception:
        return None


def _from_pubspec_yaml(project_dir: Path) -> str | None:
    path = project_dir / "pubspec.yaml"
    if not path.exists():
        return None
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            ver = data.get("version")
            return str(ver) if ver else None
    except Exception:
        pass
    return None


def _from_csproj(project_dir: Path) -> str | None:
    csproj_files = sorted(project_dir.glob("*.csproj"))
    if not csproj_files:
        return None
    try:
        import xml.etree.ElementTree as ET

        tree = ET.parse(csproj_files[0])
        root = tree.getroot()
        for tag in ("Version", "VersionPrefix"):
            el = root.find(f"./PropertyGroup/{tag}")
            if el is not None and el.text:
                return el.text.strip()
    except Exception:
        pass
    return None
