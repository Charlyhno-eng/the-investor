import { Icon } from "../../components/Icon";
import { Tooltip } from "../../components/Tooltip";
import { useEffect, useRef, useState } from "react";
import { post } from "../../lib/api";
import { money } from "../../lib/currency";
import { percent } from "../../lib/format";
import type { Asset } from "../../lib/types";
import type { Quantities } from "../portfolio/quantities";

export type Scenario = {
  id: string;
  name: string;
  start: string;
  tone: string;
  description: string;
};
type Excluded = { id: string; name: string; reason: string };
type Result = {
  status: "ready";
  scenario: Scenario;
  total: number;
  coverage: number;
  excluded: Excluded[];
  historical_start: string;
  historical_end: string;
  paths: number;
  seed: number;
  calibration: { start: string; end: string; months: number };
  equity: {
    month: number;
    time: string;
    central: number;
    p05: number;
    p50: number;
    p95: number;
  }[];
  metrics: {
    return: number;
    p05_return: number;
    p95_return: number;
    drawdown: number;
    drawdown_p05: number;
    conditional_loss_share: number;
  };
  positions: {
    id: string;
    name: string;
    value: number;
    date: string;
    simulated_value: number;
    simulated_return: number;
    contribution: number;
    r2: number;
    validation_rmse: number;
    betas: Record<string, number>;
  }[];
  factors: {
    symbol: string;
    name: string;
    shock: number;
    first: string;
    last: string;
    source: string;
  }[];
  warnings: string[];
};
type Response =
  | Result
  | { status: "pending" }
  | { status: "insufficient"; message: string; excluded: Excluded[] };

function readCustom(): Quantities {
  try {
    const v: unknown = JSON.parse(
      localStorage.getItem("investor-simulation") ?? "{}",
    );
    if (v && typeof v === "object" && !Array.isArray(v))
      return Object.fromEntries(
        Object.entries(v).filter(
          (e) =>
            typeof e[1] === "number" &&
            Number.isFinite(e[1]) &&
            e[1] >= 0 &&
            e[1] <= 1e15,
        ),
      );
  } catch {
    /* Use an empty draft if storage is unavailable. */
  }
  return {};
}

