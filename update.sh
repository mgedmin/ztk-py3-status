#!/bin/sh
./get_zope_packages.py > packages.json
./get_pypi_status.py < packages.json > status.json
./get_deps.py < status.json > deps.json
