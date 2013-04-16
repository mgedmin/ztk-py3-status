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

import argparse
import email
import json
import os
import sys
import time
import urllib.request
from io import StringIO


class Error(Exception):
    """An error that is not a bug in this script."""


PYPI_SERVER = 'http://pypi.python.org/pypi'

# PyPI API is documented at http://wiki.python.org/moin/PyPiJson
# (or you can use XMLRPC: http://wiki.python.org/moin/PyPiXmlRpc)


ONE_DAY = 24*60*60 # seconds
UNLIMITED = None


def get_cache_filename(package_name, cache_dir):
    """Compute the pathname of the cache file corresponding to sdist_url."""
    return os.path.join(cache_dir, package_name + '.json')


def get_cached_metadata(package_name, cache_dir, max_age=ONE_DAY):
    """Compute the pathname of the cache file corresponding to sdist_url."""
    filename = get_cache_filename(package_name, cache_dir)
    try:
        with open(filename) as f:
            mtime = os.fstat(f.fileno()).st_mtime
            if max_age is not UNLIMITED and time.time() - mtime > max_age:
                return None
            return json.load(f)
    except IOError:
        return None


def put_cached_metadata(package_name, cache_dir, metadata):
    """Compute the pathname of the cache file corresponding to sdist_url."""
    filename = get_cache_filename(package_name, cache_dir)
    try:
        with open(filename, 'w') as f:
            json.dump(metadata, f)
    except IOError:
        # cache not writable? ignore
        pass


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


def get_metadata(package_name, cache_dir=None, max_age=ONE_DAY):
    """Get package metadata from PyPI."""
    url = '{base_url}/{package_name}/json'.format(
            base_url=PYPI_SERVER, package_name=package_name)
    if cache_dir:
        metadata = get_cached_metadata(package_name, cache_dir, max_age)
        if metadata is not None:
            if metadata == {}:
                headers = email.message_from_string('\n\n')
                raise urllib.error.HTTPError(url, 404, 'Not Found (cached)',
                                             headers, StringIO())
            return metadata
    try:
        metadata = get_json(url)
    except urllib.error.HTTPError as e:
        if e.code == 404 and cache_dir:
            put_cached_metadata(package_name, cache_dir, {})
        raise
    if cache_dir:
        put_cached_metadata(package_name, cache_dir, metadata)
    return metadata


def extract_py_versions(classifiers):
    """Extract a list of supported Python versions from trove classifiers."""
    pypy = 'Programming Language :: Python :: Implementation :: PyPy'
    prefix = 'Programming Language :: Python :: ' # note trailing space
    versions = []
    seen_detailed = set()
    for classifier in classifiers:
        if classifier == pypy:
            versions.append('pypy')
            continue
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


def dump_pretty_json(data, fp=sys.stdout):
    """Dump pretty-printed JSON data to a file."""
    json.dump(data, fp, sort_keys=True, indent=2, separators=(',', ': '))


class ArgFormatter(argparse.ArgumentDefaultsHelpFormatter,
                   argparse.RawDescriptionHelpFormatter):

    usage_suffix = ' < packages.json > status.json'

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
    parser.add_argument('--cache-dir', metavar='DIR', default='.cache/meta',
                        help='directory for caching PyPI metadata')
    parser.add_argument('--cache-max-age', metavar='AGE', default=ONE_DAY,
                        help='maximum age of cached metadata in seconds')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='be more verbose')
    args = parser.parse_args()
    if not os.path.isdir(args.cache_dir):
        try:
            os.makedirs(args.cache_dir)
        except Exception as e:
            parser.error('Could not create cache directory: {}: {}'.format(
                         e.__class__.__name__, e))
    packages = json.load(sys.stdin)
    for info in packages:
        package_name = info['name']
        metadata = None
        try:
            metadata = get_metadata(package_name, args.cache_dir,
                                    max_age=int(args.cache_max_age))
        except Exception as e:
            not_found = isinstance(e, urllib.error.HTTPError) and e.code == 404
            if args.verbose or not not_found:
                print('Could not fetch metadata about {}: {}: {}'.format(
                        package_name, e.__class__.__name__, e),
                      file=sys.stderr)
            if not not_found:
                # if there's an intermittent 502 error use stale data instead
                # of reporting that this package doesn't exist on PyPI.
                metadata = get_cached_metadata(package_name, args.cache_dir,
                                               max_age=UNLIMITED)
        if metadata:
            info.update(extract_interesting_information(metadata))
        else:
            info.update(version=None, sdist_url=None, supports=[])
    dump_pretty_json(packages)


if __name__ == '__main__':
    main()
