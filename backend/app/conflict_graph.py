"""
Conflict Graph — core data structure for the scheduling engine.

This module implements P2-T1 through P2-T4:

  P2-T1  course_unification()   → course_id → {students}, course_id → {dept: name}
  P2-T2  build_conflict_edges() → frozenset of (course_id, course_id) pairs
  P2-T3  graph_statistics()     → node/edge counts, degree map, max-degree node
  P2-T4  max_clique()           → exact lower bound on exam days required

The unified course_id is the sole key for conflict detection (spec.md §7.1).
Cross-department display-name variation is transparent at this layer — only
student sets matter for edge construction.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Data containers
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CourseInfo:
    """Everything the graph needs to know about one unified course."""
    course_id: str
    students: set[str] = field(default_factory=set)
    # dept → display_name (one entry per department this course appears in)
    dept_names: dict[str, str] = field(default_factory=dict)


@dataclass
class ConflictGraph:
    """
    Conflict graph for the scheduling problem.

    nodes: set of course_id strings
    edges: set of frozenset({course_id_a, course_id_b}) pairs
    course_map: course_id → CourseInfo
    """
    course_map: dict[str, CourseInfo]
    edges: set[frozenset]

    @property
    def nodes(self) -> set[str]:
        return set(self.course_map.keys())

    def degree(self, course_id: str) -> int:
        """Number of conflict edges for *course_id*."""
        return sum(course_id in e for e in self.edges)

    def neighbours(self, course_id: str) -> set[str]:
        """Set of course_ids that conflict with *course_id*."""
        result: set[str] = set()
        for e in self.edges:
            if course_id in e:
                result |= e - {course_id}
        return result


# ─────────────────────────────────────────────────────────────────────────────
# P2-T1 — Course unification
# ─────────────────────────────────────────────────────────────────────────────

def course_unification(df: pd.DataFrame) -> dict[str, CourseInfo]:
    """
    Build the unified course map from the validated DataFrame.

    Returns: course_id → CourseInfo
      where CourseInfo.students = set of all student_names registered in that course
            CourseInfo.dept_names = { department: display_name, … }

    Rows with a blank course_id are skipped (they are a validation error and
    must not reach the graph-building step).
    """
    course_map: dict[str, CourseInfo] = {}
    valid = df[df["course_id"] != ""]

    for _, row in valid.iterrows():
        cid = row["course_id"]
        student = row["student_name"]
        dept = row["department"]
        name = row["course_display_name"]

        if cid not in course_map:
            course_map[cid] = CourseInfo(course_id=cid)

        info = course_map[cid]
        info.students.add(student)
        # Last seen display name wins per department (Rule 3 violations are
        # already blocked by validation before this point is reached)
        info.dept_names[dept] = name

    return course_map


# ─────────────────────────────────────────────────────────────────────────────
# P2-T2 — Conflict edge detection
# ─────────────────────────────────────────────────────────────────────────────

def build_conflict_edges(course_map: dict[str, CourseInfo]) -> set[frozenset]:
    """
    For every pair of courses that share at least one student, add an edge.

    Returns a set of frozensets, each of size 2: {course_id_a, course_id_b}.
    Self-loops are impossible by construction.

    Complexity: O(C² · S) worst case where C = number of courses, S = max
    student set size.  For the reference dataset (167 courses, max 96
    students/course) this is fast enough in Python — benchmarked in P3-T7.
    """
    edges: set[frozenset] = set()
    course_ids = list(course_map.keys())

    for i, cid_a in enumerate(course_ids):
        students_a = course_map[cid_a].students
        for cid_b in course_ids[i + 1:]:
            students_b = course_map[cid_b].students
            if students_a & students_b:          # non-empty intersection → conflict
                edges.add(frozenset({cid_a, cid_b}))

    return edges


# ─────────────────────────────────────────────────────────────────────────────
# P2-T3 — Graph statistics
# ─────────────────────────────────────────────────────────────────────────────

def graph_statistics(graph: ConflictGraph) -> dict:
    """
    Compute and return graph-level statistics used by the results dashboard
    and the infeasibility diagnostic report.

    Returns:
      {
        node_count:       int,
        edge_count:       int,
        degree_map:       { course_id: int },
        max_degree:       int,
        max_degree_nodes: [course_id, ...],   # all nodes tied for max degree
        isolated_nodes:   [course_id, ...],   # courses with zero conflicts
        density:          float,              # 2E / (N*(N-1))
      }
    """
    nodes = graph.nodes
    n = len(nodes)
    e = len(graph.edges)

    degree_map: dict[str, int] = {cid: 0 for cid in nodes}
    for edge in graph.edges:
        a, b = tuple(edge)
        degree_map[a] += 1
        degree_map[b] += 1

    max_deg = max(degree_map.values(), default=0)
    max_deg_nodes = [cid for cid, d in degree_map.items() if d == max_deg]
    isolated = [cid for cid, d in degree_map.items() if d == 0]
    density = (2 * e / (n * (n - 1))) if n > 1 else 0.0

    return {
        "node_count": n,
        "edge_count": e,
        "degree_map": degree_map,
        "max_degree": max_deg,
        "max_degree_nodes": max_deg_nodes,
        "isolated_nodes": isolated,
        "density": round(density, 6),
    }


# ─────────────────────────────────────────────────────────────────────────────
# P2-T4 — Maximum clique (exact lower bound on exam days required)
# ─────────────────────────────────────────────────────────────────────────────

def max_clique(graph: ConflictGraph) -> list[str]:
    """
    Find the maximum clique in the conflict graph using the Bron-Kerbosch
    algorithm with pivot selection (Tomita variant).

    Returns the list of course_ids forming the largest clique found.
    The size of this clique is the mathematically exact lower bound on the
    number of exam days required (spec.md FR-5, §17 Glossary).

    For the reference dataset (167 nodes, 538 edges, known max clique = 9)
    this runs in well under 1 second. For pathological dense graphs it can
    be slow, but the reference data is sparse enough that exact solving is
    always feasible here.
    """
    nodes = list(graph.nodes)
    # Build adjacency sets for O(1) neighbour lookup
    adj: dict[str, set[str]] = {n: graph.neighbours(n) for n in nodes}

    best: list[str] = []

    def _bron_kerbosch(R: set[str], P: set[str], X: set[str]) -> None:
        nonlocal best
        if not P and not X:
            if len(R) > len(best):
                best = list(R)
            return
        # Pivot: choose the vertex in P ∪ X with the most neighbours in P
        pivot = max(P | X, key=lambda v: len(adj[v] & P))
        for v in list(P - adj[pivot]):
            _bron_kerbosch(R | {v}, P & adj[v], X & adj[v])
            P.remove(v)
            X.add(v)

    _bron_kerbosch(set(), set(nodes), set())
    return best


def max_clique_size(graph: ConflictGraph) -> int:
    """Convenience wrapper returning just the size."""
    return len(max_clique(graph))


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: build a ConflictGraph from a validated DataFrame in one call
# ─────────────────────────────────────────────────────────────────────────────

def build_graph(df: pd.DataFrame) -> ConflictGraph:
    """Build the full ConflictGraph from a validated DataFrame."""
    course_map = course_unification(df)
    edges = build_conflict_edges(course_map)
    return ConflictGraph(course_map=course_map, edges=edges)
