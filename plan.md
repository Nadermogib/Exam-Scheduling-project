# Exam Scheduling System — Phased Development Plan

> **How to use this file:** Each phase must be approved and its tasks fully verified before the next phase begins. Check off tasks as they are completed. "Done" criteria are concrete, programmatically or visually verifiable outcomes directly tied to the Functional Requirements (FR-1 through FR-5) and Acceptance Criteria in `spec.md`.

---

## ⚠️ Ambiguities / Open Questions (Please Resolve Before Execution)

All five open questions have been resolved. Decisions are locked and reflected in the task descriptions below.

| # | Question | Decision |
|---|---|---|
| AQ-1 | Day-balancing objective | **Minimize max courses per day** (Option A — simpler CP-SAT model, justified by comfortable safety margin in real data) |
| AQ-2 | Inline correction interaction | **Full in-browser cell editing** (Option A — explicit requirement; users edit the flagged cell directly in the validation table without re-uploading) |
| AQ-3 | Course-code mapping persistence | **Server-side SQLite** (Option A — no external DB server needed; designed for future migration to a hosted DB) |
| AQ-4 | Deployment target | **Local/desktop for now** (Option A — FastAPI on localhost; architecture must support future migration to hosted server without structural changes) |
| AQ-5 | Infeasibility report export format | **Excel only** (Option A — consistent with all other system exports; PDF is a future enhancement) |

---

## Phase 0 — Project Scaffold & Toolchain

*Goal: A runnable skeleton with no business logic — just the two-process (backend + frontend) architecture wired together, with the technology stack confirmed and the development environment reproducible.*

- [ ] **P0-T1 — Backend scaffold**
  Create a FastAPI project with a `/health` endpoint that returns `{"status": "ok"}`.
  **Done when:** `GET /health` returns HTTP 200 with the expected JSON body.

- [ ] **P0-T2 — Frontend scaffold**
  Create a React (Vite) project with a placeholder home page that displays "Exam Scheduling System" in Arabic (`نظام جدولة الامتحانات`) and in English.
  **Done when:** `npm run dev` serves the page at `localhost:5173` with no console errors.

- [ ] **P0-T3 — RTL / Arabic font baseline**
  Add global RTL CSS (`dir="rtl"` on `<html>`, `direction: rtl` in CSS) and load an Arabic-compatible font (e.g., Cairo or Noto Kufi Arabic from Google Fonts).
  **Done when:** Text renders right-to-left; Arabic characters display correctly without box artifacts.

- [ ] **P0-T4 — CORS & API client wiring**
  Configure FastAPI CORS to allow the frontend origin. Create an Axios (or `fetch`) API client wrapper in the frontend that calls `/health` and displays the response.
  **Done when:** The frontend successfully calls the backend `/health` endpoint and the response is visible in the UI (even as a debug label).

- [ ] **P0-T5 — Dependency lock & README**
  Pin all Python dependencies (`requirements.txt` or `pyproject.toml`) and all JS dependencies (`package.json`). Write a `README.md` with one-command setup and start instructions.
  **Done when:** A developer following only the README can get the app running with no extra steps.

- [ ] **P0-T6 — Sample test data fixture**
  Create a synthetic `.xlsx` test fixture that mirrors the real schema (5 Arabic columns, ~30 rows, 8 departments, intentional Critical and Warning validation errors seeded in for later testing).
  **Done when:** The file opens in Excel with the correct column headers in Arabic and contains at least one of each error type defined in §6.

- [ ] **P0-T7 — SQLite database initialisation**
  Create the SQLite database file and initialise the `course_name_map` table schema: `(course_id TEXT, department TEXT, display_name TEXT, last_updated TIMESTAMP, PRIMARY KEY (course_id, department))`. Expose a `GET /api/db/status` endpoint that confirms the DB is reachable and returns the table row count.
  **Done when:** `GET /api/db/status` returns `{ "ok": true, "row_count": 0 }` on a fresh install; the `.sqlite` file exists on disk in the backend data directory.

---

## Phase 1 — Data Ingestion & Validation Backend

*Goal: The backend can receive an `.xlsx` file, parse it, run all §6 validation rules, and return a structured validation report. Zero UI work in this phase — pure backend and unit tests.*

