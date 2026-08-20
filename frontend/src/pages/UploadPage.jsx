import { useRef, useState } from 'react';
import { ClipboardList, LayoutGrid, Type, Ruler, Globe, CheckCircle, Folder, FileSpreadsheet, AlertTriangle, Download } from 'lucide-react';
import { uploadFile, downloadTemplate } from '../api/client';
import './UploadPage.css';

const REQUIREMENTS = [
  { icon: <ClipboardList size={18} />, text: 'الصيغة: ملف Excel بامتداد .xlsx فقط' },
  { icon: <LayoutGrid size={18} />, text: 'خمسة أعمدة إلزامية: اسم الطالب · القسم · رمز المادة · المقرر · الفصل' },
  { icon: <Type size={18} />, text: 'رموز المواد (course_id) يجب أن تكون متسقة في جميع الصفوف' },
  { icon: <Ruler size={18} />, text: 'الحجم الأقصى للملف: 20 ميغابايت' },
  { icon: <Globe size={18} />, text: 'يدعم النص العربي والإنجليزي في خلايا البيانات' },
];

export default function UploadPage({ onUploadSuccess }) {
  const [file, setFile]           = useState(null);
  const [dragOver, setDragOver]   = useState(false);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState(null);
  const [dlLoading, setDlLoading] = useState(false);
  const inputRef = useRef();

  /* ── File selection ──────────────────────────────────────────────── */
  const acceptFile = (f) => {
    setError(null);
    if (!f) return;
    if (!f.name.toLowerCase().endsWith('.xlsx')) {
      setError('يُقبل فقط ملفات بصيغة .xlsx — يُرجى اختيار ملف Excel صحيح.');
      return;
    }
    if (f.size > 20 * 1024 * 1024) {
      setError('حجم الملف يتجاوز 20 ميغابايت. يُرجى اختيار ملف أصغر حجماً.');
      return;
    }
    setFile(f);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    acceptFile(e.dataTransfer.files[0]);
  };

  /* ── Upload ──────────────────────────────────────────────────────── */
  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const data = await uploadFile(file);
      onUploadSuccess(data);
    } catch (err) {
      setError(err.userMessage || 'حدث خطأ أثناء رفع الملف. يُرجى المحاولة مجدداً.');
    } finally {
      setLoading(false);
    }
  };

  /* ── Template download ───────────────────────────────────────────── */
  const handleTemplate = async () => {
    setDlLoading(true);
    try {
      const blob = await downloadTemplate();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = 'exam_schedule_template.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError('تعذّر تحميل القالب. تحقق من أن الخادم يعمل وأعد المحاولة.');
    } finally {
      setDlLoading(false);
    }
  };

  /* ── Render ──────────────────────────────────────────────────────── */
  const dropCls = [
    'drop-zone',
    dragOver ? 'drop-zone--drag-over' : '',
    file      ? 'drop-zone--selected'  : '',
  ].join(' ');

  return (
    <main className="upload-page">
      {/* Header */}
      <div>
        <h1 className="page-title">رفع ملف التسجيل</h1>
        <p className="page-subtitle">
          ارفع ملف Excel المصدّر من نظام التسجيل ليبدأ النظام في التحقق من البيانات تلقائياً.
        </p>
      </div>

      {/* Drop zone */}
      <div
        id="drop-zone"
        className={dropCls}
        onDragEnter={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragOver={(e)  => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={()  => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current.click()}
        role="button"
        tabIndex={0}
        aria-label="منطقة رفع الملف"
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current.click()}
      >
        <input
          ref={inputRef}
          id="file-input"
          className="drop-zone__input"
          type="file"
          accept=".xlsx"
          onChange={(e) => acceptFile(e.target.files[0])}
        />

        <span className="drop-zone__icon">
          {file ? <CheckCircle size={48} color="var(--color-success)" /> : <Folder size={48} color="var(--color-text-muted)" />}
        </span>

        {file ? (
          <>
            <p className="drop-zone__title">تم اختيار الملف</p>
            <div className="drop-zone__selected-name">
              <FileSpreadsheet size={16} />
              <span>{file.name}</span>
              <span style={{ color: 'var(--color-text-muted)', fontWeight: 400 }}>
                ({(file.size / 1024).toFixed(0)} KB)
              </span>
            </div>
            <p className="drop-zone__sub" style={{ marginTop: 'var(--space-3)' }}>
              انقر للتغيير أو اسحب ملفاً آخر
            </p>
          </>
        ) : (
          <>
            <p className="drop-zone__title">اسحب وأفلت ملف Excel هنا</p>
            <p className="drop-zone__sub">أو انقر لاستعراض الملفات</p>
          </>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="upload-error" role="alert">
          <AlertTriangle size={20} />
          <span>{error}</span>
        </div>
      )}

      {/* Actions */}
      <div className="upload-actions">
        <button
          id="btn-upload"
          className="btn btn-primary"
          disabled={!file || loading}
          onClick={handleUpload}
        >
          {loading ? (
            <span className="btn-loading">
              <span className="spinner" /> جارٍ رفع الملف...
            </span>
          ) : (
            'رفع الملف والتحقق من البيانات ←'
          )}
        </button>

        <button
          id="btn-template"
          className="btn btn-secondary"
          onClick={handleTemplate}
          disabled={dlLoading}
        >
          {dlLoading ? 'جارٍ التحميل...' : <><Download size={16} /> تحميل قالب Excel</>}
        </button>
      </div>

      {/* Requirements checklist */}
      <div className="requirements-card">
        <p className="requirements-card__title">متطلبات الملف</p>
        <ul className="requirements-list">
          {REQUIREMENTS.map((r, i) => (
            <li key={i}>
              <span className="req-icon">{r.icon}</span>
              <span>{r.text}</span>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
