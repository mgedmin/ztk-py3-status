#!/usr/bin/python3
"""Determine direct blockers for Python 3 support for a package.

Blockers are required packages that do not support Python 3 yet.

Acts as a filter: reads a JSON list of package records ::

  [{"name": "zope.interface",
    "requires": ["setuptools"],
    "supports": ["2.6", "2.7", "3.2", "3.3"]}, ...]

and produces an annotated JSON list ::

  [{"name": "zope.interface",
    "requires": ["setuptools"],
    "supports": ["2.6", "2.7", "3.2", "3.3"],
    "supports_py3": true,
    "blockers": []}, ...]

This script requires Python 3.
"""

import json
import sys


def dump_pretty_json(data, fp=sys.stdout):
    """Dump pretty-printed JSON data to a file."""
    json.dump(data, fp, sort_keys=True, indent=2, separators=(',', ': '))


def main():
    packages = json.load(sys.stdin)
    # A subtle bit of logic: we compute a set of known packages that do not
    # express support for Python 3 instead of computing a set of known packages
    # that *do* express support for Python 3.  We want to assume that
    # *unknown* packages support Python 3, otherwise we'll introduce false
    # positives into our blocker lists.  False negatives are less painful.
    do_not_support_py3 = {
        info['name'] for info in packages
        if not any(v.startswith('3') for v in info['supports'])}
    for info in packages:
        package_name = info['name']
        if package_name in do_not_support_py3:
            info['supports_py3'] = False
            info['blockers'] = [pkg for pkg in info.get('requires') or []
                                if pkg in do_not_support_py3]
        else:
            info['supports_py3'] = True
            info['blockers'] = []
        info['blocks'] = []
    package_by_name = {info['name']: info for info in packages}
    for info in packages:
        for blocker in info['blockers']:
            package_by_name[blocker]['blocks'].append(info['name'])
    dump_pretty_json(packages)


if __name__ == '__main__':
    main()
