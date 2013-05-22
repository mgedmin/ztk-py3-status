#!/usr/bin/python3
"""List packages that match the desired criteria.

By default lists all packages; if you specify more than one criterion,
they're ANDed together.

Acts as a filter: reads a JSON list of package records ::

  [{"name": "zope.interface",
    "requires": ["setuptools"],
    "blockers": [],
    "supports_py3": true}, ...]

Prints names of packages

  ./list_packages.py < data.json
  zope.interface
  ...

This script requires Python 3.
"""

import argparse
import json
import sys


class ArgFormatter(argparse.RawDescriptionHelpFormatter):

    usage_suffix = ' < blockers.json'

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
    parser.add_argument('--with-blockers', action='store_true',
        help='list packages that have blockers'
             ' (dependencies not yet ported to Python 3)')
    parser.add_argument('--without-blockers', action='store_true',
        help='list packages that do not have blockers')
    parser.add_argument('--in-github', action='store_true',
        help='list packages that are hosted on Github')
    parser.add_argument('--in-subversion', '--in-svn', action='store_true',
        help='list packages that are hosted on svn.zope.org')
    parser.add_argument('--py3', action='store_true',
        help='list packages that already support Python 3')
    parser.add_argument('--no-py3', action='store_true',
        help='list packages that do not support Python 3')
    parser.add_argument('--released', action='store_true',
        help='list packages that have releases on PyPI')
    parser.add_argument('--unreleased', action='store_true',
        help='list packages that do not have released on PyPI')
    args = parser.parse_args()

    if sys.stdin.isatty():
        parser.error('refusing to read from a terminal')

    packages = json.load(sys.stdin)
    for package in packages:
        if args.with_blockers:
            if not package['blockers']:
                continue
        if args.without_blockers:
            if package['blockers']:
                continue
        if args.in_github:
            if not package['source_web_url'].startswith('https://github.com/'):
                continue
        if args.in_subversion:
            if package['source_web_url'].startswith('https://github.com/'):
                continue
        if args.py3:
            if not package['supports_py3']:
                continue
        if args.no_py3:
            if package['supports_py3']:
                continue
        if args.released:
            if not package['sdist_url']:
                continue
        if args.unreleased:
            if package['sdist_url']:
                continue
        print(package['name'])

if __name__ == '__main__':
    main()
