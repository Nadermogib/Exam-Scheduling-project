import './StepBar.css';
import { Check } from 'lucide-react';

const STEPS = [
  { id: 0, label: 'رفع الملف' },
  { id: 1, label: 'مراجعة البيانات' },
  { id: 2, label: 'إعدادات الفترة' },
  { id: 3, label: 'تشغيل المجدول' },
  { id: 4, label: 'النتائج' },
];

export default function StepBar({ current }) {
  return (
    <nav className="step-bar" aria-label="خطوات العملية">
      {STEPS.map((step, i) => {
        const done   = step.id < current;
        const active = step.id === current;
        const cls    = done ? 'done' : active ? 'active' : '';
        return (
          <div key={step.id} className={`step-bar__item step-bar__item--${cls}`}>
            <div className="step-bar__circle">
              {done ? <Check size={18} strokeWidth={3} /> : step.id + 1}
            </div>
            <span className="step-bar__label">{step.label}</span>
            {i < STEPS.length - 1 && (
              <div className={`step-bar__connector${done ? ' step-bar__connector--done' : ''}`} />
            )}
          </div>
        );
      })}
    </nav>
  );
}
