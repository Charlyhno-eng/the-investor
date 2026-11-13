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
  returns: Record<Key, number>;
  turnover: Record<Key, number>;
  costs: Record<Key, number>;
};
type Ready = {
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

function ValidationMetrics({ ready }: { ready: Ready }) {
  return (
    <>
      <div className="table-scroll">
        <table
          className="positions-table performance-metrics validation-metrics"
          aria-label="Résultats hors échantillon"
        >
          <thead>
            <tr>
              <th scope="col">Indicateur</th>
              {series.map((s) => (
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
                series.map(({ key }) => {
                  const raw = ready.metrics[key][metric.key];
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
                  {series.map(({ key }) => {
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
                              compare(values.buy_hold, "l’achat-conservation"),
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
      <p className="metric-signals-legend">
        Premier trait : comparaison à {ready.benchmark_name}. Second trait pour
        les deux méthodes : comparaison à l’achat-conservation. Vert : meilleur
        · Rouge : moins bon · Gris : égal ou indisponible.
      </p>
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

type ValidationMode = "volatility" | "mean_reversion" | "correlation";

export function ValidationPanel({
  holdings,
  mode,
  dataRevision,
}: {
  holdings: string;
  mode: ValidationMode;
  dataRevision: string;
}) {
  // Universe edits reset the form; background catalogue updates preserve the user’s work.
  return (
    <ValidationForm
      key={holdings}
      holdings={holdings}
      mode={mode}
      dataRevision={dataRevision}
    />
  );
}

function ValidationForm({
  holdings,
  mode,
  dataRevision,
}: {
  holdings: string;
  mode: ValidationMode;
  dataRevision: string;
}) {
  const [years, setYears] = useState(5);
  const [fee, setFee] = useState("0.5");
  const [capital, setCapital] = useState("10000");
  const [wholeShares, setWholeShares] = useState(false);
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
  const validReversion =
    mode !== "mean_reversion" ||
    (inRange(entryZ, 0.5, 4) && inRange(exitZ, 0, 4));
  const title = {
    volatility: "Volatilité minimale",
    mean_reversion: "Retour à la moyenne",
    correlation: "Corrélation minimale",
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
  const lines = useMemo(
    () =>
      ready
        ? series.map((s) => ({
            title: s.key === "benchmark" ? ready.benchmark_name : s.title,
            color: s.color,
            points: ready.equity.map((p) => ({
              time: p.time,
              value: p[s.key],
            })),
          }))
        : [],
    [ready],
  );
  return (
    <section
      className="portfolio-content portfolio-validation"
      aria-label="Validation historique"
    >
      <div className="portfolio-section-heading">
        <div>
          <h2>{title}</h2>
          <p>
            Trois années glissantes pour calculer les décisions. Rééquilibrage
            trimestriel pour les allocations optimisées ; seuils vérifiés chaque
            séance pour le retour à la moyenne.
          </p>
        </div>
      </div>
      <form
        className="validation-controls"
        onSubmit={(event) => {
          event.preventDefault();
          if (!validFee || !validCapital || !validReversion) return;
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
              benchmark_asset_id: null,
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
            !validReversion
          }
        >
          {loading ? "Validation en cours…" : "Lancer la validation"}
        </button>
      </form>
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
            {series.map((s) => (
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
            accessibleLabel="Validation historique, quatre courbes nettes de frais en base 100 et en euros"
          />
          <ValidationMetrics ready={ready} />
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
                    {series.map((s) => (
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
                      {series.map((s) => (
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
              </p>
            ))}
          </details>
        </>
      )}
      <details className="validation-details">
        <summary>Comprendre la méthode et ses limites</summary>
        <p>
          Les allocations de volatilité minimale et de corrélation minimale
          utilisent les trois années précédant chaque signal trimestriel.
          L’exécution a lieu à la clôture commune suivante. Au moins la moitié
          des actifs éligibles à cette date est retenue, avec 3 % minimum par
          ligne et 35 % maximum dès trois actifs. La corrélation minimale
          minimise la variance pondérée de rendements standardisés : elle ne
          garantit pas des actifs indépendants.
        </p>
        <p>
          Le retour à la moyenne s’applique aux actions et cryptomonnaies. Les
          autres actifs sont achetés à parts égales puis conservés à quantité
          constante, dès leurs premières cotations disponibles. Les actifs sans
          cours exploitable gardent leur part en liquidités. Chaque séance, il
          recalcule une régression du logarithme des cours ajustés en devise
          native sur les trois dernières années. Le z-score est l’écart à cette
          tendance divisé par l’écart type résiduel. Au seuil d’achat choisi, un
          achat vise une part égale du capital actif par position ouverte ou
          nouvelle, plafonnée à 25 % de la valeur totale du portefeuille, frais
          d’achat compris, même pour la première entrée. La sortie après repli
          s’active une fois le seuil haut atteint, puis attend un recul de 1 σ
          depuis le plus haut écart-type observé pendant la détention : par
          exemple, activation à +2 σ, plus haut à +2,7 σ, vente à +1,7 σ ou
          moins avec un repli de 1 σ. Elle peut conserver la position tant que
          l’écart-type progresse ; ce suivi ne garantit pas la conservation d’un
          gain en prix. Les ventes de financement restent possibles avant ce
          repli. Les achats utilisent d’abord les liquidités disponibles. Une
          entrée doit représenter au moins 10 % du portefeuille, frais d’achat
          compris, ou une part équipondérée si l’univers actif dépasse dix
          actifs. Ce minimum est arrondi au titre entier supérieur si
          nécessaire. Les liquidités seules sont utilisées lorsqu’elles couvrent
          ce minimum. Sinon, la position active dont l’écart-type au signal est
          le plus élevé parmi ceux atteignant +0,3 σ est réduite, frais compris.
          Une seule ligne peut financer les achats d’une séance, seulement pour
          atteindre le minimum utile. Si elle ne suffit pas, l’entrée est
          ignorée plutôt que d’ouvrir une petite position ou de vendre une
          deuxième ligne. Une position encore sous sa tendance ou sans
          écart-type calculable ne finance pas d’achat. Le plafond porte sur la
          valeur courante, qui varie avec les cours ; il ne constitue pas quatre
          enveloppes fixes du capital initial. Les lignes passives et leurs
          budgets réservés sont conservés. Les ventes sont exécutées avant les
          achats ; les entrées simultanées ont une même taille cible, avec
          priorité à l’écart-type le plus négatif. Les ordres sont exécutés à la
          clôture commune suivante. Aucune nouvelle tranche n’est achetée tant
          que la position est ouverte ; les liquidités libérées sont disponibles
          pour les actions et cryptomonnaies et ne sont pas rémunérées. Le seuil
          est vérifié à la clôture : l’écart peut le franchir d’un seul coup
          entre deux séances. La colonne Écart-type affiche la valeur au signal,
          pas celle du lendemain à l’exécution.
        </p>
        <p>
          Un actif récent n’écourte pas le test des autres lignes. Il ne peut
          être acheté avant sa première cotation connue ; les signaux et les
          optimisations attendent trois ans d’historique propre à cet actif. Les
          comparateurs investissent sa part à sa disponibilité (à la prochaine
          révision pour l’équipondération). Le calendrier suit les séances de la
          référence, y compris pour les cryptomonnaies.
        </p>
        <p>
          Les courbes partent de 100 ; les positions et le journal utilisent le
          capital initial saisi. En mode fractionnaire, les parts ajustées sont
          des unités de simulation qui tiennent compte des dividendes réinvestis
          et des opérations sur titres. Elles ne correspondent pas
          nécessairement au nombre de titres d’un compte réel. Les valeurs sont
          converties en euros avec les changes historiques. En mode titres
          entiers, les quantités des actions et ETF sont des nombres entiers et
          les dividendes sont versés en liquidités.
        </p>
        <p>
          Les frais s’appliquent à chaque achat et vente, entrée comprise, sans
          vente finale fictive. L’équipondération est rétablie chaque trimestre
          ; l’achat-conservation et la référence sont achetés une seule fois. La
          référence indicielle est théorique. La rotation annuelle exclut la
          première entrée. Le dernier trimestre partiel entre dans la courbe,
          mais pas dans les statistiques de régularité. Les frais payés sont la
          somme des frais prélevés lors des achats et ventes simulés, pour le
          capital initial saisi. L’exposition au marché mesure la part du
          capital investie (valeur des positions divisée par positions +
          liquidités), pondérée par les jours calendaires depuis la première
          exécution commune. L’attente initiale avant cette exécution est
          exclue. Un portefeuille intégralement investi affiche 100 %, même si
          l’optimiseur ne retient qu’une partie des actifs.
        </p>
        <p>
          Le mode titres entiers applique l’arrondi inférieur à chaque ordre sur
          les actions et ETF, avec leur cours de clôture hors ajustement des
          dividendes. Pour les stratégies de volatilité et corrélation
          minimales, le reliquat sert à acheter des titres entiers abordables
          parmi les lignes retenues par l’optimiseur, en privilégiant les poids
          cibles. Le solde non investissable reste en liquidités ; les
          dividendes disponibles sont versés en liquidités, sans achat
          automatique de fractions. Les cryptos conservent leurs fractions. La
          référence indicielle reste théorique ; la référence utilisée est le
          S&P 500, dividendes réinvestis. Les cours du fournisseur restent
          ajustés des divisions de titres : les anciennes dénominations de parts
          ne sont pas reconstituées. Cette option ne contrôle pas l’éligibilité
          au PEA.
        </p>
        <p>
          Les prix ajustés et les changes peuvent être révisés. Les dates
          communes avec la référence déterminent les séances simulées. Les frais
          excluent fiscalité, spread et impact de marché. L’univers est celui
          sélectionné aujourd’hui ; les anciennes compositions et sociétés
          disparues ne sont pas reconstituées. Comparer de nombreux réglages
          puis retenir le meilleur peut surajuster la validation.
        </p>
      </details>
    </section>
  );
}
