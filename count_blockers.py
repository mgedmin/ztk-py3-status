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

import argparse
import json
import sys


def dump_pretty_json(data, fp=sys.stdout):
    """Dump pretty-printed JSON data to a file."""
    json.dump(data, fp, sort_keys=True, indent=2, separators=(',', ': '))


class ArgFormatter(argparse.ArgumentDefaultsHelpFormatter,
                   argparse.RawDescriptionHelpFormatter):

    usage_suffix = ' < deps.json > blockers.json'

    # argparse says: "the API of the formatter objects is still considered an
    # implementation detail."  *sigh*  So I have to either duplicate
    # information and hardcode my usage string, or rely on internal
    # implementation details.

    def _format_usage(self, *args):
        return (super(ArgFormatter, self)._format_usage(*args).rstrip('\n\n')
                + self.usage_suffix + '\n\n')


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=ArgFormatter)
    args = parser.parse_args()

    if sys.stdin.isatty():
        parser.error('refusing to read from a terminal')

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
            info['blockers_extras'] = [
                pkg
                for extra, reqs in info.get('requires_extras', {}).items()
                for pkg in reqs
                if pkg in do_not_support_py3]
            info['all_blockers'] = sorted(set(info['blockers'])
                                          | set(info['blockers_extras']))
        else:
            info['supports_py3'] = True
            info['blockers'] = []
            info['blockers_extras'] = []
            info['all_blockers'] = []
        info['blocks'] = []
        info['blocks_extras'] = []
        info['blocks_all'] = []
    package_by_name = {info['name']: info for info in packages}
    for info in packages:
        for blocker in info['blockers']:
            package_by_name[blocker]['blocks'].append(info['name'])
        for blocker in info['blockers_extras']:
            package_by_name[blocker]['blocks_extras'].append(info['name'])
        for blocker in info['all_blockers']:
            package_by_name[blocker]['blocks_all'].append(info['name'])
    dump_pretty_json(packages)


if __name__ == '__main__':
    main()
