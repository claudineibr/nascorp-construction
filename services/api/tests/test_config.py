from pathlib import Path

from app.core.config import API_ROOT, CONSTRUCTION_ROOT, ENV_FILE_PATHS, EXTERNAL_ROOT, Settings, WORKSPACE_ROOT


def test_env_file_paths_are_absolute_and_derived_from_config_file() -> None:
    assert ENV_FILE_PATHS == (
        API_ROOT / ".env",
        CONSTRUCTION_ROOT / ".env",
        EXTERNAL_ROOT / ".env",
        WORKSPACE_ROOT / ".env",
    )
    assert all(path.is_absolute() for path in ENV_FILE_PATHS)


def test_settings_env_files_do_not_depend_on_current_working_directory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    settings = Settings()

    assert settings.model_config["env_file"] == ENV_FILE_PATHS


def test_settings_parse_comma_separated_cors_origins() -> None:
    settings = Settings(cors_allowed_origins="http://127.0.0.1:8001, http://localhost:8002")

    assert settings.cors_allowed_origins == ["http://127.0.0.1:8001", "http://localhost:8002"]