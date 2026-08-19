# Exam Scheduling System — Full Specification (spec.md)

**Project:** Conflict-Free Exam Timetabling System for Supplementary/Makeup Exams ("الدور التكميلي")
**Document purpose:** This file is the complete, authoritative specification of the system to be built. It is intended to be read by an AI development agent (Google Antigravity) to produce a phased implementation plan broken into small, verifiable tasks. Every requirement below is written to be unambiguous and directly actionable.

---

## 1. Problem Statement

An exams office needs to schedule supplementary exams ("الدور التكميلي") for a two-week exam period. The input is a spreadsheet of student course registrations. Many students are registered in more than one course. If two courses a student is registered in are scheduled on the same day, that student has a scheduling conflict and cannot sit both exams.

The system must take the registration spreadsheet and automatically assign every course to a single day within the exam period such that:

1. No student ever has two (or more) of their registered courses scheduled on the same day (hard constraint — must be guaranteed, not merely likely).
2. Subject to constraint (1), the distribution of courses across days should be as dense/balanced as possible (i.e., maximize use of available days rather than clustering courses into a few days while leaving others empty).

The system must also correctly unify courses that are shared across departments but have different display names (same course content, different label per department), and must handle the case where no valid conflict-free schedule exists within the available days, by producing an actionable diagnostic report instead of a partial or silently-wrong schedule.

---

## 2. Goals

1. Ingest a single Excel file of student–course registrations and validate it before any processing.
2. Detect every potential conflict between courses based on shared students.
3. Generate an exam schedule for a configurable exam period (default: two weeks) such that no student has two exams on the same day — with a mathematical (not probabilistic) guarantee of zero conflicts.
4. Maximize the use of available exam days (avoid unnecessary clustering of courses into few days).
5. Correctly treat courses that are the same underlying course but labeled differently per department, using a unified course code, while still displaying each student the course name used in their own department.
6. When no conflict-free schedule is possible within the available period, provide a precise root-cause diagnosis and concrete, numeric, actionable suggestions (not a generic error).
7. Export the final schedule as Excel: one master schedule, plus one schedule per department (department-specific course names).

---

## 3. Scope

### 3.1 In Scope
- Upload of a single `.xlsx` file containing student registrations.
- Automated data-quality validation with a detailed error/warning report before scheduling runs.
- Building a conflict model between courses and solving it with a constraint-based solver (exact, not heuristic).
- Generating a schedule for a configurable period (default two weeks), one exam slot per day per course (no AM/PM sessions — see 3.2).
- Excluding non-exam days (weekends / holidays) from the schedulable date range.
- Interactive in-app display of the resulting schedule, plus Excel export (master + per-department).
- A detailed diagnostic/infeasibility report with concrete suggested fixes when no valid schedule exists.

### 3.2 Out of Scope (current phase)
- Exam room/venue capacity constraints.
- Proctor/invigilator assignment.
- Multiple exam sessions per day (morning/evening). **Explicit product decision: exactly one exam slot per day; a course occupies a full day.**
- Direct integration with a university Student Information System (SIS). Input is via Excel file only.

---

## 4. Users & Roles

| Role | Description | Core permissions |
|---|---|---|
| Exam Coordinator (primary user) | Staff member responsible for preparing the makeup-exam schedule | Upload file, review/fix validation errors, configure exam period, run the solver, review results, export |
| Department Viewer (future/optional) | Reviews only their department's schedule | View and export their department's schedule only; no edit/run permissions |

### Key Use Cases
- UC-1: Upload a new registration file and generate a schedule from scratch.
- UC-2: Fix data errors flagged by validation before proceeding to scheduling.
- UC-3: Adjust the exam period/settings and re-run the solver after an initial infeasible result.
- UC-4: Review and export a single department's schedule only.
- UC-5: Maintain/update the course-code reference mapping for future exam cycles.

---

## 5. Input Data Specification

The input is a single Excel (`.xlsx`) file. This schema is derived from and validated against a real sample file (1198 rows) already analyzed for this project.

| Column (Arabic, as in source file) | Meaning | Required | Notes |
|---|---|---|---|
| `اسم الطالب` (student_name) | Full student name | Yes | **No unique student ID exists in the current data.** The full name is the only student identifier. See §5.1 for the implication. |
| `القسم` (department) | Student's academic department | Yes | Used to determine which course display-name to show this student |
| `رمز المادة` (course_id) | Unified course code | Yes | This is the **primary key for conflict detection**. Must never be blank. |
| `المقرر` (course_display_name) | Course name as labeled within the student's department | Yes | The same `course_id` may legitimately have different `المقرر` values across different departments — this is expected and correct, not an error (see §6, rule 4). |
| `الفصل` (academic_level/semester) | Descriptive academic level of the student | Yes (present in current file) | **Not used anywhere in conflict detection or scheduling logic.** Purely descriptive. |

