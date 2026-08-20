"""
Unit tests for Phase 2: conflict graph construction.

Tests cover P2-T1 through P2-T4 in isolation using small, hand-crafted
DataFrames. No file I/O or server calls.

Run with:
    pytest tests/test_phase2.py -v
"""
from __future__ import annotations

from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from app.conflict_graph import (
    ConflictGraph,
    CourseInfo,
    build_conflict_edges,
    build_graph,
    course_unification,
    graph_statistics,
    max_clique,
    max_clique_size,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_df(rows: list[tuple]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=[
        "student_name", "department", "course_id",
        "course_display_name", "academic_level",
    ])
    df.index = range(2, len(df) + 2)
    for col in df.columns:
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df


def _make_graph(edges: list[tuple[str, str]], nodes: list[str] | None = None) -> ConflictGraph:
    """Build a ConflictGraph directly from an edge list (no DataFrame needed)."""
    all_nodes = set(nodes or [])
    for a, b in edges:
        all_nodes.add(a)
        all_nodes.add(b)
    course_map = {n: CourseInfo(course_id=n) for n in all_nodes}
    edge_set = {frozenset({a, b}) for a, b in edges}
    return ConflictGraph(course_map=course_map, edges=edge_set)


# ─────────────────────────────────────────────────────────────────────────────
# P2-T1 — Course unification
# ─────────────────────────────────────────────────────────────────────────────

class TestCourseUnification:
    def test_basic_mapping(self):
        """Single student, single course → course_map with one entry."""
        df = _make_df([("أحمد", "قسم أ", "C01", "مادة أ", "ث2")])
        cm = course_unification(df)
        assert "C01" in cm
        assert "أحمد" in cm["C01"].students
        assert cm["C01"].variants == {"قسم أ": {("ث2", "مادة أ")}}

    def test_student_in_multiple_courses(self):
        """One student enrolled in 3 courses → all 3 course nodes exist."""
        df = _make_df([
            ("أحمد", "قسم أ", "C01", "مادة أ", "ث2"),
            ("أحمد", "قسم أ", "C02", "مادة ب", "ث2"),
            ("أحمد", "قسم أ", "C03", "مادة ج", "ث2"),
        ])
        cm = course_unification(df)
        assert set(cm.keys()) == {"C01", "C02", "C03"}
        for cid in ("C01", "C02", "C03"):
            assert "أحمد" in cm[cid].students

    def test_cross_department_unification(self):
        """
        Same course_id in two departments → one CourseInfo with two dept_names
        entries, and students from both departments in the same set.
        """
        df = _make_df([
            ("أحمد", "قسم أ", "C900", "الرياضيات المتقطعة", "ث2"),
            ("سارة", "قسم ب", "C900", "رياضيات الحوسبة",    "ث2"),
        ])
        cm = course_unification(df)
        assert len(cm) == 1
        info = cm["C900"]
        assert info.students == {"أحمد", "سارة"}
        assert info.variants == {
            "قسم أ": {("ث2", "الرياضيات المتقطعة")},
            "قسم ب": {("ث2", "رياضيات الحوسبة")},
        }

    def test_blank_course_id_skipped(self):
        """Rows with blank course_id are ignored (validation error rows)."""
        df = _make_df([
            ("أحمد", "قسم أ", "",    "مجهول", "ث2"),
            ("سارة", "قسم أ", "C01", "مادة",  "ث2"),
        ])
        cm = course_unification(df)
        assert "" not in cm
        assert "C01" in cm

    def test_many_students_one_course(self):
        """96 students in one course → course_map has that course with 96 students."""
        rows = [(f"طالب{i}", "قسم أ", "C01", "مادة كبيرة", "ث3") for i in range(96)]
        df = _make_df(rows)
        cm = course_unification(df)
        assert len(cm["C01"].students) == 96


# ─────────────────────────────────────────────────────────────────────────────
# P2-T2 — Conflict edge detection
# ─────────────────────────────────────────────────────────────────────────────

class TestConflictEdgeDetection:
    def test_plan_example(self):
        """
        Plan spec example:
          Alice → A, B
          Bob   → B, C
          No student in both A and C
        Expected edges: {A,B} and {B,C} only — NOT {A,C}.
        """
        df = _make_df([
            ("Alice", "dept", "A", "Course A", "Y1"),
            ("Alice", "dept", "B", "Course B", "Y1"),
            ("Bob",   "dept", "B", "Course B", "Y1"),
            ("Bob",   "dept", "C", "Course C", "Y1"),
        ])
        cm = course_unification(df)
        edges = build_conflict_edges(cm)
        assert frozenset({"A", "B"}) in edges
        assert frozenset({"B", "C"}) in edges
        assert frozenset({"A", "C"}) not in edges
        assert len(edges) == 2

    def test_zero_conflicts(self):
        """No student shared across courses → empty edge set."""
        df = _make_df([
            ("أحمد", "قسم", "C01", "مادة أ", "ث2"),
            ("سارة", "قسم", "C02", "مادة ب", "ث2"),
            ("منى",  "قسم", "C03", "مادة ج", "ث2"),
        ])
        cm = course_unification(df)
        edges = build_conflict_edges(cm)
        assert len(edges) == 0

    def test_complete_graph_three_courses(self):
        """
        One student in all 3 courses → a complete graph (triangle): 3 edges.
        """
        df = _make_df([
            ("أحمد", "قسم", "A", "مادة أ", "ث2"),
            ("أحمد", "قسم", "B", "مادة ب", "ث2"),
            ("أحمد", "قسم", "C", "مادة ج", "ث2"),
        ])
        cm = course_unification(df)
        edges = build_conflict_edges(cm)
        assert len(edges) == 3
        assert frozenset({"A", "B"}) in edges
        assert frozenset({"A", "C"}) in edges
        assert frozenset({"B", "C"}) in edges

    def test_student_with_five_courses(self):
        """Max real-data scenario: one student in 5 courses → C(5,2) = 10 edges."""
        df = _make_df([
            ("أحمد", "قسم", f"C0{i}", f"مادة {i}", "ث3") for i in range(5)
        ])
        cm = course_unification(df)
        edges = build_conflict_edges(cm)
        assert len(edges) == 10   # C(5,2)

    def test_clique_of_four(self):
        """Four mutually conflicting courses → 6 edges = C(4,2)."""
        df = _make_df([
            ("s1", "dept", "A", "a", "y"),
            ("s1", "dept", "B", "b", "y"),
            ("s2", "dept", "B", "b", "y"),
            ("s2", "dept", "C", "c", "y"),
            ("s3", "dept", "C", "c", "y"),
            ("s3", "dept", "D", "d", "y"),
            ("s4", "dept", "A", "a", "y"),
            ("s4", "dept", "C", "c", "y"),
            ("s5", "dept", "A", "a", "y"),
            ("s5", "dept", "D", "d", "y"),
            ("s6", "dept", "B", "b", "y"),
            ("s6", "dept", "D", "d", "y"),
        ])
        cm = course_unification(df)
        edges = build_conflict_edges(cm)
        assert len(edges) == 6


# ─────────────────────────────────────────────────────────────────────────────
# P2-T3 — Graph statistics
# ─────────────────────────────────────────────────────────────────────────────

class TestGraphStatistics:
    def test_empty_graph(self):
        graph = _make_graph([], nodes=["A", "B", "C"])
        stats = graph_statistics(graph)
        assert stats["node_count"] == 3
        assert stats["edge_count"] == 0
        assert stats["max_degree"] == 0
        assert set(stats["isolated_nodes"]) == {"A", "B", "C"}

    def test_triangle_stats(self):
        graph = _make_graph([("A", "B"), ("B", "C"), ("A", "C")])
        stats = graph_statistics(graph)
        assert stats["node_count"] == 3
        assert stats["edge_count"] == 3
        assert stats["max_degree"] == 2
        # All nodes have degree 2 in a triangle
        assert all(d == 2 for d in stats["degree_map"].values())
        assert stats["isolated_nodes"] == []

    def test_star_graph(self):
        """Hub C connected to A, B, D — spokes have degree 1, hub has degree 3."""
        graph = _make_graph([("C", "A"), ("C", "B"), ("C", "D")])
        stats = graph_statistics(graph)
        assert stats["max_degree"] == 3
        assert stats["max_degree_nodes"] == ["C"]
        assert stats["degree_map"]["A"] == 1

    def test_fixture_calibration(self):
        """
        Build graph from the test fixture and verify stats are sensible.
        The fixture has ~10 unique course_ids and known conflicts.
        """
        fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "test_fixture.xlsx"
        if not fixture_path.exists():
            pytest.skip("test_fixture.xlsx not generated")
        from app.ingestion import read_excel
        df = read_excel(fixture_path.read_bytes())
        graph = build_graph(df)
        stats = graph_statistics(graph)
        assert stats["node_count"] >= 5
        assert stats["edge_count"] >= 1
        assert stats["max_degree"] >= 1


# ─────────────────────────────────────────────────────────────────────────────
# P2-T4 — Maximum clique
# ─────────────────────────────────────────────────────────────────────────────

class TestMaxClique:
    def test_triangle_clique_size_3(self):
        """Triangle (3 nodes, all connected) → max clique = 3."""
        graph = _make_graph([("A", "B"), ("B", "C"), ("A", "C")])
        assert max_clique_size(graph) == 3

    def test_path_graph_clique_size_2(self):
        """Path A-B-C (no A-C edge) → max clique = 2."""
        graph = _make_graph([("A", "B"), ("B", "C")])
        assert max_clique_size(graph) == 2

    def test_empty_graph_clique_size_1(self):
        """Isolated nodes → max clique = 1."""
        graph = _make_graph([], nodes=["A", "B", "C"])
        # Bron-Kerbosch: a single node with no edges = clique of size 1
        assert max_clique_size(graph) == 1

    def test_single_node(self):
        """One node, no edges → max clique = 1."""
        graph = _make_graph([], nodes=["A"])
        assert max_clique_size(graph) == 1

    def test_k4_clique(self):
        """Complete graph on 4 nodes (K4) → max clique = 4."""
        graph = _make_graph([
            ("A", "B"), ("A", "C"), ("A", "D"),
            ("B", "C"), ("B", "D"),
            ("C", "D"),
        ])
        assert max_clique_size(graph) == 4

    def test_5node_triangle_plus_extras(self):
        """5 nodes: A-B-C form a triangle; D and E each connect to only one node."""
        graph = _make_graph([
            ("A", "B"), ("B", "C"), ("A", "C"),  # triangle
            ("D", "A"),                            # D only touches A
            ("E", "B"),                            # E only touches B
        ])
        # The maximum clique remains the triangle {A, B, C}
        assert max_clique_size(graph) == 3
        clique = max_clique(graph)
        assert set(clique) == {"A", "B", "C"}

    def test_clique_is_valid(self):
        """Every returned clique member must be connected to every other member."""
        graph = _make_graph([
            ("A", "B"), ("A", "C"), ("A", "D"),
            ("B", "C"), ("B", "D"),
            ("C", "D"),
            ("E", "A"),  # E is only connected to A
        ])
        clique = max_clique(graph)
        # Verify all pairs in the clique share an edge
        for i, u in enumerate(clique):
            for v in clique[i + 1:]:
                assert frozenset({u, v}) in graph.edges, \
                    f"Pair ({u},{v}) in returned clique but no edge exists"

    def test_fixture_clique_reasonable(self):
        """
        Fixture max clique should be ≥ 2 (at least one conflict exists)
        and ≤ 14 (comfortably fits in a two-week window).
        """
        fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "test_fixture.xlsx"
        if not fixture_path.exists():
            pytest.skip("test_fixture.xlsx not generated")
        from app.ingestion import read_excel
        df = read_excel(fixture_path.read_bytes())
        graph = build_graph(df)
        sz = max_clique_size(graph)
        assert 1 <= sz <= 14


# ─────────────────────────────────────────────────────────────────────────────
# Integration: full build_graph pipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildGraph:
    def test_build_graph_from_df(self):
        """build_graph() returns a ConflictGraph with correct nodes and edges."""
        df = _make_df([
            ("Alice", "dept", "A", "a", "y"),
            ("Alice", "dept", "B", "b", "y"),
            ("Bob",   "dept", "B", "b", "y"),
            ("Bob",   "dept", "C", "c", "y"),
        ])
        graph = build_graph(df)
        assert graph.nodes == {"A", "B", "C"}
        assert frozenset({"A", "B"}) in graph.edges
        assert frozenset({"B", "C"}) in graph.edges
        assert frozenset({"A", "C"}) not in graph.edges

    def test_degree_method(self):
        graph = _make_graph([("A", "B"), ("A", "C")])
        assert graph.degree("A") == 2
        assert graph.degree("B") == 1

    def test_neighbours_method(self):
        graph = _make_graph([("A", "B"), ("A", "C"), ("B", "C")])
        assert graph.neighbours("A") == {"B", "C"}
        assert graph.neighbours("B") == {"A", "C"}
