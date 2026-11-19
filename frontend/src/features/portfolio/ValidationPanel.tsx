import { useEffect, useMemo, useState } from "react";
import { HistoryChart } from "../../components/HistoryChart";
import { post } from "../../lib/api";
import { date, number, percent } from "../../lib/format";

const series = [
  { key: "benchmark", title: "Référence", color: "#739de8" },
  { key: "buy_hold", title: "Achat-conservation", color: "#bc9de0" },
  { key: "equal", title: "Équipondération trimestrielle", color: "#65c7a5" },
  { key: "strategy", title: "Méthode testée", color: "#d5aa73" },
] as const;
type Key = (typeof series)[number]["key"];
type Metrics = Record<string, number | null>;
type Fold = {
  signal: string;
  execution: string;
  end: string;
  train_start: string;
  train_end: string;
  complete: boolean;
  observations: number;
  weights: number[];
  risk_contributions?: number[] | null;
  risk_contributions_execution?: number[] | null;
  risk_contributions_end?: number[] | null;
  rebalance_skipped?: boolean;
  returns: Record<Key, number>;
  turnover: Record<Key, number>;
  costs: Record<Key, number>;
};
export type Ready = {
  diagnostics?: {
    id: string;
    name: string;
    z: number | null;
    phi: number | null;
    half_life: number | null;
    recent_shift: number | null;
    slope_change: number | null;
  }[];
  position_traces?: {
    time: string;
    id: string;
    price: number;
    z: number | null;
  }[];
  status: "ready";
  parameters?: { whole_shares: boolean };
  start: string;
  end: string;
  notices?: string[];
  requested_start: string;
  benchmark_name: string;
  completed_quarters: number;
  assets: { id: string; name: string }[];
  equity: ({ time: string } & Record<Key, number>)[];
  metrics: Record<Key, Metrics>;
  folds: Fold[];
  final_portfolio: {
    date: string;
    initial_capital: number;
    total: number;
    cash: number;
    positions: {
      id: string;
      name: string;
      quantity: number;
      value: number;
      weight: number;
    }[];
  };
  transactions: {
    asset_id: string;
    name: string;
    signal: string;
    execution: string;
    side: "buy" | "sell";
    quantity: number;
    price: number;
    amount: number;
    fee: number;
    z: number | null;
    profit_return?: number | null;
    reason?: string;
    cash_after?: number;
  }[];
};
type Result = Ready | { status: "insufficient"; message: string };
const metricNumber = (value: number | null) =>
  value == null ? "—" : number(value, 2);

const metricRows = [
  { key: "total_return", label: "Rendement net" },
  { key: "cagr", label: "CAGR net" },
  {
    key: "max_drawdown",
    label: "Drawdown maximal",
    hint: "Baisse moins forte",
  },
  { key: "volatility", label: "Volatilité annualisée", lower: true },
  {
    key: "annual_turnover",
    label: "Rotation annuelle hors entrée",
    lower: true,
  },
  { key: "worst_quarter", label: "Pire trimestre complet" },
  { key: "sharpe", label: "Sharpe · taux de référence 0 %", format: "number" },
  {
    key: "cost_eur",
    label: "Frais payés (€)",
    lower: true,
    format: "money",
  },
  {
    key: "positive_quarters",
    label: "Trimestres complets positifs",
    format: "quarters",
  },
  {
    key: "winning_quarters",
    label: "Trimestres complets battant la référence",
    format: "quarters",
  },
  {
    key: "market_exposure",
    label: "Exposition au marché",
    neutral: true,
    hint: "Part moyenne du capital investi depuis la première exécution",
  },
] as const;

