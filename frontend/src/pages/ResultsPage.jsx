import { useState, useMemo } from 'react';
import api from '../api/client';
import CourseReferenceTable from '../components/CourseReferenceTable';
import './ResultsPage.css';

/* ── Summary card ──────────────────────────────────────────────────────────── */
function SummaryCard({ icon, value, label, highlight }) {
  return (
    <div className={`summary-card${highlight ? ' summary-card--highlight' : ''}`}>
      <span className="summary-card__icon">{icon}</span>
      <span className="summary-card__value">{value}</span>
      <span className="summary-card__label">{label}</span>
    </div>
  );
}

/* ── Collapsible section ───────────────────────────────────────────────────── */
function Section({ title, icon, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="results-section">
      <div
        className="results-section__header"
        onClick={() => setOpen((o) => !o)}
        role="button" tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && setOpen((o) => !o)}
      >
        <div className="results-section__title">
          <span>{icon}</span>{title}
        </div>
        <span className="section-chevron">{open ? '▲' : '▼'}</span>
      </div>
      {open && children}
    </div>
  );
}

/* ── Export helper ─────────────────────────────────────────────────────────── */
function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

async function doExport(url, filename, setLoading) {
  setLoading(true);
  try {
    const resp = await api.get(url, { responseType: 'blob' });
    triggerDownload(resp.data, filename);
  } catch (e) {
    alert(e.userMessage || 'تعذّر تنزيل الملف.');
  } finally {
    setLoading(false);
  }
}

