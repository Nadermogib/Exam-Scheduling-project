/**
 * PrintScheduleTable — Phase 8-C / 8-D / 8-E
 *
 * Renders a print-ready, university-style exam grid table:
 *   Rows    = exam days (Arabic day name + date)
 *   Columns = departments (one column per dept, or single column when filtered)
 *
 * Props
 * -----
 *   schedule    {Object}  — { "YYYY-MM-DD": [{course_id, display_names, academic_level, ...}] }
 *   departments {string[]} — ordered list of all dept names (without the "" first entry)
 *   deptFilter  {string}  — currently selected dept ("" = all)
 *   exportRef   {ref}     — forwarded ref on the exportable area div (for html2canvas)
 *   headerText  {string}  — editable title (controlled from parent)
 *   onHeaderChange {fn}   — called when user edits the title text
 *   universityText {string} — editable university/faculty name (controlled from parent)
 *   onUniversityTextChange {fn} — called when user edits the university text
 *   logoDataUrl {string|null} — base-64 data URL of custom logo, or null → default
 *   onLogoUpload  {fn}    — called with new base-64 data URL when user uploads
 *   onLogoRemove  {fn}    — called when user clicks "إزالة الشعار المخصص"
 *   saving      {bool}    — shows saving indicator next to title
 */
import { useRef, useState } from 'react';
import { toPng } from 'html-to-image';
import { Settings, Loader, FolderOpen, AlertTriangle, Download } from 'lucide-react';
import defaultLogo from '../assets/Taizz_University_logo.jpg';
import './PrintScheduleTable.css';

// ── Utility: normalise academic_level to "فX" format ─────────────────────────
export function normalizeLevel(raw) {
  if (!raw || raw.trim() === '') return '';
  let s = raw.trim();
  // Strip known Arabic prefixes
  s = s.replace(/^الفصل\s+الـ?\s*/u, '');
  s = s.replace(/^الفصل\s*/u, '');
  s = s.replace(/^ف+/u, '');  // strip one or more leading ف
  s = s.trim();
  return s ? `ف${s}` : '';
}

// ── Utility: get Arabic weekday name from an ISO date string ──────────────────
const DAY_NAMES_AR = ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'];

function arabicDayName(isoDate) {
  // Parse as local date to avoid UTC offset issues
  const [y, m, d] = isoDate.split('-').map(Number);
  const dayIndex = new Date(y, m - 1, d).getDay();
  return DAY_NAMES_AR[dayIndex] ?? isoDate;
}

// ── Utility: compute dynamic default academic year header ─────────────────────
export function defaultHeaderText() {
  const y = new Date().getFullYear();
  return `جدول اختبارات الدور التكميلي للعام الجامعي ${y - 1}/${y}`;
}

