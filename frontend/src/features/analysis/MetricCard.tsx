import { Tooltip } from "../../components/Tooltip";
import { number, percent } from "../../lib/format";
import type { Metrics } from "../../lib/types";
const definitions = [
  {
    key: "sharpe",
    label: "Sharpe ratio",
    text: "Rendement excédentaire moyen / volatilité, annualisé. Taux sans risque fixé à 0 %. > 1 : rapport rendement/risque favorable ; > 2 : élevé. Un historique court rend ce ratio fragile.",
  },
  {
    key: "sortino",
    label: "Sortino ratio",
    text: "Rendement excédentaire rapporté aux seules variations sous le taux sans risque. > 1 : favorable ; > 2 : élevé. Indisponible en l’absence de risque baissier mesuré.",
  },
  {
    key: "calmar",
    label: "Calmar ratio",
    text: "Rendement annualisé / drawdown maximal sur le test. > 1 : rendement annualisé supérieur à la pire baisse ; plus élevé est préférable. Sensible à la durée choisie.",
  },
  {
    key: "annualized_volatility",
    label: "Volatilité annualisée",
    pct: true,
    text: "Écart-type des rendements multiplié par la racine du nombre de périodes annuelles : 252 actions, 365 crypto, 12 séries mensuelles. Plus élevé = plus variable. Aucun seuil universel.",
  },
  {
    key: "maximum_drawdown",
    label: "Drawdown maximal",
    pct: true,
    text: "Plus forte perte entre un sommet du capital et le creux suivant, capital initial inclus. 20 % signifie une baisse de 20 % depuis un sommet. Plus faible est préférable.",
  },
  {
    key: "var_95",
    label: "VaR 95 %",
    pct: true,
    text: "Perte au quantile historique de 5 % des rendements nets. Horizon : une observation (jour ou mois selon la série). 5 % des pertes observées peuvent la dépasser ; ce n’est pas une perte maximale.",
  },
  {
    key: "alpha",
    label: "Alpha annualisé",
    pct: true,
    text: "Intercept annualisé de la régression des rendements excédentaires de la stratégie sur ceux du même actif en achat-conservation. > 0 : excédent après exposition au marché, sans preuve de significativité statistique.",
  },
  {
    key: "beta",
    label: "Bêta",
    text: "Sensibilité au même actif en achat-conservation : 1 = exposition comparable, 0 = faible sensibilité linéaire, < 0 = relation inverse. Indisponible si le benchmark ne varie pas.",
  },
] as const;
export function MetricCards({
  strategy,
  benchmark,
}: {
  strategy: Metrics;
  benchmark: Metrics;
}) {
  return (
    <div className="metric-grid">
      {definitions.map((metric) => {
        const value = strategy[metric.key],
          reference = benchmark[metric.key];
        const fmt = (n: number | null) =>
          n == null ? "—" : "pct" in metric ? percent(n) : number(n);
        return (
          <div className="metric-card" key={metric.key}>
            <div className="metric-label">
              {metric.label}
              <Tooltip label={metric.label}>
                <span>{metric.text}</span>
              </Tooltip>
            </div>
            <strong>{fmt(value)}</strong>
            <small>
              Marché <span>{fmt(reference)}</span>
            </small>
          </div>
        );
      })}
    </div>
  );
}
