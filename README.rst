Scripts to determine the Python 3 porting status of various Zope packages
=========================================================================

Usage::

  ./get_zope_packages.py > packages.json
  ./get_pypi_status.py < packages.json > status.json
  ./get_deps.py < status.json > deps.json

This takes a while (8 minutes just to get PyPI status; more to download
source distributions).

Example output::

  [{"name": "zope.interface",
    "version": "4.0.3",
    "supports": ["2.6", "2.7", "3.2", "3.3"]},
    "requires": ["setuptools"],
   ...]


Caching
-------

The sdist cache used by get_deps.py is (a) configurable, and (b) compatible
with buildout.  If you use a shared buildout cache, so you can speed up
the initial dependency extraction with ::

  ./get_deps --cache-dir=~/.buildout/cache/dist < status.json > deps.json
