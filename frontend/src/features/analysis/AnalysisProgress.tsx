import { useEffect, useState } from "react";

export function AnalysisProgress() {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="analysis-loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <div>
        <strong>Entraînement GaussianHMM et simulation en cours</strong>
        <small>
          {elapsed >= 30
            ? "Le calcul prend plus de temps sur cet historique. Vous pouvez patienter sur cette page."
            : "Trois initialisations sont comparées avant le test sur la seconde période. Patientez sur cette page."}
        </small>
        <span className="analysis-elapsed" aria-hidden="true">
          Temps écoulé : {elapsed} s
        </span>
      </div>
    </div>
  );
}
