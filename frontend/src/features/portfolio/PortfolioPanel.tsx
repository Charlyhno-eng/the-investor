import { BankAccounts } from "./BankAccounts";
import {
  readBankAccounts,
  bankAccountsKey,
  type BankAccount,
} from "./bankAccounts";
import { PortfolioPrediction } from "./PortfolioPrediction";
import { PositionsTable } from "./PositionsTable";
import { CorrelationPanel } from "./CorrelationPanel";
import type { Quantities } from "./quantities";
import type { PortfolioResult as Result } from "./types";
import { sectorInfo } from "../../lib/sectors";
import { useEffect, useState, type ReactNode } from "react";
import { VolatilityPanel } from "../volatility/VolatilityPanel";
import { PerformancePanel } from "./PerformancePanel";
import { post } from "../../lib/api";
import { money } from "../../lib/currency";
import { categories } from "../../lib/format";
import type { Asset } from "../../lib/types";
import { Icon } from "../../components/Icon";
import { AllocationChart } from "./AllocationChart";
import { RecommendationsPanel } from "../recommendations/RecommendationsPanel";
export function PortfolioPanel({
  assets,
  quantities,
  onQuantity,
  title = "Portfolio",
  simulation = false,
  positionsHeader,
  lockedAssetIds = [],
  onToggleLock,
  recommendationAssets = assets,
}: {
  lockedAssetIds?: string[];
  onToggleLock?: (id: string) => void;
  title?: string;
  simulation?: boolean;
  positionsHeader?: ReactNode;
  assets: Asset[];
  quantities: Quantities;
  onQuantity: (id: string, quantity: number) => void;
  recommendationAssets?: Asset[];
}) {
  const [tab, setTab] = useState("positions");
  const [bankAccounts, setBankAccounts] = useState(readBankAccounts);
  const [includeBankAccounts, setIncludeBankAccounts] = useState(false);
  const [bankError, setBankError] = useState("");
  const bankTotal = bankAccounts.reduce(
    (sum, account) => sum + account.balance,
    0,
  );
  function updateBankAccounts(accounts: BankAccount[]) {
    setBankAccounts(accounts);
    try {
      localStorage.setItem(bankAccountsKey, JSON.stringify(accounts));
      setBankError("");
    } catch {
      setBankError(
        "Les comptes restent disponibles dans cette session, mais leur enregistrement local a échoué.",
      );
    }
  }

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
    assets.map((a) => [a.data_revision, a.last_date, a.last_value, a.points]),
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
  const includeCorrelation = tab === "correlation";
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
          {
            holdings: JSON.parse(holdings),
            years: includeCorrelation ? years : 3,
            include_benchmark: includeCorrelation,
            include_correlation: includeCorrelation,
          },
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
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [holdings, years, revision, historyRevision, includeCorrelation]);
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
              <button
                type="button"
                className="portfolio-total-toggle"
                disabled={simulation}
                aria-pressed={!simulation && includeBankAccounts}
                title={
                  simulation
                    ? undefined
                    : "Basculer entre investissements seuls et investissements + comptes bancaires"
                }
                onClick={() => setIncludeBankAccounts((value) => !value)}
              >
                <span>
                  {simulation
                    ? "Valeur simulée"
                    : includeBankAccounts
                      ? "Patrimoine total"
                      : "Valeur du Portfolio"}
                </span>
                <strong>
                  {result
                    ? money(
                        result.total +
                          (!simulation && includeBankAccounts ? bankTotal : 0),
                      )
                    : "—"}
                </strong>
                {!simulation && (
                  <small>
                    {includeBankAccounts
                      ? "Investissements + comptes bancaires"
                      : "Investissements seuls"}{" "}
                    · ⇄
                  </small>
                )}
              </button>
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
            ...(!simulation
              ? [["bank-accounts", "Comptes bancaires", "layers"]]
              : []),
            ["prediction", "Prédiction", "analysis"],
            ["performance", "Comparaison & optimisation", "stock"],
            ["correlation", "Corrélations", "analysis"],
            ["volatility", "Frontières d’efficience", "analysis"],
            ...(!simulation
              ? [["recommendations", "Recommandation action", "stock"]]
              : []),
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
        {tab !== "bank-accounts" &&
          tab !== "recommendations" &&
          tab !== "prediction" &&
          loading && (
            <p role="status">Actualisation des valeurs du portefeuille…</p>
          )}
        {tab !== "bank-accounts" &&
          tab !== "recommendations" &&
          tab !== "prediction" &&
          error && (
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
        {tab !== "bank-accounts" &&
          tab !== "recommendations" &&
          !assets.length && (
            <p>
              {simulation
                ? "Ajoutez des actifs à cette stratégie pour commencer."
                : "Ajoutez une étoile or à vos actifs détenus pour commencer."}
            </p>
          )}
        {!simulation && bankError && (
          <p className="error" role="alert">
            {bankError}
          </p>
        )}
        {tab === "bank-accounts" && !simulation && (
          <BankAccounts accounts={bankAccounts} onChange={updateBankAccounts} />
        )}
        {tab === "prediction" && (
          <PortfolioPrediction
            holdings={holdings}
            dataRevision={historyRevision}
          />
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
            dataRevision={historyRevision}
            holdings={holdings}
            lockedAssetIds={lockedAssetIds}
          />
        )}
        {tab === "recommendations" && !simulation && (
          <RecommendationsPanel
            assets={recommendationAssets}
            heldAssetIds={assets.map((a) => a.id)}
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
            <PositionsTable
              assets={assets}
              result={result}
              deviations={deviations}
              quantities={quantities}
              onQuantity={onQuantity}
              lockedAssetIds={lockedAssetIds}
              onToggleLock={onToggleLock}
              simulation={simulation}
            />
          </section>
        )}
        {tab === "positions" && (
          <>
            <section
              className="portfolio-content portfolio-allocation"
              aria-label="Répartition du portefeuille"
            >
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
                  key={allocationView}
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
          </>
        )}
        {tab === "correlation" && (
          <CorrelationPanel
            correlation={result?.correlation}
            years={years}
            onYearsChange={setYears}
          />
        )}
        {tab !== "bank-accounts" &&
          tab !== "volatility" &&
          tab !== "recommendations" &&
          tab !== "prediction" &&
          !!result?.excluded.length && (
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
