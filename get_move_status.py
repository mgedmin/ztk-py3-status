#!/usr/bin/python3
"""Determine whether a project was removed from Subversion.

Acts as a filter: reads a JSON list of package records ::

  [{"name": "zope.interface", "svn_web_url": "http://..."}, ...]

and produces an annotated JSON list ::

  [{"name": "zope.interface",
    "svn_web_url": "http://...",
    "removed_from_svn": true}, ...]

The information is extracted by performing 'svn ls' on the repository
URL and looking for a file named MOVED_TO_GITHUB.txt.

Requires Python 3 and the 'svn' command-line tool.
"""

import argparse
import json
import subprocess
import sys


ZOPE_SVN = 'svn://svn.zope.org/repos/main' # must not have trailing /
ZOPE_SVN_WEB = 'http://zope3.pov.lt/trac/browser/' # trailing / mandatory


def svn_ls(url):
    """Fetch a list of Zope projects from Subversion.

    Requires the command-line subversion tool.
    """
    return [line.strip().decode('UTF-8')
            for line in subprocess.Popen(['svn', 'ls', url],
                                         stdout=subprocess.PIPE).stdout]


def dump_pretty_json(data, fp=sys.stdout):
    """Dump pretty-printed JSON data to a file."""
    json.dump(data, fp, sort_keys=True, indent=2, separators=(',', ': '))


class ArgFormatter(argparse.ArgumentDefaultsHelpFormatter,
                   argparse.RawDescriptionHelpFormatter):

    usage_suffix = ' < packages.json > move-status.json'

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
    args = parser.parse_args() # just so we get --help

    packages = json.load(sys.stdin)
    for info in packages:
        package_name = info['name']
        if 'svn_web_url' in info and 'github_web_url' in info:
            if info['svn_web_url'].startswith(ZOPE_SVN_WEB):
                # RelStorage is at .../repos/main/relstorage
                package_name = info['svn_web_url'][len(ZOPE_SVN_WEB):]
            svn_url = '{}/{}/trunk'.format(ZOPE_SVN, package_name)
            try:
                files_in_trunk = svn_ls(svn_url)
            except Exception as e:
                print('Could not list contents of {}: {}: {}'.format(
                        svn_url, e.__class__.__name__, e), file=sys.stderr)
            else:
                info['removed_from_svn'] = (not files_in_trunk or
                        any('MOVED' in fn for fn in files_in_trunk))
    dump_pretty_json(packages)


if __name__ == '__main__':
    main()
