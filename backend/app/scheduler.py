"""
CP-SAT Scheduling Engine (Phase 3)

Implements P3-T1 through P3-T5:

  P3-T1  solve()            — CP-SAT model with minimize-max-load objective
  P3-T2  verify_solution()  — independent conflict-free guard (used in tests + QA)
  P3-T3  Infeasibility guaranteed: INFEASIBLE → no assignment ever returned
  P3-T4  dsatur_hint()      — DSATUR warm-start heuristic fed to CP-SAT as hint
  P3-T5  Configurable solver timeout (default 30 s)

Spec guarantees (spec.md §7.2–7.4):
  - Zero conflicts is a HARD CONSTRAINT, not a post-hoc check.
  - If INFEASIBLE, NO partial schedule is ever returned.
  - The authoritative schedule comes from CP-SAT, not the greedy hint.
  - Objective: minimize the maximum number of courses assigned to any single day
    (AQ-1 Option A — minimize max load).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Optional

from ortools.sat.python import cp_model

from app.conflict_graph import ConflictGraph


# ─────────────────────────────────────────────────────────────────────────────
# Return types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SolveResult:
    """
    Returned by solve().  Either a valid assignment or an infeasibility report.

    On success:  status ∈ {"OPTIMAL", "FEASIBLE"}, assignment is populated.
    On failure:  status == "INFEASIBLE",            assignment is None.

    The assignment maps course_id → date (not day index) for readability.
    """
    status: str                               # "OPTIMAL" | "FEASIBLE" | "INFEASIBLE"
    assignment: Optional[dict[str, date]]     # course_id → exam date; None if INFEASIBLE
    wall_time_seconds: float
    # Populated only on success
    days_used: int = 0
    courses_per_day: Optional[dict[str, list[str]]] = None  # date.isoformat() → [course_ids]
    max_load: int = 0                         # max courses on any single day


# ─────────────────────────────────────────────────────────────────────────────
# P3-T4 — DSATUR greedy warm-start
# ─────────────────────────────────────────────────────────────────────────────

def dsatur_hint(graph: ConflictGraph, num_days: int) -> Optional[dict[str, int]]:
    """
    DSATUR greedy graph-colouring used as a warm-start hint for CP-SAT.

    Returns a dict {course_id: day_index} if a valid colouring with ≤ num_days
    colours is found, or None if DSATUR exceeds the day budget (which is a
    strong signal of infeasibility, but CP-SAT will make the final call).

    This result is fed to CP-SAT via AddHint() to speed up solving on large
    instances (spec.md §7.2 — warm-start is explicitly permitted).
    """
    colour: dict[str, int] = {}
    saturation: dict[str, set[int]] = {n: set() for n in graph.nodes}
    uncoloured = set(graph.nodes)

    while uncoloured:
        # Pick node with highest saturation; break ties by degree
        node = max(
            uncoloured,
            key=lambda n: (len(saturation[n]), graph.degree(n)),
        )
        # Assign the lowest available colour
        used_by_neighbours = saturation[node]
        c = 0
        while c in used_by_neighbours:
            c += 1
        if c >= num_days:
            return None          # exceeds budget
        colour[node] = c
        uncoloured.remove(node)
        # Update saturation of neighbours
        for nb in graph.neighbours(node):
            if nb in uncoloured:
                saturation[nb].add(c)

    return colour


# ─────────────────────────────────────────────────────────────────────────────
# P3-T2 — Independent conflict-free verification guard
# ─────────────────────────────────────────────────────────────────────────────

def verify_solution(
    assignment: dict[str, date],
    graph: ConflictGraph,
) -> list[tuple[str, str, date]]:
    """
    Independently verify that *assignment* is conflict-free.

    This function is intentionally NOT a thin wrapper around "trust the solver"
    — it re-checks the constraint from scratch.  Used in unit tests (P3-T2)
    and as an optional QA assertion after every successful solve.

    Returns a list of violations: [(course_id_a, course_id_b, shared_date), ...].
    An empty list means the schedule is valid.
    """
    violations: list[tuple[str, str, date]] = []
    for edge in graph.edges:
        a, b = tuple(edge)
        if a in assignment and b in assignment:
            if assignment[a] == assignment[b]:
                violations.append((a, b, assignment[a]))
    return violations


# ─────────────────────────────────────────────────────────────────────────────
# P3-T1 — CP-SAT model + solve
# ─────────────────────────────────────────────────────────────────────────────

def solve(
    graph: ConflictGraph,
    available_days: list[date],
    *,
    timeout_seconds: float = 30.0,
    use_dsatur_hint: bool = True,
) -> SolveResult:
    """
    Assign each course in *graph* to one of *available_days* using CP-SAT.

    Hard constraint: no two conflicting courses share a day.
    Objective:       minimise the maximum number of courses on any single day
                     (AQ-1 Option A — minimize max load).

    Parameters
    ----------
    graph           : ConflictGraph built from the validated DataFrame
    available_days  : ordered list of schedulable dates (weekends/holidays excluded)
    timeout_seconds : solver wall-clock limit (P3-T5); default 30 s
    use_dsatur_hint : feed DSATUR result as a warm-start hint (P3-T4)

    Returns
    -------
    SolveResult with status "OPTIMAL", "FEASIBLE", or "INFEASIBLE".
    On INFEASIBLE, assignment is guaranteed to be None (spec.md §7.4).
    """
    t0 = time.perf_counter()
    course_ids = list(graph.nodes)
    n_days = len(available_days)

    if n_days == 0:
        return SolveResult(
            status="INFEASIBLE",
            assignment=None,
            wall_time_seconds=time.perf_counter() - t0,
        )

    # ── Pre-filter isolated nodes (P7-T6 performance optimisation) ─────────
    # Isolated nodes (zero-degree courses) cannot conflict with anything.
    # Remove them from the CP-SAT model entirely and assign them post-solve
    # to the least-loaded days. This can cut model size by 30-40% on real data.
    isolated  = [c for c in course_ids if graph.degree(c) == 0]
    connected = [c for c in course_ids if graph.degree(c) > 0]

    # ── Build CP-SAT model on connected subgraph only ────────────────────
    model = cp_model.CpModel()

    # Decision variables only for connected courses
    day_var: dict[str, cp_model.IntVar] = {
        c: model.NewIntVar(0, n_days - 1, f"day_{c}")
        for c in connected
    }

    # ── Hard constraints ─────────────────────────────────────────────────
    for edge in graph.edges:
        a, b = tuple(edge)
        if a in day_var and b in day_var:
            model.Add(day_var[a] != day_var[b])

    # ── Objective: minimise max load (only over connected courses) ────────
    max_load_var = model.NewIntVar(0, len(connected), "max_load")
    for d in range(n_days):
        indicators = []
        for c in connected:
            b_var = model.NewBoolVar(f"on_{c}_{d}")
            model.Add(day_var[c] == d).OnlyEnforceIf(b_var)
            model.Add(day_var[c] != d).OnlyEnforceIf(b_var.Not())
            indicators.append(b_var)
        day_load = model.NewIntVar(0, len(connected), f"load_{d}")
        model.Add(day_load == sum(indicators))
        model.Add(max_load_var >= day_load)
    model.Minimize(max_load_var)

    # DSATUR warm-start only for connected subgraph
    connected_graph_nodes = {c for c in connected}
    if use_dsatur_hint and connected_graph_nodes:
        hint = dsatur_hint(graph, n_days)
        if hint is not None:
            for c, d in hint.items():
                if c in day_var:
                    model.AddHint(day_var[c], d)

    # ── Solve ─────────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout_seconds
    # P7-T6: tighter parameters for faster solving on real-data instances
    import os
    n_cpu = min(4, os.cpu_count() or 1)
    solver.parameters.num_workers = n_cpu
    solver.parameters.linearization_level = 0   # faster on graph-colouring problems

    status_code = solver.Solve(model)
    wall_time = time.perf_counter() - t0

    # ── Interpret result ─────────────────────────────────────────────────────
    if status_code == cp_model.INFEASIBLE:
        # Spec §7.4: MUST NOT return a partial schedule
        return SolveResult(
            status="INFEASIBLE",
            assignment=None,
            wall_time_seconds=wall_time,
        )

    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # Build assignment for connected courses
        assignment: dict[str, date] = {}
        courses_per_day: dict[str, list[str]] = {}

        for c in connected:
            d_idx = solver.Value(day_var[c])
            exam_date = available_days[d_idx]
            assignment[c] = exam_date
            iso = exam_date.isoformat()
            courses_per_day.setdefault(iso, []).append(c)

        # Assign isolated courses to least-loaded days (greedy round-robin)
        for c in isolated:
            # Pick the day with fewest courses so far
            least_day = min(
                available_days,
                key=lambda d: len(courses_per_day.get(d.isoformat(), []))
            )
            assignment[c] = least_day
            courses_per_day.setdefault(least_day.isoformat(), []).append(c)

        days_used = len(courses_per_day)
        max_load = max(len(v) for v in courses_per_day.values()) if courses_per_day else 0

        status_str = "OPTIMAL" if status_code == cp_model.OPTIMAL else "FEASIBLE"
        return SolveResult(
            status=status_str,
            assignment=assignment,
            wall_time_seconds=wall_time,
            days_used=days_used,
            courses_per_day=courses_per_day,
            max_load=max_load,
        )

    # UNKNOWN / MODEL_INVALID / other — treat as infeasible for safety
    return SolveResult(
        status="INFEASIBLE",
        assignment=None,
        wall_time_seconds=wall_time,
    )
