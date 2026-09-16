# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import List, Optional


@dataclass
class PackageStatus:
    """Status of an installed package versus a required version.

    Attributes:
        package: Package name.
        required: Required version (from requirements file).
        installed: Installed version, or None if the package is not installed.
    """

    package: str
    required: str
    installed: Optional[str]


def _parse_requirements(requirements_path: Path) -> List[tuple[str, str]]:
    """Parse a requirements file for pinned ``package==version`` entries.

    Only lines containing ``"=="`` are considered; comments and blank lines
    are ignored.

    Args:
        requirements_path: Path to a requirements.txt-style file.

    Returns:
        List of (package, version) tuples extracted from the file.
    """
    requirements: List[tuple[str, str]] = []
    for raw_line in requirements_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        package, version = line.split("==", 1)
        requirements.append((package.strip(), version.strip()))
    return requirements


def get_package_mismatches(requirements_path: Path) -> List[PackageStatus]:
    """Detect packages whose installed versions differ from requirements.

    For each pinned requirement in the given file, this function compares the
    installed version (if any) to the required version and records any
    mismatches.

    Args:
        requirements_path: Path to a requirements file with pinned versions.

    Returns:
        List of PackageStatus objects for packages that are missing or have a
        different version than required.
    """
    mismatches: List[PackageStatus] = []
    for package, required_version in _parse_requirements(requirements_path):
        try:
            installed_version = metadata.version(package)
        except metadata.PackageNotFoundError:
            installed_version = None
        if installed_version != required_version:
            mismatches.append(
                PackageStatus(
                    package=package,
                    required=required_version,
                    installed=installed_version,
                )
            )
    return mismatches


def build_update_commands(requirements_path: Path, mismatches: List[PackageStatus]) -> str:
    """Build shell commands to update mismatched packages.

    The generated commands:

    1. Upgrade pip.
    2. Force-reinstall the mismatched packages at their required versions.
    3. Install all packages from the requirements file to ensure consistency.

    Args:
        requirements_path: Path to the requirements file.
        mismatches: List of PackageStatus entries from
            :func:`get_package_mismatches`.

    Returns:
        A newline-separated string of shell commands. Returns an empty string
        if there are no mismatches.
    """
    if not mismatches:
        return ""
    package_specs = " ".join(f"{item.package}=={item.required}" for item in mismatches)
    return "\n".join(
        [
            "python -m pip install --upgrade pip",
            f"python -m pip install --upgrade --force-reinstall {package_specs}",
            f"python -m pip install -r \"{requirements_path}\"",
        ]
    )