### 5.1 No Unique Student Identifier — Explicit Risk
The current source file has no student ID; the full name string is the sole identifier. This creates a theoretical risk: two different students who happen to share an identical full name would be incorrectly treated as one student, creating a false conflict between their courses. In the real sample analyzed (584 unique student names, 1198 rows), no critical case of this was found, but the system must still:
- Detect and flag (non-blocking warning) any exact full-name duplication for manual review.
- Recommend, in documentation/UI copy, that a unique student ID column be added in future data exports.

### 5.2 Reference: Real Sample Data Statistics (for calibration/testing)
These are the actual statistics from the sample file used to validate this specification. Use them to build realistic test fixtures.

- Total rows: 1198
- Unique students: 584
- Unique course codes (`course_id`): 167
- Departments: 8 — `شبكات الحاسوب` (Computer Networks), `اتصالات` (Communications), `برمجيات` (Software), `تقنية معلومات` (IT), `ذكاء اصطناعي` (AI), `صناعية` (Industrial), `طاقة متجددة` (Renewable Energy), `ميكاترونيات` (Mechatronics)
- Max courses registered by a single student: 5
- Mean courses per student: ≈2.05
- Blank cells: none
- Course codes shared across more than one department (same `course_id`, different `المقرر` name per department): **54 codes** — this confirms the unification-by-code mechanism (§6, §7) is not an edge case but a routine, frequent scenario.
- Largest single course by enrollment: 96 students.
- Conflict graph (built from this sample): 167 nodes, **538 conflict edges**, max single-course degree = 47, maximum fully-interconnected clique = **9 courses**, greedy (DSATUR) coloring requires **9 days minimum**. This means a 12–14 day window (two weeks minus weekends) leaves a comfortable safety margin — infeasibility is unlikely with data of this shape, but the infeasibility-handling feature (§9) is still a required, first-class part of the system, not an edge case to skip.

---

## 6. Data Validation Rules

Validation runs immediately after upload, before any scheduling computation. Each rule is classified **Critical** (blocks progression until fixed) or **Warning** (does not block, shown for awareness).

| # | Rule | Class | Required user action |
|---|---|---|---|
| 1 | Any required column is blank in a row | Critical | Fill the cell or remove the row |
| 2 | `course_id` is blank | Critical | Cannot build the conflict graph without it; must be filled |
| 3 | Same `course_id` + same `القسم` (department), but two different `المقرر` (display name) values | Critical | User must pick/confirm the single correct name for that department. **Real example found in the sample data:** course code `C0508` in department `شبكات الحاسوب` appeared with two names, `الشبكات اللاسلكية والموبايل` and `شبكات لاسلكية والاتصالات الخلوية`; confirmed by the product owner to be the same course and unified. |
| 4 | Same `course_id`, different `المقرر` names **across different departments** | Not an error — expected | No action. This is legitimate (a shared course labeled differently per department). Confirmed to occur 54 times in the real sample. |
| 5 | Identical `المقرر` name string linked to two different `course_id` values | Warning | Manual review to confirm they really are two distinct courses |
| 6 | Exact full student name duplicated across rows | Warning | Confirm these are genuinely two different students, not a duplicate data-entry error |

---

## 7. Core Algorithm & Mathematical Model

### 7.1 Problem Framing: Graph Coloring
- Each unique `course_id` = one graph **node**.
- If at least one student is registered in both course A and course B, draw a conflict **edge** between A and B.
- Each available exam day = one **color**.
- Required solution: assign each course a day (color) such that no two courses connected by an edge share the same day.

### 7.2 Solver Choice: Constraint Programming (Google OR-Tools CP-SAT) — Required, Not Optional
Greedy heuristic graph-coloring algorithms (e.g., Welsh-Powell, DSATUR) do **not** guarantee a valid solution within a fixed number of days — they can produce a colorable-looking assignment that still has hidden faults in edge cases, or simply fail to find the best packing. This system requires a **hard-constraint exact solver**:

- Use **Google OR-Tools, CP-SAT solver**.
- Zero conflicts must be enforced as a hard constraint inside the model itself, not as a post-hoc check. The solver either returns a certified valid solution or returns `INFEASIBLE` — there is no third outcome where an invalid schedule is returned.
- A fast greedy algorithm (e.g., DSATUR) MAY be used internally only as a pre-solve heuristic (e.g., to warm-start the solver or quickly estimate a lower bound on days needed for diagnostics), but the **authoritative, user-facing schedule must come from CP-SAT.**

