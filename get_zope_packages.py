#!/usr/bin/python3
"""Determine the names of packages maintained by the Zope Foundation.

Lists the repositories on svn.zope.org and github.com/ZopeFoundation.

Requires Python 3 and the 'svn' command-line tool.

Prints JSON data (a list of dictionaries) to the standard output.
Example output::

    [{"name": "zope.interface",
      "source_web_url": "https://...",
      "github_web_url": "https://..."},
     {"name": "zope.fixers",
      "source_web_url": "http://...",
      "svn_web_url": "http://..."},
      ...]

"""

import argparse
import itertools
import json
import subprocess
import sys
import urllib.request
from operator import itemgetter
from collections import defaultdict


class Error(Exception):
    """An error that is not a bug in this script."""


# How do get a list of interesting Zope packages?
# One option: list all projects in Zope SVN and ZopeFoundation github
# Another option: look at the KGS definition at
# http://zope3.pov.lt/trac/browser/zope.release/trunk/releases/controlled-packages.cfg?format=txt


ZOPE_GITHUB_LIST = 'https://api.github.com/orgs/ZopeFoundation/repos'
ZOPE_SVN = 'svn://svn.zope.org/repos/main'
# or we could do an HTTP request from http://svn.zope.org/ and scrape HTML

ZOPE_SVN_WEB = 'http://zope3.pov.lt/trac/browser/{}'
# the official one is 'http://svn.zope.org/{}', but I prefer trac to viewcvs


EXCEPTIONS = {
    # I've no idea what 'docutils' is doing in svn.zope.org, but it's version
    # 0.4.0
    'docutils',
    # same with pytz, it was probably an external import
    'pytz',
    # more of these
    'ClientForm', 'mechanize',
    # Just a name clash for some very generic names
    'book', 'test',
    # Things that are unlikely to ever be released to PyPI
    '2github', 'Sandbox', 'ReleaseSupport', 'Skeletons',
    'buildout-website', 'developer_docs', 'docs.zope.org_website',
    'non-zpl-doc-resources', 'www.zope.org', 'www.zope.org_buildout',
    'zodbdocs', 'zope-foundation-admin', 'zope-story-website',
    'zpt-docs', 'zopetoolkit', 'zopefoundation.github.io', 'website-zope.de',
    'groktoolkit',
    # Org-wide github templates, not a python package at all
    '.github',
    'meta',  # confusingly, https://pypi.org/p/meta exists but is unrelated
}


OVERRIDES = {
    # buildout is on github but not in https://github.com/zopefoundation
    'zc.buildout': {
        'source_web_url': 'https://github.com/buildout/buildout',
        'github_web_url': 'https://github.com/buildout/buildout',
    },
    # manuel wants to be free from zopefoundation
    'manuel': {
        'source_web_url': 'https://github.com/benji-york/manuel',
        'github_web_url': 'https://github.com/benji-york/manuel',
    },
    # apparently relstorage was moved to github a while ago
    # also its PyPI name is capitalized
    'relstorage': {
        'name': 'RelStorage',
        'source_web_url': 'https://github.com/zodb/relstorage',
        'github_web_url': 'https://github.com/zodb/relstorage',
    },
}


# We get ZODB3 (in svn) _and_ ZODB (in git), is that ok?  I think so,
# the package was split (old ZODB3 into separate persistent, BTrees,
# ZODB, ZEO)


def list_zope_packages_from_svn():
    """Fetch a list of Zope projects from Subversion.

    Requires the command-line subversion tool.
    """
    packages = []
    for line in subprocess.Popen(['svn', 'ls', ZOPE_SVN],
                                 stdout=subprocess.PIPE).stdout:
        line = line.strip()
        if line.endswith(b'/'):
            name = line[:-1].decode('UTF-8')
            if name not in EXCEPTIONS:
                url = ZOPE_SVN_WEB.format(name)
                packages.append(dict(name=name,
                                     source_web_url=url,
                                     svn_web_url=url))
    return packages


