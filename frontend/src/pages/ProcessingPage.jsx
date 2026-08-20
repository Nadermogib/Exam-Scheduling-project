import { useEffect, useState } from 'react';
import { Folder, Network, Calculator, CheckCircle, AlertTriangle, Settings } from 'lucide-react';
import { runSchedule } from '../api/client';
import './ProcessingPage.css';

const STAGES = [
  { id: 0, icon: <Folder size={18} />, label: 'قراءة البيانات من الجلسة' },
  { id: 1, icon: <Network size={18} />, label: 'بناء مصفوفة التعارض' },
  { id: 2, icon: <Calculator size={18} />, label: 'تشغيل خوارزمية CP-SAT' },
  { id: 3, icon: <CheckCircle size={18} />, label: 'التحقق من صحة النتائج' },
];

export default function ProcessingPage({ config, onSuccess, onInfeasible, onBack }) {
  const [stage,   setStage]   = useState(0);
  const [error,   setError]   = useState(null);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    if (started) return;
    setStarted(true);

    // Simulate stage progression while the real API call is running
    let currentStage = 0;
    const advance = (delay) =>
      new Promise((res) => setTimeout(() => { currentStage++; setStage(currentStage); res(); }, delay));

    const run = async () => {
      try {
        // Stage 0 is already shown; advance quickly through visual stages
        const resultPromise = runSchedule(config);
        await advance(600);   // stage 1: graph building
        await advance(800);   // stage 2: CP-SAT running

        const result = await resultPromise;   // actual API call
        setStage(3);                          // stage 3: verification
        await new Promise((r) => setTimeout(r, 500));

        if (result.status === 'INFEASIBLE') {
          onInfeasible(result);
        } else {
          onSuccess(result);
        }
      } catch (err) {
        setStage(-1);
        setError(
          err.userMessage ||
          err.response?.data?.detail ||
          'حدث خطأ أثناء الاتصال بالخادم. تحقق من تشغيل الخادم وأعد المحاولة.'
        );
      }
    };

    run();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const hasError = stage === -1;

  return (
    <main className="processing-page">
      <div className="processing-orb">
        {hasError ? <AlertTriangle size={40} color="var(--color-danger)" /> : stage >= 3 ? <CheckCircle size={40} color="var(--color-success)" /> : <Settings size={40} color="var(--color-accent)" />}
      </div>

      <div style={{ textAlign: 'center' }}>
        <h1 className="processing-title">
          {hasError
            ? 'حدث خطأ'
            : stage >= 3
            ? 'اكتمل التشغيل'
            : 'جارٍ تشغيل المجدول…'
          }
        </h1>
        <p className="processing-subtitle">
          {hasError
            ? 'لم يتم إنجاز الجدولة بسبب الخطأ أدناه.'
            : stage >= 3
            ? 'تم بنجاح — جارٍ عرض النتائج…'
            : 'يعمل المجدول الآن على إيجاد جدول خالٍ من التعارضات باستخدام CP-SAT.'
          }
        </p>
      </div>

      {/* Stage progress list */}
      {!hasError && (
        <div className="stage-list">
          {STAGES.map((s) => {
            const done   = s.id < stage;
            const active = s.id === stage;
            const cls    = `stage-item${active ? ' stage-item--active' : done ? ' stage-item--done' : ''}`;
            return (
              <div key={s.id} className={cls}>
                <span className="stage-item__icon">{done ? <CheckCircle size={18} color="var(--color-success)" /> : s.icon}</span>
                <span className="stage-item__label">{s.label}</span>
                {active && <span className="stage-spinner" />}
                <span className="stage-item__status">
                  {done ? 'اكتمل' : active ? 'جارٍ…' : ''}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Error state */}
      {hasError && (
        <>
          <div className="processing-error" role="alert">
            <AlertTriangle size={20} />
            <span>{error}</span>
          </div>
          <div className="processing-actions">
            <button id="btn-back-settings" className="btn btn-ghost" onClick={onBack}>
              ← العودة إلى الإعدادات
            </button>
          </div>
        </>
      )}
    </main>
  );
}
