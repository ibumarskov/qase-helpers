import pytest

from qase_helper.config import DEFAULT_LOG_LEVEL, DEFAULT_MAX_LENGTH, DEFAULT_RUN_TITLE, load_settings
from qase_helper.errors import ConfigError


def test_defaults_without_config_file():
    settings = load_settings()
    assert settings.log_level == DEFAULT_LOG_LEVEL
    assert settings.log_file is None
    assert settings.max_length == DEFAULT_MAX_LENGTH
    assert settings.run_title == DEFAULT_RUN_TITLE
    assert settings.complete_run is True
    assert settings.qase_project is None


def test_missing_explicit_config_file_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_settings(config_file=str(tmp_path / "missing.yaml"))


def test_default_config_file_in_cwd_is_loaded(tmp_path):
    (tmp_path / "qase-helper.yaml").write_text("qase:\n  project: AUTO\n")
    assert load_settings().qase_project == "AUTO"


def test_yaml_file_is_loaded(tmp_path):
    config = tmp_path / "custom.yaml"
    config.write_text(
        "qase:\n  project: FROMYAML\n"
        "junit:\n  max_length: 100\n  case_id_map_file: m.yaml\n  exclude_skipped: true\n"
        "report:\n  run_title: YAML title\n  complete_run: false\n"
        "cases:\n  suite: Smoke\n"
        "logging:\n  level: INFO\n"
    )
    settings = load_settings(config_file=str(config))
    assert settings.qase_project == "FROMYAML"
    assert settings.run_title == "YAML title"
    assert settings.max_length == 100
    assert settings.complete_run is False
    assert settings.case_id_map_file == "m.yaml"
    assert settings.exclude_skipped is True
    assert settings.suite == "Smoke"
    assert settings.log_level == "INFO"


def test_example_config_is_valid():
    from pathlib import Path

    example = Path(__file__).resolve().parent.parent / "qase-helper.example.yaml"
    settings = load_settings(config_file=str(example))
    assert settings.qase_project == "DEMO"


@pytest.mark.parametrize(
    "content, message",
    [
        ("qase: [1, 2]\n", "must be a mapping"),
        ("unknown:\n  a: 1\n", "Unknown section"),
        ("report:\n  run_titel: typo\n", "Unknown key"),
        ("qase: {project: [\n", "Invalid YAML"),
        ("junit:\n  max_length: 0\n", "Invalid configuration"),
        ("junit:\n  max_length: 256\n", "Invalid configuration"),
        ("report:\n  max_length: 100\n", "Unknown key"),
    ],
)
def test_invalid_yaml_config(tmp_path, content, message):
    config = tmp_path / "bad.yaml"
    config.write_text(content)
    with pytest.raises(ConfigError, match=message):
        load_settings(config_file=str(config))


def test_env_overrides_yaml(monkeypatch, tmp_path):
    config = tmp_path / "c.yaml"
    config.write_text("qase:\n  project: FROMYAML\n")
    monkeypatch.setenv("QASE_HELPER_PROJECT", "FROMENV")
    assert load_settings(config_file=str(config)).qase_project == "FROMENV"


def test_cli_overrides_env_and_yaml(monkeypatch, tmp_path):
    config = tmp_path / "c.yaml"
    config.write_text("qase:\n  project: FROMYAML\n")
    monkeypatch.setenv("QASE_HELPER_PROJECT", "FROMENV")
    assert load_settings(config_file=str(config), qase_project="FROMCLI").qase_project == "FROMCLI"


def test_none_cli_values_do_not_shadow_env(monkeypatch):
    monkeypatch.setenv("QASE_HELPER_PROJECT", "FROMENV")
    assert load_settings(qase_project=None).qase_project == "FROMENV"


@pytest.mark.parametrize("env_name", ["QASE_HELPER_TOKEN", "QASE_TOKEN"])
def test_token_env_vars(monkeypatch, env_name):
    monkeypatch.setenv(env_name, "secret")
    assert load_settings().qase_token == "secret"


def test_prefixed_env_vars(monkeypatch):
    monkeypatch.setenv("QASE_HELPER_CASE_ID_MAP", "/path/cases.yaml")
    monkeypatch.setenv("QASE_HELPER_MAX_LENGTH", "120")
    monkeypatch.setenv("QASE_HELPER_COMPLETE_RUN", "false")
    settings = load_settings()
    assert settings.case_id_map_file == "/path/cases.yaml"
    assert settings.max_length == 120
    assert settings.complete_run is False


def test_require_credentials():
    with pytest.raises(ConfigError, match="token"):
        load_settings(qase_project="DEMO").require_credentials()
    with pytest.raises(ConfigError, match="project"):
        load_settings(qase_token="t").require_credentials()
    load_settings(qase_token="t", qase_project="DEMO").require_credentials()


def test_run_url_defaults_to_qase_saas():
    settings = load_settings(qase_project="DEMO")
    assert settings.run_url(123) == "https://app.qase.io/run/DEMO/dashboard/123"


def test_run_url_uses_app_url(monkeypatch):
    monkeypatch.setenv("QASE_HELPER_APP_URL", "https://qase.example.com/")
    settings = load_settings(qase_project="DEMO", api_host="https://api-qase.example.com/v1")
    assert settings.run_url(5) == "https://qase.example.com/run/DEMO/dashboard/5"


def test_run_url_unknown_for_custom_api_host_without_app_url():
    assert load_settings(qase_project="DEMO", api_host="https://api-qase.example.com/v1").run_url(5) is None


def test_app_url_from_yaml(tmp_path):
    config = tmp_path / "c.yaml"
    config.write_text("qase:\n  project: P\n  app_url: https://ui.example.com\n")
    assert load_settings(config_file=str(config)).run_url(1) == "https://ui.example.com/run/P/dashboard/1"
