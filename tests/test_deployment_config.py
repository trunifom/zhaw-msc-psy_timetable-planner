"""
Tests for this repo's deployment configuration files (requirements.txt,
environment.yaml) - not application code, but config that's just as
capable of silently breaking a real deployment as a code bug is.

Why this file exists: while investigating a live report of "changes
pushed to GitHub don't show up on Streamlit Community Cloud", direct
verification confirmed GitHub itself was fully up to date (`git
ls-remote origin` showed the pushed commit as the true remote HEAD) -
ruling out a git/push problem entirely. That leaves the deployment
pipeline between GitHub and the running app. Streamlit Community Cloud
builds a plain `pip install -r requirements.txt` environment (it only
picks up a conda spec if one is named exactly `environment.yml` at the
repo root - this repo's is named `environment.yaml`, a valid YAML
extension but NOT the exact name Community Cloud looks for, so in
practice requirements.txt is authoritative for what actually gets
installed on Cloud, regardless of what's tested locally via
environment.yaml/conda). If that fresh pip install resolves a dependency
version never actually exercised locally, the Cloud build can fail (or
succeed but crash at runtime) in ways this repo's own test suite - which
always runs inside the already-working, hand-curated `zhaw_planner_env`
conda environment - structurally cannot catch.

This was not hypothetical: requirements.txt was found to be missing the
numpy<2.0 pin that environment.yaml carries (with its own comment
explaining exactly why: numpy 2.x breaks the pandas/Streamlit C-API
compatibility this app relies on). git history confirms requirements.txt
had that same pin once (commit 68aa17d) and lost it in a later cleanup
(commit 1abc45c), months before this session - so a from-scratch Cloud
build (e.g. one triggered by any dependency-affecting change, or a fresh
"Reboot app") could have silently resolved an incompatible numpy that
was never present in the environment these tests normally run against.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS_PATH = REPO_ROOT / "requirements.txt"
ENVIRONMENT_YAML_PATH = REPO_ROOT / "environment.yaml"


def _parse_requirements_txt() -> dict[str, str]:
    """Very small parser: '<package><version-spec>' per non-comment line
    -> {package_name: version_spec_or_"" }. Good enough for this repo's
    simple, single-constraint-per-line requirements.txt; not a general
    requirements-file parser."""
    packages: dict[str, str] = {}
    for raw_line in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.match(r"^([A-Za-z0-9_.\-]+)\s*(.*)$", line)
        if match:
            packages[match.group(1).lower()] = match.group(2).strip()
    return packages


def _parse_environment_yaml_pip_and_conda_deps() -> dict[str, str]:
    """
    Even smaller parser, specific to this repo's environment.yaml shape
    (a flat `dependencies:` list, with a nested `- pip:` sub-list for
    pip-only packages) - not a general conda-environment-file parser.
    Strips inline comments and the conda channel-pin syntax this file
    doesn't use, and lower-cases package names for case-insensitive
    comparison against requirements.txt.
    """
    packages: dict[str, str] = {}
    for raw_line in ENVIRONMENT_YAML_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line.startswith("- ") or line in ("- pip:",):
            continue
        entry = line[2:].strip()
        match = re.match(r"^([A-Za-z0-9_.\-]+)\s*(.*)$", entry)
        if match:
            packages[match.group(1).lower()] = match.group(2).strip()
    return packages


def test_requirements_and_environment_files_exist():
    assert REQUIREMENTS_PATH.exists()
    assert ENVIRONMENT_YAML_PATH.exists()


def test_requirements_txt_pins_numpy_below_2():
    """
    The specific, concrete regression this file exists to prevent - see
    the module docstring for the full incident. A from-scratch `pip
    install -r requirements.txt` (what Streamlit Community Cloud actually
    runs) must never be able to resolve numpy>=2.0.
    """
    requirements = _parse_requirements_txt()
    assert "numpy" in requirements, (
        "requirements.txt has no numpy entry at all - a fresh install could resolve "
        "any numpy version, including 2.x, which environment.yaml's own comment warns "
        "breaks pandas/Streamlit C-API compatibility."
    )
    spec = requirements["numpy"]
    assert "<2" in spec.replace(" ", ""), (
        f"requirements.txt's numpy constraint is {spec!r}, which doesn't clearly forbid "
        "numpy 2.x - see environment.yaml's numpy line for the pin this should match."
    )


def test_requirements_txt_and_environment_yaml_agree_on_shared_packages():
    """
    Softer, general-purpose companion to the numpy-specific test above:
    for every package listed in *both* files, their version constraints
    should say the same thing. A mismatch here means "works locally"
    (tested against environment.yaml's conda env) and "works on Cloud"
    (built from requirements.txt's pip spec) are quietly no longer
    testing the same set of dependency versions - exactly the class of
    drift that let the numpy pin disappear from one file but not the
    other in the first place.
    """
    requirements = _parse_requirements_txt()
    conda_env = _parse_environment_yaml_pip_and_conda_deps()

    shared_packages = set(requirements) & set(conda_env)
    assert "pandas" in shared_packages  # sanity check: both files do list overlapping packages

    mismatches = {
        pkg: (requirements[pkg], conda_env[pkg])
        for pkg in shared_packages
        if requirements[pkg] != conda_env[pkg]
    }
    assert not mismatches, (
        f"requirements.txt and environment.yaml disagree on version constraints for "
        f"{len(mismatches)} shared package(s) - (requirements.txt, environment.yaml): {mismatches}"
    )


def test_no_stray_runtime_or_python_version_file_conflicts_with_environment_yaml():
    """
    environment.yaml pins Python 3.11. Streamlit Community Cloud reads a
    `runtime.txt` (content like "python-3.11") to choose its Python
    version if present, and otherwise falls back to a platform default
    that may not match 3.11 at all. This repo has no runtime.txt (a
    deliberate choice at the time of writing, not verified here - this
    test only guards against the file *existing* with a value that
    silently contradicts environment.yaml's 3.11 pin, which would be
    worse than having no opinion at all).
    """
    runtime_txt = REPO_ROOT / "runtime.txt"
    if not runtime_txt.exists():
        return
    content = runtime_txt.read_text(encoding="utf-8").strip()
    assert "3.11" in content, (
        f"runtime.txt exists with {content!r}, which doesn't match environment.yaml's "
        "python=3.11 pin - Streamlit Cloud would build against a different Python "
        "version than this project is actually developed/tested against."
    )
