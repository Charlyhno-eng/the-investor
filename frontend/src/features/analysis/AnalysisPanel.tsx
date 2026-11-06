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
    slippage_bps: 0,
    min_hold: 1,
    entry_confirmation: 5,
    exit_confirmation: 3,
    max_trades: null,
    entry_probability: 0.8,
    exit_probability: 0.5,
    risk_free_rate: 0,
  };
}
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
    if (loading) return;
    const c = new AbortController();
    controller.current?.abort();
    controller.current = c;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await post<Analysis>(
        `/assets/${encodeURIComponent(asset.id)}/analysis`,
        parameters,
        c.signal,
      );
      if (!c.signal.aborted) setResult(response);
    } catch (e) {
      if (!c.signal.aborted) setError((e as Error).message);
    } finally {
      if (!c.signal.aborted) setLoading(false);
    }
  }
  return (
    <section className="analysis-panel" aria-label="Analyse HMM">
      <fieldset className="analysis-controls" disabled={loading}>
        <legend className="sr-only">Périodes et paramètres de l’analyse</legend>
        <PeriodSelector
          points={points}
          periods={parameters}
          onChange={update}
          disabled={loading}
        />
        {!valid && (
          <p className="error" role="alert">
            La période 1 doit précéder la période 2, sans chevauchement.
          </p>
        )}
        {parameters.exit_probability >= parameters.entry_probability && (
          <p className="error" role="alert">
            Le seuil de sortie doit être inférieur au seuil d’achat.
          </p>
        )}
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
                  Frais par ordre
                  <Tooltip label="Frais par ordre">
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
              <label>
                <span className="field-label">
                  Achat au-dessus de
                  <Tooltip label="Hystérésis">
                    <span>
                      Entrer lorsque la probabilité du régime de hausse dépasse
                      le seuil d’entrée ; sortir sous le seuil de sortie.
                      L’écart entre les deux limite les changements de position.
                    </span>
                  </Tooltip>
                </span>
                <div className="number-field">
                  <NumberInput
                    min="51"
                    max="95"
                    value={Math.round(parameters.entry_probability * 100)}
                    onChange={(value) =>
                      update({
                        ...parameters,
                        entry_probability: value / 100,
                      })
                    }
                  />
                  <span>%</span>
                </div>
              </label>
              <label>
                <span className="field-label">Vente en dessous de</span>
                <div className="number-field">
                  <NumberInput
                    min="5"
                    max="90"
                    value={Math.round(parameters.exit_probability * 100)}
                    onChange={(value) =>
                      update({
                        ...parameters,
                        exit_probability: value / 100,
                      })
                    }
                  />
                  <span>%</span>
                </div>
              </label>
              {(
                [
                  ["entry_confirmation", "Confirmations à l’achat"],
                  ["exit_confirmation", "Confirmations à la vente"],
                ] as const
              ).map(([key, label]) => (
                <label key={key}>
                  <span className="field-label">
                    {label}
                    <Tooltip label={label}>
                      <span>
                        Nombre d’observations consécutives avant{" "}
                        {key === "entry_confirmation" ? "achat" : "vente"}. Une
                        interruption remet le compteur à zéro.
                      </span>
                    </Tooltip>
                  </span>
                  <div className="number-field">
                    <NumberInput
                      min={1}
                      max={30}
                      step={1}
                      value={parameters[key]}
                      onChange={(value) =>
                        update({ ...parameters, [key]: value })
                      }
                    />
                    <span>
                      {asset.frequency === "monthly" ? "mois" : "jours"}
                    </span>
                  </div>
                </label>
              ))}
            </div>
          </details>
        )}
      </fieldset>
      <div className="run-bar analysis-run-bar">
        <button
          className="primary-button"
          disabled={
            loading ||
            !valid ||
            parameters.exit_probability >= parameters.entry_probability
          }
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
      {loading && <AnalysisProgress />}
      {result && <AnalysisResults result={result} />}
    </section>
  );
}
