"""
Unit tests + performance benchmark for Phase 3: CP-SAT scheduling engine.

Covers P3-T1 through P3-T8:
  P3-T1  Model construction (hard constraints + objective)
  P3-T2  verify_solution() is independent of solver trust
  P3-T3  INFEASIBLE → assignment is guaranteed None
  P3-T4  DSATUR hint produces a valid greedy colouring
  P3-T5  Timeout yields FEASIBLE or INFEASIBLE, never an exception
  P3-T7  Real-sample-scale benchmark (167 courses, 538 edges) ≤ 10 s
  P3-T8  Triangle, zero-conflict, infeasibility, and timeout test cases

Run with:
    pytest tests/test_phase3.py -v
"""
from __future__ import annotations

import time
import random
from datetime import date, timedelta
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.conflict_graph import ConflictGraph, CourseInfo, build_graph
from app.date_utils import available_dates
from app.scheduler import SolveResult, dsatur_hint, solve, verify_solution


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _days(n: int, start: date = date(2025, 1, 1)) -> list[date]:
    """Return n consecutive dates starting from *start* (no weekends excluded)."""
    return [start + timedelta(days=i) for i in range(n)]


def _make_graph(edges: list[tuple[str, str]], extra_nodes: list[str] | None = None) -> ConflictGraph:
    nodes: set[str] = set(extra_nodes or [])
    for a, b in edges:
        nodes.add(a)
        nodes.add(b)
    course_map = {n: CourseInfo(course_id=n, students={f"s_{n}"}) for n in nodes}
    edge_set = {frozenset({a, b}) for a, b in edges}
    return ConflictGraph(course_map=course_map, edges=edge_set)


def _triangle() -> ConflictGraph:
    return _make_graph([("A", "B"), ("B", "C"), ("A", "C")])


def _independent(n: int) -> ConflictGraph:
    """n courses with zero conflicts between them."""
    nodes = [f"C{i:02d}" for i in range(n)]
    cm = {n: CourseInfo(course_id=n, students={f"s_{n}"}) for n in nodes}
    return ConflictGraph(course_map=cm, edges=set())


# ─────────────────────────────────────────────────────────────────────────────
# P3-T1 — Model construction and basic solving
# ─────────────────────────────────────────────────────────────────────────────

class TestModelConstruction:
    def test_triangle_3_days_feasible(self):
        """Triangle (A↔B, B↔C, A↔C) with 3 days → OPTIMAL."""
        graph = _triangle()
        result = solve(graph, _days(3))
        assert result.status in ("OPTIMAL", "FEASIBLE")
        assert result.assignment is not None
        # All three courses assigned to different days
        days_used = set(result.assignment.values())
        assert len(days_used) == 3

    def test_triangle_2_days_infeasible(self):
        """Triangle with only 2 days → INFEASIBLE (plan spec P3-T1 exact check)."""
        graph = _triangle()
        result = solve(graph, _days(2))
        assert result.status == "INFEASIBLE"

    def test_zero_conflict_graph_optimal_load(self):
        """
        P3-T8: 10 independent courses, 14 available days.

        The minimize-max-load objective spreads courses as evenly as possible.
        With no hard constraints, the optimal solution assigns at most 1 course
        per day (max_load = 1), using exactly 10 days for 10 courses.

        NOTE: the plan spec wording "all courses on day 1" reflected a
        pack-tight intuition; the actual minimize-max-load objective (AQ-1)
        does the opposite — it minimises the busiest day, so it spreads
        courses. This is the correct, user-beneficial behavior.
        """
        graph = _independent(10)
        result = solve(graph, _days(14))
        assert result.status in ("OPTIMAL", "FEASIBLE")
        assert result.assignment is not None
        assert len(result.assignment) == 10
        # Optimal max_load for 10 courses over 14 days = 1 (one per day)
        assert result.max_load == 1
        assert result.days_used == 10

    def test_objective_balances_load(self):
        """
        4 independent courses, 2 days → objective should spread them 2+2, not 3+1.
        """
        graph = _independent(4)
        result = solve(graph, _days(2))
        assert result.status in ("OPTIMAL", "FEASIBLE")
        assert result.max_load <= 2   # ≤ 2 means balanced; 4 on 2 days = 2 each

    def test_wall_time_populated(self):
        graph = _triangle()
        result = solve(graph, _days(3))
        assert result.wall_time_seconds >= 0

    def test_single_course_no_conflicts(self):
        graph = _make_graph([], extra_nodes=["SOLO"])
        result = solve(graph, _days(5))
        assert result.status in ("OPTIMAL", "FEASIBLE")
        assert "SOLO" in result.assignment


# ─────────────────────────────────────────────────────────────────────────────
# P3-T2 — Independent verify_solution guard
# ─────────────────────────────────────────────────────────────────────────────

