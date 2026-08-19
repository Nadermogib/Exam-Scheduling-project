import { useState } from 'react';
import StepBar           from './components/StepBar';
import UploadPage        from './pages/UploadPage';
import ValidationPage    from './pages/ValidationPage';
import SettingsPage      from './pages/SettingsPage';
import ProcessingPage    from './pages/ProcessingPage';
import ResultsPage       from './pages/ResultsPage';
import InfeasibilityPage from './pages/InfeasibilityPage';
import './App.css';

/*
 * Step indices
 *   0  Upload
 *   1  Validation
 *   2  Settings
 *   3  Processing
 *   4  Results / Infeasibility   (Phase 5)
 */

export default function App() {
  const [step,           setStep]           = useState(0);
  const [uploadData,     setUploadData]     = useState(null);  // raw upload response
  const [sessionId,      setSessionId]      = useState(null);
  const [scheduleConfig, setScheduleConfig] = useState(null);  // settings form output
  const [scheduleResult, setScheduleResult] = useState(null);  // solver output

  /* ── Step 0 → 1 : upload succeeded ───────────────────────────────── */
  const handleUploadSuccess = (data) => {
    setUploadData(data);
    setSessionId(data.session_id);
    setStep(1);
  };

  /* ── Step 1 → 2 : validation cleared ─────────────────────────────── */
  const handleValidated = (sid, _report) => {
    setSessionId(sid);
    setStep(2);
  };

  /* ── Step 2 → 3 : settings confirmed ────────────────────────────── */
  const handleSettingsConfirm = (config) => {
    setScheduleConfig(config);
    setStep(3);
  };

  /* ── Step 3 → 4a : success ───────────────────────────────────────── */
  const handleScheduleSuccess = (result) => {
    setScheduleResult({ ...result, type: 'success' });
    setStep(4);
  };

  /* ── Step 3 → 4b : infeasible ────────────────────────────────────── */
  const handleInfeasible = (result) => {
    setScheduleResult({ ...result, type: 'infeasible' });
    setStep(4);
  };

  /* ── Render ──────────────────────────────────────────────────────── */
  const renderPage = () => {
    switch (step) {
      case 0:
        return <UploadPage onUploadSuccess={handleUploadSuccess} />;

      case 1:
        return (
          <ValidationPage
            uploadData={uploadData}
            onValidated={handleValidated}
            onBack={() => setStep(0)}
          />
        );

      case 2:
        return (
          <SettingsPage
            sessionId={sessionId}
            onConfirm={handleSettingsConfirm}
            onBack={() => setStep(1)}
          />
        );

      case 3:
        return (
          <ProcessingPage
            config={scheduleConfig}
            onSuccess={handleScheduleSuccess}
            onInfeasible={handleInfeasible}
            onBack={() => setStep(2)}
          />
        );

      case 4:
        if (!scheduleResult) return null;
        if (scheduleResult.type === 'infeasible') {
          return (
            <InfeasibilityPage
              result={scheduleResult}
              sessionId={sessionId}
              onBack={() => setStep(2)}
              onRestart={doRestart}
            />
          );
        }
        return (
          <ResultsPage
            result={scheduleResult}
            sessionId={sessionId}
            onRestart={doRestart}
          />
        );

      default:
        return null;
    }
  };

  const doRestart = () => {
    setStep(0); setUploadData(null); setSessionId(null);
    setScheduleConfig(null); setScheduleResult(null);
  };

  return (
    <div className="app">
      {/* Top navigation bar */}
      <header className="app-header">
        <div className="app-header__inner">
          <div className="app-logo">
            <span className="app-logo__icon">🗓️</span>
            <div>
              <span className="app-logo__name">نظام جدولة الامتحانات</span>
              <span className="app-logo__sub">الدور التكميلي</span>
            </div>
          </div>
        </div>
      </header>

      {/* Step indicator */}
      <StepBar current={step} />

      {/* Page content */}
      <div className="app-content">
        {renderPage()}
      </div>
    </div>
  );
}

