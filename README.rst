Scripts to determine the Python 3 porting status of various ZTK packages
========================================================================

Usage::

  ./update.py > status.json

This takes a while (8 minutes for me).

Example output::

  [{'name': 'zope.interface',
    'version': '4.0.3',
    'supports': ['2.6', '2.7', '3.2', '3.3']},
   ...]
