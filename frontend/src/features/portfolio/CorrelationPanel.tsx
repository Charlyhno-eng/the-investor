import { Tooltip } from "../../components/Tooltip";
import { number } from "../../lib/format";
import { correlationColor } from "./correlationColor";
import type { PortfolioResult } from "./types";

export function CorrelationPanel({
  correlation,
  years,
  onYearsChange: setYears,
}: {
  correlation?: PortfolioResult["correlation"];
  years: number;
  onYearsChange: (years: number) => void;
}) {
  return (
    <>
      <div className="portfolio-section-heading">
        <div>
          <h2 className="correlation-title">
            Matrice de corrélation{" "}
            <Tooltip label="Méthode de corrélation">
              Corrélation de Pearson des rendements logarithmiques en USD,
              dividendes réinvestis pour les actions. Dates communes uniquement,
              sans remplissage des données manquantes. Les quantités ne
              modifient pas les coefficients.
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
          Renseignez au moins deux positions pour comparer leurs corrélations.
        </p>
      )}
    </>
  );
}
