#!/usr/bin/python3
"""Determine the Python 3 porting status of various ZTK packages."""

import json
import subprocess
import sys
import urllib.request


class Error(Exception):
    """An error that is not a bug in this script."""


PYPI_SERVER = 'http://pypi.python.org/pypi'

# PyPI API is documented at http://wiki.python.org/moin/PyPiJson
# (or you can use XMLRPC: http://wiki.python.org/moin/PyPiXmlRpc)


def _get_json_and_headers(url):
    with urllib.request.urlopen(url) as r:
        # We expect PyPI to return UTF-8, but let's verify that.
        content_type = r.info().get('Content-Type', '').lower()
        if content_type not in ('application/json; charset="utf-8"',
                                'application/json; charset=utf-8'):
            raise Error('Did not get UTF-8 JSON data from {}, got {}'
                        .format(url, content_type))
        return json.loads(r.read().decode('UTF-8')), r.info()


def get_json(url):
    """Perform HTTP GET for a URL, return deserialized JSON."""
    return _get_json_and_headers(url)[0]


def get_metadata(package_name):
    """Get package metadata from PyPI."""
    return get_json('{base_url}/{package_name}/json'.format(
        base_url=PYPI_SERVER, package_name=package_name))


def extract_py_versions(classifiers):
    """Extract a list of supported Python versions from trove classifiers."""
    prefix = 'Programming Language :: Python :: ' # note trailing space
    versions = []
    seen_detailed = set()
    for classifier in classifiers:
        if not classifier.startswith(prefix):
            continue
        rest = classifier[len(prefix):]
        if not rest:
            # invalid data, shouldn't happen, but protects us against
            # an IndexError in subsequent checks
            continue
        if not rest[0].isdigit():
            # e.g. "Programming Language :: Python :: Implementation :: CPython"
            continue
        if '.' in rest:
            # if we've seen e.g. '2.x', make a note omit '2' from the list
            seen_detailed.add(rest.partition('.')[0])
        versions.append(rest)
    return [v for v in versions if v not in seen_detailed]


def extract_interesting_information(metadata):
    """Extract interesting package information from PyPI metadata."""
    info = metadata['info']
    return dict(name=info['name'], version=info['version'],
                supports=extract_py_versions(info['classifiers']))


# How do get a list of interesting Zope packages?
# One option: list all projects in Zope SVN and ZopeFoundation github
# Another option: look at the KGS definition at
# http://zope3.pov.lt/trac/browser/zope.release/trunk/releases/controlled-packages.cfg?format=txt


ZOPE_GITHUB_LIST = 'https://api.github.com/orgs/ZopeFoundation/repos'
ZOPE_SVN = 'svn://svn.zope.org/repos/main'
# or we could do an HTTP request from http://svn.zope.org/ and scrape HTML


def list_zope_packages_from_svn():
    """Fetch a list of Zope projects from Subversion.

    Requires the command-line subversion tool.
    """
    EXCEPTIONS = {
        # Things that are unlikely to ever be released to PyPI
        '2github', 'Sandbox', 'ReleaseSupport', 'Skeletons',
        'buildout-website', 'developer_docs', 'docs.zope.org_website',
        'non-zpl-doc-resources', 'www.zope.org', 'www.zope.org_buildout',
        'zodbdocs', 'zope-foundation-admin', 'zope-story-website',
    }
    subdirs = []
    for line in subprocess.Popen(['svn', 'ls', ZOPE_SVN],
                                 stdout=subprocess.PIPE).stdout:
        line = line.strip()
        if line.endswith(b'/'):
            name = line[:-1].decode('UTF-8')
            if name not in EXCEPTIONS:
                subdirs.append(name)
    return subdirs


def get_github_list(url):
    """Perform (a series of) HTTP GETs for a URL, return deserialized JSON.

    Supports batching (which Github indicates by the presence of a Link header,
    e.g. ::

        Link: <https://api.github.com/resource?page=2>; rel="next",
              <https://api.github.com/resource?page=5>; rel="last"

    """
    res, headers = _get_json_and_headers('{}?per_page=100'.format(url))
    page = 1
    while 'rel="next"' in headers.get('Link', ''):
        page += 1
        more, headers = _get_json_and_headers('{}?page={}&per_page=100'.format(
                                                    url, page))
        res += more
    return res


def list_zope_packages_from_github():
    """Fetch a list of Zope projects from Github."""
    return [repo['name'] for repo in get_github_list(ZOPE_GITHUB_LIST)]


def list_zope_packages():
    """Fetch a list of Zope projects from multiple sources."""
    return sorted(set(list_zope_packages_from_svn()) |
                  set(list_zope_packages_from_github()))


def main():
    verbose = False
    packages = list_zope_packages()
    res = []
    for package_name in packages:
        try:
            metadata = get_metadata(package_name)
        except Exception as e:
            if verbose:
                print('Could not fetch metadata about {}: {}: {}'.format(
                        package_name, e.__class__.__name__, e),
                    file=sys.stderr)
            info = dict(name=package_name, version=None, supports=[])
        else:
            info = extract_interesting_information(metadata)
        res.append(info)
    print(json.dumps(res, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