- [ ] **P1-T1 — File upload endpoint**
  Implement `POST /api/upload` that accepts a multipart `.xlsx` file, saves it temporarily in-memory or to a temp path, and returns the raw parsed rows as JSON.
  **Done when:** Posting the P0-T6 fixture returns a JSON array of the parsed rows with the correct 5 column keys (`student_name`, `department`, `course_id`, `course_display_name`, `academic_level`).

- [ ] **P1-T2 — Validation Rule 1 — Blank required cells**
  Implement a check that every required column (`اسم الطالب`, `القسم`, `رمز المادة`, `المقرر`) in every row is non-empty.
  **Done when:** A fixture row with a blank `course_id` is returned in the report with class `Critical`, the row number, and the offending column name.

- [ ] **P1-T3 — Validation Rule 2 — Blank `course_id` (dedicated check)**
  Implement the explicit `course_id` blank check (§6 Rule 2) as a distinct error type from the generic blank-cell check, since it has special messaging ("cannot build conflict graph without it").
  **Done when:** A blank `course_id` cell surfaces exactly two error entries — one from Rule 1 and one from Rule 2 (or is deduplicated with the Rule 2 message taking priority — document the choice).

- [ ] **P1-T4 — Validation Rule 3 — Same `course_id` + same department + different display name**
  Implement a check that groups rows by (`course_id`, `department`) and flags any group where more than one distinct `course_display_name` exists.
  **Done when:** A fixture that seeds the real-world example (`C0508` in `شبكات الحاسوب` with two different `المقرر` values) is correctly flagged as Critical with both conflicting names shown.

- [ ] **P1-T5 — Validation Rule 4 — Same `course_id`, different display names across departments (non-error)**
  Confirm that the same `course_id` appearing with different names in different departments produces **no error or warning**.
  **Done when:** A fixture with 54 such cross-department name variants returns zero errors for those rows.

- [ ] **P1-T6 — Validation Rule 5 — Same display name, different `course_id` (warning)**
  Implement the check that groups rows by `course_display_name` and flags any group where more than one distinct `course_id` appears.
  **Done when:** A fixture row pair sharing an identical `المقرر` name but different `course_id` values is returned with class `Warning` and both `course_id` values shown.

- [ ] **P1-T7 — Validation Rule 6 — Duplicate student full names (warning)**
  Implement the check that counts occurrences of each unique `student_name` value across all rows and flags any name appearing more than once as a Warning.
  **Done when:** A fixture with one deliberately duplicated student name returns a Warning listing the name and the affected row numbers.

- [ ] **P1-T8 — Validation report endpoint**
  Aggregate all validation errors and warnings into a single structured JSON response from `POST /api/upload`. Shape: `{ errors: [...], warnings: [...], row_count: N, is_valid: bool }` where `is_valid` is `true` only when `errors` is empty.
  **Done when:** Posting the P0-T6 fixture (which contains seeded Critical and Warning issues) returns a correctly populated report with `is_valid: false`.

- [ ] **P1-T9 — Excel template endpoint**
  Implement `GET /api/template` that generates and returns a downloadable `.xlsx` file with the correct 5 Arabic column headers and 2–3 example rows of fake data.
  **Done when:** Downloading and opening the file in Excel shows the 5 Arabic headers correctly with right-to-left orientation; example rows are present.

- [ ] **P1-T10 — Unit tests for validation logic**
  Write pytest unit tests covering each validation rule (P1-T2 through P1-T7) in isolation, using small in-memory DataFrames (not file I/O).
  **Done when:** `pytest` passes all tests with 100% pass rate; each rule has at least one "should flag" and one "should not flag" test case.

---

## Phase 2 — Conflict Graph Construction

*Goal: Given a validated dataset, build the conflict graph data structure and expose it via API. This phase isolates the graph-building logic as a testable unit before the solver is added.*

- [ ] **P2-T1 — Course unification by `course_id`**
  Implement a function that takes the parsed DataFrame and produces a mapping: `course_id → set(student_names)` and `course_id → dict(department → display_name)`.
  **Done when:** Applied to the P0-T6 fixture, the output correctly maps each `course_id` to its registered students (regardless of how many departments the course appears in), and each `course_id` to its per-department display names.

