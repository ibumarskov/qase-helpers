"""qase-helper: report JUnit test results to Qase and manage Qase test runs."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("qase-helper")
except PackageNotFoundError:  # running from a source tree without installation
    __version__ = "0.0.0+unknown"