// ── Sub-component: a single table cell ───────────────────────────────────────
function DeptCell({ courses, deptName }) {
  if (!courses || courses.length === 0) {
    return (
      <td className="col-dept">
        <span className="print-cell-empty">—</span>
      </td>
    );
  }

  return (
    <td className="col-dept">
      {courses.map((c) => {
        // Fallback for missing/malformed variants data
        let vs = c.variants?.[deptName] || [];
        if (vs.length === 0 && c.variants) {
          // If no variants for this specific dept but variants exist, pick first available
          const firstDept = Object.keys(c.variants)[0];
          if (firstDept) vs = c.variants[firstDept];
        }

        if (vs.length === 0) {
          return (
            <div key={c.course_id} className="print-course-entry">
              <span className="print-course-name">{c.course_id}</span>
            </div>
          );
        }

        return (
          <div key={c.course_id} style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '8px', borderBottom: courses.length > 1 ? '1px dashed rgba(46,134,193,0.3)' : 'none', paddingBottom: courses.length > 1 ? '4px' : '0' }}>
            {vs.map((v, idx) => {
              const level = normalizeLevel(v.academic_level);
              return (
                <div key={`${c.course_id}-${idx}`} className="print-course-entry" style={{ marginBottom: 0 }}>
                  <span className="print-course-name">{v.display_name}</span>
                  {level && <span className="print-course-level">{level}</span>}
                </div>
              );
            })}
          </div>
        );
      })}
    </td>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function PrintScheduleTable({
  schedule,
  departments,
  deptFilter,
  exportRef,
  headerText,
  onHeaderChange,
  universityText,
  onUniversityTextChange,
  logoDataUrl,
  onLogoUpload,
  onLogoRemove,
  saving = false,
}) {
  const fileInputRef = useRef(null);
  const [exporting, setExporting] = useState(false);
  const [exportWarn, setExportWarn] = useState(false);

  // ── PNG export handler (Phase 8-E) ────────────────────────────────────────
  const MAX_EXPORT_HEIGHT_PX = 8000;

  async function exportTable() {
    const el = exportRef?.current;
    if (!el) return;

    // Size guard: warn if the element is too tall for a reliable render
    const { scrollHeight, scrollWidth } = el;
    if (scrollHeight > MAX_EXPORT_HEIGHT_PX) {
      setExportWarn(true);
      return;
    }
    setExportWarn(false);
    setExporting(true);

    // Wait a moment for React to apply exporting=true to the DOM, 
    // which removes the scrollbars so they don't appear in the PNG.
    await new Promise(resolve => setTimeout(resolve, 50));

    try {
      // html-to-image handles Arabic perfectly by using SVG foreignObject,
      // which uses the browser's native text shaping engine.
      await document.fonts.ready;

      const dataUrl = await toPng(el, {
        cacheBust: true,
        backgroundColor: '#ffffff',
        pixelRatio: 2, // 2x resolution
        // Force the capture width so it doesn't wrap artificially if the screen is narrow
        width: scrollWidth,
        height: scrollHeight,
        style: {
          transform: 'scale(1)',
          transformOrigin: 'top left',
          width: scrollWidth + 'px',
        }
      });

      const a = document.createElement('a');
      a.href = dataUrl;
      const deptSuffix = deptFilter ? `_${deptFilter}` : '';
      a.download = `جدول_الامتحانات${deptSuffix}.png`;
      a.click();
    } catch (err) {
      console.error('Export failed:', err);
      alert('تعذّر تصدير الجدول. يُرجى المحاولة مجدداً.');
    } finally {
      setExporting(false);
    }
  }

  // Which departments to show as columns
  const activeDepts = deptFilter ? [deptFilter] : departments;

  // Sort days chronologically
  const sortedDays = Object.entries(schedule)
    .sort(([a], [b]) => a.localeCompare(b))
    .filter(([, courses]) => {
      if (!deptFilter) return courses.length > 0;
      return courses.some((c) => c.variants && deptFilter in c.variants);
    });

  // Handle logo file upload
  function handleLogoFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => onLogoUpload(ev.target.result);
    reader.readAsDataURL(file);
    // Reset input so same file can be re-uploaded
    e.target.value = '';
  }

  const logoSrc = logoDataUrl || defaultLogo;
  const displayHeaderText = headerText || defaultHeaderText();
  const displayUniversityText = universityText || "جامعة تعز — كلية السعيد للهندسة وتقنية المعلومات";

  return (
    <div className="print-table-wrapper">

      {/* ── Controls (not exported) ─────────────────────────────────────── */}
      <div className="print-table-controls">
        <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', marginBottom: '-8px' }}>
          <span style={{ color: 'var(--color-text-primary)', fontWeight: 700, fontSize: '1.05rem', display: 'flex', alignItems: 'center', gap: '8px' }}><Settings size={18} /> إعدادات الترويسة</span>
          {saving && (
            <span style={{ fontSize: '0.85rem', color: '#f59e0b', fontWeight: 600, background: 'rgba(245, 158, 11, 0.15)', padding: '4px 10px', borderRadius: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Loader size={14} /> جارٍ الحفظ…
            </span>
          )}
        </div>

        <div className="print-controls-inputs">
          <div className="print-input-group">
            <label htmlFor="print-university-text">الجامعة والكلية:</label>
            <input
              id="print-university-text"
              type="text"
              value={universityText ?? ''}
              placeholder="جامعة تعز — كلية السعيد للهندسة وتقنية المعلومات"
              onChange={(e) => onUniversityTextChange(e.target.value)}
              aria-label="تعديل اسم الجامعة والكلية"
              dir="rtl"
            />
          </div>
          <div className="print-input-group">
            <label htmlFor="print-header-text">عنوان الجدول:</label>
            <input
              id="print-header-text"
              type="text"
              value={headerText ?? ''}
              placeholder={defaultHeaderText()}
              onChange={(e) => onHeaderChange(e.target.value)}
              aria-label="تعديل عنوان الجدول"
              dir="rtl"
            />
          </div>
        </div>

        <div className="print-controls-logo">
          <label>شعار الجامعة:</label>
          <div className="print-logo-box">
            <img src={logoSrc} alt="شعار الجامعة" className="print-table-logo-preview" />
            <div className="print-logo-actions">
              <button
                className="btn-logo-upload"
                onClick={() => fileInputRef.current?.click()}
                title="رفع شعار مخصص"
                style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <FolderOpen size={16} /> تغيير الشعار
              </button>
              {logoDataUrl && (
                <button className="btn-logo-remove" onClick={onLogoRemove} title="إزالة الشعار المخصص">
                  ✕ حذف
                </button>
              )}
            </div>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={handleLogoFile}
            aria-label="رفع شعار مخصص"
          />
        </div>
      </div>

      {/* ── Exportable area ─────────────────────────────────────────────── */}
      <div ref={exportRef} className="print-table-export-area">

        {/* Header */}
        <div className="print-table-header">
          {/* Logo box — right side (RTL) */}
          <div className="print-table-header__logo-box">
            <img src={logoSrc} alt="شعار جامعة تعز" className="print-table-header__logo" />
          </div>

          {/* Centered title */}
          <div className="print-table-header__title-block">
            <div className="print-table-header__university">{displayUniversityText}</div>
            <div className="print-table-header__main-title">{displayHeaderText}</div>
          </div>

          {/* Spacer so title stays centered */}
          <div className="print-table-header__spacer" aria-hidden="true" />
        </div>



        {/* Grid table */}
        <div style={{ overflowX: exporting ? 'visible' : 'auto' }}>
          <table className="print-grid-table">
            <thead>
              <tr>
                <th className="col-day">اليوم / التاريخ</th>
                {activeDepts.map((dept) => (
                  <th key={dept}>{dept}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedDays.map(([isoDate, courses]) => {
                // Filter to only relevant courses if single dept mode
                const dayCourses = deptFilter
                  ? courses.filter((c) => c.variants && deptFilter in c.variants)
                  : courses;

                // Build a lookup: dept → courses for this day
                const deptCourses = {};
                for (const dept of activeDepts) {
                  deptCourses[dept] = dayCourses.filter((c) => c.variants && dept in c.variants);
                }

                return (
                  <tr key={isoDate}>
                    <td className="col-day">
                      <span className="print-day-name">{arabicDayName(isoDate)}</span>
                      <span className="print-day-date">{isoDate}</span>
                    </td>
                    {activeDepts.map((dept) => (
                      <DeptCell key={dept} courses={deptCourses[dept]} deptName={dept} />
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>{/* end export area */}

      {/* ── Export button (Phase 8-E) ─────────────────────────────────────── */}
      <div className="print-table-actions">
        {exportWarn && (
          <div style={{
            width: '100%',
            textAlign: 'center',
            padding: '8px 16px',
            background: 'rgba(234, 179, 8, 0.12)',
            border: '1px solid rgba(234, 179, 8, 0.4)',
            borderRadius: '8px',
            color: '#b45309',
            fontSize: '0.85rem',
            marginBottom: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px'
          }}>
            <AlertTriangle size={18} /> الجدول كبير جدًا للتصدير كصورة واحدة، يُفضل تصغير الفترة الزمنية أو تصفية قسم واحد ثم التصدير.
          </div>
        )}
        <button
          id="btn-export-png"
          className="btn btn-primary"
          disabled={exporting}
          onClick={exportTable}
          style={{ minWidth: '180px' }}
        >
          {exporting ? <><Loader size={16} /> جارٍ التصدير…</> : <><Download size={16} /> تصدير الجدول (PNG)</>}
        </button>
      </div>

    </div>
  );
}
