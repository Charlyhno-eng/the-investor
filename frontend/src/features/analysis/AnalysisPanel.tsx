import { useEffect, useMemo, useRef, useState } from "react";
import { post } from "../../lib/api";
import { date, percent } from "../../lib/format";
import type { Asset, Periods, Point } from "../../lib/types";
import { HistoryChart } from "../../components/HistoryChart";
import { Tooltip } from "../../components/Tooltip";
import { PeriodSelector } from "./PeriodSelector";
const colors = ["#ff5252", "#ffb52e", "#3399ff", "#18d6b0"];
type Detection = {
  current: string;
  date: string;
  observations: number;
  train_observations: number;
  actual_train: string[];
  actual_test: string[];
  points: (Point & { state: number; confidence: number })[];
  states: {
    name: string;
    probability: number;
    next_probability: number;
    mean: number;
    volatility: number;
  }[];
};
export function AnalysisPanel({
  asset,
  points,
}: {
  asset: Asset;
  points: Point[];
}) {
  const [periods, setPeriods] = useState<Periods>(() => {
    const recent = points.slice(-2000);
    const split = Math.max(
      1,
      Math.min(recent.length - 2, Math.floor(recent.length * 0.7)),
    );
    return {
      train_start: recent[0].time,
      train_end: recent[split - 1].time,
      test_start: recent[split].time,
      test_end: recent.at(-1)!.time,
    };
  });
  const [result, setResult] = useState<Detection | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const resultsSection = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!result) return;
    const frame = requestAnimationFrame(() =>
      resultsSection.current?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
        block: "start",
      }),
    );
    return () => cancelAnimationFrame(frame);
  }, [result]);
  const orderedStates = useMemo(
    () =>
      result?.states
        .map((state, index) => ({ ...state, index }))
        .sort((a, b) => {
          const direction = (mean: number) => (mean > 0 ? 0 : mean < 0 ? 1 : 2);
          return (
            direction(a.mean) - direction(b.mean) ||
            a.volatility - b.volatility ||
            a.index - b.index
          );
        }) ?? [],
    [result],
  );
  useEffect(() => () => controller.current?.abort(), []);
  const valid =
    periods.train_start < periods.train_end &&
    periods.train_end < periods.test_start &&
    periods.test_start < periods.test_end;
  const dots = useMemo(
    () => result?.points.map((p) => ({ ...p, color: colors[p.state] })),
    [result],
  );
  async function run() {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await post<Detection>(
        `/assets/${encodeURIComponent(asset.id)}/regime`,
        periods,
        request.signal,
      );
      if (!request.signal.aborted) setResult(data);
    } catch (e) {
      if (!request.signal.aborted) setError((e as Error).message);
    } finally {
      if (!request.signal.aborted) setLoading(false);
    }
  }
  return (
    <section
      className="regime-panel"
      aria-label="Détection des régimes de marché"
    >
      <PeriodSelector
        points={points}
        periods={periods}
        onChange={(value) => {
          controller.current?.abort();
          setLoading(false);
          setResult(null);
          setError("");
          setPeriods(value);
        }}
      />
      <div className="regime-actions">
        <button
          className="primary-button"
          onClick={run}
          disabled={loading || !valid}
        >
          {loading ? "Estimation des régimes…" : "Entraîner et tester"}
        </button>
        <Tooltip label="Méthode du HMM">
          Quatre états gaussiens appris uniquement sur l’entraînement, classés
          par rendement moyen croissant. Sur le test, les paramètres restent
          figés et chaque point indique le régime filtré après la clôture, sans
          données futures. La prévision suivante utilise la matrice de
          transition. Minimum : 252 prix d’entraînement et 2 prix de test.
        </Tooltip>
      </div>
      {(loading || result || error) && <hr className="regime-separator" />}
      {!valid && (
        <p className="error" role="alert">
          L’entraînement doit précéder le test, sans chevauchement.
        </p>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {loading && (
        <p className="sr-only" role="status">
          Entraînement du modèle en cours.
        </p>
      )}
      {result && (
        <div className="regime-results" ref={resultsSection}>
          <div className="regime-chart-heading">
            <span>
              Test · {date(result.actual_test[0])} →{" "}
              {date(result.actual_test[1])}
            </span>
            <span>
              {result.current} ·{" "}
              {percent(Math.max(...result.states.map((s) => s.probability)))}
            </span>
          </div>
          <div className="regime-legend">
            {orderedStates.map((state) => (
              <span key={state.name}>
                <i style={{ background: colors[state.index] }} />
                {state.name}
              </span>
            ))}
          </div>
          <HistoryChart points={result.points} regimeDots={dots} />
          <details className="model-details">
            <summary>Probabilités et paramètres</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Régime</th>
                    <th>Dernière clôture</th>
                    <th>Observation suivante</th>
                    <th>Rendement moyen</th>
                    <th>Volatilité</th>
                  </tr>
                </thead>
                <tbody>
                  {orderedStates.map((s) => (
                    <tr key={s.name}>
                      <th style={{ color: colors[s.index] }}>{s.name}</th>
                      <td>{percent(s.probability)}</td>
                      <td>{percent(s.next_probability)}</td>
                      <td>{percent(s.mean)}</td>
                      <td>{percent(s.volatility)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="fine-print">
              Rendement et volatilité par observation ·{" "}
              {result.train_observations} rendements d’entraînement ·{" "}
              {result.observations} points de test.
            </p>
          </details>
        </div>
      )}
    </section>
  );
}
