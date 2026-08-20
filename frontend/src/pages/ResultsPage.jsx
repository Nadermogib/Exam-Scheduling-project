import { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import { CheckCircle2, Book, Calendar, BarChart, Zap, CalendarDays, FileDown, Download, Loader, Printer, ClipboardList, PartyPopper } from 'lucide-react';
import api from '../api/client';
import PrintScheduleTable from '../components/PrintScheduleTable';
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
function Section({ title, icon, children, defaultOpen = true, className = "" }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`results-section ${className}`}>
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
  const [search, setSearch] = useState('');
  const [deptFilter, setDeptFilter] = useState('');
  const [dlMaster, setDlMaster] = useState(false);
  const [dlDept, setDlDept] = useState(false);

  // Phase 8-C/D: print table state
  const [headerText, setHeaderText] = useState(null);   // null = use dynamic default
  const [universityText, setUniversityText] = useState(null); // null = use default
  const [logoDataUrl, setLogoDataUrl] = useState(null);   // null = use default asset
  const [savingHeader, setSavingHeader] = useState(false);
  const printExportRef = useRef(null);
  const headerSaveTimer = useRef(null);

  // Load persisted print settings on mount
  useEffect(() => {
    api.get('/api/print-settings')
      .then(res => {
        if (res.data.header_text !== null) setHeaderText(res.data.header_text);
        if (res.data.university_text !== null) setUniversityText(res.data.university_text);
        if (res.data.logo_data_url !== null) setLogoDataUrl(res.data.logo_data_url);
      })
      .catch(() => {/* silently ignore — defaults will be used */ });
  }, []);

  // Debounced save of header text (800ms after last keystroke)
  const handleHeaderChange = useCallback((newText) => {
    setHeaderText(newText);
    setSavingHeader(true);
    clearTimeout(headerSaveTimer.current);
    headerSaveTimer.current = setTimeout(async () => {
      try {
        await api.patch('/api/print-settings', { header_text: newText });
      } catch {
        // silently ignore
      } finally {
        setSavingHeader(false);
      }
    }, 800);
  }, []);

  const handleUniversityTextChange = useCallback((newText) => {
    setUniversityText(newText);
    setSavingHeader(true);
    clearTimeout(headerSaveTimer.current);
    headerSaveTimer.current = setTimeout(async () => {
      try {
        await api.patch('/api/print-settings', { university_text: newText });
      } catch {
        // silently ignore
      } finally {
        setSavingHeader(false);
      }
    }, 800);
  }, []);

  // Logo upload: save to backend immediately
  const handleLogoUpload = useCallback(async (dataUrl) => {
    setLogoDataUrl(dataUrl);
    try {
      await api.patch('/api/print-settings', { logo_data_url: dataUrl });
    } catch { /* ignore */ }
  }, []);

  // Logo remove: delete from backend
  const handleLogoRemove = useCallback(async () => {
    setLogoDataUrl(null);
    try {
      await api.delete('/api/print-settings/logo');
    } catch { /* ignore */ }
  }, []);

  const { schedule, total_courses, days_used, max_load, wall_time_seconds,
    avg_courses_per_day, status } = result;

  /* ── Derive departments list from schedule ─────────────────────── */
  const departments = useMemo(() => {
    const depts = new Set();
    Object.values(schedule).forEach((courses) =>
      courses.forEach((c) => {
        if (c.variants) {
          Object.keys(c.variants).forEach((d) => depts.add(d));
        }
      })
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
          filtered = filtered.filter((c) => c.variants && deptFilter in c.variants);
        }

        // Text search: matches course_id or any display name
        if (q) {
          filtered = filtered.filter((c) => {
            if (c.course_id.toLowerCase().includes(q)) return true;
            if (c.variants) {
              return Object.values(c.variants).some((vs) =>
                vs.some((v) => v.display_name.toLowerCase().includes(q))
              );
            }
            return false;
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
      <div className="no-print">
        <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <PartyPopper size={28} color="var(--color-accent)" /> تم إنشاء الجدول بنجاح
        </h1>
        <p className="page-subtitle">
          الحالة: <strong style={{ color: 'var(--color-success)' }}>{status}</strong> —
          خالٍ تماماً من التعارضات (مضمون رياضياً).
          زمن الحل: {wall_time_seconds}ث
        </p>
      </div>

      {/* ── Summary cards (P5-T1) ────────────────────────────────── */}
      <div className="summary-cards">
        <SummaryCard icon={<CheckCircle2 size={28} color="var(--color-success)" />} value="صفر" label="تعارضات" highlight />
        <SummaryCard icon={<Book size={28} color="var(--color-accent)" />} value={total_courses} label="مادة مجدولة" />
        <SummaryCard icon={<Calendar size={28} color="var(--color-accent)" />} value={days_used} label="أيام امتحانات" />
        <SummaryCard icon={<BarChart size={28} color="var(--color-accent)" />} value={max_load} label="أقصى مواد/يوم" />
        <SummaryCard icon={<Zap size={28} color="var(--color-accent)" />} value={avg_courses_per_day} label="متوسط مواد/يوم" />
      </div>

      {/* ── Controls bar (P5-T3, P5-T4) ─────────────────────────── */}
      <div className="controls-bar">
        <input
          id="search-courses"
          className="controls-bar__search"
          type="text"
          placeholder="ابحث برمز المادة أو اسمها…"
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
      <Section icon={<CalendarDays size={20} />} title="جدول الامتحانات يوماً بيوم" defaultOpen className="no-print">
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
                    // Flatten variants for display Name
                    const vs = c.variants ? (c.variants[deptFilter] || Object.values(c.variants)[0] || []) : [];
                    const displayName = vs.length > 0 ? vs[0].display_name : c.course_id;
                    const isMatch = search && (
                      c.course_id.toLowerCase().includes(search.toLowerCase()) ||
                      (c.variants && Object.values(c.variants).some((deptVs) => deptVs.some((v) => v.display_name.toLowerCase().includes(search.toLowerCase()))))
                    );
                    const tooltipText = c.variants ? Object.entries(c.variants).map(([d, deptVs]) => `${d}: ${deptVs.map(v => v.display_name).join('، ')}`).join('\n') : '';
                    return (
                      <div
                        key={c.course_id}
                        className={`course-chip${isMatch ? ' course-chip--highlighted' : ''}`}
                        title={tooltipText}
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
        <span className="export-bar__title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><FileDown size={20} /> تصدير الجدول:</span>
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
          {dlMaster ? <><Loader size={16} /> جارٍ التصدير…</> : <><Download size={16} /> الجدول الكامل (Excel)</>}
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
            {dlDept ? <><Loader size={16} /> …</> : <><Download size={16} /> جدول قسم {deptFilter}</>}
          </button>
        )}
      </div>

      {/* ── Print-ready table (Phase 8-C/D/E) ────────────────────────── */}
      <Section icon={<Printer size={20} />} title="جدول الطباعة الرسمي" defaultOpen={false}>
        <div style={{ padding: 'var(--space-2)' }}>
          <PrintScheduleTable
            schedule={schedule}
            departments={departments.slice(1)}
            deptFilter={deptFilter}
            exportRef={printExportRef}
            headerText={headerText}
            onHeaderChange={handleHeaderChange}
            universityText={universityText}
            onUniversityTextChange={handleUniversityTextChange}
            logoDataUrl={logoDataUrl}
            onLogoUpload={handleLogoUpload}
            onLogoRemove={handleLogoRemove}
            saving={savingHeader}
          />
        </div>
      </Section>


      {/* ── Bottom action ────────────────────────────────────────── */}
      <div className="no-print" style={{ display: 'flex', justifyContent: 'center', paddingBottom: 'var(--space-8)' }}>
        <button id="btn-new-schedule" className="btn btn-ghost" onClick={onRestart}>
          ↺ بدء جدولة جديدة
        </button>
      </div>
    </main>
  );
}
