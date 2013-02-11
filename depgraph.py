#!/usr/bin/python3
"""Produce a dependency graph in graphviz format.

Acts as a filter: reads a JSON list of package records ::

  [{"name": "zope.interface",
    "requires": ["setuptools"],
    "supports_py3": true}, ...]

Produce a PNG or SVG like this::

  ./depgraph.py < blockers.json > graph.dot
  dot -Tpng -O graph.dot        # see graph.dot.png
  dot -Tsvg -O graph.dot        # see graph.dot.svg

This script requires Python 3.
"""

import argparse
import json
import sys


class ArgFormatter(argparse.ArgumentDefaultsHelpFormatter,
                   argparse.RawDescriptionHelpFormatter):

    usage_suffix = ' < blockers.json > graph.dot'

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
    parser.add_argument('package_names', nargs='*',
        metavar='package-name', default=argparse.SUPPRESS,
        help='include these packages and their dependencies only'
             ' (default: all packages that either have or are dependencies)')
    parser.add_argument('-l', '--layout', default='neato',
        help='specify graph layout (e.g. dot, neato, twopi, circo, fdp)')
    parser.add_argument('-b', '--big-nodes', action='store_true',
        help='use large nodes (works better with --layout=dot)')
    args = parser.parse_args()

    packages = json.load(sys.stdin)
    package_by_name = {info['name']: info for info in packages}

    if getattr(args, 'package_names', None):
        include = set(args.package_names)
        title = "{} deps".format(" ".join(args.package_names))
        for pkg in args.package_names:
            if pkg not in package_by_name:
                print("{}: unknown package: {}".format(parser.prog, pkg),
                      file=sys.stderr)
    else:
        include = {pkg['name'] for pkg in packages
                   if any(r != 'setuptools' for r in pkg['requires'])}
        title = "zope.* deps"

    reachable = set()
    def visit(pkg):
        if pkg not in reachable:
            reachable.add(pkg)
            requires = package_by_name.get(pkg, {}).get('requires', [])
            for dep in requires:
                visit(dep)
    for pkg in include:
        visit(pkg)

    print('strict digraph "{}" {{'.format(title)) # }} -- fix vim's autoindent
    print('  graph[layout="{}", outputorder="edgesfirst"];'.format(args.layout))
    if args.big_nodes:
        print('  node[shape="box", style="filled"];')
    else:
        print('  node[label="", shape="point", width=0.1, height=0.1];')
        print('  edge[arrowhead="open", arrowsize=0.3];')
    print('  node[color="#dddddd", fillcolor="#e8e8e880"];')
    print('  edge[color="#cccccc"];')
    for info in packages:
        if info['name'] not in reachable:
            continue
        if info['supports_py3']:
            print('  "{}"[color="#ccffcc", fillcolor="#ddffdd80"];'
                  .format(info['name']))
        else:
            print('  "{}"[color="#ffcccc", fillcolor="#ffdddd80"];'
                  .format(info['name']))
        requires = [r for r in info['requires'] if r != 'setuptools']
        for other in requires:
            if other in info['blockers']:
                attrs = '[color="#bbbbbb"]'
            else:
                attrs = ''
            print('  "{}" -> "{}"{};'.format(info['name'], other, attrs))
    print('}')


if __name__ == '__main__':
    main()
