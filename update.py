#!/usr/bin/python3
"""Determine the Python 3 porting status of various ZTK packages."""

import json


# PyPI API is documented at http://wiki.python.org/moin/PyPiJson
# (or you can use XMLRPC: http://wiki.python.org/moin/PyPiXmlRpc)


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


def main():
    res = [
        {'name': 'zope.interface',
         'version': '4.0.3',
         'suports': ['2.6', '2.7', '3.2', '3.3'],
        },
    ]
    print(json.dumps(res, indent=2))


if __name__ == '__main__':
    main()