class TestVerifySolution:
    def test_valid_solution_zero_violations(self):
        graph = _triangle()
        days = _days(3)
        result = solve(graph, days)
        violations = verify_solution(result.assignment, graph)
        assert violations == [], f"Unexpected violations: {violations}"

    def test_deliberately_invalid_solution(self):
        """Manually create a conflicting assignment and verify it is caught."""
        graph = _triangle()
        bad_assignment = {
            "A": date(2025, 1, 1),
            "B": date(2025, 1, 1),   # A and B both on day 1 — conflict!
            "C": date(2025, 1, 2),
        }
        violations = verify_solution(bad_assignment, graph)
        assert len(violations) == 1
        conflict_pair = (violations[0][0], violations[0][1])
        assert set(conflict_pair) == {"A", "B"}

    def test_empty_assignment_no_violations(self):
        graph = _triangle()
        assert verify_solution({}, graph) == []

    def test_solver_output_always_valid(self):
        """
        Full integration: solve() output always passes verify_solution().
        Test on a denser graph (10-node path).
        """
        edges = [(f"C{i}", f"C{i+1}") for i in range(9)]
        graph = _make_graph(edges)
        result = solve(graph, _days(10))
        if result.status != "INFEASIBLE":
            violations = verify_solution(result.assignment, graph)
            assert violations == []


# ─────────────────────────────────────────────────────────────────────────────
# P3-T3 — No partial schedule on INFEASIBLE
# ─────────────────────────────────────────────────────────────────────────────

class TestInfeasibilityGuard:
    def test_infeasible_assignment_is_none(self):
        """When INFEASIBLE, assignment MUST be None — never a partial dict."""
        graph = _triangle()
        result = solve(graph, _days(2))
        assert result.status == "INFEASIBLE"
        assert result.assignment is None   # hard guarantee from spec §7.4

    def test_infeasible_has_no_schedule_fields(self):
        """days_used and courses_per_day should be absent / zero on INFEASIBLE."""
        graph = _triangle()
        result = solve(graph, _days(2))
        assert result.assignment is None
        assert result.days_used == 0
        assert result.courses_per_day is None

    def test_zero_days_infeasible(self):
        """Empty day list → INFEASIBLE immediately."""
        graph = _triangle()
        result = solve(graph, [])
        assert result.status == "INFEASIBLE"
        assert result.assignment is None

    def test_k5_requires_5_days(self):
        """Complete graph on 5 nodes needs exactly 5 days; 4 is infeasible."""
        nodes = list("ABCDE")
        edges = [(a, b) for i, a in enumerate(nodes) for b in nodes[i+1:]]
        graph = _make_graph(edges)
        assert solve(graph, _days(4)).status == "INFEASIBLE"
        assert solve(graph, _days(5)).status in ("OPTIMAL", "FEASIBLE")


# ─────────────────────────────────────────────────────────────────────────────
# P3-T4 — DSATUR warm-start hint
# ─────────────────────────────────────────────────────────────────────────────

class TestDsaturHint:
    def test_hint_valid_colouring(self):
        """DSATUR hint must assign different colours to conflicting courses."""
        graph = _triangle()
        hint = dsatur_hint(graph, 3)
        assert hint is not None
        assert hint["A"] != hint["B"]
        assert hint["B"] != hint["C"]
        assert hint["A"] != hint["C"]

    def test_hint_none_when_too_few_days(self):
        """With fewer days than clique size, DSATUR returns None."""
        graph = _triangle()
        hint = dsatur_hint(graph, 2)
        assert hint is None

    def test_hint_within_day_budget(self):
        """All assigned colours must be in [0, num_days-1]."""
        edges = [(f"C{i}", f"C{i+1}") for i in range(4)]
        graph = _make_graph(edges)
        hint = dsatur_hint(graph, 10)
        if hint is not None:
            assert all(0 <= c < 10 for c in hint.values())

    def test_solver_with_hint_same_result(self):
        """Enabling the hint doesn't change correctness of the output."""
        graph = _make_graph([("A", "B"), ("B", "C"), ("C", "D")])
        days = _days(4)
        with_hint    = solve(graph, days, use_dsatur_hint=True)
        without_hint = solve(graph, days, use_dsatur_hint=False)
        # Both must find a feasible solution
        assert with_hint.status in ("OPTIMAL", "FEASIBLE")
        assert without_hint.status in ("OPTIMAL", "FEASIBLE")
        # Both must be conflict-free
        assert verify_solution(with_hint.assignment, graph) == []
        assert verify_solution(without_hint.assignment, graph) == []


# ─────────────────────────────────────────────────────────────────────────────
# P3-T5 — Timeout handling
# ─────────────────────────────────────────────────────────────────────────────

