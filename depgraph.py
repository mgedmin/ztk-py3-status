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
from collections import defaultdict


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


class GraphGenerator(object):

    def __init__(self, stream=None):
        self.stream = stream if stream is not None else sys.stdout

    def start(self, title, kind='digraph'):
        assert kind in ('graph', 'digraph')
        self._edge = '->' if kind == 'digraph' else '--'
        self._print('strict digraph "%s" {' % title)

    def options(self, obj, **attrs):
        assert obj in ('graph', 'node', 'edge')
        if attrs:
            self._print('  %s%s;' % (obj, self._attrs(attrs)))

    def node(self, name, **attrs):
        assert self._edge, "Call start() first!"
        self._print('  "%s"%s;' % (self._quote(name), self._attrs(attrs)))

    def edge(self, src, dst, **attrs):
        self._print('  "%s" %s "%s"%s;' % (self._quote(src), self._edge,
                                           self._quote(dst),
                                           self._attrs(attrs)))

    def end(self):
        self._print('}')

    def _print(self, s):
        print(s, file=self.stream)

    def _quote(self, s):
        return (s.replace("\\", "\\\\")
                 .replace("\"", "\\\"")
                 .replace("\n", "\\n")
                 .replace("\0", "\\\\0"))

    def _value(self, value):
        if isinstance(value, str):
            return '"%s"' % self._quote(value)
        else:
            return str(value)

    def _attrs(self, attrs):
        if not attrs:
            return ''
        return '[%s]' % ', '.join('%s=%s' % (k, self._value(v))
                                  for k, v in sorted(attrs.items()))


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=ArgFormatter)
    parser.add_argument('package_names', nargs='*',
        metavar='package-name', default=argparse.SUPPRESS,
        help='include these packages and their dependencies only'
             ' (default: all packages that either have or are dependencies)')
    parser.add_argument('-e', '--extras', '--include-extras', action='store_true',
        help='include requirements for setuptools extras')
    parser.add_argument('-a', '--auto-nodes', action='store_true',
        help='use large nodes for small graphs, small nodes for large graphs')
    parser.add_argument('--auto-threshold', metavar='N', type=int, default=50,
        help='number of nodes below which the graph is considered to be small')
    parser.add_argument('-b', '--big-nodes', action='store_true',
        help='use large nodes (implies --layout=dot unless overridden)')
    parser.add_argument('-l', '--layout', default=argparse.SUPPRESS,
        help='specify graph layout (e.g. dot, neato, twopi, circo, fdp;'
             ' default: dot for --big-nodes, neato otherwise)')
    parser.add_argument('-w', '--why', metavar='PACKAGE',
        help='highlight the dependency chain that pulls in PACKAGE')
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

    if args.extras:
        def get_requirements_with_extras(info):
            requires = [(r, None) for r in info.get('requires', [])
                        if r != 'setuptools']
            seen = set(r for r, _ in requires)
            for extra, extra_requires in sorted(info.get('requires_extras', {}).items()):
                for r in extra_requires:
                    if r not in seen:
                        requires.append((r, extra))
                        seen.add(r)
            return requires
    else:
        def get_requirements_with_extras(info):
            return [(r, None) for r in info.get('requires', [])
                    if r != 'setuptools']
    def get_requirements(info):
        return [(r, e) for r, e in get_requirements_with_extras(info)
                if '[' not in r]

    reachable = set()
    required_by = defaultdict(list)
    def visit(pkg):
        if pkg not in reachable:
            reachable.add(pkg)
            info = package_by_name.get(pkg, {})
            for dep, extra in get_requirements_with_extras(info):
                required_by[dep].append((pkg, extra))
            for dep, extra in get_requirements(info):
                visit(dep)
    for pkg in include:
        visit(pkg)

    highlight = set()
    highlight_edges = set()
    if args.why:
        def traverse(pkg):
            if pkg not in highlight:
                highlight.add(pkg.partition('[')[0])
                for other, extra in required_by[pkg]:
                    highlight_edges.add((other, extra, pkg))
                    traverse('%s[%s]' % (other, extra) if extra else other)
        traverse(args.why)

    if args.auto_nodes:
        big_nodes = len(reachable) < args.auto_threshold
    else:
        big_nodes = args.big_nodes

    if getattr(args, 'layout', None):
        layout = args.layout
    elif big_nodes:
        layout = 'dot'
    else:
        layout = 'neato'

    graph = GraphGenerator()
    graph.start(title)
    graph.options('graph', layout=layout, outputorder="edgesfirst")
    if big_nodes:
        graph.options('node', shape="box", style="filled")
    else:
        graph.options('node', label="", shape="point", width=0.1, height=0.1)
        graph.options('edge', arrowhead="open", arrowsize=0.3)
    graph.options('node', color="#dddddd", fillcolor="#e8e8e880")
    graph.options('edge', color="#cccccc")
    for info in packages:
        if info['name'] not in reachable:
            continue
        attrs = {}
        if info['supports_py3']:
            attrs['color'] = "#ccffcc"
            attrs['fillcolor'] = "#ddffdd80"
        else:
            attrs['color'] = "#ffcccc"
            attrs['fillcolor'] = "#ffdddd80"
        if info['name'] in highlight:
            attrs['color'] = "#ff8c00"
        graph.node(info['name'], **attrs)
        requires = get_requirements(info)
        for other, extra in requires:
            attrs = {}
            if other in info['blockers']:
                attrs['color'] = "#bbbbbb"
            if extra:
                attrs['style'] = "dotted"
                if big_nodes:
                    attrs['label'] = extra
            if (info['name'], extra, other) in highlight_edges:
                attrs['color'] = "#ff8c00"
            graph.edge(info['name'], other, **attrs)
    graph.end()


if __name__ == '__main__':
    main()
