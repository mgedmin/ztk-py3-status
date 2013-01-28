Scripts to determine the Python 3 porting status of various ZTK packages
========================================================================

Usage (this is science fiction at the moment)::

  ./update.py > status.json

Example output::

  [{'name': 'zope.interface',
    'version': '4.0.3',
    'supports': ['2.6', '2.7', '3.2', '3.3']},
   ...]

