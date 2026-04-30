import os
import subprocess
import sys
from pathlib import Path

from tests.integration_database import create_reachable_engine_or_skip, get_integration_database_url


API_ROOT = Path(__file__).resolve().parents[1]


def run_alembic_command(*args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["CONSTRUCTION_DATABASE_URL"] = get_integration_database_url()
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


def assert_alembic_success(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stdout + result.stderr


async def test_alembic_upgrade_downgrade_upgrade_smoke() -> None:
    engine = await create_reachable_engine_or_skip()
    await engine.dispose()

    assert_alembic_success(run_alembic_command("upgrade", "head"))
    assert_alembic_success(run_alembic_command("downgrade", "-1"))
    assert_alembic_success(run_alembic_command("upgrade", "head"))

    current_result = run_alembic_command("current")

    assert_alembic_success(current_result)
    assert "20260430_0005" in current_result.stdout