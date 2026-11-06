import { useEffect, useState } from "react";
import { Tooltip } from "../../components/Tooltip";
import { api } from "../../lib/api";
import { date, number } from "../../lib/format";
import type { Asset } from "../../lib/types";

type DividendHistory = {
  currency: string;
  coverage: {
    first_date: string;
    last_date: string;
    updated_at: string;
  } | null;
  events: { time: string; amount: number }[];
};
function yearStart(end: string) {
  const d = new Date(`${end}T00:00:00Z`);
  d.setUTCFullYear(d.getUTCFullYear() - 1);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}
export function DividendPanel({ asset }: { asset: Asset }) {
  const [history, setHistory] = useState<DividendHistory | null>(null);
  const [error, setError] = useState("");
  const [start, setStart] = useState(
    yearStart(asset.last_date) < asset.first_date
      ? asset.first_date
      : yearStart(asset.last_date),
  );
  const [end, setEnd] = useState(asset.last_date);
  useEffect(() => {
    const controller = new AbortController();
    function load() {
      api<DividendHistory>(
        `/assets/${encodeURIComponent(asset.id)}/dividends`,
        { signal: controller.signal },
      )
        .then((result) => {
          setHistory(result);
          setError("");
        })
        .catch((e) => {
          if (e.name !== "AbortError") setError(e.message);
        });
    }
    load();
    const timer = setInterval(load, 15000);
    return () => {
      clearInterval(timer);
      controller.abort();
    };
  }, [asset.id, asset.last_date]);
  const coverage = history?.coverage;
  const invalid = !start || !end || start > end;
  const outside =
    !!coverage && (start < coverage.first_date || end > coverage.last_date);
  const events =
    history?.events.filter((e) => e.time >= start && e.time <= end) ?? [];
  const latest = history?.events.at(-1);
  const total = events.reduce((sum, e) => sum + e.amount, 0);
  const lastYear =
    history?.events
      .filter(
        (e) =>
          e.time >= yearStart(coverage?.last_date ?? asset.last_date) &&
          e.time <= (coverage?.last_date ?? asset.last_date),
      )
      .reduce((sum, e) => sum + e.amount, 0) ?? 0;
  return (
    <section className="dividend-panel" aria-label="Dividendes">
      <div className="dividend-heading">
        <div>
          <span className="eyebrow">REVENUS DE L’ACTION</span>
          <h2>
            Dividendes{" "}
            <Tooltip label="Dividendes par action">
              Montants bruts par action fournis par Yahoo Finance, corrigés des
              divisions d’actions selon le fournisseur. Les dates sont les dates
              de détachement, pas de paiement. Les clôtures du graphique sont
              déjà ajustées des dividendes : ne les ajoutez pas à nouveau à leur
              performance. Aucun dividende futur n’est garanti.
            </Tooltip>
          </h2>
        </div>
        <span className="source-badge">
          {history?.currency ?? asset.unit} / action
        </span>
      </div>
      {error ? (
        <p role="alert" className="error">
          {error}
        </p>
      ) : !history ? (
        <p className="muted" role="status">
          Chargement des dividendes…
        </p>
      ) : !coverage ? (
        <p className="muted" role="status">
          Historique des dividendes en attente de la prochaine actualisation du
          worker.
        </p>
      ) : (
        <>
          <div className="dividend-summary">
            <div>
              <span className="field-label">Dernier dividende connu</span>
              <strong>
                {latest ? number(latest.amount, 4) : "—"}
                <small>{history.currency}</small>
              </strong>
              <span className="muted">
                {latest
                  ? `Détaché le ${date(latest.time)}`
                  : "Aucun détachement dans l’historique disponible"}
              </span>
            </div>
            <div>
              <span className="field-label">Cumul sur 12 mois</span>
              <strong>
                {number(lastYear, 4)}
                <small>{history.currency}</small>
              </strong>
              <span className="muted">
                Au {date(coverage.last_date)}
                {coverage.first_date > yearStart(coverage.last_date)
                  ? " · historique partiel"
                  : ""}
              </span>
            </div>
          </div>
          <div className="dividend-period">
            <div>
              <span className="field-label">Période de détachement</span>
              <span className="muted">Dates incluses</span>
            </div>
            <label>
              Du
              <input
                type="date"
                aria-label="Dividendes du"
                value={start}
                min={coverage.first_date}
                max={coverage.last_date}
                onChange={(e) => setStart(e.target.value)}
              />
            </label>
            <label>
              Au
              <input
                type="date"
                aria-label="Dividendes au"
                value={end}
                min={coverage.first_date}
                max={coverage.last_date}
                onChange={(e) => setEnd(e.target.value)}
              />
            </label>
            <button
              className="secondary-button"
              onClick={() => {
                setStart(
                  yearStart(coverage.last_date) < coverage.first_date
                    ? coverage.first_date
                    : yearStart(coverage.last_date),
                );
                setEnd(coverage.last_date);
              }}
            >
              12 mois
            </button>
            <button
              className="secondary-button"
              onClick={() => {
                setStart(coverage.first_date);
                setEnd(coverage.last_date);
              }}
            >
              Tout
            </button>
          </div>
          {invalid ? (
            <p className="error" role="alert">
              Sélectionnez une période valide, du début à la fin.
            </p>
          ) : outside ? (
            <p className="error" role="alert">
              Historique disponible du {date(coverage.first_date)} au{" "}
              {date(coverage.last_date)}. Choisissez une période couverte.
            </p>
          ) : (
            <>
              <div className="dividend-total">
                <span>
                  Total brut par action
                  <strong>
                    {number(total, 4)} <small>{history.currency}</small>
                  </strong>
                </span>
                <span>
                  {events.length} détachement{events.length > 1 ? "s" : ""}
                </span>
              </div>
              {events.length ? (
                <details className="dividend-events">
                  <summary>Détail des dividendes</summary>
                  <div className="dividend-table">
                    <table>
                      <thead>
                        <tr>
                          <th>Détachement</th>
                          <th>Montant par action · {history.currency}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...events].reverse().map((event) => (
                          <tr key={event.time}>
                            <td>{date(event.time)}</td>
                            <td>{number(event.amount, 4)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              ) : (
                <p className="muted">
                  Aucun dividende enregistré sur cette période.
                </p>
              )}
            </>
          )}
          <div className="dividend-coverage">
            Historique disponible : {date(coverage.first_date)} —{" "}
            {date(coverage.last_date)} · Montants bruts, hors fiscalité et
            conversion de devise.
          </div>
        </>
      )}
    </section>
  );
}
