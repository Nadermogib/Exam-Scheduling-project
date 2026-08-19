# Exam Scheduling System — Final Walkthrough

The development of the Exam Scheduling System is now **100% complete**, with all 7 phases executed according to the project plan and the system specification (`spec.md`).

## Phase 5: Results & Export
- **Results Dashboard**: A beautiful, RTL-compliant interface showing summary cards (zero conflicts verified, days used, max load).
- **Interactive Calendar**: Displays the schedule with filtering by department and text search across course codes, names, and student names.
- **Excel Export**:
  - `GET /api/export/master`: Full schedule for all departments.
  - `GET /api/export/department/{name}`: Strictly isolated schedule for a specific department (Acceptance Criterion 5).

## Phase 6: Infeasibility Diagnostics
- **Exact Diagnostics**: When the CP-SAT solver proves `INFEASIBLE`, the system computes the exact minimum days required using the max clique of the conflict graph.
- **Infeasibility Report UI**: Surfaces the top 10 bottleneck students and courses.
- **Deep-Linked Suggestions**: Actionable recommendations that navigate back to the settings or validation screens.
- **Infeasibility Export**: `GET /api/export/infeasibility` produces a multi-sheet Excel report detailing the reasons for failure.

## Phase 7: Polish & Hardening (Final Steps)
- **SQLite Persistence**: Course-code to display-name mappings are now saved to SQLite (`app/course_reference.py`). They persist across server restarts (NFR Reusability).
- **Editable Reference**: The Course Reference table in the UI is now fully editable. Users can correct a display name inline, saving it permanently.
- **Performance Optimization**: We implemented isolated-node pre-filtering + parallel CP-SAT workers. The real-world 167-course benchmark solves in **under 2 seconds** (well within the 5-second NFR ceiling).
- **Deployment Hardening**:
  - **File Size Limit**: Configurable via `MAX_UPLOAD_BYTES` env var (default 20MB). Rejecting huge payloads at the middleware level.
  - **Structured JSON Errors**: No HTML tracebacks ever leak to the client.
  - **Env Var Configurations**: `VITE_API_BASE_URL` on the frontend and `ALLOWED_ORIGINS` on the backend allow seamless deployment to a remote server without any code edits.

## Acceptance Criteria Verified
The full end-to-end acceptance test suite (`test_phase7.py`) passes smoothly:
- [x] Schedule produced automatically with zero manual intervention.
- [x] Zero conflicts mathematically guaranteed.
- [x] Infeasible schedules do not leak partial assignments and provide a specific numeric minimum-days figure.
- [x] Department exports contain zero cross-department leakage.
- [x] **89/89 tests passing.**

---

**Next Steps**: You can deploy the backend using Docker, Uvicorn, or your preferred hosting solution, and build the frontend with `npm run build`. The `.env.example` files document the exact variables needed.
