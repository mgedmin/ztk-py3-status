#!/usr/bin/python3
"""Produce a dependency graph in graphviz format.

Acts as a filter: reads a JSON list of package records ::

  [{"name": "zope.interface",
    "requires": ["setuptools"],
    "supports_py3": true}, ...]

Produce a PNG or SVG like this::

  ./depgraph.py < blockers.json > graph.dot
  neato -Tpng -O graph.dot      # see graph.dot.png
  neato -Tsvg -O graph.dot      # see graph.dot.svg

This script requires Python 3.
"""

import json
import sys


def main():
    packages = json.load(sys.stdin)
    print('strict digraph "zope.* deps" {')
    print('  graph[layout="neato", outputorder="edgesfirst"];')
    print('  node[label="", shape="point", width=0.1, height=0.1];')
    print('  node[color="#000000", fillcolor="#44444480"];')
    print('  edge[color="#cccccc", arrowhead="open", arrowsize=0.3];')
    should_appear = {r for info in packages for r in info['requires']}
    for info in packages:
        requires = [r for r in info['requires'] if r != 'setuptools']
        if not requires and info['name'] not in should_appear:
            continue
        if info['supports_py3']:
            print('  "{}"[color="#ccffcc", fillcolor="#ddffdd80"];'
                  .format(info['name']))
        else:
            print('  "{}"[color="#ffcccc", fillcolor="#ffdddd80"];'
                  .format(info['name']))
        for other in requires:
            if other in info['blockers']:
                attrs = '[color="#bbbbbb"]'
            else:
                attrs = ''
            print('  "{}" -> "{}"{};'.format(info['name'], other, attrs))
    print('}')


if __name__ == '__main__':
    main()
