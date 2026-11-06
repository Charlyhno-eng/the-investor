import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { Icon } from "../../components/Icon";
import { api, post } from "../../lib/api";
import type { ImportJob } from "../../lib/types";
const suggestions = [
  ["AAPL", "Apple"],
  ["MSFT", "Microsoft"],
  ["NVDA", "NVIDIA"],
  ["MC.PA", "LVMH"],
  ["AIR.PA", "Airbus"],
  ["7203.T", "Toyota"],
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
  const [symbol, setSymbol] = useState("");
  const [job, setJob] = useState<ImportJob | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  useEffect(() => {
    if (job?.status === "completed" && job.asset_id) {
      refresh();
      navigate(`/assets/${job.asset_id}`);
      close();
    }
    if (job?.status === "failed") {
      setError(job.error ?? "Import échoué.");
      setLoading(false);
    }
    if (!job?.id || !["queued", "running"].includes(job.status)) return;
    const controller = new AbortController();
    const timeout = setTimeout(() => {
      api<ImportJob>(`/asset-imports/${job.id}`, { signal: controller.signal })
        .then(setJob)
        .catch((e) => {
          if (e.name !== "AbortError") {
            setError(e.message);
            setLoading(false);
          }
        });
    }, 1600);
    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, [job, close, navigate, refresh]);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      setJob(
        await post<ImportJob>("/asset-imports", {
          symbol: symbol.trim().toUpperCase(),
          category: "stock",
        }),
      );
    } catch (e) {
      setError((e as Error).message);
      setLoading(false);
    }
  }
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
        Un symbole, son historique complet. Conservé localement.
      </p>
      <form onSubmit={submit}>
        <label className="field-label" htmlFor="symbol">
          Symbole de cotation
        </label>
        <div className="symbol-field">
          <Icon name="search" />
          <input
            id="symbol"
            autoFocus
            placeholder="AAPL, MC.PA, 7203.T…"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            pattern="[A-Za-z0-9][A-Za-z0-9.\-]{0,23}"
            required
            disabled={loading}
          />
        </div>
        <div className="suggestions">
          {suggestions.map(([s, name]) => (
            <button
              type="button"
              key={s}
              disabled={loading}
              onClick={() => setSymbol(s)}
            >
              <span>{name}</span>
              <small>{s}</small>
            </button>
          ))}
        </div>
        <p className="fine-print">
          Clôtures quotidiennes ajustées · Yahoo Finance
          <br />
          Le suffixe indique la place : .PA Paris, .L Londres, .T Tokyo.
        </p>
        {loading && (
          <div className="notice" role="status">
            <span className="pulse-dot" />
            {job?.status === "running"
              ? "Téléchargement de l’historique…"
              : "En attente du worker…"}
            <small>
              Le processus « make worker » doit être lancé. Vous pouvez fermer
              cette fenêtre ; l’import reste en file.
            </small>
          </div>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button
          type="submit"
          className="primary-button full"
          disabled={loading || !symbol.trim()}
        >
          {loading ? "Import en cours" : "Télécharger l’historique"}
          <Icon name={loading ? "layers" : "arrow"} size={16} />
        </button>
      </form>
    </dialog>
  );
}
