import { RegressionDeviation } from "./RegressionDeviation";
import { sectorInfo } from "../../lib/sectors";
import { useEffect, useState, type ReactNode } from "react";
import { VolatilityPanel } from "../volatility/VolatilityPanel";
import { PerformancePanel } from "./PerformancePanel";
import { Link } from "react-router";
import { post } from "../../lib/api";
import { money } from "../../lib/currency";
import { categories, date, number } from "../../lib/format";
import type { Asset } from "../../lib/types";
import { NumberInput } from "../../components/NumberInput";
import { Tooltip } from "../../components/Tooltip";
import { Icon } from "../../components/Icon";
import { stockCountry } from "../../lib/countries";
import { AllocationChart, correlationColor } from "./AllocationChart";
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
  price: number;
  value: number;
  fx_date: string | null;
  weight: number;
  date: string;
};
type Result = {
  status: "ready";
  positions: Position[];
  total: number;
  currency: "EUR";
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
  title = "Portfolio",
  simulation = false,
  positionsHeader,
  lockedAssetIds = [],
  onToggleLock,
}: {
  lockedAssetIds?: string[];
  onToggleLock?: (id: string) => void;
  title?: string;
  simulation?: boolean;
  positionsHeader?: ReactNode;
  assets: Asset[];
  quantities: Quantities;
  onQuantity: (id: string, quantity: number) => void;
}) {
  const [tab, setTab] = useState("positions");
  const [allocationView, setAllocationView] = useState("assets");
  const [years, setYears] = useState(3);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [revision, setRevision] = useState(0);
  const [deviations, setDeviations] = useState<
    {
      id: string;
      z: number | null;
      start?: string;
      end?: string;
      reason?: string;
    }[]
  >([]);
  const [deviationError, setDeviationError] = useState("");
  const assetIds = JSON.stringify(assets.map((a) => a.id));
  const historyRevision = JSON.stringify(
    assets.map((a) => [a.last_date, a.last_value, a.points]),
  );
  useEffect(() => {
    if (tab !== "positions") return;
    const controller = new AbortController();
    setDeviationError("");
    setDeviations([]);
    post<{ positions: typeof deviations }>(
      "/portfolio/regression",
      { asset_ids: JSON.parse(assetIds) },
      controller.signal,
    )
      .then((data) => {
        if (!controller.signal.aborted) setDeviations(data.positions);
      })
      .catch((e: Error) => {
        if (!controller.signal.aborted) setDeviationError(e.message);
      });
    return () => controller.abort();
  }, [assetIds, historyRevision, tab]);
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
          { holdings: JSON.parse(holdings), years, include_benchmark: true },
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
  const sectorPositions = Object.values(
    (result?.positions ?? []).reduce<
      Record<
        string,
        {
          id: string;
          name: string;
          color: string;
          value: number;
          weight: number;
        }
      >
    >((groups, position) => {
      const asset = assets.find((a) => a.id === position.id);
      const info =
        asset?.category === "stock"
          ? sectorInfo(asset.sector)
          : {
              name:
                categories.find((c) => c.id === asset?.category)?.name ??
                "Autres actifs",
              color: "#8490a2",
            };
      const group = (groups[info.name] ??= {
        id: info.name,
        name: info.name,
        color: info.color,
        value: 0,
        weight: 0,
      });
      group.value += position.value;
      group.weight += position.weight;
      return groups;
    }, {}),
  );
  const correlation = result?.correlation;
  return (
    <>
      {tab === "positions" && positionsHeader}
      <section
        className="portfolio-panel"
        aria-label={
          simulation ? `Vue d’ensemble ${title}` : "Vue d’ensemble du Portfolio"
        }
      >
        <header className="portfolio-heading">
          <div className="asset-title">
            <span className="asset-emblem stock">
              <Icon name="layers" size={24} />
            </span>
            <div>
              <span className="eyebrow">
                {simulation ? "SIMULATION" : "VOTRE PATRIMOINE"}
              </span>
              <h1>{title}</h1>
            </div>
          </div>
          <div className="portfolio-summary">
            <div className="portfolio-total">
              <span>
                {simulation ? "Valeur simulée" : "Valeur du Portfolio"}
              </span>
              <strong>{result ? money(result.total) : "—"}</strong>
            </div>
            <div>
              <span>Actifs détenus</span>
              <strong>
                {assets.filter((a) => (quantities[a.id] ?? 0) > 0).length}
                <small> / {assets.length} sélectionnés</small>
              </strong>
            </div>
          </div>
        </header>
        <div
          className="detail-tabs"
          role="tablist"
          aria-label="Vues du Portfolio"
        >
          {[
            ["positions", "Positions", "layers"],
            ["allocation", "Répartition", "allocation"],
            ["performance", "Comparaison & optimisation", "stock"],
            ["correlation", "Corrélations", "analysis"],
            ["volatility", "Frontières d’efficience", "analysis"],
          ].map(([key, title, icon]) => (
            <button
              key={key}
              role="tab"
              aria-selected={tab === key}
              onClick={() => setTab(key)}
            >
              <Icon name={icon} size={16} />
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
          <p>
            {simulation
              ? "Ajoutez des actifs à cette stratégie pour commencer."
              : "Ajoutez une étoile or à vos actifs détenus pour commencer."}
          </p>
        )}
        {tab === "volatility" && (
          <VolatilityPanel
            holdings={JSON.parse(holdings)}
            assets={assets}
            lockedAssetIds={lockedAssetIds}
          />
        )}
        {tab === "performance" && (
          <PerformancePanel
            holdings={holdings}
            lockedAssetIds={lockedAssetIds}
          />
        )}
        {tab === "positions" && (
          <section
            className="portfolio-content"
            aria-label="Positions détenues"
          >
            <div className="portfolio-section-heading">
              <div>
                <h2>Vos positions</h2>
                <p>
                  Ajustez vos quantités, y compris les fractions d’actif.
                  {onToggleLock &&
                    " Le cadenas fixe la quantité dans toutes les optimisations. Déverrouillez-la pour la modifier."}
                </p>
              </div>
              <span className="fine-print">Enregistrées sur ce navigateur</span>
            </div>
            {deviationError && (
              <p className="error" role="alert">
                Écarts à la régression indisponibles : {deviationError}
              </p>
            )}
            <div className="table-scroll">
              <table className="positions-table">
                <thead>
                  <tr>
                    <th>Actif</th>
                    <th>Quantité détenue</th>
                    <th>Valeur en €</th>
                    <th>Date du cours</th>
                    <th>
                      Écart à la régression{" "}
                      <Tooltip
                        floating
                        label="Écart à la régression sur cinq ans"
                      >
                        Écart du dernier prix à la régression logarithmique des
                        cinq dernières années, divisé par l’écart-type des
                        résidus (n − 2). Vert : sous la tendance ; jaune :
                        proche de la tendance ; rouge : au-dessus. Repères ± 1,5
                        σ. Si l’actif est récent, seul son historique disponible
                        est utilisé ; les dates figurent au survol. Ce repère
                        décrit le prix, sans garantir un signal d’achat ou de
                        vente.
                      </Tooltip>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {assets.map((asset, index) => {
                    const position = result?.positions.find(
                      (p) => p.id === asset.id,
                    );
                    const deviation = deviations.find((p) => p.id === asset.id);
                    return (
                      <tr
                        key={asset.id}
                        className={
                          index > 0 &&
                          assets[index - 1].category !== asset.category
                            ? "position-category-start"
                            : undefined
                        }
                      >
                        <th>
                          <Link
                            to={
                              simulation
                                ? `/assets/${asset.id}`
                                : `/assets/${asset.id}?library=portfolio`
                            }
                          >
                            {asset.name}
                          </Link>
                          <small>
                            {asset.category === "stock"
                              ? `${stockCountry(asset)} · `
                              : ""}
                            {asset.unit}
                            {asset.category === "commodity"
                              ? " · quantité dans l’unité cotée"
                              : ""}
                          </small>
                        </th>
                        <td>
                          <label>
                            <span className="sr-only">
                              Quantité {asset.name}
                            </span>
                            <NumberInput
                              disabled={lockedAssetIds.includes(asset.id)}
                              min={0}
                              max={1e15}
                              step="any"
                              value={quantities[asset.id] ?? 0}
                              onChange={(value) => onQuantity(asset.id, value)}
                            />
                          </label>
                          {onToggleLock && (
                            <button
                              type="button"
                              className="quantity-lock"
                              aria-label={`${lockedAssetIds.includes(asset.id) ? "Déverrouiller" : "Verrouiller"} ${asset.name}`}
                              aria-pressed={lockedAssetIds.includes(asset.id)}
                              title="Conserver cette quantité dans toutes les optimisations"
                              onClick={() => onToggleLock(asset.id)}
                            >
                              <Icon
                                name={
                                  lockedAssetIds.includes(asset.id)
                                    ? "lock"
                                    : "unlock"
                                }
                                size={18}
                              />
                            </button>
                          )}
                        </td>
                        <td>{position ? money(position.value) : "—"}</td>
                        <td>{position ? date(position.date) : "—"}</td>
                        <td>
                          <RegressionDeviation deviation={deviation} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )}
        {tab === "allocation" && (
          <>
            <section className="portfolio-content">
              <div className="portfolio-section-heading">
                <div>
                  <h2>
                    Répartition par{" "}
                    {allocationView === "assets" ? "actif" : "secteur"}
                  </h2>
                  <p>Explorez le poids de vos actifs ou de leurs secteurs.</p>
                </div>
              </div>
              <label className="allocation-view-control">
                Afficher par{" "}
                <select
                  aria-label="Répartition par"
                  value={allocationView}
                  onChange={(e) => setAllocationView(e.target.value)}
                >
                  <option value="assets">Actif</option>
                  <option value="sectors">Secteur</option>
                </select>
              </label>
              {result?.positions.length ? (
                <AllocationChart
                  positions={
                    allocationView === "assets"
                      ? result.positions
                      : sectorPositions
                  }
                  label={allocationView === "assets" ? "ACTIF" : "SECTEUR"}
                  total={result.total}
                />
              ) : (
                <div className="portfolio-empty">
                  Renseignez vos quantités dans Positions pour afficher la
                  répartition.
                </div>
              )}
            </section>
            <p className="fine-print">
              Quantité × dernier prix disponible, converti en euros. Le change
              utilisé est celui du jour du cours, ou le dernier connu dans les 7
              jours précédents. Les dates des prix figurent dans Positions. Les
              actifs sans prix monétaire exploitable sont exclus du total ; les
              quantités ne sont pas réajustées automatiquement lors des
              divisions d’actions.
            </p>
          </>
        )}
        {tab === "correlation" && (
          <>
            <div className="portfolio-section-heading">
              <div>
                <h2 className="correlation-title">
                  Matrice de corrélation{" "}
                  <Tooltip label="Méthode de corrélation">
                    Corrélation de Pearson des rendements logarithmiques en USD,
                    dividendes réinvestis pour les actions. Dates communes
                    uniquement, sans remplissage des données manquantes. Les
                    quantités ne modifient pas les coefficients.
                    {correlation?.frequency === "monthly" &&
                      " Les séries sont alignées sur les mois terminés."}
                    {correlation &&
                      ` « — » : dispersion nulle ou moins de ${correlation.minimum} rendements communs.`}
                  </Tooltip>
                </h2>
              </div>
              <label className="portfolio-period">
                Période
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
            </div>
            {correlation && correlation.assets.length > 0 ? (
              <>
                <div className="correlation-meta">
                  <span>
                    {correlation.observations} rendements{" "}
                    {correlation.frequency === "monthly"
                      ? "entre mois communs"
                      : "sur dates communes"}{" "}
                    · {correlation.start ?? "—"} → {correlation.end ?? "—"}
                  </span>
                  <div className="correlation-scale">
                    <span>−1 · Opposés</span>
                    <i />
                    <span>+1 · Similaires</span>
                  </div>
                </div>
                <div className="table-scroll correlation-scroll">
                  <table className="correlation-table">
                    <caption className="sr-only">
                      Corrélations des actifs et du S&P 500
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
                                    ? "#171d29"
                                    : correlationColor(value),
                                color:
                                  value === null
                                    ? "#8490a2"
                                    : Math.abs(value) > 0.72
                                      ? "#fff"
                                      : "#172235",
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
              </>
            ) : (
              <p>
                Renseignez au moins deux positions pour comparer leurs
                corrélations.
              </p>
            )}
          </>
        )}
        {tab !== "volatility" && !!result?.excluded.length && (
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
    </>
  );
}
