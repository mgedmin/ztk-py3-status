#!/bin/sh
./get_zope_packages.py > packages.json
./get_pypi_status.py < packages.json > status.json
##./get_deps.py --cache-dir=~/.buildout/cache/dist < status.json > deps.json
./get_deps.py < status.json > deps.json
./count_blockers.py < deps.json > blockers.json
./depgraph.py < blockers.json > deps.dot
# Now to produce PNG or SVG files, install graphviz and
##neato -Tsvg deps.dot > deps.svg
##neato -Tpng deps.dot > deps.png
