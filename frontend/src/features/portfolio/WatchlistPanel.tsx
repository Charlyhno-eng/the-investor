import { Fragment, useEffect, useState } from "react";
import { Link } from "react-router";
import { post } from "../../lib/api";
import { categories, date } from "../../lib/format";
import { stockCountry } from "../../lib/countries";
import { Icon } from "../../components/Icon";
import { RegressionDeviation, type Deviation } from "./RegressionDeviation";
import type { Asset } from "../../lib/types";
type Row = Deviation;
import { useMomentumScores } from "../momentum/useMomentumScores";
import { MomentumCell, MomentumHeading } from "../momentum/MomentumCell";
export function WatchlistPanel({ assets }: { assets: Asset[] }) {
  const momentum = useMomentumScores(assets);
  const orderedAssets = [...assets].sort(
    (a, b) =>
      categories.findIndex((c) => c.id === a.category) -
      categories.findIndex((c) => c.id === b.category),
  );
  const supportsDeviation = (a: Asset) =>
    a.category === "stock" || a.category === "crypto";
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const revision = JSON.stringify(
    assets
      .filter(supportsDeviation)
      .map((a) => [a.id, a.data_revision, a.last_date, a.last_value]),
  );
  useEffect(() => {
    const controller = new AbortController();
    setRows([]);
    setError("");
    const assetIds = (JSON.parse(revision) as [string, string, number][]).map(
      ([id]) => id,
    );
    if (!assetIds.length) return () => controller.abort();
    post<{ positions: Row[] }>(
      "/portfolio/regression",
      { asset_ids: assetIds },
      controller.signal,
    )
      .then((r) => setRows(r.positions))
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [revision]);
  return (
    <section
      className="portfolio-panel"
      aria-label="Vue d’ensemble de la Watchlist"
    >
      <header className="portfolio-heading">
        <div className="asset-title">
          <span className="asset-emblem stock">
            <Icon name="star" size={24} />
          </span>
          <div>
            <span className="eyebrow">VOTRE SÉLECTION</span>
            <h1>Watchlist</h1>
          </div>
        </div>
      </header>
      <section className="portfolio-content">
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <div className="table-scroll">
          <table className="positions-table">
            <thead>
              <tr>
                <th>Actif</th>
                <th>Date du cours</th>
                <th>
                  <MomentumHeading />
                </th>
                <th>Écart à la régression</th>
              </tr>
            </thead>
            <tbody>
              {orderedAssets.map((a, index) => {
                const row = rows.find((r) => r.id === a.id);
                return (
                  <Fragment key={a.id}>
                    {(index === 0 ||
                      orderedAssets[index - 1].category !== a.category) && (
                      <tr className="watchlist-class-heading">
                        <th colSpan={4}>
                          {categories.find((c) => c.id === a.category)?.name}
                        </th>
                      </tr>
                    )}
                    <tr
                      className={
                        index > 0 &&
                        orderedAssets[index - 1].category !== a.category
                          ? "position-category-start"
                          : undefined
                      }
                    >
                      <th>
                        <Link to={`/assets/${a.id}?library=watchlist`}>
                          {a.name}
                        </Link>
                        <small>
                          {a.category === "stock"
                            ? `${stockCountry(a)} · `
                            : ""}
                          {a.unit}
                        </small>
                      </th>
                      <td>{date(a.last_date)}</td>
                      <td>
                        <MomentumCell asset={a} momentum={momentum} />
                      </td>
                      <td>
                        {supportsDeviation(a) ? (
                          <RegressionDeviation deviation={row} />
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
      {!assets.length && <p>Ajoutez des actifs avec une étoile argent.</p>}
    </section>
  );
}
