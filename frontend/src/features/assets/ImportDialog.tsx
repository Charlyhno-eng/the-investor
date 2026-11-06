import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { Icon } from "../../components/Icon";
import { api, post } from "../../lib/api";
import type { ImportJob } from "../../lib/types";

type Stock = {
  symbol: string;
  name: string;
  exchange: string;
  imported?: boolean;
};
type SearchResponse = { results: Stock[]; warning: string | null };
const suggestions: Stock[] = [
  { symbol: "AAPL", name: "Apple", exchange: "NASDAQ" },
  { symbol: "MSFT", name: "Microsoft", exchange: "NASDAQ" },
  { symbol: "NVDA", name: "NVIDIA", exchange: "NASDAQ" },
  { symbol: "MC.PA", name: "LVMH", exchange: "Paris" },
  { symbol: "AIR.PA", name: "Airbus", exchange: "Paris" },
  { symbol: "7203.T", name: "Toyota", exchange: "Tokyo" },
];
export function ImportDialog({
  close,
  refresh,
}: {
  close: () => void;
  refresh: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Stock | null>(null);
  const [results, setResults] = useState<Stock[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [warning, setWarning] = useState("");
  const [job, setJob] = useState<ImportJob | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [pollRevision, setPollRevision] = useState(0);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  useEffect(() => {
    if (selected || query.trim().length < 2) {
      setSearching(false);
      return;
    }
    const controller = new AbortController();
    setSearching(true);
    setSearchError("");
    setWarning("");
    setResults([]);
    const timer = setTimeout(() => {
      api<SearchResponse>(
        `/stocks/search?q=${encodeURIComponent(query.trim())}`,
        { signal: controller.signal },
      )
        .then((data) => {
          setResults(data.results);
          setWarning(data.warning ?? "");
        })
        .catch((e) => {
          if (e.name !== "AbortError") setSearchError(e.message);
        })
        .finally(() => {
          if (!controller.signal.aborted) setSearching(false);
        });
    }, 350);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [query, selected]);
  useEffect(() => {
    if (job?.status === "completed" && job.asset_id) {
      refresh();
      navigate(`/assets/${job.asset_id}`);
      close();
      return;
    }
    if (job?.status === "failed") {
      setError(job.error ?? "Import échoué.");
      setLoading(false);
      return;
    }
    if (!job?.id || !["queued", "running"].includes(job.status)) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api<ImportJob>(`/asset-imports/${job.id}`, { signal: controller.signal })
        .then((data) => {
          setJob(data);
          setError("");
        })
        .catch((e) => {
          if (e.name !== "AbortError") {
            setError("Connexion interrompue. Reconnexion automatique…");
            setPollRevision((v) => v + 1);
          }
        });
    }, 1000);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [job, pollRevision, close, navigate, refresh]);
  function choose(stock: Stock) {
    setSelected(stock);
    setQuery(stock.name);
    setError("");
    setSearchError("");
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!selected) {
      const exact = results.find(
        (stock) => stock.symbol.toLowerCase() === query.trim().toLowerCase(),
      );
      if (exact) choose(exact);
      return;
    }
    setLoading(true);
    setError("");
    setJob(null);
    try {
      setJob(
        await post<ImportJob>("/asset-imports", {
          symbol: selected.symbol,
          category: "stock",
        }),
      );
    } catch (e) {
      setError((e as Error).message);
      setLoading(false);
    }
  }
  const canDirect =
    !selected &&
    !searching &&
    (searchError || (query.trim().length >= 2 && !results.length)) &&
    /^[A-Za-z0-9][A-Za-z0-9.\-]{0,23}$/.test(query.trim());
  return (
    <dialog
      ref={dialog}
      onCancel={close}
      onClick={(e) => {
        if (e.target === dialog.current) close();
      }}
      className="import-dialog"
    >
      <div className="dialog-heading">
        <span className="eyebrow">VOTRE BIBLIOTHÈQUE</span>
        <button className="icon-button" onClick={close} aria-label="Fermer">
          <Icon name="close" />
        </button>
      </div>
      <h2>
        Ajouter une action<span className="accent">.</span>
      </h2>
      <p className="muted">
        Recherchez une entreprise, choisissez sa cotation.
      </p>
      <form onSubmit={submit}>
        <label className="field-label" htmlFor="stock-search">
          Nom ou symbole
        </label>
        <div className="symbol-field">
          <Icon name="search" />
          <input
            id="stock-search"
            autoFocus
            autoComplete="off"
            placeholder="Apple, LVMH, Toyota…"
            value={query}
            maxLength={80}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelected(null);
              setSearchError("");
              setResults([]);
            }}
            disabled={loading}
            aria-describedby="stock-search-status"
          />
        </div>
        {!selected &&
          (query.trim().length < 2 ? (
            <div className="suggestions">
              {suggestions.map((stock) => (
                <button
                  type="button"
                  key={stock.symbol}
                  onClick={() => choose(stock)}
                >
                  <span>{stock.name}</span>
                  <small>{stock.symbol}</small>
                </button>
              ))}
            </div>
          ) : (
            <div className="stock-results" aria-label="Résultats de recherche">
              {results.map((stock) => (
                <button
                  type="button"
                  key={stock.symbol}
                  onClick={() => choose(stock)}
                >
                  <span>
                    <strong>{stock.name}</strong>
                    <small>
                      {stock.symbol} · {stock.exchange}
                    </small>
                  </span>
                  <span className="stock-result-tag">
                    {stock.imported ? "Déjà ajouté" : "Choisir"}
                  </span>
                </button>
              ))}
            </div>
          ))}
        <div
          id="stock-search-status"
          role="status"
          className="stock-search-status"
        >
          {!selected &&
            (searching ? (
              <>
                <span className="spinner" />
                Recherche…
              </>
            ) : (
              searchError ||
              warning ||
              (query.trim().length >= 2
                ? results.length
                  ? `${results.length} cotation${results.length > 1 ? "s" : ""} · sélectionnez la place souhaitée`
                  : "Aucune action trouvée. Essayez un autre nom ou un symbole."
                : "")
            ))}
        </div>
        {canDirect && (
          <button
            type="button"
            className="secondary-button direct-symbol"
            onClick={() =>
              choose({
                symbol: query.trim().toUpperCase(),
                name: query.trim().toUpperCase(),
                exchange: "Symbole exact · vérifié à l’import",
              })
            }
          >
            Utiliser le symbole {query.trim().toUpperCase()}
          </button>
        )}
        {selected && (
          <div className="selected-stock">
            <div>
              <strong>{selected.name}</strong>
              <small>
                {selected.symbol} · {selected.exchange}
              </small>
            </div>
            <button
              type="button"
              disabled={loading}
              className="icon-button"
              aria-label="Changer d’action"
              onClick={() => {
                setSelected(null);
                setQuery("");
              }}
            >
              <Icon name="close" size={14} />
            </button>
          </div>
        )}
        {loading && (
          <div className="notice" role="status">
            <span className="spinner" />
            {job?.status === "running"
              ? "Téléchargement des cours et dividendes…"
              : "Préparation du téléchargement…"}
            <small>
              L’historique sera conservé localement. Vous pouvez fermer cette
              fenêtre, l’import continue.
            </small>
          </div>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <p className="fine-print">
          Historique quotidien disponible · Yahoo Finance
        </p>
        <button
          type="submit"
          className="primary-button full"
          disabled={loading || !selected}
        >
          {loading
            ? "Import en cours"
            : selected?.imported
              ? "Ouvrir l’action"
              : "Télécharger l’historique"}
          <Icon name={loading ? "layers" : "arrow"} size={16} />
        </button>
      </form>
    </dialog>
  );
}
