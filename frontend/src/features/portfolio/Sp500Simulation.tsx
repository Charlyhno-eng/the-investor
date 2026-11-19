import { useEffect, useMemo, useRef, useState } from "react";
import { HistoryChart } from "../../components/HistoryChart";
import { post, postStream } from "../../lib/api";
import { ValidationMetrics, type Ready } from "./ValidationPanel";

import { Sp500BatchTable, type BatchResult } from "./Sp500BatchTable";

const regressionCurves = [
  { key: "benchmark", title: "S&P 500 · Buy & Hold", color: "#739de8" },
  { key: "strategy", title: "S&P 500 · Régression", color: "#d5aa73" },
] as const;

const downsideCurves = [
  regressionCurves[0],
  {
    ...regressionCurves[1],
    title: "S&P 500 · Filtre de baisses + cinq modèles",
  },
] as const;

type Comparison = Omit<Ready, "metrics" | "equity"> & {
  metrics: Partial<Ready["metrics"]>;
  equity: { time: string; benchmark: number; strategy: number }[];
};
type Result =
  | {
      status: "ready";
      comparison: Comparison;
      simulation: {
        seed: number;
        source_start: string;
        source_end: string;
      };
    }
  | { status: "insufficient"; message: string };

export function Sp500Simulation({ downside = false }: { downside?: boolean }) {
  const curves = downside ? downsideCurves : regressionCurves;
  const [years, setYears] = useState("5");
  const [capital, setCapital] = useState("10000");
  const [fee, setFee] = useState("0.12");
  const [mode, setMode] = useState(downside ? "batch" : "single");
  const [count, setCount] = useState("1000");
  const [batch, setBatch] = useState<BatchResult | null>(null);
  const [wholeShares, setWholeShares] = useState(true);
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  // The server snapshots the source history at launch. Catalogue polling must
  // not cancel that calculation or discard its results when prices change.
  useEffect(() => () => controller.current?.abort(), []);
  const ready = result?.status === "ready" ? result : null;
  const lines = useMemo(
    () =>
      ready
        ? curves.map((curve) => ({
            title: curve.title,
            color: curve.color,
            points: ready.comparison.equity.map((p) => ({
              time: p.time,
              value: p[curve.key],
            })),
          }))
        : [],
    [ready, curves],
  );
  async function generate() {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    setLoading(true);
    setResult(null);
    setBatch(null);
    setError("");
    try {
      if (mode === "batch") {
        let finished = false;
        await postStream<BatchResult | { status: "error"; message: string }>(
          "/portfolio/sp500-simulation/batch",
          {
            years: Number(years),
            initial_capital: Number(capital),
            ...(downside ? { strategy: "downside" } : {}),
            fee_rate: Number(fee) / 100,
            whole_shares: wholeShares,
            count: Number(count),
          },
          request.signal,
          (value) => {
            if (request.signal.aborted) return;
            if (value.status === "error") throw new Error(value.message);
            finished = value.status === "complete";
            setBatch(value);
          },
        );
        if (!finished && !request.signal.aborted)
          throw new Error("Calcul interrompu : résultats partiels affichés.");
        return;
      }
      const next = await post<Result>(
        "/portfolio/sp500-simulation",
        {
          years: Number(years),
          initial_capital: Number(capital),
          ...(downside ? { strategy: "downside" } : {}),
          fee_rate: Number(fee) / 100,
          whole_shares: wholeShares,
        },
        request.signal,
      );
      if (!request.signal.aborted) setResult(next);
    } catch (e) {
      if (!request.signal.aborted)
        setError(e instanceof Error ? e.message : "Le calcul a échoué.");
    } finally {
      if (!request.signal.aborted) setLoading(false);
    }
  }
  function invalidate() {
    controller.current?.abort();
    setResult(null);
    setBatch(null);
    setError("");
    setLoading(false);
  }
  return (
    <section
      className="portfolio-content portfolio-validation portfolio-validation-standalone"
      aria-label="Simulation aléatoire S&P 500"
    >
      <div className="portfolio-section-heading">
        <div>
          <h1>{curves[1].title}</h1>
          <p>
            Des parcours fictifs tirés de séquences historiques du S&P 500 PEA
            en euros, avec une légère variation aléatoire. La stratégie actuelle
            et le Buy & Hold suivent exactement le même marché.
          </p>
        </div>
      </div>
      <form
        className="validation-controls"
        onSubmit={(event) => {
          event.preventDefault();
          void generate();
        }}
      >
        <label>
          Mode de génération
          <select
            value={mode}
            onChange={(e) => {
              invalidate();
              setMode(e.target.value);
            }}
          >
            <option value="single">Un parcours</option>
            <option value="batch">Plusieurs parcours</option>
          </select>
        </label>
        {mode === "batch" && (
          <label>
            Nombre de parcours
            <input
              type="number"
              min="1"
              max="10000"
              step="1"
              required
              value={count}
              onChange={(e) => {
                invalidate();
                setCount(e.target.value);
              }}
            />
          </label>
        )}
        <label>
          Capital initial (€)
          <input
            type="number"
            min="1"
            max="1000000000000"
            step="any"
            required
            value={capital}
            onChange={(e) => {
              invalidate();
              setCapital(e.target.value);
            }}
          />
        </label>
        <label>
          Durée simulée
          <select
            value={years}
            onChange={(e) => {
              invalidate();
              setYears(e.target.value);
            }}
          >
            {[1, 3, 5, 10].map((n) => (
              <option key={n} value={n}>
                {n} {n === 1 ? "an" : "ans"}
              </option>
            ))}
          </select>
        </label>
        <label>
          Frais par achat/vente (%)
          <input
            type="number"
            min="0"
            max="10"
            step="any"
            required
            value={fee}
            onChange={(e) => {
              invalidate();
              setFee(e.target.value);
            }}
          />
        </label>
        <label className="validation-whole-shares">
          <input
            type="checkbox"
            checked={wholeShares}
            onChange={(e) => {
              invalidate();
              setWholeShares(e.target.checked);
            }}
          />
          Titres entiers
        </label>
        <button className="secondary-button" disabled={loading} type="submit">
          {loading
            ? "Simulation en cours…"
            : mode === "batch"
              ? "Lancer les simulations"
              : "Générer un nouveau parcours"}
        </button>
        {loading && (
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              controller.current?.abort();
              setLoading(false);
            }}
          >
            Arrêter
          </button>
        )}
      </form>
      {batch && (
        <Sp500BatchTable
          result={batch}
          running={loading}
          strategyName={
            downside ? "Filtre de baisses + cinq modèles" : "Régression"
          }
        />
      )}
      {loading && !batch && (
        <p role="status">
          Génération du parcours et calcul des deux portefeuilles…
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {result?.status === "insufficient" && (
        <p role="status">{result.message}</p>
      )}
      {ready && (
        <>
          <div
            className="performance-series-summary validation-chart-legend"
            role="group"
            aria-label="Légende de la simulation"
          >
            {curves.map((curve) => (
              <div key={curve.key}>
                <span>
                  <i style={{ background: curve.color }} aria-hidden="true" />
                  {curve.title}
                </span>
              </div>
            ))}
          </div>
          <HistoryChart
            lines={lines}
            accessibleLabel="Simulation aléatoire : Buy & Hold et stratégie S&P 500, deux courbes nettes de frais en base 100"
          />
          <ValidationMetrics
            ready={ready.comparison}
            displayedSeries={curves}
            accessibleLabel="Résultats de la simulation aléatoire"
            showComparisonLegend={false}
          />
        </>
      )}
    </section>
  );
}