### 7.3 Model Formulation

```
Sets:
  C = set of unique course_id values
  D = set of available exam days (full date range minus excluded weekends/holidays)

Variables:
  day[c] ∈ D   for each course c ∈ C

Hard constraint:
  for every conflicting pair (c1, c2)   →   day[c1] ≠ day[c2]
  (a pair (c1, c2) is "conflicting" if at least one student is registered in both c1 and c2)

Objective:
  Maximize even/dense utilization of available days
  (e.g., minimize the maximum number of days used beyond necessary, or minimize variance
   of course-count across days — exact objective formula is an implementation detail,
   but the goal is: do not needlessly cluster courses into few days while leaving others empty)
```

### 7.4 Guaranteed Properties
- Zero conflicts for any student is mathematically guaranteed for any schedule the system labels as "successful" — regardless of how many courses a single student has (2 courses or 5 courses, as seen in the real data, are handled identically and correctly by the pairwise constraint).
- If the solver returns `INFEASIBLE`, the system **must never** fall back to displaying a partial, best-effort, or conflict-containing schedule. It must transition to the diagnostic flow (§9 / FR-5).

---

## 8. Functional Requirements

### FR-1: File Upload & Validation
- Support `.xlsx` upload via drag-and-drop or manual file picker.
- Provide a downloadable official Excel template matching the 5-column schema in §5.
- Run all validation rules from §6 immediately on upload, before any other processing.
- Present a detailed error/warning report: row number, error type, offending value(s).
- Allow inline correction of individual cells, or full re-upload.
- Block progression to the settings step until all **Critical** issues are resolved.

### FR-2: Exam Period Configuration
- Configure exam period start date and end date (default: two weeks).
- Configure excluded weekly rest days (configurable, not hardcoded — e.g., Friday, or Friday+Saturday, depending on institution).
- Allow marking additional ad-hoc excluded dates (public holidays).
- Enforce exactly one exam slot per day per course (no AM/PM double-booking) — this is a fixed product rule, not a configurable option.

### FR-3: Scheduling Engine
- Build the unified `course_id` as the sole key for conflict detection, independent of any `المقرر` display-name variation across departments.
- Build the conflict graph from student registrations (§7.1).
- Run CP-SAT (§7.2–7.3) to produce a conflict-free, day-dense assignment.
- On success → proceed to FR-4 (results). On failure (`INFEASIBLE`) → proceed to FR-5 (diagnostics).

