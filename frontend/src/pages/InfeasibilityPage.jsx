import { useState } from 'react';
import api from '../api/client';
import './ResultsPage.css'; /* reuse shared styles */

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

/* ── Infeasibility metric card ─────────────────────────────────────────────── */
function MetricCard({ icon, value, label, danger }) {
  return (
    <div className={`summary-card${danger ? '' : ''}`} style={danger ? { borderColor: 'var(--color-error)', background: 'rgba(248,81,73,0.05)' } : {}}>
      <span className="summary-card__icon">{icon}</span>
      <span className="summary-card__value" style={{ color: danger ? 'var(--color-error)' : 'var(--color-warning)' }}>
        {value}
      </span>
      <span className="summary-card__label">{label}</span>
    </div>
  );
}

/* ── Main InfeasibilityPage ────────────────────────────────────────────────── */
export default function InfeasibilityPage({ result, sessionId, onBack, onRestart }) {
  const [studentsOpen,  setStudentsOpen]  = useState(true);
  const [coursesOpen,   setCoursesOpen]   = useState(true);
  const [dlExport,      setDlExport]      = useState(false);

  const {
    available_days,
    min_days_required,
    additional_days_needed,
    wall_time_seconds,
    top_students      = [],
    bottleneck_courses = [],
    suggestions       = [],
  } = result;

  return (
    <main className="results-page">
      {/* ── Header ───────────────────────────────────────────────── */}
      <div>
        <h1 className="page-title" style={{ color: 'var(--color-error)' }}>
          ⚠️ الجدولة غير ممكنة في الفترة المحددة
        </h1>
        <p className="page-subtitle">
          أثبت محلل CP-SAT رياضياً أنه لا يوجد جدول خالٍ من التعارضات مع الأيام المتاحة الحالية.
          هذا ليس خطأً في البيانات — بل قيداً رياضياً صارماً ناتجاً عن بنية التسجيل.
          زمن التحليل: {wall_time_seconds}ث
        </p>
      </div>

      {/* ── Metric cards (P6-T1) ─────────────────────────────────── */}
      <div className="summary-cards">
        <MetricCard icon="📅" value={available_days}       label="أيام متاحة حالياً" />
        <MetricCard icon="🧮" value={min_days_required}    label="الحد الأدنى المطلوب" danger />
        <MetricCard icon="➕" value={additional_days_needed} label="أيام إضافية مطلوبة" danger />
      </div>

      {/* ── Math explanation ─────────────────────────────────────── */}
      <div className="results-section">
        <div className="results-section__header" style={{ cursor: 'default' }}>
          <div className="results-section__title">
            <span>📐</span>شرح القيد الرياضي
          </div>
        </div>
        <div style={{ padding: 'var(--space-5) var(--space-6)', lineHeight: 1.8, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)' }}>
          <p>
            الحد الأدنى لعدد أيام الامتحانات يساوي حجم <strong style={{ color: 'var(--color-accent)' }}>أكبر عيارة (clique)</strong> في مصفوفة التعارض.
            العيارة هي مجموعة من المواد يشترك كل طالبَين منها في طالب واحد على الأقل،
            ومن ثمَّ يجب جدولة كل منها في يوم مستقل.
          </p>
          <p style={{ marginTop: 'var(--space-3)' }}>
            أكبر عيارة في بياناتك تحتوي على <strong style={{ color: 'var(--color-error)' }}>{min_days_required}</strong> مادة،
            بينما الأيام المتاحة هي <strong>{available_days}</strong> فقط.
            يجب إضافة <strong style={{ color: 'var(--color-error)' }}>{additional_days_needed}</strong> يوم
            على الأقل لاستيعاب هذه المجموعة.
          </p>
        </div>
      </div>

      {/* ── Numbered suggestions (P6-T5) ────────────────────────── */}
      {suggestions.length > 0 && (
        <div className="results-section">
          <div className="results-section__header" style={{ cursor: 'default' }}>
            <div className="results-section__title"><span>💡</span>توصيات محددة</div>
          </div>
          <div style={{ padding: 'var(--space-5) var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            {suggestions.map((s) => (
              <div key={s.id} style={{
                display: 'flex', gap: 'var(--space-4)', alignItems: 'flex-start',
                padding: 'var(--space-4)', background: 'var(--color-surface-2)',
                borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)',
              }}>
                <span style={{
                  width: 28, height: 28, borderRadius: '50%',
                  background: 'var(--color-accent)', color: '#0d1117',
                  fontWeight: 900, fontSize: 'var(--font-size-sm)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                }}>{s.id}</span>
                <div>
                  <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-primary)', fontWeight: 600 }}>
                    {s.action === 'extend_period' ? '⟳ تمديد فترة الامتحانات' : '🔍 مراجعة بيانات الطالب'}
                  </p>
                  <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', marginTop: 4 }}>
                    {s.message}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Top students (P6-T2) ─────────────────────────────────── */}
      <div className="results-section">
        <div
          className="results-section__header"
          onClick={() => setStudentsOpen((o) => !o)}
          role="button" tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && setStudentsOpen((o) => !o)}
        >
          <div className="results-section__title">
            <span>👥</span>الطلاب الأكثر تأثيراً على التعقيد
          </div>
          <span className="section-chevron">{studentsOpen ? '▲' : '▼'}</span>
        </div>
        {studentsOpen && top_students.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table className="reference-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>اسم الطالب</th>
                  <th>عدد المواد</th>
                  <th>رموز المواد</th>
                </tr>
              </thead>
              <tbody>
                {top_students.map((s, i) => (
                  <tr key={i}>
                    <td style={{ color: 'var(--color-text-muted)', fontVariantNumeric: 'tabular-nums' }}>{i + 1}</td>
                    <td style={{ fontWeight: 700 }}>{s.name}</td>
                    <td>
                      <span style={{
                        background: 'rgba(248,81,73,0.15)', color: 'var(--color-error)',
                        borderRadius: 999, padding: '1px 10px', fontWeight: 700, fontSize: 'var(--font-size-xs)',
                      }}>{s.course_count}</span>
                    </td>
                    <td style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                      {s.courses.join(' · ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Bottleneck courses (P6-T3) ───────────────────────────── */}
      <div className="results-section">
        <div
          className="results-section__header"
          onClick={() => setCoursesOpen((o) => !o)}
          role="button" tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && setCoursesOpen((o) => !o)}
        >
          <div className="results-section__title">
            <span>🕸️</span>المواد الأكثر تعارضاً (أعلى درجة في المصفوفة)
          </div>
          <span className="section-chevron">{coursesOpen ? '▲' : '▼'}</span>
        </div>
        {coursesOpen && bottleneck_courses.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table className="reference-table">
              <thead>
                <tr>
                  <th>رمز المادة</th>
                  <th>عدد التعارضات</th>
                  <th>الأقسام</th>
                </tr>
              </thead>
              <tbody>
                {bottleneck_courses.map((c, i) => (
                  <tr key={i}>
                    <td><code style={{ color: 'var(--color-accent)', fontWeight: 700 }}>{c.course_id}</code></td>
                    <td>
                      <span style={{
                        background: 'rgba(255,176,0,0.15)', color: 'var(--color-warning)',
                        borderRadius: 999, padding: '1px 10px', fontWeight: 700, fontSize: 'var(--font-size-xs)',
                      }}>{c.degree}</span>
                    </td>
                    <td style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)' }}>
                      {Object.entries(c.display_names).map(([d, n]) => `${d}: ${n}`).join(' | ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {/* ── Export bar (P6-T6) ───────────────────────────────────── */}
      <div className="export-bar" style={{ justifyContent: 'center' }}>
        <span className="export-bar__title">📥 تصدير التقرير:</span>
        <button
          id="btn-export-infeasible"
          className="btn btn-primary"
          disabled={dlExport}
          onClick={() => doExport(
            `/api/export/infeasibility?session_id=${sessionId}`,
            'تقرير_عدم_إمكانية_الجدولة.xlsx',
            setDlExport
          )}
        >
          {dlExport ? '⏳ جارٍ التصدير…' : '⬇ تقرير عدم الإمكانية (Excel)'}
        </button>
      </div>

      {/* ── Actions ──────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'center', paddingBottom: 'var(--space-8)' }}>
        <button id="btn-back-to-settings" className="btn btn-secondary" onClick={onBack}>
          ← تعديل الإعدادات
        </button>
        <button id="btn-restart-infeasible" className="btn btn-ghost" onClick={onRestart}>
          ↺ بدء جدولة جديدة
        </button>
      </div>
    </main>
  );
}