- [ ] **P2-T2 — Conflict edge detection**
  Implement a function that takes the `course_id → set(students)` mapping and computes the conflict edge list: for every pair of courses, if their student sets intersect, add an edge.
  **Done when:** Given a small hand-crafted fixture where student Alice is in courses A and B, student Bob is in courses B and C, and no student is in both A and C, the output edges are exactly `{(A,B), (B,C)}` and NOT `(A,C)`.

- [ ] **P2-T3 — Graph statistics computation**
  Implement a function that computes: node count, edge count, per-node degree, max degree node, and chromatic number lower bound (max clique size — see §7.5 / FR-5).
  **Done when:** Applied to the real-sample-calibrated fixture, the reported node/edge counts and max degree are consistent with the spec's sample stats (167 nodes, 538 edges, max degree 47). For the synthetic test fixture, values are hand-verified.

- [ ] **P2-T4 — Max clique computation**
  Implement a max-clique algorithm (exact for small graphs; heuristic upper-bounded for large ones). This is required for FR-5 (infeasibility diagnostics) and is the mathematically exact lower bound on exam days needed.
  **Done when:** Applied to a hand-crafted 5-node fixture where 3 nodes form a triangle (clique of size 3), the function returns `3`. Applied to a fixture where no node shares more than one neighbor, it returns `2` (or `1` if isolated).

- [ ] **P2-T5 — Graph API endpoint**
  Implement `POST /api/graph` that accepts the same file upload, validates it (reusing Phase 1 logic), then builds and returns the conflict graph statistics as JSON: `{ nodes: N, edges: E, max_degree: D, max_clique_size: K, conflict_pairs: [...] }`.
  **Done when:** Posting the P0-T6 fixture returns a correct graph stats object; conflict pairs are listed as `[course_id_1, course_id_2]` tuples.

- [ ] **P2-T6 — Unit tests for graph construction**
  Write pytest unit tests for P2-T1 through P2-T4 in isolation.
  **Done when:** All tests pass; includes at least: single-student-many-courses, many-students-two-courses, zero-conflict (no shared student) case, and a clique-of-4 case.

---

## Phase 3 — CP-SAT Scheduling Engine

*Goal: The core solver is implemented, tested in isolation, and exposed via API. This phase enforces the exact-solving requirement from §7.2 unconditionally.*

- [ ] **P3-T1 — CP-SAT model construction**
  Implement a function `solve(conflict_edges, available_days)` that:
  1. Creates one CP-SAT `IntVar` per course, domain = `{0 … len(available_days)-1}`.
  2. Adds `day[c1] != day[c2]` as a hard constraint for every conflict edge.
  3. Adds the day-balancing objective: introduce an auxiliary `IntVar max_load`; constrain it to be ≥ the number of courses assigned to each day; minimize `max_load`. This minimises the maximum number of courses assigned to any single day (AQ-1: Option A).
  4. Calls the solver and returns either `{ status: "OPTIMAL" | "FEASIBLE", assignment: { course_id: day_index } }` or `{ status: "INFEASIBLE" }`.
  **Done when:** Given a 3-course triangle fixture (A↔B, B↔C, A↔C) and 3 available days, the solver returns a valid 3-coloring. Given 2 available days for the same triangle, it returns `INFEASIBLE`.

