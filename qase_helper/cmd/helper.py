import argparse
import logging
import sys

from qase_helper.lib.config import Config
from qase_helper.lib.process_junit_report import processing
from qase_helper.lib.settings import QHLP_LOG_FILE, QHLP_LOG_LEVEL

logging.basicConfig(
    format='%(asctime)s %(name)s %(levelname)s: %(message)s',
    filename=QHLP_LOG_FILE,
    level=QHLP_LOG_LEVEL,
)
LOG = logging.getLogger(__name__)
LOG.addHandler(logging.StreamHandler(sys.stdout))


def truncate(args, config):
    LOG.info('========== Run truncate ==========')
    LOG.info(f"Input JUnit report file: {args.input}")
    LOG.info(f"Output JUnit report file: {args.output}")
    LOG.info(f"Remove skipped: {args.remove_skipped}")
    processing(args.input, args.output, remove_skipped=args.remove_skipped)


def main():
    config = Config()
    parser = argparse.ArgumentParser(prog='qase-helpers')
    subparsers = parser.add_subparsers(help='subcommand help')
    # ================================ process junit results ================================
    parser_a = subparsers.add_parser('truncate',
                                     help='Truncate test names in JUnit report to comply with Qase name restrictions '
                                          'and remove skipped tests.')
    parser_a.add_argument(
        'input', metavar='JUnit report', type=str,
        help='Path to the JUnit report (.xml) file.'
    )
    parser_a.add_argument(
        'output', metavar='Output file', type=str,
        help='Write processed report to file.', default="",
    )
    parser_a.add_argument(
        '--remove-skipped', dest='remove_skipped', action="store_true",
        default=False,
        help='Remove skipped test cases from report.'
    )
    parser_a.set_defaults(func=truncate)
    # =========================================================================
    args = parser.parse_args()
    args.func(args, config)


if __name__ == "__main__":
    main()
