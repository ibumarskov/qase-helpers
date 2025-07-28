import os

# Qase Helper (QHLP)
QHLP_LOG_FILE = os.environ.get("QHLP_LOG_FILE", os.path.join(os.getcwd(), 'qase-helper.log'))
QHLP_LOG_LEVEL = os.environ.get("QHLP_LOG_LEVEL", "DEBUG")
QHLP_MAX_LENGTH = os.environ.get("QHLP_MAX_LENGTH", 255)
QHLP_EXCEPT_TAGS = os.environ.get("QHLP_EXCEPT_TAGS", {"[IPv6]", "[IPv4]"})
