import { useEffect, useState } from "react";
import { post } from "../../lib/api";
import { percent } from "../../lib/format";
import type {
  predictPortfolio,
  HoldingSeries,
} from "../prediction/portfolioModel";
import { PredictionChart } from "../prediction/PredictionChart";
import { money } from "../../lib/currency";

type Result =
  | { status: "pending" }
  | {
      status: "insufficient";
      message: string;
      excluded: { id: string; name: string; reason: string }[];
    }
  | {
      status: "ready";
      series: HoldingSeries[];
      current_total: number;
    };

type Projection = ReturnType<typeof predictPortfolio>;
const projectionCache = new Map<
  string,
  { result: Result; model: Projection }
>();

export function PortfolioPrediction({
  holdings,
  dataRevision,
  active = true,
}: {
  holdings: string;
  dataRevision: string;
  active?: boolean;
}) {
  const [result, setResult] = useState<Result | null>(null);
  const [model, setModel] = useState<Projection | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!(JSON.parse(holdings) as unknown[]).length) {
      setResult({
        status: "insufficient",
        message:
          "Renseignez vos quantités dans Positions pour afficher la prédiction.",
        excluded: [],
      });
      setModel(null);
      setError("");
      return;
    }
    const key = holdings + ":" + dataRevision;
    const cached = projectionCache.get(key);
    if (cached && revision === 0) {
      setResult(cached.result);
      setModel(cached.model);
      setError("");
      return;
    }
    let worker: Worker | undefined;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    setResult(null);
    setModel(null);
    setError("");
    async function load() {
      try {
        const data = await post<Result>(
          "/portfolio/prediction",
          { holdings: JSON.parse(holdings) },
          controller.signal,
        );
        if (controller.signal.aborted) return;
        if (data.status === "pending") {
          if (++attempts >= 60)
            throw new Error(
              "L’import des historiques prend plus de temps que prévu. Réessayez dans un instant.",
            );
          timer = setTimeout(load, 2000);
        }
        setResult(data);
        if (data.status === "ready") {
          worker = new Worker(
            new URL("../prediction/portfolioWorker.ts", import.meta.url),
            { type: "module" },
          );
          worker.onmessage = (
            event: MessageEvent<{ model?: Projection; error?: string }>,
          ) => {
            if (controller.signal.aborted) return;
            if (event.data.model) {
              setModel(event.data.model);
              projectionCache.set(key, {
                result: data,
                model: event.data.model,
              });
              if (projectionCache.size > 4)
                projectionCache.delete(projectionCache.keys().next().value!);
            } else setError(event.data.error ?? "La projection a échoué.");
            worker?.terminate();
          };
          worker.onerror = () => {
            if (!controller.signal.aborted)
              setError("Le calcul de la projection a échoué. Réessayez.");
            worker?.terminate();
          };
          worker.postMessage(data.series);
        }
      } catch (e) {
        if (!controller.signal.aborted) setError((e as Error).message);
      }
    }
    void load();
    return () => {
      controller.abort();
      worker?.terminate();
      clearTimeout(timer);
    };
  }, [holdings, dataRevision, revision]);
  return (
    <section
      hidden={!active}
      className="portfolio-content"
      aria-label="Projection du portefeuille"
    >
      {error ? (
        <p className="error" role="alert">
          {error}{" "}
          <button
            className="secondary-button"
            onClick={() => setRevision((v) => v + 1)}
          >
            Réessayer
          </button>
        </p>
      ) : !result || result.status === "pending" ? (
        <p role="status">
          Préparation de l’historique du portefeuille en euros…
        </p>
      ) : result.status === "insufficient" ? (
        <>
          <p role="status">{result.message}</p>
          {result.excluded.map((p) => (
            <p key={p.id} className="fine-print">
              {p.name} : {p.reason}
            </p>
          ))}
        </>
      ) : !model ? (
        <p role="status">Calcul de la projection…</p>
      ) : active ? (
        <JointProjection model={model} />
      ) : null}
    </section>
  );
}

function JointProjection({ model }: { model: Projection }) {
  const { history, forecast, short } = model;
  const terminal = forecast.at(-1)!;
  return (
    <section
      className="analysis-panel prediction-panel"
      aria-label="Prédiction du portefeuille"
    >
      <PredictionChart history={history} forecast={forecast} unit="EUR" />
      <div className="reversion-summary">
        <div>
          <span>Valeur de départ</span>
          <strong>{money(history.at(-1)!.value)}</strong>
        </div>
        <div>
          <span>Médiane à 6 mois · P50</span>
          <strong>{money(terminal.p50)}</strong>
          <small>
            {percent(terminal.p50 / history.at(-1)!.value - 1, true)}
          </small>
        </div>
        <div>
          <span>Zone centrale à 50 % à l’échéance</span>
          <strong>
            {money(terminal.p25)} – {money(terminal.p75)}
          </strong>
        </div>
        <div>
          <span>Zone centrale à 90 % à l’échéance</span>
          <strong>
            {money(terminal.p05)} – {money(terminal.p95)}
          </strong>
        </div>
      </div>
      <p className="fine-print">
        Quantités et taux de change constants. Simulations conjointes des
        actifs, dépendances historiques estimées ; probabilités conditionnelles
        au modèle.
      </p>
      {short.length > 0 && (
        <p role="status">
          Historique trop court pour GARCH : {short.join(", ")}. Modèle
          provisoire sans tendance, volatilité historique disponible ; une seule
          cotation ne permet pas d’estimer le risque.
        </p>
      )}
    </section>
  );
}
