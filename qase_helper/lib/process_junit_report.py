import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

from qase_helper.lib.settings import QHLP_EXCEPT_TAGS, QHLP_MAX_LENGTH


def processing(input, output, remove_skipped=False):
    def _clean_name(name: str) -> str:
        # Function to remove all bracketed tags except QHLP_EXCEPT_TAGS
        def remove_brackets_except(s):
            def replacer(match):
                tag = match.group(0)
                return tag if tag in QHLP_EXCEPT_TAGS else ''

            return re.sub(r'\[[^][]*?\]', replacer, s)

        if len(name) > QHLP_MAX_LENGTH:
            name = remove_brackets_except(name)
            name = name.strip()
            # Remove double namespaces
            name = name.replace("  ", " ")
        return name[:QHLP_MAX_LENGTH]

    tree = ET.parse(input)
    root = tree.getroot()

    name_counts = defaultdict(int)
    to_remove = []

    for testcase in root.iter('testcase'):
        # Remove <testcase> if it contains a <skipped> child
        if testcase.find('skipped') is not None:
            to_remove.append(testcase)
            continue

        name = testcase.get('name')
        if name:
            if len(name) > QHLP_MAX_LENGTH:
                # Add a suffix to modified titles for easier tracking.
                name = f"#1 {name}"
                name_cleaned = _clean_name(name)
                name_counts[name_cleaned] += 1
                # Handle duplicate names
                if name_counts[name_cleaned] > 1:
                    # Increase suffix value
                    new_name = f"#{name_counts[name_cleaned]}{name[2:]}"
                    name_cleaned = _clean_name(new_name)
            else:
                # The name length does not exceed the restriction — leave it as is.
                name_cleaned = name
            testcase.set('name', name_cleaned)

    # Remove skipped testcases
    if remove_skipped:
        for testcase in to_remove:
            parent = testcase.getparent() if hasattr(testcase, 'getparent') else root
            parent.remove(testcase)

    ET.indent(tree, space="  ", level=0)
    if output == "":
        # Write to stdout
        output = sys.stdout
    tree.write(output, encoding='unicode', xml_declaration=True)
