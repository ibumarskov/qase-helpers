import pytest

JUNIT_TEMPLATE = """<?xml version="1.0" ?>
<testsuites><testsuite name="suite">
{cases}
</testsuite></testsuites>
"""


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch, tmp_path):
    """Run every test in an empty cwd with no qase-helper env vars set."""
    import os

    for name in list(os.environ):
        if name.startswith("QASE_HELPER_") or name == "QASE_TOKEN":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def write_junit(tmp_path):
    def _write(cases_xml: str, name: str = "report.xml"):
        path = tmp_path / name
        path.write_text(JUNIT_TEMPLATE.format(cases=cases_xml))
        return path

    return _write