/* ── Main ResultsPage ──────────────────────────────────────────────────────── */
export default function ResultsPage({ result, sessionId, onRestart }) {
  const [search,       setSearch]       = useState('');
  const [deptFilter,   setDeptFilter]   = useState('');
  const [dlMaster,     setDlMaster]     = useState(false);
  const [dlDept,       setDlDept]       = useState(false);
  const [refOpen,      setRefOpen]      = useState(false);

  const { schedule, total_courses, days_used, max_load, wall_time_seconds,
          avg_courses_per_day, status } = result;

  /* ── Derive departments list from schedule ─────────────────────── */
  const departments = useMemo(() => {
    const depts = new Set();
    Object.values(schedule).forEach((courses) =>
      courses.forEach((c) => Object.keys(c.display_names).forEach((d) => depts.add(d)))
    );
    return ['', ...Array.from(depts).sort()];
  }, [schedule]);

  /* ── Filter + search logic ─────────────────────────────────────── */
  const filteredSchedule = useMemo(() => {
    const q = search.trim().toLowerCase();
    return Object.entries(schedule)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, courses]) => {
        let filtered = courses;

        // Department filter
        if (deptFilter) {
          filtered = filtered.filter((c) => deptFilter in c.display_names);
        }

        // Text search: matches course_id or any display name
        if (q) {
          filtered = filtered.filter((c) => {
            if (c.course_id.toLowerCase().includes(q)) return true;
            return Object.values(c.display_names).some((n) => n.toLowerCase().includes(q));
          });
        }

        return { date, courses: filtered };
      })
      .filter(({ courses }) => courses.length > 0);
  }, [schedule, deptFilter, search]);



  /* ── Render ────────────────────────────────────────────────────── */
  return (
    <main className="results-page">
      {/* ── Header ───────────────────────────────────────────────── */}
      <div>
        <h1 className="page-title">🎉 تم إنشاء الجدول بنجاح</h1>
        <p className="page-subtitle">
          الحالة: <strong style={{ color: 'var(--color-success)' }}>{status}</strong> —
          خالٍ تماماً من التعارضات (مضمون رياضياً).
          زمن الحل: {wall_time_seconds}ث
        </p>
      </div>

      {/* ── Summary cards (P5-T1) ────────────────────────────────── */}
      <div className="summary-cards">
        <SummaryCard icon="✅" value="صفر" label="تعارضات" highlight />
        <SummaryCard icon="📚" value={total_courses} label="مادة مجدولة" />
        <SummaryCard icon="📅" value={days_used}     label="أيام امتحانات" />
        <SummaryCard icon="📊" value={max_load}      label="أقصى مواد/يوم" />
        <SummaryCard icon="⚡" value={avg_courses_per_day} label="متوسط مواد/يوم" />
      </div>

      {/* ── Controls bar (P5-T3, P5-T4) ─────────────────────────── */}
      <div className="controls-bar">
        <input
          id="search-courses"
          className="controls-bar__search"
          type="text"
          placeholder="🔍 ابحث برمز المادة أو اسمها…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="بحث في المواد"
        />
        <select
          id="dept-filter"
          className="controls-bar__select"
          value={deptFilter}
          onChange={(e) => setDeptFilter(e.target.value)}
          aria-label="فلترة حسب القسم"
        >
          <option value="">جميع الأقسام</option>
          {departments.slice(1).map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        {(search || deptFilter) && (
          <button
            className="btn btn-ghost"
            style={{ padding: 'var(--space-3)' }}
            onClick={() => { setSearch(''); setDeptFilter(''); }}
          >
            ✕ إلغاء الفلتر
          </button>
        )}
      </div>

      {/* ── Schedule calendar (P5-T2) ────────────────────────────── */}
      <Section icon="🗓️" title="جدول الامتحانات يوماً بيوم" defaultOpen>
        <div className="schedule-grid" style={{ padding: 'var(--space-4)' }}>
          {filteredSchedule.length === 0 ? (
            <div className="no-results">لا توجد نتائج مطابقة للبحث أو الفلتر المختار.</div>
          ) : (
            filteredSchedule.map(({ date, courses }) => (
              <div
                key={date}
                className={`schedule-day${search || deptFilter ? ' schedule-day--highlighted' : ''}`}
              >
                <div className="schedule-day__header">
                  <span className="schedule-day__date">{date}</span>
                  <span className="schedule-day__count">{courses.length} مادة</span>
                </div>
                <div className="schedule-day__courses">
                  {courses.map((c) => {
                    const displayName = deptFilter
                      ? (c.display_names[deptFilter] || Object.values(c.display_names)[0])
                      : Object.values(c.display_names)[0];
                    const isMatch = search && (
                      c.course_id.toLowerCase().includes(search.toLowerCase()) ||
                      Object.values(c.display_names).some((n) => n.toLowerCase().includes(search.toLowerCase()))
                    );
                    return (
                      <div
                        key={c.course_id}
                        className={`course-chip${isMatch ? ' course-chip--highlighted' : ''}`}
                        title={Object.entries(c.display_names).map(([d, n]) => `${d}: ${n}`).join('\n')}
                      >
                        <span className="course-chip__id">{c.course_id}</span>
                        {displayName && <span className="course-chip__name">{displayName}</span>}
                        <span className="course-chip__students">{c.student_count} طالب</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>
      </Section>

      {/* ── Export bar (P5-T7) ───────────────────────────────────── */}
      <div className="export-bar">
        <span className="export-bar__title">📥 تصدير الجدول:</span>
        <button
          id="btn-export-master"
          className="btn btn-primary"
          disabled={dlMaster}
          onClick={() => doExport(
            `/api/export/master?session_id=${sessionId}`,
            'الجدول_الكامل.xlsx',
            setDlMaster
          )}
        >
          {dlMaster ? '⏳ جارٍ التصدير…' : '⬇ الجدول الكامل (Excel)'}
        </button>

        {deptFilter && (
          <button
            id="btn-export-dept"
            className="btn btn-secondary"
            disabled={dlDept}
            onClick={() => doExport(
              `/api/export/department/${encodeURIComponent(deptFilter)}?session_id=${sessionId}`,
              `جدول_${deptFilter}.xlsx`,
              setDlDept
            )}
          >
            {dlDept ? '⏳ …' : `⬇ جدول قسم ${deptFilter}`}
          </button>
        )}
      </div>

      {/* ── Course reference table (P5-T8, P7-T3) ──────────────────────── */}
      <Section icon="📋" title="جدول مرجعي: رموز المواد ومسمياتها" defaultOpen={false}>
        <CourseReferenceTable />
      </Section>

      {/* ── Bottom action ────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'center', paddingBottom: 'var(--space-8)' }}>
        <button id="btn-new-schedule" className="btn btn-ghost" onClick={onRestart}>
          ↺ بدء جدولة جديدة
        </button>
      </div>
    </main>
  );
}
