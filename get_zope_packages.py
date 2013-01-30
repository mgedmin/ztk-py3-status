#!/usr/bin/python3
"""Determine the names of packages maintained by the Zope Foundation.

Lists the repositories on svn.zope.org and github.com/ZopeFoundation.

Requires Python 3 and the 'svn' command-line tool.

Prints JSON data (a list of dictionaries) to the standard output.
Example output::

    [{"name": "zope.interface"}, ...]

"""

import json
import sys
import subprocess
import urllib.request


class Error(Exception):
    """An error that is not a bug in this script."""


# How do get a list of interesting Zope packages?
# One option: list all projects in Zope SVN and ZopeFoundation github
# Another option: look at the KGS definition at
# http://zope3.pov.lt/trac/browser/zope.release/trunk/releases/controlled-packages.cfg?format=txt


ZOPE_GITHUB_LIST = 'https://api.github.com/orgs/ZopeFoundation/repos'
ZOPE_SVN = 'svn://svn.zope.org/repos/main'
# or we could do an HTTP request from http://svn.zope.org/ and scrape HTML


EXCEPTIONS = {
    # Things that are unlikely to ever be released to PyPI
    '2github', 'Sandbox', 'ReleaseSupport', 'Skeletons',
    'buildout-website', 'developer_docs', 'docs.zope.org_website',
    'non-zpl-doc-resources', 'www.zope.org', 'www.zope.org_buildout',
    'zodbdocs', 'zope-foundation-admin', 'zope-story-website',
}


def list_zope_packages_from_svn():
    """Fetch a list of Zope projects from Subversion.

    Requires the command-line subversion tool.
    """
    subdirs = []
    for line in subprocess.Popen(['svn', 'ls', ZOPE_SVN],
                                 stdout=subprocess.PIPE).stdout:
        line = line.strip()
        if line.endswith(b'/'):
            name = line[:-1].decode('UTF-8')
            if name not in EXCEPTIONS:
                subdirs.append(name)
    return subdirs


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


def get_github_list(url):
    """Perform (a series of) HTTP GETs for a URL, return deserialized JSON.

    Supports batching (which Github indicates by the presence of a Link header,
    e.g. ::

        Link: <https://api.github.com/resource?page=2>; rel="next",
              <https://api.github.com/resource?page=5>; rel="last"

    """
    # API documented at http://developer.github.com/v3/#pagination
    res, headers = get_json_and_headers('{}?per_page=100'.format(url))
    page = 1
    while 'rel="next"' in headers.get('Link', ''):
        page += 1
        more, headers = get_json_and_headers('{}?page={}&per_page=100'.format(
                                                    url, page))
        res += more
    return res


def list_zope_packages_from_github():
    """Fetch a list of Zope projects from Github."""
    # API documented at
    # http://developer.github.com/v3/repos/#list-organization-repositories
    return [repo['name'] for repo in get_github_list(ZOPE_GITHUB_LIST)]


def list_zope_packages():
    """Fetch a list of Zope projects from multiple sources."""
    return sorted(set(list_zope_packages_from_svn()) |
                  set(list_zope_packages_from_github()))


def dump_pretty_json(data, fp=sys.stdout):
    """Dump pretty-printed JSON data to a file."""
    json.dump(data, fp, sort_keys=True, indent=2, separators=(',', ': '))


def main():
    package_names = list_zope_packages()
    packages = [dict(name=name) for name in package_names]
    dump_pretty_json(packages)


if __name__ == '__main__':
    main()