- [ ] **P3-T2 — Hard constraint guarantee test**
  Write a test that runs the solver on the P0-T6 fixture, takes the returned assignment, and programmatically verifies that no two courses sharing a conflict edge were assigned the same day.
  **Done when:** Test passes unconditionally; the verification loop is written as a separate function (not just an assertion on the solver's word) so it can be re-used for QA validation of any output.

- [ ] **P3-T3 — Infeasibility detection (no silent fallback)**
  Verify that when `status == "INFEASIBLE"`, the `assignment` field is absent (never a partial/best-effort result) and the return value includes no schedule data whatsoever.
  **Done when:** A fixture with more conflicting courses than available days returns exactly `{ status: "INFEASIBLE" }` — no partial assignment, no empty dict, no exception.

- [ ] **P3-T4 — DSATUR warm-start heuristic (optional performance enhancement)**
  Implement a DSATUR greedy coloring as a heuristic pre-solve step whose result is fed to CP-SAT as a solution hint. This is expressly permitted by §7.2 and can speed up large-instance solving.
  **Done when:** With the hint enabled, the solver finds a valid solution for the real-sample-sized fixture at least as fast as without the hint (benchmark both; regression is a fail).

- [ ] **P3-T5 — Solver timeout configuration**
  Add a configurable solver timeout (default: 30 seconds). If the solver times out on a feasible problem without finding OPTIMAL, it may return `FEASIBLE` (a valid but not maximally balanced schedule). If it times out on an infeasible problem, it must return `INFEASIBLE` (not a partial result).
  **Done when:** Setting a 1-millisecond timeout on a complex instance produces either `FEASIBLE` or `INFEASIBLE` — never a Python exception or a schedule with conflicts.

- [ ] **P3-T6 — Scheduling endpoint**
  Implement `POST /api/schedule` that accepts: the uploaded file + exam period configuration (start date, end date, excluded weekdays, excluded ad-hoc dates). It runs Phase 1 validation (rejects if Critical errors exist), builds the conflict graph (Phase 2), runs CP-SAT (Phase 3), and returns either the full assignment or an infeasibility report.
  **Done when:** Posting the P0-T6 fixture with a valid 14-day window returns a conflict-free assignment; posting with a 2-day window (insufficient) returns `INFEASIBLE`.

- [ ] **P3-T7 — Performance benchmark**
  Run the solver on a fixture scaled to the real sample size (167 courses, 538 conflict edges) and measure wall-clock time.
  **Done when:** The solver returns a certified valid schedule (or INFEASIBLE) in under 10 seconds on a standard development machine. (Acceptance criterion in spec is "a few seconds" — 10 s is the hard ceiling for Phase 3; optimization in later phases if needed.)

- [ ] **P3-T8 — Unit tests for scheduling engine**
  Write pytest tests covering: triangle/clique fixtures, zero-conflict (independent graph) fixtures, infeasibility detection, and partial timeout behavior.
  **Done when:** All tests pass; zero-conflict input schedules all courses on day 1 (trivially optimal).

---

## Phase 4 — Frontend: Upload, Validation & Settings Screens

*Goal: The complete user-facing flow from file upload through exam period configuration. No results display yet — that is Phase 5.*

- [ ] **P4-T1 — Upload screen UI**
  Build the upload screen (§10.1): drag-and-drop zone, manual file picker, "Download Template" button, visual checklist of file requirements.
  **Done when:** The user can drag an `.xlsx` file onto the zone or click to browse; the file name is shown; the "Download Template" button downloads the Phase 1 template file. (FR-1)

- [ ] **P4-T2 — Upload → validation API integration**
  Wire the frontend to `POST /api/upload`. Display a loading spinner while the request is in flight.
  **Done when:** Uploading the P0-T6 fixture calls the API and the raw JSON response (errors + warnings) is logged to the browser console with no CORS or network errors.

- [ ] **P4-T3 — Validation report table (Critical errors)**
  Render a table of Critical errors returned by the API: columns for Row #, Error Type, Offending Column, and Offending Value. Highlight rows in red.
  **Done when:** All Critical errors from the P0-T6 fixture appear in the table with correct row numbers and error descriptions, in Arabic.

- [ ] **P4-T4 — Validation report table (Warnings)**
  Render Warnings below the Critical table: same columns, highlighted in amber/yellow. Include a dismissible info banner explaining warnings do not block progression.
  **Done when:** All Warnings from the P0-T6 fixture appear in the warnings section; the user can dismiss the info banner; warnings alone do not prevent the "Proceed" button from being active.

- [ ] **P4-T5 — Full inline cell editing in the validation table**
  When the user clicks a cell in the Critical errors table, it becomes an editable `<input>` pre-populated with the current offending value. On blur/Enter, the frontend sends a `PATCH /api/session/{id}/row/{row}/field/{field}` request with the corrected value; the backend updates the in-memory dataset and re-runs validation; the table re-renders with updated error state. No re-upload is required.
  **Done when:** Editing a blank `course_id` cell in-browser, pressing Enter, and waiting for the re-validation response causes that row's Critical error to disappear from the table — without any file re-upload. The "Proceed" button becomes active only when the error list is empty.

- [ ] **P4-T6 — Progression gate**
  The "Proceed to Settings" button/step is visually disabled and non-clickable while any Critical error remains; it becomes enabled when the API reports `is_valid: true`.
  **Done when:** Attempting to proceed with Critical errors is impossible via the UI; no API endpoint for scheduling can be reached in this state. (Acceptance Criterion 3 in spec.)

- [ ] **P4-T7 — Exam period settings screen UI**
  Build the settings screen (§10.3): start/end date pickers, weekly rest-day checkboxes (configurable, not hardcoded — e.g., Friday only vs. Friday+Saturday), an interactive calendar to mark ad-hoc excluded dates, and a prominent "one course = one full day, no AM/PM sessions" notice.
  **Done when:** User can select a 2-week window, check Friday+Saturday as rest days, click individual calendar dates to exclude them; the count of available exam days is displayed in real time and updates as exclusions change. (FR-2)

- [ ] **P4-T8 — Settings validation**
  Block the "Run Solver" button if the configured window results in zero available exam days, or if the start date is after the end date.
  **Done when:** Setting start > end shows an inline error; setting all days as excluded shows a separate inline error; both prevent the solver from being called.

- [ ] **P4-T9 — Processing screen**
  Build the processing screen (§10.4): a progress indicator with three labeled stages ("قراءة البيانات" → "بناء مصفوفة التعارض" → "تشغيل المحلل"). Stages advance as the backend responds (or simulate sequencing if the API is a single call).
  **Done when:** After clicking "Run Solver," the three stages appear in sequence; the spinner is visible; the user cannot go back to settings while solving is in progress.

---

## Phase 5 — Frontend: Results Dashboard & Export

*Goal: Display the successful schedule and export to Excel. This phase depends on Phase 3 (engine) and Phase 4 (upload/settings flow).*

- [x] **P5-T1 — Results summary cards**
- [x] **P5-T2 — Calendar-style day-by-day course listing**
- [x] **P5-T3 — Department filter**
- [x] **P5-T4 — Student/course name search**
- [x] **P5-T5 — Master schedule Excel export (backend)**
- [x] **P5-T6 — Per-department Excel export (backend)**
- [x] **P5-T7 — Export buttons in UI**
- [x] **P5-T8 — Course-Code Reference Screen (§10.7)**
- [x] **P6-T1 — Max clique → minimum-days figure (backend)**
- [x] **P6-T2 — Most-registered students ranking**
- [x] **P6-T3 — Most-connected (bottleneck) courses ranking**
- [x] **P6-T4 — Numbered, deep-linked suggestions (backend)**
- [x] **P6-T5 — Infeasibility Report Screen (frontend)**
- [x] **P6-T6 — Infeasibility report Excel export**
- [x] **P6-T7 — No-partial-schedule guard (frontend)**
- [x] **P7-T1 — Full RTL audit**
- [x] **P7-T2 — SQLite-backed course-code reference persistence**
- [x] **P7-T3 — Course-Code Reference Screen — editable**
- [x] **P7-T4 — Full end-to-end acceptance test with real-sample-scale fixture**
- [x] **P7-T5 — Duplicate student name warning — UI display**
- [x] **P7-T6 — Performance profiling**
- [x] **P7-T7 — Error handling & edge cases**
- [x] **P7-T8 — Deployment hardening (local-first, server-ready)**

---

## Dependency Map (Sequential Order)

```
Phase 0 (Scaffold)
    ↓
Phase 1 (Validation Backend)
    ↓
Phase 2 (Conflict Graph)
    ↓
Phase 3 (CP-SAT Engine)
    ↓ (both required)
Phase 4 (Upload + Settings UI) ──────────────────┐
    ↓                                             │
Phase 5 (Results + Export)          Phase 6 (Infeasibility)
    └────────────────────────────┬────────────────┘
                                 ↓
                          Phase 7 (Polish & Hardening)
```

> **Phases 5 and 6 can be developed in parallel** after Phase 4 is complete, since they represent two mutually exclusive outcome branches of the same solver call.

---

*Plan version 1.1 — AQ-1 through AQ-5 resolved 2026-08-19. Phase 0 execution approved.*
