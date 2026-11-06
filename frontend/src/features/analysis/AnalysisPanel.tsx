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
function initial(points: Point[], monthly: boolean): Parameters {
  // Recent 8 years on daily data; use the complete available monthly history.
  const start = monthly ? 0 : Math.max(0, points.length - 252 * 8);
  const cut = Math.min(
    points.length - 2,
    start + Math.floor((points.length - start) * 0.7),
  );
  return {
    train_start: points[start].time,
    train_end: points[cut].time,
    test_start: points[cut + 1].time,
    test_end: points.at(-1)!.time,
    fee_bps: 10,
    slippage_bps: 5,
    min_hold: monthly ? 3 : 10,
    confirmation: monthly ? 2 : 3,
    max_trades: 30,
    entry_probability: 0.65,
    exit_probability: 0.35,
    risk_free_rate: 0,
  };
}
const fields = [
  {
    key: "fee_bps",
    label: "Frais / transaction",
    unit: "pb",
    min: 0,
    max: 500,
    step: 1,
    tip: "1 point de base = 0,01 %. Appliqués à chaque achat et vente, sur la totalité du capital engagé.",
  },
  {
    key: "slippage_bps",
    label: "Glissement estimé",
    unit: "pb",
    min: 0,
    max: 500,
    step: 1,
    tip: "Écart défavorable supposé entre le prix théorique et exécuté. S’ajoute aux frais à chaque transaction.",
  },
  {
    key: "min_hold",
    label: "Détention minimale",
    unit: "obs.",
    min: 1,
    max: 250,
    step: 1,
    tip: "Nombre minimal d’observations entre un achat et une vente. La clôture finale du test liquide toujours la position.",
  },
  {
    key: "confirmation",
    label: "Confirmation",
    unit: "obs.",
    min: 1,
    max: 30,
    step: 1,
    tip: "Nombre de signaux consécutifs requis avant un changement de position. Réduit les allers-retours.",
  },
  {
    key: "max_trades",
    label: "Plafond de transactions",
    unit: "ordres",
    min: 2,
    max: 500,
    step: 1,
    tip: "Plafond absolu des achats et ventes sur tout le test. Une place est réservée pour la liquidation finale.",
  },
  {
    key: "risk_free_rate",
    label: "Taux sans risque",
    unit: "% / an",
    min: 0,
    max: 25,
    step: 0.1,
    tip: "Taux annuel utilisé pour les ratios et la rémunération des liquidités. La valeur par défaut est 0 %.",
  },
] as const;
export function AnalysisPanel({
  asset,
  points,
}: {
  asset: Asset;
  points: Point[];
}) {
  const [parameters, setParameters] = useState(() =>
    initial(points, asset.frequency === "monthly"),
  );
  const [result, setResult] = useState<Analysis | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    controller.current?.abort();
    setResult(null);
    setError("");
    setLoading(false);
  }, [points]);
  function update(value: Parameters | Periods) {
    controller.current?.abort();
    setParameters((p) => ({ ...p, ...value }));
    setResult(null);
    setError("");
    setLoading(false);
  }
  const valid =
    parameters.train_start < parameters.train_end &&
    parameters.train_end < parameters.test_start &&
    parameters.test_start < parameters.test_end;
  async function run() {
    const c = new AbortController();
    controller.current?.abort();
    controller.current = c;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      setResult(
        await post<Analysis>(
          `/assets/${encodeURIComponent(asset.id)}/analysis`,
          parameters,
          c.signal,
        ),
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    } finally {
      if (!c.signal.aborted) setLoading(false);
    }
  }
  return (
    <section className="analysis-panel" aria-label="Laboratoire quantitatif">
      <div className="section-heading">
        <div>
          <span className="eyebrow">LABORATOIRE QUANTITATIF</span>
          <h2>
            Comprendre les régimes<span className="accent">.</span>
          </h2>
        </div>
        <span className="model-badge">
          <Icon name="analysis" size={14} />
          Markov caché <span>3 états</span>
        </span>
      </div>
      <p className="lab-description">
        {asset.metric === "yield"
          ? "Identifier les régimes de taux. Les données de rendement ne permettent pas de simuler un portefeuille obligataire."
          : "Entraîner sur le passé. Tester sur une période distincte. Comparer au marché, frais inclus."}
      </p>
      <PeriodSelector points={points} periods={parameters} onChange={update} />
      {!valid && (
        <p className="error" role="alert">
          La période 1 doit précéder la période 2, sans chevauchement.
        </p>
      )}
      {asset.metric !== "yield" && (
        <details className="parameters">
          <summary>
            <Icon name="settings" size={16} />
            Paramètres de simulation
            <span>
              {parameters.fee_bps + parameters.slippage_bps} pb / ordre ·
              détention {parameters.min_hold}{" "}
              {asset.frequency === "monthly" ? "mois" : "jours"}
            </span>
            <Icon name="chevron" size={14} />
          </summary>
          <div className="parameter-grid">
            {fields.map((f) => (
              <label key={f.key}>
                <span className="field-label">
                  {f.label}
                  <Tooltip label={f.label}>
                    <span>{f.tip}</span>
                  </Tooltip>
                </span>
                <div className="number-field">
                  <input
                    type="number"
                    min={f.min}
                    max={f.max}
                    step={f.step}
                    value={
                      f.key === "risk_free_rate"
                        ? Math.round(parameters[f.key] * 10000) / 100
                        : parameters[f.key]
                    }
                    onChange={(e) =>
                      update({
                        ...parameters,
                        [f.key]:
                          Number(e.target.value) /
                          (f.key === "risk_free_rate" ? 100 : 1),
                      })
                    }
                  />
                  <span>{f.unit}</span>
                </div>
              </label>
            ))}
            <label>
              <span className="field-label">
                Seuil d’entrée
                <Tooltip label="Hystérésis">
                  <span>
                    Entrer lorsque la probabilité du régime porteur dépasse le
                    seuil d’entrée ; sortir sous le seuil de sortie. L’écart
                    entre les deux limite les changements de position.
                  </span>
                </Tooltip>
              </span>
              <div className="number-field">
                <input
                  type="number"
                  min="51"
                  max="95"
                  value={Math.round(parameters.entry_probability * 100)}
                  onChange={(e) =>
                    update({
                      ...parameters,
                      entry_probability: +e.target.value / 100,
                    })
                  }
                />
                <span>%</span>
              </div>
            </label>
            <label>
              <span className="field-label">Seuil de sortie</span>
              <div className="number-field">
                <input
                  type="number"
                  min="5"
                  max="49"
                  value={Math.round(parameters.exit_probability * 100)}
                  onChange={(e) =>
                    update({
                      ...parameters,
                      exit_probability: +e.target.value / 100,
                    })
                  }
                />
                <span>%</span>
              </div>
            </label>
          </div>
        </details>
      )}
      <div className="run-bar">
        <span className="fine-print">
          <Icon name="check" size={13} />
          Entraînement isolé · signal causal · calcul local
        </span>
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
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {loading && (
        <div className="analysis-loading" role="status">
          <span className="spinner" />
          <div>
            Ajustement du modèle & test causal
            <small>
              Trois initialisations, sans accès aux données futures.
            </small>
          </div>
        </div>
      )}
      {result && <AnalysisResults result={result} />}
    </section>
  );
}