export function SimulationPanel({
  assets,
  portfolioIds,
  watchlistIds,
  quantities,
  onImport,
  scenarios,
  scenario,
}: {
  assets: Asset[];
  portfolioIds: string[];
  watchlistIds: string[];
  quantities: Quantities;
  onImport: () => void;
  scenarios: Scenario[];
  scenario: string;
}) {
  const pageRef = useRef<HTMLElement>(null);
  useEffect(() => {
    pageRef.current?.scrollIntoView({ block: "start" });
  }, []);
  const months = 12;
  const [custom, setCustom] = useState(false);
  const [draft, setDraft] = useState<Quantities>(readCustom);
  const [search, setSearch] = useState("");
  const [assetId, setAssetId] = useState("");
  const [error, setError] = useState("");
  const [result, setResult] = useState<Response | null>(null);
  const [request, setRequest] = useState<{
    holdings: { asset_id: string; quantity: number }[];
    scenario: string;
    months: number;
    seed: number;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!request) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    async function load() {
      try {
        const data = await post<Response>(
          "/simulation/run",
          request,
          controller.signal,
        );
        if (controller.signal.aborted) return;
        setResult(data);
        if (data.status === "pending") {
          if (++attempts >= 90)
            throw new Error(
              "Les téléchargements prennent du temps. Relancez la simulation dans quelques instants.",
            );
          timer = setTimeout(load, 2000);
        } else setBusy(false);
      } catch (e) {
        if (!controller.signal.aborted) {
          setError((e as Error).message);
          setBusy(false);
        }
      }
    }
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [request]);
  function updateDraft(next: Quantities) {
    setDraft(next);
    try {
      localStorage.setItem("investor-simulation", JSON.stringify(next));
    } catch {
      setError(
        "Le portefeuille sur mesure reste disponible dans cette session ; son enregistrement local a échoué.",
      );
    }
  }
  const ids = custom ? Object.keys(draft) : portfolioIds;
  const selected = custom ? draft : quantities;
  const holdings = ids
    .filter((id) => assets.some((a) => a.id === id) && (selected[id] ?? 0) > 0)
    .map((id) => ({ asset_id: id, quantity: selected[id] }));
  return (
    <section className="simulation-page" ref={pageRef}>
      <header className="simulation-heading">
        <span className="simulation-title-icon">
          <Icon name="simulation" size={26} />
        </span>
        <div>
          <span className="eyebrow">LABORATOIRE DE RISQUE</span>
          <h1>Simulation</h1>
        </div>
      </header>
      <section className="simulation-box" aria-label="Paramètres de simulation">
        <h2>
          Composer le portefeuille <span className="muted">· 12 mois</span>
        </h2>
        <div className="simulation-actions">
          <button
            className="secondary-button"
            aria-pressed={!custom}
            onClick={() => setCustom(false)}
          >
            Mon portefeuille
          </button>
          <button
            className="secondary-button"
            aria-pressed={custom}
            onClick={() => setCustom(true)}
          >
            Sur mesure
          </button>
          {custom && (
            <button
              className="secondary-button"
              onClick={() =>
                updateDraft(
                  Object.fromEntries(
                    portfolioIds.map((id) => [id, quantities[id] ?? 0]),
                  ),
                )
              }
            >
              Copier mon portefeuille
            </button>
          )}
        </div>
        {custom && (
          <div className="simulation-actions">
            <input
              aria-label="Rechercher un actif"
              placeholder="Rechercher dans le catalogue…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <select
              aria-label="Actif à ajouter"
              value={assetId}
              onChange={(e) => setAssetId(e.target.value)}
            >
              <option value="">Choisir un actif</option>
              {assets
                .filter(
                  (a) =>
                    !(a.id in draft) &&
                    a.name.toLowerCase().includes(search.toLowerCase()),
                )
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
            </select>
            <button
              className="secondary-button"
              disabled={!assetId}
              onClick={() => {
                updateDraft({ ...draft, [assetId]: 1 });
                setAssetId("");
              }}
            >
              Ajouter
            </button>
            <button className="secondary-button" onClick={onImport}>
              Importer une action / un ETF
            </button>
          </div>
        )}
        <p className="simulation-beta-legend">
          Cuivré : réaction dans le même sens · Bleu : réaction inverse · Gris :
          proche de zéro (±0,05).
        </p>
        <div className="simulation-table">
          <table>
            <thead>
              <tr>
                <th>Actif</th>
                <th>Quantité</th>
                {custom && <th>Retirer</th>}
              </tr>
            </thead>
            <tbody>
              {ids
                .filter((id) => assets.some((a) => a.id === id))
                .map((id) => (
                  <tr key={id}>
                    <td>{assets.find((a) => a.id === id)?.name}</td>
                    <td>
                      {custom ? (
                        <input
                          aria-label={`Quantité ${assets.find((a) => a.id === id)?.name}`}
                          type="number"
                          min="0"
                          max="1000000000000000"
                          step="any"
                          value={draft[id]}
                          onChange={(e) => {
                            const q = Number(e.target.value);
                            if (Number.isFinite(q) && q >= 0 && q <= 1e15)
                              updateDraft({ ...draft, [id]: q });
                          }}
                        />
                      ) : (
                        (quantities[id] ?? 0)
                      )}
                    </td>
                    {custom && (
                      <td>
                        <button
                          className="secondary-button"
                          aria-label={`Retirer ${assets.find((a) => a.id === id)?.name}`}
                          onClick={() => {
                            const next = { ...draft };
                            delete next[id];
                            updateDraft(next);
                          }}
                        >
                          ×
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        {!holdings.length && (
          <p>Ajoutez des actifs avec une quantité positive pour démarrer.</p>
        )}
        <button
          className="primary-button"
          disabled={busy || !holdings.length || !scenarios.length}
          onClick={() => {
            setError("");
            setResult(null);
            setBusy(true);
            setRequest({ holdings, scenario, months, seed: 42 });
          }}
        >
          Simuler ce portefeuille
        </button>
      </section>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {busy && (
        <p role="status">
          Téléchargement et préparation des historiques sans clé API, puis
          calcul des trajectoires…
        </p>
      )}
      {result?.status === "insufficient" && (
        <section className="simulation-box">
          <p role="status">{result.message}</p>
          <Exclusions items={result.excluded} />
        </section>
      )}
      {result?.status === "ready" && (
        <>
          <SimulationResults result={result} />
          <WatchlistResistance
            key={JSON.stringify(request)}
            ids={watchlistIds}
            scenario={result.scenario.id}
            portfolioReturn={result.metrics.return}
          />
        </>
      )}
    </section>
  );
}

function Exclusions({ items }: { items: Excluded[] }) {
  return (
    items.length > 0 && (
      <div className="simulation-warning">
        <strong>Positions non simulées — couverture partielle</strong>
        {items.map((p) => (
          <p key={p.id}>
            {p.name} : {p.reason}
          </p>
        ))}
      </div>
    )
  );
}

function SimulationResults({ result: r }: { result: Result }) {
  const chartRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const frame = requestAnimationFrame(() =>
      chartRef.current?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
        block: "start",
      }),
    );
    return () => cancelAnimationFrame(frame);
  }, [r]);
  const last = r.equity.at(-1)!;
  function download() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(r, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `simulation-${r.scenario.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }
  return (
    <section className="simulation-box" aria-label="Résultats de simulation">
      <div className="simulation-actions">
        <h2>
          {r.scenario.name} · {last.month} mois
        </h2>
        <button className="secondary-button" onClick={download}>
          Exporter les données JSON
        </button>
      </div>
      <p>
        Chocs observés de {r.historical_start} à {r.historical_end}, appliqués
        aux expositions récentes. Capital simulé : {money(r.total)} ·{" "}
        {percent(r.coverage)} de la valeur valorisable.
      </p>
      <Exclusions items={r.excluded} />
      <div className="simulation-stats">
        {[
          ["Valeur centrale à l’échéance", money(last.central)],
          ["Variation centrale", percent(r.metrics.return, true)],
          [
            "Fourchette conditionnelle P5–P95",
            `${money(last.p05)} – ${money(last.p95)}`,
          ],
          ["Baisse maximale mensuelle centrale", percent(r.metrics.drawdown)],
          ["Drawdown au quantile 5 %", percent(r.metrics.drawdown_p05)],
          [
            "Trajectoires terminant en perte",
            percent(r.metrics.conditional_loss_share),
          ],
        ].map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <div ref={chartRef} className="simulation-chart-target">
        <StressChart result={r} />
      </div>
      <p className="fine-print">
        Courbe : réponse aux facteurs, sans alpha extrapolé. Bande : P5–P95 de{" "}
        {r.paths} trajectoires conditionnelles. La fréquence de perte est
        interne au modèle ; elle ne mesure pas la probabilité de cette crise.
      </p>
      <section className="simulation-result-section">
        <h3>Impact par actif et qualité du modèle</h3>
        <p>
          Calibration : {r.calibration.start} → {r.calibration.end} ·{" "}
          {r.calibration.months} mois. Validation : 12 derniers mois réservés
          lors d’un ajustement distinct ; RMSE des rendements logarithmiques
          mensuels. Un R² faible ou négatif indique une faible capacité
          explicative.
        </p>
        <div className="simulation-table">
          <table>
            <thead>
              <tr>
                <th>Actif / date du prix</th>
                <th>
                  Actuel{" "}
                  <Tooltip label="Actuel" floating question>
                    <span>
                      Valeur actuelle de la position en euros. Sa taille ne
                      constitue pas une mesure de performance.
                    </span>
                  </Tooltip>
                </th>
                <th>
                  Simulé{" "}
                  <Tooltip label="Simulé" floating question>
                    <span>
                      Valeur centrale de la position après douze mois dans ce
                      scénario. Vert si supérieure à la valeur actuelle, rouge
                      si inférieure.
                    </span>
                  </Tooltip>
                </th>
                <th>
                  Variation{" "}
                  <Tooltip label="Variation" floating question>
                    <span>
                      Gain ou perte simulé par rapport à la valeur actuelle. Une
                      valeur positive est favorable dans ce scénario.
                    </span>
                  </Tooltip>
                </th>
                <th>
                  Contribution{" "}
                  <Tooltip label="Contribution" floating question>
                    <span>
                      Contribution de cette position à la variation totale, en
                      points de pourcentage. Exemple : −2 points retire 2 % au
                      capital simulé initial.
                    </span>
                  </Tooltip>
                </th>
                <th>
                  R² ajustement{" "}
                  <Tooltip label="R² ajustement" floating question>
                    <span>
                      Part des variations historiques expliquée par les
                      facteurs. Proche de 1 : meilleur ajustement ; proche de 0
                      ou négative : faible. Repères visuels : vert dès 0,70,
                      intermédiaire entre 0,30 et 0,70, rouge sous 0,30. Cela ne
                      garantit pas la précision future.
                    </span>
                  </Tooltip>
                </th>
                <th>
                  Erreur validation{" "}
                  <Tooltip label="Erreur validation" floating question>
                    <span>
                      Erreur mensuelle typique du modèle sur douze mois réservés
                      à la validation (RMSE logarithmique). Plus faible est
                      préférable. Comparer aux variations habituelles de l’actif
                      ; aucune limite universelle ne distingue une bonne erreur
                      d’une mauvaise.
                    </span>
                  </Tooltip>
                </th>
              </tr>
            </thead>
            <tbody>
              {r.positions.map((p) => (
                <tr key={p.id}>
                  <td>
                    {p.name}
                    <small>{p.date}</small>
                  </td>
                  <td className="simulation-neutral">{money(p.value)}</td>
                  <td className={tone(p.simulated_value - p.value)}>
                    {money(p.simulated_value)}
                  </td>
                  <td className={tone(p.simulated_return)}>
                    {percent(p.simulated_return, true)}
                  </td>
                  <td className={tone(p.contribution)}>
                    {(p.contribution * 100).toFixed(2)} pts
                  </td>
                  <td
                    className={
                      p.r2 >= 0.7
                        ? "positive"
                        : p.r2 < 0.3
                          ? "negative"
                          : "simulation-neutral"
                    }
                  >
                    {p.r2.toFixed(2)}
                    {p.r2 < 0.3 && " · faible"}
                  </td>
                  <td className="simulation-neutral">
                    {percent(p.validation_rmse)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="simulation-result-section">
        <h3>Facteurs du scénario et provenance</h3>
        <div className="simulation-table">
          <table>
            <thead>
              <tr>
                <th>Facteur</th>
                <th>
                  Choc cumulé{" "}
                  <Tooltip label="Choc cumulé" floating question>
                    <span>
                      Variation historique cumulée de ce facteur sur la fenêtre
                      du scénario. Son effet sur une position dépend de la
                      sensibilité de cette position.
                    </span>
                  </Tooltip>
                </th>
                <th>
                  Historique disponible{" "}
                  <Tooltip label="Historique disponible" floating question>
                    <span>
                      Premier et dernier mois des observations disponibles pour
                      ce facteur.
                    </span>
                  </Tooltip>
                </th>
              </tr>
            </thead>
            <tbody>
              {r.factors.map((f) => (
                <tr key={f.symbol}>
                  <td>
                    <a href={f.source} target="_blank" rel="noreferrer">
                      {f.name} · {f.symbol}
                    </a>
                  </td>
                  <td>{percent(f.shock, true)}</td>
                  <td>
                    {f.first} → {f.last}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="simulation-result-section">
        <h3>Sensibilités estimées par facteur</h3>
        <p>
          Une sensibilité de +1,50 indique environ +1,5 % pour l’actif lorsque
          le facteur gagne 1 %, les autres facteurs étant constants. Une valeur
          négative indique une réaction inverse. Le signe décrit une exposition,
          pas une bonne ou mauvaise performance.
        </p>
        <p className="simulation-beta-legend">
          Cuivré : réaction dans le même sens · Bleu : réaction inverse · Gris :
          proche de zéro (±0,05).
        </p>
        <div className="simulation-table">
          <table>
            <thead>
              <tr>
                <th>Actif</th>
                {r.factors.map((f) => (
                  <th key={f.symbol}>
                    {f.symbol}{" "}
                    <Tooltip
                      label={`Sensibilité · ${f.name}`}
                      floating
                      question
                    >
                      <span>
                        Réaction estimée de l’actif à +1 % sur {f.name}, tous
                        les autres facteurs constants. +1,50 ≈ +1,5 % ; −0,50 ≈
                        −0,5 % ; proche de zéro : faible exposition directe.
                        L’ampleur indique la sensibilité, sans note de qualité.
                        Pour EUR/USD, +1 % correspond à un renforcement de
                        l’euro face au dollar.
                      </span>
                    </Tooltip>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {r.positions.map((p) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  {r.factors.map((f) => (
                    <td
                      key={f.symbol}
                      className={
                        p.betas[f.symbol] > 0.05
                          ? "beta-direct"
                          : p.betas[f.symbol] < -0.05
                            ? "beta-inverse"
                            : "muted"
                      }
                    >
                      {p.betas[f.symbol].toFixed(2)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}

function tone(value: number) {
  return value > 0 ? "positive" : value < 0 ? "negative" : "muted";
}

function StressChart({ result }: { result: Result }) {
  const [hover, setHover] = useState<number | null>(null);
  const points = result.equity;
  const active = hover === null ? null : points[hover];
  const min = Math.min(...points.map((p) => Math.min(p.p05, p.central))) * 0.95;
  const max = Math.max(...points.map((p) => Math.max(p.p95, p.central))) * 1.05;
  const x = (i: number) => 105 + (i / (points.length - 1)) * 750;
  const y = (v: number) => 280 - ((v - min) / (max - min || 1)) * 245;
  const line = points.map((p, i) => `${x(i)},${y(p.central)}`).join(" ");
  const band = [
    ...points.map((p, i) => `${x(i)},${y(p.p95)}`),
    ...points.map((p, i) => `${x(i)},${y(p.p05)}`).reverse(),
  ].join(" ");
  return (
    <figure className="stress-chart">
      <div className="stress-readout" aria-live="polite">
        {active ? (
          <>
            <span>{active.month === 0 ? "Départ" : `M+${active.month}`}</span>
            <strong className={tone(active.central / result.total - 1)}>
              {percent(active.central / result.total - 1, true)}
            </strong>
            <strong>{money(active.central)}</strong>
          </>
        ) : (
          <span className="muted">
            Survolez le graphique pour explorer chaque mois
          </span>
        )}
      </div>
      <svg
        viewBox="0 0 900 330"
        onPointerLeave={() => setHover(null)}
        onPointerMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const sx = ((e.clientX - rect.left) / rect.width) * 900;
          setHover(
            Math.max(
              0,
              Math.min(
                points.length - 1,
                Math.round(((sx - 105) / 750) * (points.length - 1)),
              ),
            ),
          );
        }}
        role="img"
        aria-label="Évolution mensuelle du capital simulé en euros, réponse centrale et bande conditionnelle P5 à P95"
      >
        <title>Projection conditionnelle du portefeuille en euros</title>
        {[0, 1, 2, 3, 4].map((i) => {
          const v = min + ((max - min) * i) / 4;
          return (
            <g key={i}>
              <line
                x1="105"
                x2="855"
                y1={y(v)}
                y2={y(v)}
                stroke="currentColor"
                opacity="0.1"
              />
              <text x="95" y={y(v) + 4} textAnchor="end">
                {Math.round(v).toLocaleString("fr-FR")} €
              </text>
            </g>
          );
        })}
        <polygon points={band} fill="var(--accent, #317d78)" opacity="0.17" />
        <line
          x1="105"
          x2="855"
          y1={y(result.total)}
          y2={y(result.total)}
          stroke="currentColor"
          strokeDasharray="4 4"
          opacity="0.4"
        />
        <polyline
          points={line}
          fill="none"
          stroke="var(--accent, #317d78)"
          strokeWidth="3"
        />
        {active && hover !== null && (
          <g pointerEvents="none">
            <line
              x1={x(hover)}
              x2={x(hover)}
              y1="35"
              y2="280"
              stroke="var(--accent)"
              strokeDasharray="3 3"
            />
            <circle
              cx={x(hover)}
              cy={y(active.central)}
              r="5"
              fill="var(--accent)"
            />
          </g>
        )}
        {points.map((p, i) => (
          <text key={i} x={x(i)} y="310" textAnchor="middle">
            {i === 0 ? "Départ" : `M+${p.month}`}
          </text>
        ))}
      </svg>
      <figcaption>
        Capital en EUR · réponse centrale et enveloppe conditionnelle à 90 % ·
        ligne pointillée : capital initial
      </figcaption>
    </figure>
  );
}

function WatchlistResistance({
  ids,
  scenario,
  portfolioReturn,
}: {
  ids: string[];
  scenario: string;
  portfolioReturn: number;
}) {
  const [data, setData] = useState<{
    status: string;
    results: Result[];
    excluded: Excluded[];
  } | null>(null);
  const [error, setError] = useState("");
  const identity = JSON.stringify(ids);
  useEffect(() => {
    if (!JSON.parse(identity).length) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    async function load() {
      try {
        const response = await post<{
          status: string;
          results: Result[];
          excluded: Excluded[];
        }>(
          "/simulation/watchlist",
          { asset_ids: JSON.parse(identity), scenario, seed: 42 },
          controller.signal,
        );
        if (controller.signal.aborted) return;
        setData(response);
        if (response.status === "pending") {
          if (++attempts >= 90)
            throw new Error(
              "Les historiques de la watchlist ne sont pas encore disponibles. Relancez le calcul dans quelques instants.",
            );
          timer = setTimeout(load, 2000);
        }
      } catch (e) {
        if (!controller.signal.aborted) setError((e as Error).message);
      }
    }
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [identity, scenario]);
  const ranked = [...(data?.results ?? [])].sort(
    (a, b) => b.metrics.return - a.metrics.return,
  );
  return (
    <section
      className="simulation-box watchlist-resistance"
      aria-label="Résistance de la watchlist"
    >
      <h2>Quels actifs de votre watchlist résistent le mieux ?</h2>
      <p>
        Mêmes chocs, horizon de douze mois et méthode de calcul, avec 10 000 €
        investis dans chaque actif séparément. Classement par rendement central
        final ; la baisse maximale mesure la résistance pendant le parcours. Les
        périodes de calibration peuvent différer selon les historiques
        disponibles.
      </p>
      {!ids.length ? (
        <p className="muted">
          Ajoutez des actifs à votre watchlist pour comparer leur résistance.
        </p>
      ) : error ? (
        <p role="alert" className="error">
          {error}
        </p>
      ) : (
        (!data || data.status === "pending") && (
          <p role="status">
            Calcul de la résistance des actifs de la watchlist…
          </p>
        )
      )}
      {ranked.length > 0 && (
        <>
          <div className="simulation-table">
            <table>
              <thead>
                <tr>
                  {[
                    "Actif",
                    "Capital final / 10 000 €",
                    "Variation",
                    "Écart au portefeuille",
                    "P5–P95",
                    "Baisse maximale",
                    "Drawdown P5",
                    "Trajectoires en perte",
                    "R²",
                    "Erreur validation",
                  ].map((label) => (
                    <th key={label}>
                      {label}
                      <Tooltip floating question label={label}>
                        <span>
                          {label === "Écart au portefeuille"
                            ? "Différence de rendement central en points par rapport au portefeuille simulé. Positive : cet actif finit mieux dans ce scénario."
                            : label === "P5–P95"
                              ? "Fourchette conditionnelle du capital final pour 10 000 € investis. Elle ne mesure pas la probabilité de la crise."
                              : label.includes("Drawdown") ||
                                  label === "Baisse maximale"
                                ? "Baisse depuis le sommet précédent, calculée mensuellement. Plus proche de zéro : parcours plus résistant. Drawdown P5 : quantile défavorable des trajectoires."
                                : label === "R²"
                                  ? "Qualité de l’ajustement historique, pas garantie de précision future. Plus proche de 1 : meilleure explication par les facteurs."
                                  : label === "Erreur validation"
                                    ? "RMSE des rendements logarithmiques mensuels sur les douze mois de validation. Plus faible est préférable."
                                    : label === "Trajectoires en perte"
                                      ? "Part des trajectoires finissant sous le capital initial, conditionnellement à ce scénario."
                                      : "Résultat central à douze mois, calculé séparément sur une base comparable de 10 000 € par actif."}
                        </span>
                      </Tooltip>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ranked.map((r) => (
                  <tr key={r.positions[0].id}>
                    <td>{r.positions[0].name}</td>
                    <td className={tone(r.metrics.return)}>
                      {money(10000 * (1 + r.metrics.return))}
                    </td>
                    <td className={tone(r.metrics.return)}>
                      {percent(r.metrics.return, true)}
                    </td>
                    <td className={tone(r.metrics.return - portfolioReturn)}>
                      {((r.metrics.return - portfolioReturn) * 100).toFixed(2)}{" "}
                      pts
                    </td>
                    <td>
                      {money(10000 * (1 + r.metrics.p05_return))} –{" "}
                      {money(10000 * (1 + r.metrics.p95_return))}
                    </td>
                    <td className={tone(r.metrics.drawdown)}>
                      {percent(r.metrics.drawdown)}
                    </td>
                    <td className={tone(r.metrics.drawdown_p05)}>
                      {percent(r.metrics.drawdown_p05)}
                    </td>
                    <td>{percent(r.metrics.conditional_loss_share)}</td>
                    <td>{r.positions[0].r2.toFixed(2)}</td>
                    <td>{percent(r.positions[0].validation_rmse)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {data && <Exclusions items={data.excluded} />}
    </section>
  );
}
