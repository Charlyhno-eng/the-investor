import { number } from "../../lib/format";
import type { Asset } from "../../lib/types";
import { Tooltip } from "../../components/Tooltip";
import { weightedScore, partialHistory, MOMENTUM_HORIZONS } from "./score";
import { useMomentumScores } from "./useMomentumScores";

export function MomentumHeading() {
  return (
    <>
      Momentum{" "}
      <Tooltip floating label="Score pondéré de Momentum">
        Score sur 100 combinant les horizons 36, 12 et 6 mois, dernier mois
        exclu. Les poids et la référence sont ceux choisis dans l’onglet
        Momentum pour chaque catégorie (40 / 35 / 25 ; S&P 500 pour les actions
        et ETF, Bitcoin pour les cryptomonnaies par défaut). Toutes les devises
        sont incluses, sans effet de change. 50 : neutre. Actions, ETF et
        cryptomonnaies : si un horizon manque, les poids des horizons
        disponibles sont recalculés et le score est signalé comme partiel.
      </Tooltip>
    </>
  );
}
export function MomentumCell({
  asset,
  momentum,
}: {
  asset: Asset;
  momentum: ReturnType<typeof useMomentumScores>;
}) {
  if (!["stock", "crypto", "etf"].includes(asset.category)) return <>—</>;
  const scores =
    asset.category === "crypto"
      ? momentum.crypto
      : asset.category === "etf"
        ? momentum.etf
        : momentum;
  const stock = scores.stocks.find((s) => s.id === asset.id);
  const score = weightedScore(stock?.scores ?? null, scores.weights);
  const partial = partialHistory(stock?.scores ?? null);
  const coverage = MOMENTUM_HORIZONS.filter(
    (_, i) => stock?.scores?.[i] != null,
  ).join(" / ");
  const reason =
    scores.error ||
    (scores.pending
      ? "Chargement du Momentum…"
      : stock?.reason ||
        "Score indisponible : historique insuffisant ou poids nuls.");
  return (
    <span
      className={`momentum-cell ${score === null ? "muted" : score >= 50 ? "positive" : "negative"}`}
      title={
        score === null
          ? reason
          : `Score pondéré au ${scores.asOf} · 50 : neutre${partial ? ` · historique partiel : ${coverage} mois ; poids recalculés` : ""}`
      }
      aria-label={
        score === null ? reason : `Momentum : ${number(score, 1)} sur 100`
      }
    >
      {score === null
        ? scores.pending
          ? "…"
          : "—"
        : `${number(score, 1)} / 100`}
      {score !== null && partial && (
        <small className="momentum-partial">Historique partiel</small>
      )}
    </span>
  );
}