export function ValidationMetrics({
  ready,
  displayedSeries = series,
  accessibleLabel = "Résultats hors échantillon",
  showComparisonLegend = true,
}: {
  ready: Pick<Ready, "completed_quarters" | "benchmark_name"> & {
    metrics: Partial<Ready["metrics"]>;
  };
  displayedSeries?: readonly { key: Key; title: string; color: string }[];
  accessibleLabel?: string;
  showComparisonLegend?: boolean;
}) {
  return (
    <>
      <div className="table-scroll">
        <table
          className="positions-table performance-metrics validation-metrics"
          aria-label={accessibleLabel}
        >
          <thead>
            <tr>
              <th scope="col">Indicateur</th>
              {displayedSeries.map((s) => (
                <th scope="col" key={s.key}>
                  {s.key === "benchmark" ? ready.benchmark_name : s.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metricRows.map((metric) => {
              const neutral = "neutral" in metric && metric.neutral;
              const lower = "lower" in metric && metric.lower;
              const format = "format" in metric ? metric.format : "percent";
              const values = Object.fromEntries(
                displayedSeries.map(({ key }) => {
                  const raw = ready.metrics[key]?.[metric.key] ?? null;
                  const unavailable =
                    format === "quarters" &&
                    (!ready.completed_quarters ||
                      (metric.key === "winning_quarters" &&
                        key === "benchmark"));
                  return [
                    key,
                    !unavailable && raw != null && Number.isFinite(raw)
                      ? raw
                      : null,
                  ];
                }),
              ) as Record<Key, number | null>;
              const available = Object.values(values).filter(
                (v): v is number => v != null,
              );
              const best = available.length
                ? lower
                  ? Math.min(...available)
                  : Math.max(...available)
                : null;
              const hasDifference =
                available.length > 1 &&
                Math.max(...available) - Math.min(...available) > 1e-10;
              return (
                <tr key={metric.key}>
                  <th scope="row">
                    {metric.label}
                    <small>
                      {"hint" in metric
                        ? metric.hint
                        : lower
                          ? "Plus faible"
                          : "Plus élevé"}
                    </small>
                  </th>
                  {displayedSeries.map(({ key }) => {
                    const value = values[key];
                    const compare = (
                      reference: number | null,
                      name: string,
                    ) => {
                      const delta =
                        value == null || reference == null
                          ? null
                          : (value - reference) * (lower ? -1 : 1);
                      const state =
                        neutral || delta == null
                          ? "unavailable"
                          : Math.abs(delta) < 1e-10
                            ? "equal"
                            : delta > 0
                              ? "better"
                              : "worse";
                      const status =
                        state === "unavailable"
                          ? neutral
                            ? "L’exposition décrit le temps investi, sans classement meilleur ou moins bon"
                            : `Comparaison indisponible avec ${name}`
                          : state === "equal"
                            ? `Équivalent à ${name}`
                            : state === "better"
                              ? `Meilleur que ${name}`
                              : `Moins bon que ${name}`;
                      return { state, status };
                    };
                    const benchmark = compare(
                      values.benchmark,
                      ready.benchmark_name,
                    );
                    const markers =
                      key === "benchmark"
                        ? [
                            {
                              state: "reference",
                              status: `Référence ${ready.benchmark_name}`,
                            },
                          ]
                        : key === "buy_hold"
                          ? [benchmark]
                          : [
                              benchmark,
                              ...(displayedSeries.some(
                                (s) => s.key === "buy_hold",
                              )
                                ? [
                                    compare(
                                      values.buy_hold,
                                      "l’achat-conservation",
                                    ),
                                  ]
                                : []),
                            ];
                    const isBest =
                      !neutral &&
                      hasDifference &&
                      value != null &&
                      best != null &&
                      Math.abs(value - best) < 1e-10;
                    return (
                      <td
                        key={key}
                        data-comparison={
                          key === "benchmark" ? "reference" : benchmark.state
                        }
                        data-best={isBest || undefined}
                        title={markers.map((m) => m.status).join(" · ")}
                      >
                        <span className="metric-value">
                          <span className="metric-signals">
                            {markers.map((m, i) => (
                              <i
                                key={i}
                                data-comparison={m.state}
                                role="img"
                                aria-label={m.status}
                                title={m.status}
                              />
                            ))}
                          </span>
                          {value == null
                            ? "—"
                            : format === "quarters"
                              ? `${value} / ${ready.completed_quarters}`
                              : format === "money"
                                ? `${metricNumber(value)} €`
                                : format === "number"
                                  ? metricNumber(value)
                                  : percent(value)}
                        </span>
                        {isBest && (
                          <small
                            className="validation-best-label"
                            title="Meilleure valeur pour cet indicateur"
                          >
                            Meilleur
                          </small>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {showComparisonLegend &&
        (displayedSeries.some((s) => s.key === "buy_hold") ? (
          <p className="metric-signals-legend">
            Premier trait : comparaison à {ready.benchmark_name}. Second trait
            pour les deux méthodes : comparaison à l’achat-conservation. Vert :
            meilleur · Rouge : moins bon · Gris : égal ou indisponible.
          </p>
        ) : (
          <p className="metric-signals-legend">
            Comparaison à {ready.benchmark_name} · Vert : meilleur · Rouge :
            moins bon · Gris : égal ou indisponible.
          </p>
        ))}
    </>
  );
}

function ValidationLedger({ ready }: { ready: Ready }) {
  const [page, setPage] = useState(0);
  const portfolio = ready.final_portfolio;
  const trades = useMemo(
    () => ready.transactions.slice().reverse(),
    [ready.transactions],
  );
  const pageSize = 50;
  const pages = Math.max(1, Math.ceil(trades.length / pageSize));
  const money = (v: number) => `${number(v, 2)} €`;
  return (
    <div className="validation-ledger">
      <h3>Portefeuille simulé au {date(portfolio.date)}</h3>
      <p>
        Capital initial : {money(portfolio.initial_capital)} · Valeur finale :{" "}
        {money(portfolio.total)} · Liquidités : {money(portfolio.cash)}
      </p>
      <div className="table-scroll">
        <table
          className="positions-table"
          aria-label="Positions finales de la méthode"
        >
          <thead>
            <tr>
              <th>Actif</th>
              <th>
                {ready.parameters?.whole_shares ? "Quantité" : "Parts ajustées"}
              </th>
              <th>Valeur en euros</th>
              <th>Poids final</th>
            </tr>
          </thead>
          <tbody>
            {portfolio.positions.map((p) => (
              <tr key={p.id}>
                <th scope="row">{p.name}</th>
                <td>{number(p.quantity, 4)}</td>
                <td>{money(p.value)}</td>
                <td>{percent(p.weight)}</td>
              </tr>
            ))}
            <tr>
              <th scope="row">Liquidités</th>
              <td>—</td>
              <td>{money(portfolio.cash)}</td>
              <td>{percent(portfolio.cash / portfolio.total)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      {!portfolio.positions.some((p) => p.quantity > 0) && (
        <p>Tout le capital est en liquidités.</p>
      )}
      <h3>Journal des achats et ventes</h3>
      <p>
        {trades.length} opération(s) · Les plus récentes en premier · Frais
        séparés du montant échangé · Gain des ventes net de frais, dividendes
        encaissés inclus
      </p>
      {trades.length ? (
        <>
          <div className="table-scroll">
            <table
              className="positions-table"
              aria-label="Journal des achats et ventes"
            >
              <thead>
                <tr>
                  <th>Exécution</th>
                  <th>Signal</th>
                  <th>Actif</th>
                  <th>Opération</th>
                  <th>
                    {ready.parameters?.whole_shares
                      ? "Quantité"
                      : "Parts ajustées"}
                  </th>
                  <th>Montant</th>
                  <th>Frais</th>
                  <th>Écart-type</th>
                  <th>Liquidités après</th>
                </tr>
              </thead>
              <tbody>
                {trades
                  .slice(page * pageSize, (page + 1) * pageSize)
                  .map((t, i) => (
                    <tr key={i}>
                      <td>{date(t.execution)}</td>
                      <td>{date(t.signal)}</td>
                      <th scope="row">{t.name}</th>
                      <td
                        className={
                          t.side === "sell" && t.profit_return != null
                            ? t.profit_return > 0
                              ? "positive"
                              : t.profit_return < 0
                                ? "negative"
                                : undefined
                            : undefined
                        }
                      >
                        {t.side === "buy"
                          ? "Achat"
                          : `Vente${t.profit_return != null ? ` (${percent(t.profit_return, true)})` : ""}`}
                        {(t.reason === "etf_passive_sp500" ||
                          t.reason === "etf_rebound_sp500" ||
                          t.reason === "etf_defensive_sp500" ||
                          t.reason === "etf_slow_entry_sp500" ||
                          t.reason === "etf_slow_defensive_sp500") && (
                          <small className="validation-trade-reason">
                            {t.reason === "etf_passive_sp500"
                              ? "Poche passive · achat-conservation"
                              : t.reason === "etf_rebound_sp500"
                                ? "Poche défensive · rebond · cible 100 %"
                                : t.reason === "etf_defensive_sp500"
                                  ? "Poche défensive · cible 10 %"
                                  : t.reason === "etf_slow_entry_sp500"
                                    ? "Poche lente · entrée · cible 100 %"
                                    : "Poche lente · cible 10 %"}
                          </small>
                        )}
                        {t.reason === "agreement_rebalance" && (
                          <small className="validation-trade-reason">
                            Ajustement à la cible des cinq modèles et du filtre
                            de baisses
                          </small>
                        )}
                        {t.reason === "funding" && (
                          <small className="validation-trade-reason">
                            Financement d’un achat
                          </small>
                        )}
                        {t.reason === "trailing_z" && (
                          <small className="validation-trade-reason">
                            Repli de l’écart-type
                          </small>
                        )}
                      </td>
                      <td>{number(t.quantity, 4)}</td>
                      <td>{money(t.amount)}</td>
                      <td>{money(t.fee)}</td>
                      <td>{metricNumber(t.z)}</td>
                      <td>
                        {t.cash_after == null ? "—" : money(t.cash_after)}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          {pages > 1 && (
            <div className="validation-pagination">
              <button
                type="button"
                disabled={page === 0}
                onClick={() => setPage(page - 1)}
              >
                Précédent
              </button>
              <span>
                Page {page + 1} / {pages}
              </span>
              <button
                type="button"
                disabled={page + 1 >= pages}
                onClick={() => setPage(page + 1)}
              >
                Suivant
              </button>
            </div>
          )}
        </>
      ) : (
        <p>Aucun achat ni aucune vente sur cette période.</p>
      )}
    </div>
  );
}

type ValidationMode =
  | "volatility"
  | "mean_reversion"
  | "correlation"
  | "risk_parity"
  | "etf_switch"
  | "psp5_downside";

export function ValidationPanel({
  holdings,
  mode,
  dataRevision,
  prominentHeading = false,
}: {
  holdings: string;
  mode: ValidationMode;
  dataRevision: string;
  prominentHeading?: boolean;
}) {
  // Universe edits reset the form; background catalogue updates preserve the user’s work.
  return (
    <ValidationForm
      key={mode + holdings}
      holdings={holdings}
      mode={mode}
      dataRevision={dataRevision}
      prominentHeading={prominentHeading}
    />
  );
}

function ValidationForm({
  holdings,
  mode,
  dataRevision,
  prominentHeading = false,
}: {
  holdings: string;
  mode: ValidationMode;
  dataRevision: string;
  prominentHeading?: boolean;
}) {
  const sp500 = mode === "etf_switch" || mode === "psp5_downside";
  const [years, setYears] = useState(5);
  const [fee, setFee] = useState(sp500 ? "0.12" : "0.5");
  const [capital, setCapital] = useState("10000");
  const [wholeShares, setWholeShares] = useState(sp500);
  const [entryZ, setEntryZ] = useState("2");
  const [exitZ, setExitZ] = useState("2");
  const [job, setJob] = useState<{
    body: object;
    revision: number;
    sourceRevision: string;
  } | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const ids = (JSON.parse(holdings) as { asset_id: string }[]).map(
    (h) => h.asset_id,
  );
  const validFee =
    fee.trim() !== "" &&
    Number.isFinite(Number(fee)) &&
    Number(fee) >= 0 &&
    Number(fee) <= 10;
  const validCapital =
    capital.trim() !== "" &&
    Number.isFinite(Number(capital)) &&
    Number(capital) >= 1 &&
    Number(capital) <= 1e12;
  const inRange = (value: string, minimum: number, maximum: number) =>
    value.trim() !== "" &&
    Number.isFinite(Number(value)) &&
    Number(value) >= minimum &&
    Number(value) <= maximum;
  const validUniverse = !sp500 || ids.length === 1;
  const validReversion =
    mode !== "mean_reversion" ||
    (inRange(entryZ, 0.5, 4) && inRange(exitZ, 0, 4));
  const title = {
    volatility: "Volatilité minimale",
    mean_reversion: "Retour à la moyenne",
    correlation: "Corrélation minimale",
    risk_parity: "Parité de risque",
    psp5_downside: "S&P 500 · Filtre de baisses + cinq modèles",
    etf_switch: "S&P 500 · Régression",
  }[mode];
  function invalidate() {
    setJob(null);
    setResult(null);
    setLoading(false);
    setError("");
  }
  useEffect(() => {
    if (!job) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    async function load() {
      try {
        const data = await post<Result | { status: "pending" }>(
          "/portfolio/validation",
          job!.body,
          controller.signal,
        );
        if (controller.signal.aborted) return;
        if (data.status === "pending") {
          if (++attempts >= 60)
            throw new Error(
              "Les données sont encore en cours d’import. Réessayez dans un instant.",
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
  }, [job]);
  const ready = result?.status === "ready" ? result : null;
  const chartSeries = useMemo(
    () =>
      sp500
        ? series.filter((s) => s.key === "benchmark" || s.key === "strategy")
        : series,
    [sp500],
  );
  const lines = useMemo(
    () =>
      ready
        ? chartSeries.map((s) => ({
            title: s.key === "benchmark" ? ready.benchmark_name : s.title,
            color: s.color,
            points: ready.equity.map((p) => ({
              time: p.time,
              value: p[s.key],
            })),
          }))
        : [],
    [ready, chartSeries],
  );
  return (
    <section
      className={`portfolio-content portfolio-validation${prominentHeading ? " portfolio-validation-standalone" : ""}`}
      aria-label="Validation historique"
    >
      <div className="portfolio-section-heading">
        <div>
          {prominentHeading ? <h1>{title}</h1> : <h2>{title}</h2>}
          <p>
            {mode === "psp5_downside"
              ? "Chaque séance, cinq modèles et un filtre de baisses sur 32 séances déterminent la part de PSP5 à détenir. Après l’achat initial, un écart d’au moins 5 points avec la cible déclenche un ordre à la clôture suivante."
              : sp500
                ? "Régression PSP5 : 75 % lente 60 mois, 25 % défensive 18 mois, exposition 10 à 100 %. Sans poche passive, transfert ni rééquilibrage entre poches. État lent initial reconstitué avec les seuls signaux antérieurs au test."
                : "Trois années glissantes pour calculer les décisions. Rééquilibrage trimestriel pour les allocations optimisées ; seuils vérifiés chaque séance pour le retour à la moyenne."}
          </p>
        </div>
      </div>
      <form
        className="validation-controls"
        onSubmit={(event) => {
          event.preventDefault();
          if (!validFee || !validCapital || !validReversion || !validUniverse)
            return;
          setResult(null);
          setError("");
          setLoading(true);
          setJob({
            body: {
              asset_ids: ids,
              mode,
              years,
              fee_rate: Number(fee) / 100,
              initial_capital: Number(capital),
              whole_shares: wholeShares,
              benchmark_asset_id: sp500 ? "yf-psp5.pa" : null,
              ...(mode === "risk_parity"
                ? {
                    rebalance_tolerance: 0.03,
                    risk_rebalance_tolerance: 0.03,
                  }
                : mode === "volatility" || mode === "correlation"
                  ? { rebalance_tolerance: 0.03 }
                  : {}),
              ...(mode === "mean_reversion"
                ? {
                    reversion_entry_z: Number(entryZ),
                    reversion_exit_z: Number(exitZ),
                    reversion_exit_mode: "trailing_z",
                    reversion_trailing_gap: 1,
                    reversion_funding_min_z: 0.3,
                  }
                : {}),
            },
            revision: (job?.revision ?? 0) + 1,
            sourceRevision: dataRevision,
          });
        }}
      >
        {mode === "mean_reversion" && (
          <>
            <label>
              Seuil d’achat (−σ)
              <input
                type="number"
                min="0.5"
                max="4"
                step="0.1"
                required
                value={entryZ}
                onChange={(e) => {
                  invalidate();
                  setEntryZ(e.target.value);
                }}
              />
            </label>
            <label>
              Seuil de vente ou d’activation (+σ)
              <input
                type="number"
                min="0"
                max="4"
                step="0.1"
                required
                value={exitZ}
                onChange={(e) => {
                  invalidate();
                  setExitZ(e.target.value);
                }}
              />
            </label>
          </>
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
          Période de validation
          <select
            aria-label="Période de validation"
            value={years}
            onChange={(e) => {
              invalidate();
              setYears(Number(e.target.value));
            }}
          >
            {[1, 3, 5, 10].map((v) => (
              <option key={v} value={v}>
                {v} an{v > 1 ? "s" : ""}
              </option>
            ))}
          </select>
        </label>
        <label>
          Frais par achat et vente (%)
          <input
            type="number"
            min="0"
            max="10"
            step="0.01"
            value={fee}
            required
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
          Titres entiers uniquement (actions et ETF)
        </label>
        <button
          type="submit"
          className="primary-button"
          disabled={
            loading ||
            !ids.length ||
            ids.length > 20 ||
            !validFee ||
            !validCapital ||
            !validReversion ||
            !validUniverse
          }
        >
          {loading ? "Validation en cours…" : "Lancer la validation"}
        </button>
      </form>
      {!validUniverse && (
        <p role="status">
          L’ETF PSP5.PA doit être présent dans la bibliothèque.
        </p>
      )}
      {(!ids.length || ids.length > 20) && (
        <p className="fine-print">
          Sélectionnez entre 1 et 20 actifs pour lancer la validation.
        </p>
      )}
      {loading && (
        <p role="status">Calcul des fenêtres chronologiques et des frais…</p>
      )}
      {error && (
        <p className="error" role="alert">
          {error} Relancez la validation pour réessayer.
        </p>
      )}
      {result?.status === "insufficient" && (
        <p className="portfolio-empty" role="status">
          {result.message}
        </p>
      )}
      {ready && (
        <>
          {!!ready.diagnostics?.length && (
            <details>
              <summary>
                Diagnostic du retour à la moyenne · informatif, sans filtre
              </summary>
              <p>
                AR(1) proche de 1 : résidus persistants. Demi-vie indicative en
                observations. Déplacement : valeur absolue de la moyenne récente
                / dispersion. Variation de pente : pente logarithmique
                annualisée de la seconde moitié moins celle de la première ;
                aucune preuve de stationnarité.
              </p>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Actif</th>
                      <th>Score</th>
                      <th>AR(1)</th>
                      <th>Demi-vie</th>
                      <th>Déplacement</th>
                      <th>Variation de pente</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ready.diagnostics.map((d) => (
                      <tr key={d.id}>
                        <td>{d.name}</td>
                        <td>{metricNumber(d.z)}</td>
                        <td>{metricNumber(d.phi)}</td>
                        <td>{metricNumber(d.half_life)}</td>
                        <td>{metricNumber(d.recent_shift)}</td>
                        <td>{metricNumber(d.slope_change)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
          {!!ready.position_traces?.length && (
            <details>
              <summary>Prix et score pendant les détentions</summary>
              <p>
                Prix ajustés en devise native au signal ; le score est recalculé
                chaque séance. Les périodes de détention successives figurent
                dans le journal des transactions.
              </p>
              {ready.assets.map((a) => (
                <details key={a.id}>
                  <summary>{a.name}</summary>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Date du signal</th>
                          <th>Prix</th>
                          <th>Score</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ready.position_traces
                          ?.filter((p) => p.id === a.id)
                          .map((p) => (
                            <tr key={p.time}>
                              <td>{date(p.time)}</td>
                              <td>{number(p.price, 2)}</td>
                              <td>{metricNumber(p.z)}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              ))}
            </details>
          )}
          {ready.notices?.map((notice) => (
            <p className="fine-print" key={notice}>
              {notice}
            </p>
          ))}
          {job?.sourceRevision !== dataRevision && (
            <p className="fine-print">
              Des données ont été actualisées depuis ce calcul. Le résultat
              reste affiché ; relancez la validation pour les utiliser.
            </p>
          )}
          {ready.completed_quarters < 4 && (
            <p className="validation-bias">
              Moins de quatre trimestres complets : recul limité pour apprécier
              la régularité.
            </p>
          )}
          <div
            className="performance-series-summary validation-chart-legend"
            role="group"
            aria-label="Légende des courbes"
          >
            {chartSeries.map((s) => (
              <div key={s.key}>
                <span>
                  <i style={{ background: s.color }} aria-hidden="true" />
                  {s.key === "benchmark" ? ready.benchmark_name : s.title}
                </span>
              </div>
            ))}
          </div>
          <HistoryChart
            lines={lines}
            accessibleLabel={`Validation historique, ${chartSeries.length} courbes nettes de frais en base 100 et en euros`}
          />
          <ValidationMetrics ready={ready} displayedSeries={chartSeries} />
          <ValidationLedger key={JSON.stringify(job)} ready={ready} />
          <details className="validation-details">
            <summary>Détail des décisions et des trimestres</summary>
            <div className="table-scroll">
              <table
                className="positions-table"
                aria-label="Fenêtres de validation"
              >
                <thead>
                  <tr>
                    <th>Apprentissage</th>
                    <th>Signal → exécution</th>
                    <th>Fin de détention</th>
                    {chartSeries.map((s) => (
                      <th key={s.key}>
                        {s.key === "benchmark" ? ready.benchmark_name : s.title}
                      </th>
                    ))}
                    <th>Rotation de la méthode</th>
                  </tr>
                </thead>
                <tbody>
                  {ready.folds.map((f) => (
                    <tr key={f.signal}>
                      <td>
                        {date(f.train_start)} — {date(f.train_end)}
                        <br />
                        {f.observations} variations
                      </td>
                      <td>
                        {date(f.signal)} → {date(f.execution)}
                      </td>
                      <td>
                        {date(f.end)}
                        {!f.complete && " · Partiel"}
                      </td>
                      {chartSeries.map((s) => (
                        <td key={s.key}>{percent(f.returns[s.key], true)}</td>
                      ))}
                      <td>{percent(f.turnover.strategy)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {ready.folds.map((f) => (
              <p className="fine-print" key={f.signal}>
                Allocation au {date(f.signal)} :{" "}
                {ready.assets
                  .map((a, i) => `${a.name} ${percent(f.weights[i])}`)
                  .join(" · ")}
                {f.risk_contributions && (
                  <>
                    <br />
                    Contributions au risque estimées à la cible :{" "}
                    {ready.assets
                      .map(
                        (a, i) =>
                          `${a.name} ${percent(f.risk_contributions![i])}`,
                      )
                      .join(" · ")}
                  </>
                )}
                {f.risk_contributions_execution && (
                  <>
                    <br />
                    Contributions après exécution
                    {f.rebalance_skipped
                      ? " (révision sans transaction)"
                      : ""}{" "}
                    :{" "}
                    {ready.assets
                      .map(
                        (a, i) =>
                          `${a.name} ${percent(f.risk_contributions_execution![i])}`,
                      )
                      .join(" · ")}
                  </>
                )}
                {f.risk_contributions_end && (
                  <>
                    <br />
                    Contributions en fin de période :{" "}
                    {ready.assets
                      .map(
                        (a, i) =>
                          `${a.name} ${percent(f.risk_contributions_end![i])}`,
                      )
                      .join(" · ")}{" "}
                    (quantités effectives, covariance connue au signal ;
                    liquidités hors risque)
                  </>
                )}
              </p>
            ))}
          </details>
        </>
      )}
      {!sp500 && (
        <details className="validation-details">
          <summary>Comprendre la méthode et ses limites</summary>
          <p>
            Les allocations de volatilité minimale et de corrélation minimale
            utilisent les trois années précédant chaque signal trimestriel.
            L’exécution a lieu à la clôture commune suivante. La volatilité
            minimale conserve au moins la moitié des actifs éligibles, avec 3 %
            minimum par ligne et 35 % maximum dès trois actifs. La corrélation
            minimale optimise tous les actifs ensemble, sans plancher ni nombre
            minimal de positions, avec un plafond de 35 % dès trois actifs. Elle
            minimise la variance pondérée de rendements standardisés : deux
            actifs corrélés peuvent être conservés s’ils diversifient le reste
            du portefeuille. Leur présence n’est pas garantie.
          </p>
          <p>
            Le retour à la moyenne s’applique aux actions et cryptomonnaies. Les
            autres actifs sont achetés à parts égales puis conservés à quantité
            constante, dès leurs premières cotations disponibles. Les actifs
            sans cours exploitable gardent leur part en liquidités. Chaque
            séance, il recalcule une régression du logarithme des cours ajustés
            en devise native sur les trois dernières années. Le z-score est
            l’écart à cette tendance divisé par l’écart type résiduel. Au seuil
            d’achat choisi, un achat vise une part égale du capital actif par
            position ouverte ou nouvelle, plafonnée à 25 % de la valeur totale
            du portefeuille, frais d’achat compris, même pour la première
            entrée. La sortie après repli s’active une fois le seuil haut
            atteint, puis attend un recul de 1 σ depuis le plus haut écart-type
            observé pendant la détention : par exemple, activation à +2 σ, plus
            haut à +2,7 σ, vente à +1,7 σ ou moins avec un repli de 1 σ. Elle
            peut conserver la position tant que l’écart-type progresse ; ce
            suivi ne garantit pas la conservation d’un gain en prix. Les ventes
            de financement restent possibles avant ce repli. Les achats
            utilisent d’abord les liquidités disponibles. Une entrée doit
            représenter au moins 10 % du portefeuille, frais d’achat compris, ou
            une part équipondérée si l’univers actif dépasse dix actifs. Ce
            minimum est arrondi au titre entier supérieur si nécessaire. Les
            liquidités seules sont utilisées lorsqu’elles couvrent ce minimum.
            Sinon, la position active dont l’écart-type au signal est le plus
            élevé parmi ceux atteignant +0,3 σ est réduite, frais compris. Une
            seule ligne peut financer les achats d’une séance, seulement pour
            atteindre le minimum utile. Si elle ne suffit pas, l’entrée est
            ignorée plutôt que d’ouvrir une petite position ou de vendre une
            deuxième ligne. Une position encore sous sa tendance ou sans
            écart-type calculable ne finance pas d’achat. Le plafond porte sur
            la valeur courante, qui varie avec les cours ; il ne constitue pas
            quatre enveloppes fixes du capital initial. Les lignes passives et
            leurs budgets réservés sont conservés. Les ventes sont exécutées
            avant les achats ; les entrées simultanées ont une même taille
            cible, avec priorité à l’écart-type le plus négatif. Les ordres sont
            exécutés à la clôture commune suivante. Aucune nouvelle tranche
            n’est achetée tant que la position est ouverte ; les liquidités
            libérées sont disponibles pour les actions et cryptomonnaies et ne
            sont pas rémunérées. Le seuil est vérifié à la clôture : l’écart
            peut le franchir d’un seul coup entre deux séances. La colonne
            Écart-type affiche la valeur au signal, pas celle du lendemain à
            l’exécution.
          </p>
          <p>
            Un actif récent n’écourte pas le test des autres lignes. Il ne peut
            être acheté avant sa première cotation connue ; les signaux et les
            optimisations attendent trois ans d’historique propre à cet actif.
            Les comparateurs investissent sa part à sa disponibilité (à la
            prochaine révision pour l’équipondération). Le calendrier suit les
            séances de la référence, y compris pour les cryptomonnaies.
          </p>
          <p>
            Les courbes partent de 100 ; les positions et le journal utilisent
            le capital initial saisi. En mode fractionnaire, les parts ajustées
            sont des unités de simulation qui tiennent compte des dividendes
            réinvestis et des opérations sur titres. Elles ne correspondent pas
            nécessairement au nombre de titres d’un compte réel. Les valeurs
            sont converties en euros avec les changes historiques. En mode
            titres entiers, les quantités des actions et ETF sont des nombres
            entiers et les dividendes sont versés en liquidités.
          </p>
          <p>
            Les frais s’appliquent à chaque achat et vente, entrée comprise,
            sans vente finale fictive. L’équipondération est rétablie chaque
            trimestre ; l’achat-conservation et la référence sont achetés une
            seule fois. La référence indicielle est théorique. La rotation
            annuelle exclut la première entrée. Le dernier trimestre partiel
            entre dans la courbe, mais pas dans les statistiques de régularité.
            Les frais payés sont la somme des frais prélevés lors des achats et
            ventes simulés, pour le capital initial saisi. L’exposition au
            marché mesure la part du capital investie (valeur des positions
            divisée par positions + liquidités), pondérée par les jours
            calendaires depuis la première exécution commune. L’attente initiale
            avant cette exécution est exclue. Un portefeuille intégralement
            investi affiche 100 %, même si l’optimiseur ne retient qu’une partie
            des actifs.
          </p>
          <p>
            Le mode titres entiers applique l’arrondi inférieur à chaque ordre
            sur les actions et ETF, avec leur cours de clôture hors ajustement
            des dividendes. Pour les stratégies de volatilité et corrélation
            minimales et de parité de risque, le reliquat sert à acheter des
            titres entiers abordables parmi les lignes retenues par
            l’optimiseur, en privilégiant les poids cibles. Le solde non
            investissable reste en liquidités ; les dividendes disponibles sont
            versés en liquidités, sans achat automatique de fractions. Les
            cryptos conservent leurs fractions. La référence indicielle reste
            théorique ; la référence utilisée est le S&P 500, dividendes
            réinvestis. Les cours du fournisseur restent ajustés des divisions
            de titres : les anciennes dénominations de parts ne sont pas
            reconstituées. Cette option ne contrôle pas l’éligibilité au PEA.
          </p>
          <p>
            Les prix ajustés et les changes peuvent être révisés. Les dates
            communes avec la référence déterminent les séances simulées. Les
            frais excluent fiscalité, spread et impact de marché. L’univers est
            celui sélectionné aujourd’hui ; les anciennes compositions et
            sociétés disparues ne sont pas reconstituées. Comparer de nombreux
            réglages puis retenir le meilleur peut surajuster la validation.
          </p>
        </details>
      )}
    </section>
  );
}
