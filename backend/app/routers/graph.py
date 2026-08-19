"""
POST /api/graph — Conflict graph analysis endpoint (P2-T5).

Accepts a session_id (from a prior upload) and returns the full conflict graph
statistics plus the conflict edge list and max-clique size.

This endpoint is also used internally by the scheduler to avoid re-building
the graph from scratch on every solve call.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.conflict_graph import build_graph, graph_statistics, max_clique_size
from app.session_store import get_session

router = APIRouter(prefix="/api", tags=["graph"])


class GraphRequest(BaseModel):
    session_id: str


@router.post("/graph")
async def get_conflict_graph(body: GraphRequest):
    """
    Build the conflict graph from the validated session DataFrame.

    Returns:
    {
      session_id:      str,
      nodes:           int,
      edges:           int,
      max_degree:      int,
      max_degree_nodes:[str, ...],
      isolated_nodes:  [str, ...],
      density:         float,
      max_clique_size: int,           ← exact lower bound on exam days needed
      conflict_pairs:  [[str, str], ...]
    }
    """
    session = get_session(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة أو انتهت صلاحيتها.")

    if session.validation_report and not session.validation_report.get("is_valid", True):
        raise HTTPException(
            status_code=422,
            detail="لا يمكن بناء مصفوفة التعارض قبل حل جميع الأخطاء الحرجة.",
        )

    graph = build_graph(session.df)
    stats = graph_statistics(graph)
    clique_sz = max_clique_size(graph)

    # Serialise edges as sorted pairs for deterministic output
    conflict_pairs = sorted(
        [sorted(list(e)) for e in graph.edges],
        key=lambda p: (p[0], p[1]),
    )

    return JSONResponse({
        "session_id": body.session_id,
        "nodes": stats["node_count"],
        "edges": stats["edge_count"],
        "max_degree": stats["max_degree"],
        "max_degree_nodes": stats["max_degree_nodes"],
        "isolated_nodes": stats["isolated_nodes"],
        "density": stats["density"],
        "max_clique_size": clique_sz,
        "conflict_pairs": conflict_pairs,
    })
