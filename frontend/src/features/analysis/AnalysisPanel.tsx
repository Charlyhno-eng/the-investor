import { useEffect, useRef, useState } from "react";
import { Icon } from "../../components/Icon";
import { Tooltip } from "../../components/Tooltip";
import { post } from "../../lib/api";
import type {
  Analysis,
  Asset,
  Parameters,
  Periods,
  Point,
} from "../../lib/types";
import { PeriodSelector } from "./PeriodSelector";
import { AnalysisResults } from "./AnalysisResults";
import { NumberInput } from "./NumberInput";
import { AnalysisProgress } from "./AnalysisProgress";
function initial(points: Point[], asset: Asset): Parameters {
  // Recent 8 years on daily data; use the complete available monthly history.
  const start =
    asset.frequency === "monthly" ? 0 : Math.max(0, points.length - 252 * 8);
  const cut = Math.min(
    points.length - 2,
    start + Math.floor((points.length - start) * 0.7),
  );
  return {
    train_start: points[start].time,
    train_end: points[cut].time,
    test_start: points[cut + 1].time,
    test_end: points.at(-1)!.time,
    fee_bps: asset.category === "crypto" ? 1 : 50,
  };
}
export function AnalysisPanel({
  asset,
  points,
}: {
  asset: Asset;
  points: Point[];
}) {
  const [parameters, setParameters] = useState(() => initial(points, asset));
  const [result, setResult] = useState<Analysis | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [started, setStarted] = useState(false);
  const [revision, setRevision] = useState(0);
  const active = useRef<Promise<void> | null>(null);
  const output = useRef<HTMLDivElement>(null);
  const manualScroll = useRef(false);
  const valid =
    parameters.train_start < parameters.train_end &&
    parameters.train_end < parameters.test_start &&
    parameters.test_start < parameters.test_end;
  function update(value: Parameters | Periods) {
    setParameters((p) => ({ ...p, ...value }));
    setError("");
  }
  function scrollToChart() {
    const target =
      output.current?.querySelector(".performance-chart") ?? output.current;
    target?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function run() {
    manualScroll.current = true;
    setStarted(true);
    setRevision((v) => v + 1);
    requestAnimationFrame(scrollToChart);
  }
  useEffect(() => {
    if (!started || !valid) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const timer = setTimeout(
      () => {
        const previous = active.current;
        const task = (async () => {
          // Serialize calculations: changing an input must not overlap model fits.
          await previous;
          if (cancelled) return;
          try {
            const response = await post<Analysis>(
              `/assets/${encodeURIComponent(asset.id)}/analysis`,
              parameters,
            );
            if (!cancelled) {
              setResult(response);
              setError("");
              if (manualScroll.current) {
                manualScroll.current = false;
                requestAnimationFrame(scrollToChart);
              }
            }
          } catch (e) {
            if (!cancelled) setError((e as Error).message);
          } finally {
            if (!cancelled) setLoading(false);
          }
        })();
        active.current = task;
      },
      manualScroll.current ? 0 : 450,
    );
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [parameters, started, revision, valid, asset.id, points]);
  return (
    <section className="analysis-panel" aria-label="Analyse HMM">
      <fieldset className="analysis-controls">
        <legend className="sr-only">Périodes et paramètres de l’analyse</legend>
        <PeriodSelector
          points={points}
          periods={parameters}
          onChange={update}
        />
        {!valid && (
          <p className="error" role="alert">
            La période 1 doit précéder la période 2, sans chevauchement.
          </p>
        )}
        <div className="analysis-settings-row">
          {asset.metric !== "yield" && (
            <details className="parameters" open>
              <summary>
                <Icon name="settings" size={16} />
                Paramètres de la stratégie
                <Icon name="chevron" size={14} />
              </summary>
              <div className="parameter-grid">
                <label>
                  <span className="field-label">
                    Frais à l’achat et à la vente
                    <Tooltip label="Frais à l’achat et à la vente">
                      <span>
                        Pourcentage prélevé à chaque achat et vente. 0,1 %
                        correspond à 1 € pour un ordre de 1 000 €.
                      </span>
                    </Tooltip>
                  </span>
                  <div className="number-field">
                    <NumberInput
                      min={0}
                      max={5}
                      step={0.01}
                      value={Number((parameters.fee_bps / 100).toFixed(4))}
                      onChange={(value) =>
                        update({
                          ...parameters,
                          fee_bps: Number((value * 100).toFixed(4)),
                        })
                      }
                    />
                    <span>%</span>
                  </div>
                </label>
              </div>
            </details>
          )}
          <div className="run-bar analysis-run-bar">
            <button
              className="primary-button"
              disabled={loading || !valid}
              onClick={run}
            >
              {loading ? (
                <span className="spinner" />
              ) : (
                <Icon name="play" size={15} />
              )}{" "}
              {loading
                ? "Analyse en cours…"
                : asset.metric === "yield"
                  ? "Analyser les régimes"
                  : "Lancer la simulation"}
            </button>
          </div>
        </div>
      </fieldset>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div ref={output} className="analysis-output" aria-busy={loading}>
        {loading && (
          <>
            <p role="status">
              {result
                ? "Actualisation de la simulation… La courbe précédente reste affichée."
                : "Calcul de la simulation…"}
            </p>
            <AnalysisProgress />
          </>
        )}
        {result && <AnalysisResults result={result} />}
      </div>
    </section>
  );
}
