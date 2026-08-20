import { useState, useMemo } from 'react';
import { CalendarRange, CalendarOff, CalendarDays, AlertTriangle } from 'lucide-react';
import './SettingsPage.css';

/* ── Helpers ────────────────────────────────────────────────────────────────── */
const WEEKDAYS = [
  { idx: 0, label: 'الإثنين' },
  { idx: 1, label: 'الثلاثاء' },
  { idx: 2, label: 'الأربعاء' },
  { idx: 3, label: 'الخميس' },
  { idx: 4, label: 'الجمعة' },
  { idx: 5, label: 'السبت' },
  { idx: 6, label: 'الأحد' },
];

const MONTH_NAMES_AR = [
  'يناير','فبراير','مارس','أبريل','مايو','يونيو',
  'يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر'
];

function parseDate(str) { return str ? new Date(str + 'T00:00:00') : null; }
function toISO(d)       { return d ? d.toISOString().slice(0, 10) : null; }
function sameDay(a, b)  { return a && b && toISO(a) === toISO(b); }

/* Return ordered list of schedulable dates (mirrors backend logic) */
function buildAvailableDates(startStr, endStr, excludedWeekdays, excludedISOs) {
  if (!startStr || !endStr) return [];
  const start = parseDate(startStr);
  const end   = parseDate(endStr);
  if (start > end) return [];
  const excSet = new Set(excludedISOs);
  const result = [];
  const cur = new Date(start);
  while (cur <= end) {
    const iso = toISO(cur);
    if (!excludedWeekdays.includes(cur.getDay() === 0 ? 6 : cur.getDay() - 1) && !excSet.has(iso)) {
      result.push(iso);
    }
    cur.setDate(cur.getDate() + 1);
  }
  return result;
}

