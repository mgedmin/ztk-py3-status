#!/usr/bin/python3
"""Extract dependency information of Python packages.

Acts as a filter: reads a JSON list of package records ::

  [{"name": "zope.interface", "sdist_url": "http://..."}, ...]

and produces an annotated JSON list ::

  [{"name": "zope.interface",
    "sdist_url": "http://...",
    "requires": ["setuptools"]}, ...]

The information is extracted from setuptools metadata in source
distributions, which have to be downloaded from the Internet.

This script requires Python 3.
"""

import json
import os
import sys
import tarfile
import zipfile
from urllib.parse import urlparse
from urllib.request import urlretrieve


CACHE_DIR = os.path.expanduser('~/.buildout/cache/dist') # XXX hardcoded to my prefs


class Error(Exception):
    """An error that is not a bug in this script."""


# Plan of action:
#  - determine packages we're interested in (json.load(sys.stdin))
#  - download sdists into a cache directory
#    (maybe by reusing pip or buildout?)
#  - extract */*.egg-info/requires.txt from each
#  - strip version constraints
#  - XXX decide what to do with extras information


def get_cache_filename(sdist_url):
    """Compute the pathname of the cache file corresponding to sdist_url."""
    basename = os.path.basename(urlparse(sdist_url).path)
    return os.path.join(CACHE_DIR, basename)


def get_local_sdist(sdist_url):
    """Return the filename corresponding to a source distribution.

    Downloads the file from sdist_url into the cache directory if necessary.
    """
    filename = get_cache_filename(sdist_url)
    if not os.path.exists(filename):
        # This would be a good spot for a "Downloading {}" message if verbose
        urlretrieve(sdist_url, filename)
    return filename


def extract_requirements_from_tar(sdist_filename):
    """Extract a file named **/*.egg-info/requires.txt in a .tar[.gz] sdist.

    Returns bytes or None.
    """
    with tarfile.open(sdist_filename, 'r') as f:
        for name in f.getnames():
            if name.endswith('.egg-info/requires.txt'):
                return f.extractfile(name).read()
    return None


def extract_requirements_from_zip(sdist_filename):
    """Extract a file named **/*.egg-info/requires.txt in a .zip sdist.

    Returns bytes or None.
    """
    with zipfile.ZipFile(sdist_filename, 'r') as f:
        for name in f.namelist():
            if name.endswith('.egg-info/requires.txt'):
                return f.read(name)
    return None


def extract_requirements(sdist_filename):
    """Extract a file named **/*.egg-info/requires.txt in an sdist.

    Returns bytes or None.
    """
    if sdist_filename.endswith('.zip'):
        return extract_requirements_from_zip(sdist_filename)
    elif sdist_filename.endswith(('.tar.gz', '.tar.bz2', '.tar')):
        return extract_requirements_from_tar(sdist_filename)
    else:
        raise Error('Unsupported archive format: {}'.format(sdist_filename))


def strip_version_constraints(requirement):
    """Strip version constraints from a requirement.

        >>> strip_version_constraints('zope.foo')
        'zope.foo'

        >>> strip_version_constraints('zope.foo ==4.0.0')
        'zope.foo'

        >>> strip_version_constraints('zope.foo >=4.0.0, <4.1.0a1')
        'zope.foo'

    """
    return (requirement.partition('=')[0]
                       .partition('<')[0]
                       .partition('>')[0]
                       .strip())


def parse_requirements(requires_txt_data):
    """Parse a setuptools requires.txt file.

    Returns a list of requirements.

    Ignores setuptools extras.

    Drops all version constraints.
    """
    requirements = []
    for line in requires_txt_data.decode('UTF-8').splitlines():
        if line.startswith('['):
            # we're done with normal requirements and not interested in extras
            break
        if not line:
            continue
        requirements.append(strip_version_constraints(line))
    return requirements


def dump_pretty_json(data, fp=sys.stdout):
    """Dump pretty-printed JSON data to a file."""
    json.dump(data, fp, sort_keys=True, indent=2, separators=(',', ': '))


def main():
    packages = json.load(sys.stdin)
    for info in packages:
        package_name = info['name']
        sdist_url = info.get('sdist_url')
        if not sdist_url:
            continue
        requirements = []
        try:
            sdist_filename = get_local_sdist(sdist_url)
        except Exception as e:
            print('Could not fetch sdist {}: {}: {}'.format(
                        sdist_url, e.__class__.__name__, e),
                      file=sys.stderr)
        else:
            try:
                requires_txt_data = extract_requirements(sdist_filename)
                requirements = parse_requirements(requires_txt_data or b'')
            except Exception as e:
                print('Could not parse requires.txt for {}: {}: {}'.format(
                            sdist_filename, e.__class__, e),
                          file=sys.stderr)
        info['requires'] = requirements
    dump_pretty_json(packages)


if __name__ == '__main__':
    main()
