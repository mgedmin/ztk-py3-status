#!/usr/bin/python3
import unittest

from get_pypi_status import extract_py_versions

class Tests(unittest.TestCase):

    def test_extract_py_versions(self):
        self.assertEqual(extract_py_versions([
            # the classifiers of zope.interface 4.0.3, in case you're curious
            "Development Status :: 5 - Production/Stable",
            "Framework :: Zope3",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: Zope Public License",
            "Operating System :: OS Independent",
            "Programming Language :: Python",
            "Programming Language :: Python :: 2",
            "Programming Language :: Python :: 2.6",
            "Programming Language :: Python :: 2.7",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.2",
            "Programming Language :: Python :: 3.3",
            "Programming Language :: Python :: Implementation :: CPython",
            "Programming Language :: Python :: Implementation :: PyPy",
            "Topic :: Software Development :: Libraries :: Python Modules",
        ]), ['2.6', '2.7', '3.2', '3.3', 'pypy'])

    def test_extract_py_versions_no_specifics(self):
        self.assertEqual(extract_py_versions([
            "Programming Language :: Python :: 2",
            "Programming Language :: Python :: 2.7",
            "Programming Language :: Python :: 3",
        ]), ['2.7', '3'])


if __name__ == '__main__':
    unittest.main()
