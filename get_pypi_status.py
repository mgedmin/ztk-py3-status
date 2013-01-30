#!/usr/bin/python3
"""Determine the latest version and Python support status of various packages.

Acts as a filter: reads a JSON list of package records ::

  [{"name": "zope.interface"}, ...]

and produces an annotated JSON list ::

  [{"name": "zope.interface",
    "version": "4.0.3",
    "sdist_url": "http://...",
    "supports": ["2.6", "2.7", "3.2", "3.3"]}, ...]

The information is extracted from the Python Package Index (PyPI),
which takes a while (~8 minutes for 811 packages).

This script requires Python 3.
"""

import json
import sys
import urllib.request


class Error(Exception):
    """An error that is not a bug in this script."""


PYPI_SERVER = 'http://pypi.python.org/pypi'

# PyPI API is documented at http://wiki.python.org/moin/PyPiJson
# (or you can use XMLRPC: http://wiki.python.org/moin/PyPiXmlRpc)


def get_json(url):
    """Perform HTTP GET for a URL, return deserialized JSON."""
    with urllib.request.urlopen(url) as r:
        # We expect PyPI to return UTF-8, but let's verify that.
        content_type = r.info().get('Content-Type', '').lower()
        if content_type not in ('application/json; charset="utf-8"',
                                'application/json; charset=utf-8'):
            raise Error('Did not get UTF-8 JSON data from {}, got {}'
                        .format(url, content_type))
        return json.loads(r.read().decode('UTF-8'))


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
    return dict(version=info['version'],
                supports=extract_py_versions(info['classifiers']),
                sdist_url=extract_sdist_url(metadata))


def extract_sdist_url(metadata):
    """Extract the URL for downloading the source distribution."""
    for info in metadata['urls']:
        if info['packagetype'] == 'sdist':
            return info['url']
    return None


def main():
    verbose = False
    packages = json.load(sys.stdin)
    for info in packages:
        package_name = info['name']
        try:
            metadata = get_metadata(package_name)
        except Exception as e:
            not_found = isinstance(e, urllib.error.HTTPError) and e.code == 404
            if verbose or not not_found:
                print('Could not fetch metadata about {}: {}: {}'.format(
                        package_name, e.__class__, e),
                      file=sys.stderr)
            info.update(version=None, supports=[])
        else:
            info.update(extract_interesting_information(metadata))
    print(json.dumps(packages, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