class TestTimeout:
    def test_very_short_timeout_no_exception(self):
        """
        1-millisecond timeout must not raise an exception — must return
        OPTIMAL, FEASIBLE, or INFEASIBLE only.
        """
        graph = _triangle()
        result = solve(graph, _days(3), timeout_seconds=0.001)
        assert result.status in ("OPTIMAL", "FEASIBLE", "INFEASIBLE")
        # On INFEASIBLE from timeout, assignment must still be None
        if result.status == "INFEASIBLE":
            assert result.assignment is None

    def test_normal_timeout_solves_triangle(self):
        """A simple triangle should solve well within 1 second."""
        graph = _triangle()
        result = solve(graph, _days(3), timeout_seconds=1.0)
        assert result.status in ("OPTIMAL", "FEASIBLE")


# ─────────────────────────────────────────────────────────────────────────────
# P3-T7 — Performance benchmark: real-sample scale
# ─────────────────────────────────────────────────────────────────────────────

def _build_benchmark_graph(seed: int = 42) -> ConflictGraph:
    """
    Build a synthetic graph matching the real sample statistics:
      167 courses, target ~538 conflict edges.

    Uses a random bipartite projection: assign each of 584 synthetic students
    a random subset of courses (mean 2.05 courses each), then build the
    conflict graph from co-registration.
    """
    rng = random.Random(seed)
    n_courses = 167
    n_students = 584
    mean_courses = 2.05

    course_ids = [f"C{i:03d}" for i in range(n_courses)]
    course_students: dict[str, set[str]] = {c: set() for c in course_ids}

    for s in range(n_students):
        k = max(1, round(rng.gauss(mean_courses, 0.8)))
        k = min(k, 5)   # cap at 5 (real max in spec)
        chosen = rng.sample(course_ids, k)
        for c in chosen:
            course_students[c].add(f"s{s}")

    course_map = {
        c: CourseInfo(course_id=c, students=course_students[c])
        for c in course_ids
    }

    # Build edges
    from app.conflict_graph import build_conflict_edges
    edges = build_conflict_edges(course_map)
    return ConflictGraph(course_map=course_map, edges=edges)


class TestBenchmark:
    def test_real_scale_solve_under_10s(self):
        """
        P3-T7: 167-course, real-sample-scale graph must solve (or report
        INFEASIBLE) in under 10 seconds on any standard development machine.
        Acceptance criterion from plan: hard ceiling 10 s for Phase 3.
        """
        graph = _build_benchmark_graph()
        # 14-day window minus Fri+Sat = 10 working days (comfortable margin
        # since spec says greedy needs 9 days minimum)
        days = available_dates(
            start=date(2025, 1, 5),
            end=date(2025, 1, 18),
            excluded_weekdays=[4, 5],
        )

        t0 = time.perf_counter()
        result = solve(graph, days, timeout_seconds=10.0)
        elapsed = time.perf_counter() - t0

        print(f"\n  Benchmark: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        print(f"  Status:    {result.status}")
        print(f"  Wall time: {elapsed:.3f}s")
        if result.status != "INFEASIBLE":
            print(f"  Days used: {result.days_used}/{len(days)}")
            print(f"  Max load:  {result.max_load}")

        assert elapsed < 10.0, f"Solver took {elapsed:.2f}s — exceeds 10 s ceiling"
        assert result.status in ("OPTIMAL", "FEASIBLE", "INFEASIBLE")
        if result.status != "INFEASIBLE":
            violations = verify_solution(result.assignment, graph)
            assert violations == [], f"{len(violations)} conflicts found in benchmark result"

    def test_benchmark_graph_stats(self):
        """Sanity-check the benchmark graph is in the right ballpark."""
        graph = _build_benchmark_graph()
        assert 150 <= len(graph.nodes) <= 167
        # Edge count should be in a plausible range around 538
        assert 200 <= len(graph.edges) <= 1500


# ─────────────────────────────────────────────────────────────────────────────
# date_utils — available_dates
# ─────────────────────────────────────────────────────────────────────────────

class TestDateUtils:
    def test_two_week_minus_weekends(self):
        """14-day window excluding Fri+Sat → 10 working days."""
        days = available_dates(
            date(2025, 1, 5),  # Sunday
            date(2025, 1, 18),
            excluded_weekdays=[4, 5],  # Fri=4, Sat=5
        )
        assert len(days) == 10

    def test_start_after_end_returns_empty(self):
        days = available_dates(date(2025, 1, 10), date(2025, 1, 5))
        assert days == []

    def test_ad_hoc_exclusion(self):
        days_no_excl = available_dates(date(2025, 1, 6), date(2025, 1, 10), excluded_weekdays=[])
        days_with_excl = available_dates(
            date(2025, 1, 6), date(2025, 1, 10),
            excluded_weekdays=[],
            excluded_dates=[date(2025, 1, 8)],
        )
        assert len(days_with_excl) == len(days_no_excl) - 1

    def test_all_days_excluded_returns_empty(self):
        days = available_dates(
            date(2025, 1, 6), date(2025, 1, 12),  # Mon–Sun
            excluded_weekdays=list(range(7)),
        )
        assert days == []
