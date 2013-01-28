#!/usr/bin/python3
"""Determine the Python 3 porting status of various ZTK packages."""

import json
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
        if content_type != 'application/json; charset="utf-8"':
            raise Error('Did not get UTF-8 JSON data from {}, got {}'
                        .format(url, content_type))
        return json.loads(r.read().decode('UTF-8'))


def get_metadata(package_name):
    """Get package metadata from PyPI."""
    return get_json('{base_url}/{package_name}/json'.format(
        base_url=PYPI_SERVER, package_name=package_name))


def extract_py_versions(classifiers):
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
    info = metadata['info']
    return dict(name=info['name'], version=info['version'],
                supports=extract_py_versions(info['classifiers']))


def main():
    packages = ['zope.interface']
    res = [
        extract_interesting_information(get_metadata(package_name))
        for package_name in packages
    ]
    print(json.dumps(res, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
