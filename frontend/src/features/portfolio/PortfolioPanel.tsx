import { useEffect, useState } from "react";
import { Link } from "react-router";
import { post } from "../../lib/api";
import { date, number, percent } from "../../lib/format";
import type { Asset } from "../../lib/types";
import { NumberInput } from "../analysis/NumberInput";
export type Quantities = Record<string, number>;
export function readQuantities(): Quantities {
  try {
    const value = JSON.parse(
      localStorage.getItem("investor-quantities") ?? "{}",
    );
    if (value && typeof value === "object" && !Array.isArray(value))
      return Object.fromEntries(
        Object.entries(value).filter(
          (entry): entry is [string, number] =>
            typeof entry[1] === "number" &&
            Number.isFinite(entry[1]) &&
            entry[1] >= 0 &&
            entry[1] <= 1e15,
        ),
      );
  } catch {
    /* Session remains usable without storage. */
  }
  return {};
}
type Position = {
  id: string;
  name: string;
  quantity: number;
  price_usd: number;
  value_usd: number;
  weight: number;
  date: string;
};
type Result = {
  status: "ready";
  positions: Position[];
  total_usd: number;
  excluded: { id: string; name: string; reason: string }[];
  correlation: {
    assets: { id: string; name: string }[];
    matrix: (number | null)[][];
    observations: number;
    minimum: number;
    frequency: string;
    start: string | null;
    end: string | null;
  };
};
export function PortfolioPanel({
  assets,
  quantities,
  onQuantity,
}: {
  assets: Asset[];
  quantities: Quantities;
  onQuantity: (id: string, quantity: number) => void;
}) {
  const [tab, setTab] = useState("positions");
  const [years, setYears] = useState(3);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [revision, setRevision] = useState(0);
  const holdings = JSON.stringify(
    assets
      .filter((a) => (quantities[a.id] ?? 0) > 0)
      .map((a) => ({ asset_id: a.id, quantity: quantities[a.id] })),
  );
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    setLoading(true);
    setError("");
    async function load() {
      try {
        const data = await post<Result | { status: "pending" }>(
          "/portfolio/analytics",
          { holdings: JSON.parse(holdings), years },
          controller.signal,
        );
        if (controller.signal.aborted) return;
        if (data.status === "pending") {
          if (++attempts >= 60)
            throw new Error(
              "L’import des prix prend plus de temps que prévu. Réessayez dans un instant.",
            );
          timer = setTimeout(load, 2000);
        } else {
          setResult(data);
          setLoading(false);
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          setError((e as Error).message);
          setLoading(false);
        }
      }
    }
    timer = setTimeout(load, 450);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [holdings, years, revision]);
  const correlation = result?.correlation;
  return (
    <section
      className="portfolio-panel"
      aria-label="Vue d’ensemble du Portfolio"
    >
      <h1>Portfolio</h1>
      <p className="muted">
        Vos actifs détenus · quantités enregistrées sur ce navigateur
      </p>
      <div
        className="detail-tabs"
        role="tablist"
        aria-label="Vues du Portfolio"
      >
        {[
          ["positions", "Positions"],
          ["allocation", "Répartition par actif"],
          ["correlation", "Corrélations"],
        ].map(([key, title]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
          >
            {title}
          </button>
        ))}
      </div>
      {loading && (
        <p role="status">Actualisation des valeurs du portefeuille…</p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}{" "}
          <button
            className="secondary-button"
            onClick={() => setRevision((v) => v + 1)}
          >
            Réessayer
          </button>
        </p>
      )}
      {!assets.length && (
        <p>Ajoutez une étoile or à vos actifs détenus pour commencer.</p>
      )}
      {tab === "positions" && (
        <div className="table-scroll">
          <table className="positions-table">
            <thead>
              <tr>
                <th>Actif</th>
                <th>Quantité détenue</th>
                <th>Valeur en USD</th>
                <th>Dernier prix</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset) => {
                const position = result?.positions.find(
                  (p) => p.id === asset.id,
                );
                return (
                  <tr key={asset.id}>
                    <th>
                      <Link to={`/assets/${asset.id}?library=portfolio`}>
                        {asset.name}
                      </Link>
                      <small>
                        {asset.unit}
                        {asset.category === "commodity"
                          ? " · quantité dans l’unité cotée"
                          : ""}
                      </small>
                    </th>
                    <td>
                      <label>
                        <span className="sr-only">Quantité {asset.name}</span>
                        <NumberInput
                          min={0}
                          max={1e15}
                          step="any"
                          value={quantities[asset.id] ?? 0}
                          onChange={(value) => onQuantity(asset.id, value)}
                        />
                      </label>
                    </td>
                    <td>
                      {position ? `${number(position.value_usd)} $` : "—"}
                    </td>
                    <td>{position ? date(position.date) : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {tab === "allocation" && (
        <>
          <div className="portfolio-total">
            <span>Valeur des positions valorisables</span>
            <strong>{result ? `${number(result.total_usd)} USD` : "—"}</strong>
          </div>
          {!result?.positions.length && (
            <p>
              Renseignez vos quantités dans Positions pour afficher la
              répartition.
            </p>
          )}
          {result?.positions
            .slice()
            .sort((a, b) => b.weight - a.weight)
            .map((p) => (
              <div className="allocation-row" key={p.id}>
                <div>
                  <span>{p.name}</span>
                  <strong>{percent(p.weight)}</strong>
                  <span>{number(p.value_usd)} USD</span>
                </div>
                <progress
                  max={1}
                  value={p.weight}
                  aria-label={`Poids de ${p.name}`}
                />
              </div>
            ))}
          <p className="fine-print">
            Quantité × dernier prix disponible, converti en USD. Les dates des
            prix figurent dans Positions. Les actifs sans prix monétaire
            exploitable sont exclus du total ; les quantités ne sont pas
            réajustées automatiquement lors des divisions d’actions.
          </p>
        </>
      )}
      {tab === "correlation" && (
        <>
          <label className="portfolio-period">
            Historique de corrélation
            <select
              value={years}
              onChange={(e) => setYears(Number(e.target.value))}
            >
              {[1, 3, 5, 10].map((year) => (
                <option key={year} value={year}>
                  {year} an{year > 1 ? "s" : ""}
                </option>
              ))}
            </select>
          </label>
          <p className="fine-print">
            Corrélation de Pearson des rendements logarithmiques en USD,
            dividendes réinvestis pour les actions. −1 : mouvements opposés · 0
            : faible relation linéaire · +1 : mouvements similaires. Les
            quantités déterminent les actifs inclus, pas les coefficients.
          </p>
          {correlation && correlation.assets.length > 0 ? (
            <>
              <div className="table-scroll">
                <table className="correlation-table">
                  <caption>
                    {correlation.observations} rendements{" "}
                    {correlation.frequency === "monthly"
                      ? "entre mois communs"
                      : "sur dates communes"}{" "}
                    · {correlation.start ?? "—"} → {correlation.end ?? "—"}
                  </caption>
                  <thead>
                    <tr>
                      <th>Actif</th>
                      {correlation.assets.map((a) => (
                        <th key={a.id}>{a.name}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {correlation.assets.map((a, i) => (
                      <tr key={a.id}>
                        <th>{a.name}</th>
                        {correlation.matrix[i].map((value, j) => (
                          <td
                            key={j}
                            title={`${a.name} / ${correlation.assets[j].name}`}
                            style={{
                              background:
                                value === null
                                  ? undefined
                                  : `${value >= 0 ? "rgba(101,199,165," : "rgba(238,129,144,"}${Math.abs(value) * 0.45 + 0.05})`,
                            }}
                          >
                            {value === null ? "—" : number(value, 2)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="fine-print">
                Dates communes uniquement, sans remplissage des données
                manquantes.{" "}
                {correlation.frequency === "monthly" &&
                  "Présence de séries mensuelles : tous les actifs sont comparés à la dernière observation de chaque mois terminé. "}
                « — » signifie une dispersion nulle ou moins de{" "}
                {correlation.minimum} rendements communs. La corrélation passée
                ne prédit pas celle à venir.
              </p>
            </>
          ) : (
            <p>
              Renseignez au moins deux positions pour comparer leurs
              corrélations.
            </p>
          )}
        </>
      )}
      {!!result?.excluded.length && (
        <div className="portfolio-exclusions">
          <p>Positions non valorisées :</p>
          {result.excluded.map((entry) => (
            <p key={entry.id}>
              {entry.name} : {entry.reason}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}
