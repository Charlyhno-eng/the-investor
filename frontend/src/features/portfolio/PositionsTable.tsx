import { Link } from "react-router";
import { Icon } from "../../components/Icon";
import { NumberInput } from "../../components/NumberInput";
import { Tooltip } from "../../components/Tooltip";
import { stockCountry } from "../../lib/countries";
import { money } from "../../lib/currency";
import { date } from "../../lib/format";
import type { Asset } from "../../lib/types";
import { RegressionDeviation, type Deviation } from "./RegressionDeviation";
import type { Quantities } from "./quantities";
import type { PortfolioResult } from "./types";

export function PositionsTable({
  assets,
  result,
  deviations,
  quantities,
  onQuantity,
  lockedAssetIds,
  onToggleLock,
  simulation,
}: {
  assets: Asset[];
  result: PortfolioResult | null;
  deviations: Deviation[];
  quantities: Quantities;
  onQuantity: (id: string, quantity: number) => void;
  lockedAssetIds: string[];
  onToggleLock?: (id: string) => void;
  simulation: boolean;
}) {
  return (
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
              <Tooltip floating label="Écart à la régression sur cinq ans">
                Écart du dernier prix à la régression logarithmique des cinq
                dernières années, divisé par l’écart-type des résidus (n − 2).
                Vert : sous la tendance ; jaune : proche de la tendance ; rouge
                : au-dessus. Repères ± 1,5 σ. Si l’actif est récent, seul son
                historique disponible est utilisé ; les dates figurent au
                survol. Ce repère décrit le prix, sans garantir un signal
                d’achat ou de vente.
              </Tooltip>
            </th>
          </tr>
        </thead>
        <tbody>
          {assets.map((asset, index) => {
            const position = result?.positions.find((p) => p.id === asset.id);
            const deviation = deviations.find((p) => p.id === asset.id);
            return (
              <tr
                key={asset.id}
                className={
                  index > 0 && assets[index - 1].category !== asset.category
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
                    <span className="sr-only">Quantité {asset.name}</span>
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
                          lockedAssetIds.includes(asset.id) ? "lock" : "unlock"
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
  );
}