def get_json_and_headers(url):
    """Perform HTTP GET for a URL, return deserialized JSON and headers.

    Returns a tuple (json_data, headers) where headers is an instance
    of email.message.Message (because that's what urllib gives us).
    """
    with urllib.request.urlopen(url) as r:
        # We expect Github to return UTF-8, but let's verify that.
        content_type = r.info().get('Content-Type', '').lower()
        if content_type not in ('application/json; charset="utf-8"',
                                'application/json; charset=utf-8'):
            raise Error('Did not get UTF-8 JSON data from {}, got {}'
                        .format(url, content_type))
        return json.loads(r.read().decode('UTF-8')), r.info()


def get_github_list(url, batch_size=100):
    """Perform (a series of) HTTP GETs for a URL, return deserialized JSON.

    Supports batching (which Github indicates by the presence of a Link header,
    e.g. ::

        Link: <https://api.github.com/resource?page=2>; rel="next",
              <https://api.github.com/resource?page=5>; rel="last"

    """
    # API documented at http://developer.github.com/v3/#pagination
    res, headers = get_json_and_headers('{}?per_page={}'.format(
                                                url, batch_size))
    page = 1
    while 'rel="next"' in headers.get('Link', ''):
        page += 1
        more, headers = get_json_and_headers('{}?page={}&per_page={}'.format(
                                                    url, page, batch_size))
        res += more
    return res


def list_zope_packages_from_github(include_archived):
    """Fetch a list of Zope projects from Github."""
    # API documented at
    # http://developer.github.com/v3/repos/#list-organization-repositories
    packages = []
    for repo in get_github_list(ZOPE_GITHUB_LIST):
        if repo['name'] in EXCEPTIONS:
            continue
        if repo['archived'] and not include_archived:
            continue
        pkg = dict(name=repo['name'], github_web_url=repo['html_url'])
        if repo['size'] == 0:  # empty repository
            pkg['empty_github_repo'] = True
        else:
            pkg['source_web_url'] = repo['html_url']
        packages.append(pkg)
    return packages


def list_zope_packages(include_subversion, include_archived):
    """Fetch a list of Zope projects from multiple sources."""
    pkg_list = list_zope_packages_from_github(
        include_archived=include_archived)
    if include_subversion:
        # order matters here: if repository is both in svn and in github, we
        # assume github has the latest version (unless the github one is empty)
        pkg_list = itertools.chain(list_zope_packages_from_svn(),
                                   pkg_list)
    packages = defaultdict(dict)
    for info in pkg_list:
        packages[info['name']].update(info)
    for k, v in OVERRIDES.items():
        if k in packages:
            packages[k].update(v)
    return sorted(packages.values(), key=itemgetter('name'))


def dump_pretty_json(data, fp=sys.stdout):
    """Dump pretty-printed JSON data to a file."""
    json.dump(data, fp, sort_keys=True, indent=2, separators=(',', ': '))


class ArgFormatter(argparse.ArgumentDefaultsHelpFormatter,
                   argparse.RawDescriptionHelpFormatter):

    usage_suffix = ' > packages.json'

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
    parser.add_argument(
        'package_names', nargs='*',
        metavar='package-name', default=argparse.SUPPRESS,
        help='list these packages only (default: all packages)')
    parser.add_argument(
        '--include-subversion', action='store_true',
        help='also list old packages from svn.zope.org')
    parser.add_argument(
        '--include-archived', action='store_true',
        help='also list archived repositories on github')
    args = parser.parse_args()
    packages = list_zope_packages(include_subversion=args.include_subversion,
                                  include_archived=args.include_archived)
    filter = getattr(args, 'package_names', None)
    if filter:
        packages = [info for info in packages if info['name'] in filter]
    dump_pretty_json(packages)


if __name__ == '__main__':
    main()