/* ── Mini calendar ──────────────────────────────────────────────────────────── */
function MiniCalendar({ year, month, startISO, endISO, excludedWeekdays, excludedDates, onToggleDate, onNav }) {
  const firstDay  = new Date(year, month, 1);
  const lastDay   = new Date(year, month + 1, 0);
  const startPad  = (firstDay.getDay() + 6) % 7; // Mon=0
  const totalCells = startPad + lastDay.getDate();
  const cells = Array.from({ length: Math.ceil(totalCells / 7) * 7 }, (_, i) => {
    const day = i - startPad + 1;
    return (day >= 1 && day <= lastDay.getDate()) ? day : null;
  });

  return (
    <div className="calendar-wrap">
      <div className="calendar-nav">
        <button className="calendar-nav__btn" onClick={() => onNav(-1)}>‹</button>
        <span className="calendar-nav__title">
          {MONTH_NAMES_AR[month]} {year}
        </span>
        <button className="calendar-nav__btn" onClick={() => onNav(1)}>›</button>
      </div>

      <div className="calendar-grid">
        {['إث','ثل','أر','خم','جم','سب','أح'].map((d) => (
          <div key={d} className="cal-day-header">{d}</div>
        ))}
        {cells.map((day, i) => {
          if (!day) return <div key={i} className="cal-day cal-day--empty" />;

          const iso = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
          const date = parseDate(iso);
          const wd   = (date.getDay() + 6) % 7; // Mon=0
          const isWeekend  = excludedWeekdays.includes(wd);
          const isExcluded = excludedDates.includes(iso);
          const inRange    = startISO && endISO && iso >= startISO && iso <= endISO;
          const outOfRange = !inRange;

          let cls = 'cal-day';
          if (outOfRange)  cls += ' cal-day--out-of-range';
          else if (isWeekend)   cls += ' cal-day--weekend';
          else if (isExcluded)  cls += ' cal-day--excluded';
          else if (inRange)     cls += ' cal-day--available';

          return (
            <div
              key={i}
              className={cls}
              onClick={() => !isWeekend && !outOfRange && onToggleDate(iso)}
              title={isWeekend ? 'يوم عطلة أسبوعية' : isExcluded ? 'مستثنى — انقر للإلغاء' : 'انقر للاستثناء'}
            >
              {day}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Main SettingsPage ──────────────────────────────────────────────────────── */
export default function SettingsPage({ sessionId, onConfirm, onBack }) {
  const today     = toISO(new Date());
  const twoWeeks  = toISO(new Date(Date.now() + 14 * 86400000));

  const [startDate, setStartDate]           = useState(today);
  const [endDate,   setEndDate]             = useState(twoWeeks);
  const [excludedWeekdays, setExclWeekdays] = useState([4, 5]);   // Fri+Sat default
  const [excludedDates,    setExclDates]    = useState([]);
  const [calYear,  setCalYear]  = useState(new Date().getFullYear());
  const [calMonth, setCalMonth] = useState(new Date().getMonth());
  const [dateError, setDateError] = useState('');

  /* Derived: available days count */
  const availableDays = useMemo(
    () => buildAvailableDates(startDate, endDate, excludedWeekdays, excludedDates),
    [startDate, endDate, excludedWeekdays, excludedDates]
  );

  /* Validate dates */
  const validateDates = (start, end) => {
    if (!start || !end) { setDateError('يجب تحديد تاريخ البداية والنهاية.'); return false; }
    if (start > end)    { setDateError('تاريخ البداية يجب أن يسبق تاريخ النهاية.'); return false; }
    setDateError('');
    return true;
  };

  const handleStart = (v) => { setStartDate(v); validateDates(v, endDate); };
  const handleEnd   = (v) => { setEndDate(v);   validateDates(startDate, v); };

  const toggleWeekday = (wd) => {
    setExclWeekdays((prev) =>
      prev.includes(wd) ? prev.filter((d) => d !== wd) : [...prev, wd]
    );
  };

  const toggleDate = (iso) => {
    setExclDates((prev) =>
      prev.includes(iso) ? prev.filter((d) => d !== iso) : [...prev, iso]
    );
  };

  const navMonth = (delta) => {
    let m = calMonth + delta;
    let y = calYear;
    if (m > 11) { m = 0;  y++; }
    if (m < 0)  { m = 11; y--; }
    setCalMonth(m);
    setCalYear(y);
  };

  const handleConfirm = () => {
    if (!validateDates(startDate, endDate)) return;
    if (availableDays.length === 0) {
      setDateError('لا توجد أيام متاحة في الفترة المحددة. يُرجى مراجعة إعدادات الاستثناء.');
      return;
    }
    onConfirm({
      session_id:         sessionId,
      start_date:         startDate,
      end_date:           endDate,
      excluded_weekdays:  excludedWeekdays,
      excluded_dates:     excludedDates,
    });
  };

  return (
    <main className="settings-page">
      <div>
        <h1 className="page-title">إعدادات فترة الامتحانات</h1>
        <p className="page-subtitle">
          حدّد نطاق التاريخ وأيام العطلة وسيحسب النظام الأيام المتاحة تلقائياً.
        </p>
      </div>

      {/* Date range */}
      <div className="settings-card">
        <div className="settings-card__header">
          <CalendarRange size={20} /> نطاق الفترة الزمنية
        </div>
        <div className="settings-card__body">
          <div className="date-row">
            <div className="field-group">
              <label htmlFor="start-date" className="field-label">تاريخ البداية</label>
              <input
                id="start-date"
                type="date"
                className={`field-input${dateError ? ' field-input--error' : ''}`}
                value={startDate}
                onChange={(e) => handleStart(e.target.value)}
              />
            </div>
            <div className="field-group">
              <label htmlFor="end-date" className="field-label">تاريخ النهاية</label>
              <input
                id="end-date"
                type="date"
                className={`field-input${dateError ? ' field-input--error' : ''}`}
                value={endDate}
                onChange={(e) => handleEnd(e.target.value)}
              />
            </div>
          </div>
          {dateError && <p className="field-error"><AlertTriangle size={16} /> {dateError}</p>}
        </div>
      </div>

      {/* Weekday exclusions */}
      <div className="settings-card">
        <div className="settings-card__header">
          <CalendarOff size={20} /> أيام العطلة الأسبوعية (انقر للتبديل)
        </div>
        <div className="settings-card__body">
          <div className="weekday-grid">
            {WEEKDAYS.map(({ idx, label }) => (
              <button
                key={idx}
                id={`weekday-${idx}`}
                className={`weekday-btn${excludedWeekdays.includes(idx) ? ' weekday-btn--excluded' : ''}`}
                onClick={() => toggleWeekday(idx)}
                title={excludedWeekdays.includes(idx) ? 'مستثنى — انقر للتفعيل' : 'انقر للاستثناء'}
              >
                {excludedWeekdays.includes(idx) ? '✕ ' : ''}{label}
              </button>
            ))}
          </div>
          <p className="field-hint">
            الاستثناء الافتراضي: الجمعة والسبت. انقر على أي يوم لاستثنائه أو تفعيله.
          </p>
        </div>
      </div>

      {/* Ad-hoc exclusions calendar */}
      <div className="settings-card">
        <div className="settings-card__header">
          <CalendarDays size={20} /> استثناء أيام إضافية (إجازات رسمية)
          {excludedDates.length > 0 && (
            <span style={{ marginRight: 'auto', fontWeight: 400, fontSize: 'var(--font-size-xs)', color: 'var(--color-error)' }}>
              ({excludedDates.length} يوم مستثنى)
            </span>
          )}
        </div>
        <div className="settings-card__body">
          <MiniCalendar
            year={calYear}
            month={calMonth}
            startISO={startDate}
            endISO={endDate}
            excludedWeekdays={excludedWeekdays}
            excludedDates={excludedDates}
            onToggleDate={toggleDate}
            onNav={navMonth}
          />
          <p className="field-hint">
            <span style={{ display: 'inline-block', width: 12, height: 12, background: 'rgba(63,185,80,0.2)', borderRadius: 2, marginInlineEnd: 4 }} />متاح&nbsp;&nbsp;
            <span style={{ display: 'inline-block', width: 12, height: 12, background: 'rgba(248,81,73,0.18)', borderRadius: 2, marginInlineEnd: 4 }} />مستثنى&nbsp;&nbsp;
            <span style={{ display: 'inline-block', width: 12, height: 12, background: 'rgba(248,81,73,0.07)', borderRadius: 2, marginInlineEnd: 4 }} />عطلة أسبوعية
          </p>
        </div>
      </div>

      {/* Summary */}
      <div className="period-summary">
        <div className="period-summary__item">
          <span className={`period-summary__value${availableDays.length < 5 ? ' period-summary__warn' : ''}`}>
            {availableDays.length}
          </span>
          <span className="period-summary__label">أيام امتحانات متاحة</span>
        </div>
        <div className="period-summary__item">
          <span className="period-summary__value" style={{ color: 'var(--color-text-secondary)' }}>
            {excludedWeekdays.length}
          </span>
          <span className="period-summary__label">أيام عطلة أسبوعية</span>
        </div>
        <div className="period-summary__item">
          <span className="period-summary__value" style={{ color: excludedDates.length ? 'var(--color-warning)' : 'var(--color-text-secondary)' }}>
            {excludedDates.length}
          </span>
          <span className="period-summary__label">إجازات رسمية</span>
        </div>
      </div>

      {availableDays.length > 0 && availableDays.length < 5 && (
        <div className="gate-banner gate-banner--blocked" style={{ marginTop: 'calc(var(--space-4) * -1)' }}>
          <AlertTriangle size={20} />
          عدد الأيام المتاحة ({availableDays.length}) قد لا يكفي لجدولة جميع الامتحانات — تحقق من إعدادات الفترة.
        </div>
      )}

      {/* Actions */}
      <div className="settings-actions">
        <button id="btn-back-validation" className="btn btn-ghost" onClick={onBack}>
          ← العودة
        </button>
        <button
          id="btn-run-scheduler"
          className="btn btn-primary"
          disabled={availableDays.length === 0 || !!dateError}
          onClick={handleConfirm}
        >
          تشغيل المجدول ({availableDays.length} يوم متاح) ←
        </button>
      </div>
    </main>
  );
}