### FR-4: Results Display & Export
- Display the final schedule as a calendar-style view (days as columns/tabs, courses listed within each day).
- For each student/department context, display the course under its department-specific `المقرر` name — even though the same `course_id` is scheduled once, globally, on a single day.
- Provide filtering by department and search by student name or course name.
- Export to Excel: one master schedule (all departments, all name variants shown together) and one schedule per department (only that department's course names).
- Prominently display a zero-conflict status indicator at the top of the results view.

### FR-5: Infeasibility Diagnostic Report
Triggered whenever CP-SAT returns `INFEASIBLE`. Must include:
- Computation of the **maximum clique** in the conflict graph → this is the mathematically exact lower bound on the number of days required. Report it as a specific number.
- A ranked list of the students with the highest number of registered courses (most likely root cause contributors).
- A ranked list of the most highly-connected ("bottleneck") courses in the conflict graph.
- Concrete, numeric suggestions, e.g.: "You need at least N additional exam days" (N = max clique size − number of currently available days). Each suggestion should deep-link to the relevant settings/data screen to act on it.
- A "re-run" action that re-invokes the solver immediately after the user makes a fix, without re-uploading the file.

---

## 9. End-to-End Flow

1. Upload Excel file.
2. Run validation (§6); display error/warning report.
3. User resolves all Critical issues.
4. User configures exam period (dates, excluded days).
5. Run scheduling engine (§7).
6. **Success path:** show interactive results (FR-4) + export.
7. **Failure path:** show infeasibility diagnostics (FR-5) → user adjusts settings/data → return to step 5.

---

## 10. UI / Screens Specification

### 10.1 Upload Screen
Drag-and-drop area for the file; button to download the official template; a concise visual checklist of file requirements before upload.

### 10.2 Data Validation Screen
Table of all flagged rows, classified Critical/Warning, with inline cell correction or full re-upload. Progression is blocked while Critical issues remain.

### 10.3 Exam Period Settings Screen
Start/end date pickers; interactive calendar to mark excluded days (weekly rest days + ad-hoc holidays); explicit note that one course = one full day (no AM/PM split).

### 10.4 Processing Screen
Progress indicator showing stages: reading data → building conflict graph → running solver.

### 10.5 Results Dashboard
Summary cards at top: conflict status (0 conflicts), total courses, days used, average courses/day. Below: calendar-style day-by-day course listing. Filtering by department; search by student/course. Excel export button.

### 10.6 Infeasibility Report Screen
Clear statement of the failure; table of the most problematic students/courses; numbered actionable suggestions each linking directly to the relevant fix screen; re-run button.

### 10.7 Course-Code Reference Screen (administrative/reference)
Table of `course_id` ↔ department-specific `المقرر` name mappings; editable and reusable across future exam cycles without rebuilding from scratch.

---

## 11. Outputs

- Master schedule (Excel): all days, all courses, with all department-specific name variants shown together per course.
- Per-department schedule (Excel): one file/sheet per department, showing only that department's course names.
- (When applicable) Exportable infeasibility diagnostic report, for sharing with stakeholders.

---

## 12. Non-Functional Requirements

| Requirement | Description |
|---|---|
| Correctness | 100% mathematical guarantee of zero conflicts for any schedule presented as "successful" — never an approximate or probabilistic result |
| Performance | Process files of the real sample's scale (~1200 rows, 584 students, 167 courses) in a few seconds |
| Arabic language & RTL support | Full Arabic text and right-to-left layout support across all UI screens and all exported files (the source data and all display strings are Arabic) |
| Usability | Prevent bad data from ever reaching the solver via clear, blocking, upfront validation rather than surfacing errors after the fact |
| Reusability | The course-code mapping (§5, §10.7) persists as a durable reference reusable across future exam cycles |
| Reliability | On infeasibility, the system must never display a partial or misleading schedule under any circumstance — only a fully valid success or an explicit failure report |

---

## 13. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Two different students share an identical full name (no student ID exists) | Low, based on current sample | Auto-flag exact name duplicates as a warning; recommend adding a unique student ID in future data exports |
| A very large single course (sample max: 96 students) increases conflict density | Medium | The secondary day-balancing objective mitigates clustering; surface such courses in the "bottleneck courses" diagnostic when relevant |
| Conflicting/duplicate naming for the same `course_id` not cleaned before upload | Medium (occurred once in the real sample) | Critical validation rule (§6, rule 3) blocks progression until resolved |
| Infeasible schedule in future, more complex exam cycles | Low with current data, plausible later | Max-clique-based diagnostic report and concrete suggestions (FR-5) — required as a first-class feature, not a rare edge case |

---

## 14. Acceptance Criteria

- Given a fully valid input file, the system produces a complete schedule within a few seconds with no manual intervention beyond configuration.
- Any schedule presented to the user as "successful" achieves zero conflicts, verifiable programmatically, not just by inspection.
- Every data issue classified Critical (§6) actually blocks reaching the scheduling step until resolved.
- On infeasibility, the system always surfaces a specific numeric minimum-additional-days figure — never a generic error message alone.
- Per-department export files contain only that department's approved course names — never another department's naming variant.

---

## 15. Assumptions & Constraints

- The input file has **no day/date column** — day assignment is entirely the system's responsibility, computed from scratch.
- Exactly one exam session per day is supported (no AM/PM split) — explicit, non-configurable product decision.
- Room/venue capacity and invigilator assignment are not managed in this phase.
- The student's full name is currently the only available student identifier; a unique student ID is recommended for future data but not assumed to exist.
- The 5-column schema in §5 (`اسم الطالب`, `القسم`, `رمز المادة`, `المقرر`, `الفصل`) is the authoritative template structure, derived from a real production data sample.

---

## 16. Suggested Technology Stack

| Layer | Suggested technology |
|---|---|
| Excel read/write | `pandas` + `openpyxl` |
| Scheduling solver | Google OR-Tools — CP-SAT solver |
| Backend | Python (FastAPI) |
| Frontend | React |

(Stack choices above are suggestions consistent with the reference prototype; the implementing agent may adapt within these constraints as long as the CP-SAT-based exact-solving requirement in §7.2 is preserved.)

---

## 17. Glossary

- **course_id**: The unified course code used as the sole key for conflict detection, independent of department-specific display naming.
- **Conflict**: Two courses conflict if at least one student is registered in both.
- **Conflict graph**: Graph where nodes are courses and edges represent conflicts.
- **Infeasible**: The technical solver state meaning no valid assignment of courses to available days exists that satisfies the hard no-conflict constraint.
- **Max Clique**: The largest set of courses that are all mutually conflicting; its size is the exact lower bound on the number of exam days required.
- **Hard constraint**: A rule the solver is mathematically forbidden from violating in any returned solution (as opposed to a soft/optimization preference).
