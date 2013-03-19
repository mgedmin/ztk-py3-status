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


class Graph(object):

    def __init__(self):
        self._nodes = defaultdict(dict)
        self._edges = defaultdict(lambda: defaultdict(dict))
        self._ghost_nodes = set()

    @property
    def nodes(self):
        return sorted(self._nodes)

    @property
    def ghost_nodes(self):
        return sorted(self._ghost_nodes)

    def node_attrs(self, src):
        return self._nodes[src]

    def edges(self, src):
        return sorted(self._edges[src])

    def has_edge(self, src, dst):
        return dst in self._edges[src]

    def edge_attrs(self, src, dst):
        return self._edges[src][dst]

    def transposed(self):
        other = Graph()
        for node, attrs in self._nodes.items():
            other.add_node(node, **attrs)
        for src, edges in self._edges.items():
            for dst, attrs in edges.items():
                other.add_edge(dst, src, **attrs)
        return other

    def add_node(self, name, **attrs):
        self._nodes[name].update(attrs)
        self._ghost_nodes.discard(name)

    def add_edge(self, src, dst, **attrs):
        self._edges[src][dst].update(attrs)
        if src not in self._nodes:
            self._ghost_nodes.add(src)
        if dst not in self._nodes:
            self._ghost_nodes.add(dst)

    def remove_edges_to(self, dst):
        for src, edges in self._edges.items():
            if dst in edges:
                del edges[dst]
        if dst not in self._edges:
            self._ghost_nodes.discard(dst)

    def remove_edges_with_attr(self, attr):
        for src, edges in self._edges.items():
            for dst, attrs in list(edges.items()):
                if attrs.get(attr):
                    del edges[dst]
        self._update_ghost_nodes()

    def _update_ghost_nodes(self):
        self._ghost_nodes = set(self._edges)
        for src, edges in self._edges.items():
            self._ghost_nodes.update(edges)
        self._ghost_nodes.difference_update(self._nodes)

    def traverse(self, src, visited=None):
        if visited is None:
            visited = set([src])
        yield src
        for dst in self._edges[src]:
            if dst not in visited:
                visited.add(dst)
                for node in self.traverse(dst, visited):
                    yield node

    def traverse_edges(self, src, visited=None):
        if visited is None:
            visited = set([src])
        for dst in self._edges[src]:
            yield (src, dst)
            if dst not in visited:
                visited.add(dst)
                for edge in self.traverse_edges(dst, visited):
                    yield edge

    def transitive_closure(self, nodes):
        closure = set(nodes)
        queue = list(nodes)
        while queue:
            src = queue.pop()
            for dst in self._edges[src]:
                if dst not in closure:
                    closure.add(dst)
                    queue.append(dst)
        return closure


def package_graph(json_data):
    graph = Graph()
    for info in json_data:
        src = info['name']
        graph.add_node(src, supports_py3=info['supports_py3'])
        for dst in info.get('requires', []):
            graph.add_edge(src, dst, extra=None)
        for extra, requires in info.get('requires_extras', {}).items():
            for dst in requires:
                if not graph.has_edge(src, dst):
                    graph.add_edge(src, dst, extra=extra)
    # if a requires b[x], then a implicitly requires b
    # we show that by having all b[x] require b in our graph
    for node in graph.ghost_nodes:
        if '[' in node:
            base = node.partition('[')[0]
            graph.add_edge(node, base, extra=None)
    return graph


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=ArgFormatter)
    parser.add_argument('package_names', nargs='*',
        metavar='package-name', default=argparse.SUPPRESS,
        help='include these packages and their dependencies only'
             ' (default: all packages that either have or are dependencies)')
    parser.add_argument('-i', metavar='deps.json', dest='input', default=argparse.SUPPRESS,
        help='read package data from file (default: stdin)')
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
    parser.add_argument('--requiring', metavar='PACKAGE',
        help='show only the dependency chain that pulls in PACKAGE')
    args = parser.parse_args()

    if not hasattr(args, 'input') and sys.stdin.isatty():
        parser.error('refusing to read from a terminal')

    if hasattr(args, 'input'):
        with open(args.input) as f:
            packages = json.load(f)
    else:
        packages = json.load(sys.stdin)

    deps = package_graph(packages)
    deps.remove_edges_to('setuptools') # because everything depends on it

    if getattr(args, 'package_names', None):
        include = set(args.package_names)
        title = "{} deps".format(" ".join(args.package_names))
        for pkg in args.package_names:
            if pkg not in deps.nodes:
                print("{}: unknown package: {}".format(parser.prog, pkg),
                      file=sys.stderr)
    else:
        include = {node for node in deps.nodes if deps.edges(node)}
        title = "zope.* deps"

    if not args.extras:
        deps.remove_edges_with_attr('extra')

    for node in deps.ghost_nodes:
        deps.add_node(node)

    include = deps.transitive_closure(include)

    if args.requiring:
        rdeps = deps.transposed()
        include.intersection_update(rdeps.traverse(args.requiring))

    highlight = set()
    highlight_edges = set()
    if args.why:
        rdeps = deps.transposed()
        highlight = set(rdeps.traverse(args.why))
        highlight_edges = set(rdeps.traverse_edges(args.why))

    if args.auto_nodes:
        big_nodes = len(include) < args.auto_threshold
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
    for node in deps.nodes:
        if node not in include:
            continue
        attrs = {}
        supports_py3 = deps.node_attrs(node).get('supports_py3')
        if supports_py3:
            attrs['color'] = "#ccffcc"
            attrs['fillcolor'] = "#ddffdd80"
        elif supports_py3 is not None:
            attrs['color'] = "#ffcccc"
            attrs['fillcolor'] = "#ffdddd80"
        if node in highlight:
            attrs['color'] = "#ff8c00"
        graph.node(node, **attrs)
        for edge in deps.edges(node):
            # if foo depends on bar[extra], we want to show it depending on bar
            dest = edge.partition('[')[0]
            if dest not in include:
                continue
            attrs = {}
            if not deps.node_attrs(dest).get('supports_py3', True):
                attrs['color'] = "#bbbbbb"
            extra = deps.edge_attrs(node, edge).get('extra')
            if extra:
                attrs['style'] = "dotted"
                if big_nodes:
                    attrs['label'] = extra
            if (edge, node) in highlight_edges:
                attrs['color'] = "#ff8c00"
            graph.edge(node, edge, **attrs)
    graph.end()


if __name__ == '__main__':
    main()
