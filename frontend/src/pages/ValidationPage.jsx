import { useState } from 'react';
import { patchCell } from '../api/client';
import './ValidationPage.css';

/* ── Inline editable cell ──────────────────────────────────────────────────── */
function EditableCell({ sessionId, row, field, value, severity, onPatched }) {
  const [editing, setEditing]   = useState(false);
  const [draft,   setDraft]     = useState(value ?? '');
  const [saving,  setSaving]    = useState(false);

  const commit = async () => {
    if (draft.trim() === (value ?? '').trim()) { setEditing(false); return; }
    setSaving(true);
    try {
      const data = await patchCell(sessionId, row, field, draft.trim());
      onPatched(data);
    } catch {/* error handling in parent via toast if needed */} finally {
      setSaving(false);
      setEditing(false);
    }
  };

  if (saving) return <span className="patching-spinner" title="جارٍ الحفظ..." />;

  if (editing) {
    return (
      <input
        autoFocus
        className="editable-cell__input"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter')  commit();
          if (e.key === 'Escape') { setDraft(value ?? ''); setEditing(false); }
        }}
        aria-label={`تعديل القيمة في الصف ${row}`}
      />
    );
  }

  return (
    <div className="editable-cell">
      <span
        className={`editable-cell__value${severity === 'warning' ? ' editable-cell__value--warning' : ''}`}
        onClick={() => { setDraft(value ?? ''); setEditing(true); }}
        title="انقر للتعديل"
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && setEditing(true)}
      >
        {value || <em style={{ opacity: 0.5 }}>(فارغ)</em>}
      </span>
      <span
        className="edit-icon"
        onClick={() => { setDraft(value ?? ''); setEditing(true); }}
        aria-hidden="true"
      >✏️</span>
    </div>
  );
}

/* ── Collapsible issues section ─────────────────────────────────────────────── */
function IssuesSection({ title, issues, sessionId, severity, onPatched }) {
  const [open, setOpen] = useState(true);
  const count = issues.length;
  const badgeCls = count === 0
    ? 'section-badge--ok'
    : severity === 'critical' ? 'section-badge--error' : 'section-badge--warning';

  return (
    <div className="validation-section">
      <div
        className="validation-section__header"
        onClick={() => setOpen((o) => !o)}
        role="button"
        aria-expanded={open}
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && setOpen((o) => !o)}
      >
        <div className="validation-section__title">
          <span className={`section-badge ${badgeCls}`}>{count}</span>
          {title}
        </div>
        <span className={`section-chevron${open ? ' section-chevron--open' : ''}`}>▲</span>
      </div>

      {open && (
        <div className="issues-table-wrap">
          {count === 0 ? (
            <div className="issues-empty">
              {severity === 'critical' ? '✅ لا توجد أخطاء حرجة' : '✅ لا توجد تحذيرات'}
            </div>
          ) : (
            <table className="issues-table" aria-label={title}>
              <thead>
                <tr>
                  <th>الصف</th>
                  <th>القاعدة</th>
                  <th>العمود</th>
                  <th>القيمة (انقر للتعديل)</th>
                  <th>الوصف</th>
                </tr>
              </thead>
              <tbody>
                {issues.map((issue, i) => (
                  <tr key={i}>
                    <td><span className="row-number">{issue.row ?? '—'}</span></td>
                    <td>
                      <span className={`rule-chip rule-chip--${issue.severity === 'critical' ? 'error' : 'warning'}`}>
                        Q{issue.rule}
                      </span>
                    </td>
                    <td>{issue.column_label ?? issue.column ?? '—'}</td>
                    <td>
                      {issue.row && issue.column ? (
                        <EditableCell
                          sessionId={sessionId}
                          row={issue.row}
                          field={issue.column}
                          value={issue.offending_value}
                          severity={issue.severity}
                          onPatched={onPatched}
                        />
                      ) : (
                        <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-xs)' }}>
                          {issue.offending_value ?? '—'}
                        </span>
                      )}
                    </td>
                    <td className="message-cell">{issue.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Main ValidationPage ───────────────────────────────────────────────────── */
export default function ValidationPage({ uploadData, onValidated, onBack }) {
  const [report, setReport] = useState({
    errors:    uploadData.errors   ?? [],
    warnings:  uploadData.warnings ?? [],
    is_valid:  uploadData.is_valid,
    row_count: uploadData.row_count,
  });
  const sessionId = uploadData.session_id;

  // Called whenever the backend returns a fresh report (after a PATCH)
  const handlePatched = (freshData) => {
    setReport({
      errors:    freshData.errors   ?? [],
      warnings:  freshData.warnings ?? [],
      is_valid:  freshData.is_valid,
      row_count: freshData.row_count,
    });
  };

  const canProceed = report.is_valid;

  return (
    <main className="validation-page">
      {/* Header */}
      <div>
        <h1 className="page-title">مراجعة البيانات والتحقق</h1>
        <p className="page-subtitle">
          تم تحليل <strong>{report.row_count}</strong> صفاً من الملف.
          يمكنك تصحيح القيم مباشرةً في الجدول دون الحاجة لإعادة رفع الملف.
        </p>
      </div>

      {/* Summary banner */}
      <div className={`validation-summary validation-summary--${canProceed ? 'ok' : 'error'}`}>
        <span>{canProceed ? '✅' : '🚫'}</span>
        {canProceed
          ? `البيانات صحيحة — يمكنك المتابعة. (تحذيرات: ${report.warnings.length})`
          : `يوجد ${report.errors.length} خطأ حرج يجب تصحيحه قبل المتابعة.`
        }
      </div>

      {/* Critical errors */}
      <IssuesSection
        title="أخطاء حرجة — تمنع المتابعة"
        issues={report.errors}
        sessionId={sessionId}
        severity="critical"
        onPatched={handlePatched}
      />

      {/* Warnings */}
      <IssuesSection
        title="تحذيرات — لا تمنع المتابعة"
        issues={report.warnings}
        sessionId={sessionId}
        severity="warning"
        onPatched={handlePatched}
      />

      {/* Gate + actions */}
      <div>
        <div className={`gate-banner gate-banner--${canProceed ? 'clear' : 'blocked'}`}>
          <span>{canProceed ? '🟢' : '🔴'}</span>
          {canProceed
            ? 'جميع الأخطاء الحرجة تم حلّها — المتابعة إلى إعدادات الفترة متاحة.'
            : `يجب تصحيح ${report.errors.length} خطأ حرج قبل المتابعة — انقر على أي قيمة في العمود الرابع لتعديلها.`
          }
        </div>
      </div>

      <div className="validation-actions">
        <button id="btn-back-upload" className="btn btn-ghost" onClick={onBack}>
          ← العودة
        </button>
        <div className="validation-actions__info">
          جلسة: <code style={{ fontSize: '0.7rem' }}>{sessionId.slice(0, 8)}…</code>
        </div>
        <button
          id="btn-proceed-settings"
          className="btn btn-primary"
          disabled={!canProceed}
          onClick={() => onValidated(sessionId, report)}
        >
          المتابعة إلى إعدادات الفترة ←
        </button>
      </div>
    </main>
  );
}
