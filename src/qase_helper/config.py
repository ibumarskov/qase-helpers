"""Layered configuration: CLI options > environment variables > YAML config file > defaults.

The YAML config file (default ``./qase-helper.yaml``, override with
``--config`` / ``QASE_HELPER_CONFIG``) uses a nested schema, see
``qase-helper.example.yaml``::

    qase:
      token: null
      project: "DEMO"
      api_host: null
    report:
      run_title: "Automated run"
      run_id: null
      milestone: null
      environment: null
      plan: null
      case_id_map_file: null
      max_length: 255
      complete_run: true
    logging:
      level: "WARNING"
      file: null

A missing default config file is not an error; an explicitly passed path
that does not exist is.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import AliasChoices, Field, ValidationError
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from qase_helper.errors import ConfigError

ENV_PREFIX = "QASE_HELPER_"
CONFIG_ENV_VAR = f"{ENV_PREFIX}CONFIG"
DEFAULT_CONFIG_FILE = "qase-helper.yaml"
DEFAULT_RUN_TITLE = "Automated run"
DEFAULT_LOG_LEVEL = "WARNING"
# Qase limits test case titles to 255 characters.
DEFAULT_MAX_LENGTH = 255

# YAML section -> {yaml key: Settings field}
_YAML_SCHEMA: dict[str, dict[str, str]] = {
    "qase": {"token": "qase_token", "project": "qase_project", "api_host": "api_host"},
    "report": {
        "run_title": "run_title",
        "run_id": "run_id",
        "milestone": "milestone",
        "environment": "environment",
        "plan": "plan",
        "case_id_map_file": "case_id_map_file",
        "max_length": "max_length",
        "complete_run": "complete_run",
    },
    "logging": {"level": "log_level", "file": "log_file"},
}


class _YamlConfigSource(PydanticBaseSettingsSource):
    """Reads the nested YAML config file into flat Settings fields."""

    def __init__(self, settings_cls, yaml_path: str | Path | None):
        super().__init__(settings_cls)
        self._data = load_yaml_config(yaml_path) if yaml_path else {}

    def get_field_value(self, field, field_name: str) -> tuple[Any, str, bool]:
        return self._data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return dict(self._data)


def load_yaml_config(path: str | Path) -> dict[str, Any]:
    """Load the nested YAML config file and flatten it into Settings field names."""
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except OSError as exc:
        raise ConfigError(f"Cannot read config file {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in config file {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Config file {path} must contain a mapping at the top level.")

    unknown_sections = set(raw) - set(_YAML_SCHEMA)
    if unknown_sections:
        raise ConfigError(f"Unknown section(s) in config file {path}: {', '.join(sorted(unknown_sections))}")

    flat: dict[str, Any] = {}
    for section, keys in _YAML_SCHEMA.items():
        values = raw.get(section) or {}
        if not isinstance(values, dict):
            raise ConfigError(f"Section '{section}' in config file {path} must be a mapping.")
        unknown_keys = set(values) - set(keys)
        if unknown_keys:
            raise ConfigError(
                f"Unknown key(s) in section '{section}' of config file {path}: {', '.join(sorted(unknown_keys))}"
            )
        for yaml_key, field_name in keys.items():
            if values.get(yaml_key) is not None:
                flat[field_name] = values[yaml_key]
    return flat


class Settings(BaseSettings):
    """Resolved qase-helper configuration."""

    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, extra="ignore")

    qase_token: str | None = Field(
        default=None, validation_alias=AliasChoices(f"{ENV_PREFIX}TOKEN", "QASE_TOKEN", "qase_token")
    )
    qase_project: str | None = Field(
        default=None, validation_alias=AliasChoices(f"{ENV_PREFIX}PROJECT", "qase_project")
    )
    api_host: str | None = None

    run_title: str = DEFAULT_RUN_TITLE
    run_id: int | None = None
    milestone: str | None = None
    environment: str | None = None
    plan: str | None = None
    case_id_map_file: str | None = Field(
        default=None, validation_alias=AliasChoices(f"{ENV_PREFIX}CASE_ID_MAP", "case_id_map_file")
    )
    max_length: int = Field(default=DEFAULT_MAX_LENGTH, gt=0)
    complete_run: bool = True

    log_level: str = DEFAULT_LOG_LEVEL
    log_file: str | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        yaml_path = init_settings.init_kwargs.pop("_yaml_config_file", None)
        return (init_settings, env_settings, _YamlConfigSource(settings_cls, yaml_path))

    def require_credentials(self) -> None:
        """Raise ConfigError unless both the API token and the project code are set."""
        if not self.qase_token:
            raise ConfigError(f"Qase API token is required (--token, {ENV_PREFIX}TOKEN / QASE_TOKEN, or config file).")
        if not self.qase_project:
            raise ConfigError(f"Qase project code is required (--project, {ENV_PREFIX}PROJECT, or config file).")


def resolve_config_file(config_file: str | None) -> str | None:
    """Return the config file to load: an explicit path must exist, the default one is optional."""
    if config_file:
        if not Path(config_file).is_file():
            raise ConfigError(f"Config file not found: {config_file}")
        return config_file
    return DEFAULT_CONFIG_FILE if Path(DEFAULT_CONFIG_FILE).is_file() else None


def load_settings(config_file: str | None = None, **cli_overrides: Any) -> Settings:
    """Build Settings with precedence CLI > env > YAML file > defaults.

    ``None`` values in ``cli_overrides`` are ignored so that options the user
    did not pass do not shadow env/YAML values.
    """
    overrides = {key: value for key, value in cli_overrides.items() if value is not None}
    overrides["_yaml_config_file"] = resolve_config_file(config_file)
    try:
        return Settings(**overrides)
    except ValidationError as exc:
        raise ConfigError(f"Invalid configuration:\n{exc}") from exc
