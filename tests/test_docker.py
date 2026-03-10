"""Tests for Docker image build and runtime. Skipped when Docker is unavailable."""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
IMAGE_NAME = "leafpress:test"


def _docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(not _docker_available(), reason="Docker not available"),
]


@pytest.fixture(scope="module")
def docker_image():
    """Build the Docker image once per test module."""
    result = subprocess.run(
        ["docker", "build", "-t", IMAGE_NAME, "."],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=300,
    )
    assert result.returncode == 0, f"Docker build failed:\n{result.stderr}"
    yield IMAGE_NAME
    subprocess.run(["docker", "rmi", IMAGE_NAME], capture_output=True)


def _docker_run(
    *args: str, image: str = IMAGE_NAME, name: str | None = None, **kwargs
) -> subprocess.CompletedProcess:
    cmd = ["docker", "run", "--rm"]
    if name:
        cmd += ["--name", name]
    cmd += [*args, image, *kwargs.get("entrypoint_args", [])]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def test_docker_build(docker_image):
    """Image builds successfully."""
    result = subprocess.run(
        ["docker", "image", "inspect", docker_image],
        capture_output=True,
    )
    assert result.returncode == 0


def test_docker_version(docker_image):
    """Container prints version."""
    result = _docker_run(entrypoint_args=["--version"], image=docker_image, name="leafpress-version")
    assert result.returncode == 0
    assert "leafpress version" in result.stdout


def test_docker_help(docker_image):
    """Default CMD shows help with all commands."""
    result = _docker_run(image=docker_image, name="leafpress-help")
    assert result.returncode == 0
    for cmd in ("convert", "init", "info", "ui"):
        assert cmd in result.stdout


def test_docker_convert_pdf(docker_image, tmp_path):
    """Convert test fixtures to PDF inside the container."""
    fixtures = REPO_ROOT / "tests" / "fixtures" / "sample_mkdocs_project"
    output = tmp_path / "output"
    output.mkdir()

    result = subprocess.run(
        [
            "docker", "run", "--rm",
            "--name", "leafpress-convert-pdf",
            "-v", f"{fixtures}:/work:ro",
            "-v", f"{output}:/out",
            docker_image,
            "convert", "/work", "-f", "pdf", "-o", "/out",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"Convert failed:\n{result.stderr}"
    pdf_files = list(output.glob("*.pdf"))
    assert len(pdf_files) >= 1, f"No PDF generated. Output dir: {list(output.iterdir())}"


def test_docker_convert_env_vars(docker_image, tmp_path):
    """LEAFPRESS_* environment variables are passed through."""
    fixtures = REPO_ROOT / "tests" / "fixtures" / "sample_mkdocs_project"
    output = tmp_path / "output"
    output.mkdir()

    result = subprocess.run(
        [
            "docker", "run", "--rm",
            "--name", "leafpress-convert-env",
            "-e", "LEAFPRESS_COMPANY_NAME=TestCorp",
            "-e", "LEAFPRESS_PROJECT_NAME=TestProject",
            "-v", f"{fixtures}:/work:ro",
            "-v", f"{output}:/out",
            docker_image,
            "convert", "/work", "-f", "pdf", "-o", "/out",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"Convert failed:\n{result.stderr}"
    pdf_files = list(output.glob("*.pdf"))
    assert len(pdf_files) >= 1
