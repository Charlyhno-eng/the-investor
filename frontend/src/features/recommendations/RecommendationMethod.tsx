export function RecommendationMethod() {
  return (
    <details className="recommendation-method">
      <summary>Formule et critères de recommandation</summary>
      <p>
        Pour l’action <var>i</var>, <var>M</var>
        <sub>i</sub> ∈ [0, 100] est le Momentum pondéré sur 36, 12 et 6 mois,
        dernier mois exclu. Les poids et la référence sont ceux de l’onglet
        Momentum. En cas d’historique partiel, seuls les horizons disponibles
        sont utilisés et leurs poids sont recalculés. Les scores peuvent alors
        couvrir des durées différentes.
      </p>
      <div
        className="scientific-formula"
        role="math"
        aria-label="z i égale logarithme du prix moins prix logarithmique ajusté, divisé par sigma des résidus"
      >
        <span className="math-expression">
          <var>z</var>
          <sub>i</sub> ={" "}
          <span className="math-fraction">
            <span>
              ln <var>P</var>
              <sub>i,t</sub> − (<var>α̂</var>
              <sub>i</sub> + <var>β̂</var>
              <sub>i</sub> <var>t</var>)
            </span>
            <span>
              <var>σ̂</var>
              <sub>ε,i</sub>
            </span>
          </span>
        </span>
        <span className="math-separator">;</span>
        <span className="math-expression">
          <var>σ̂</var>
          <sub>ε,i</sub> = √
          <span className="math-fraction">
            <span>
              ∑<sub>j=1</sub>
              <sup>n</sup> <var>ε</var>
              <sub>i,j</sub>
              <sup>2</sup>
            </span>
            <span>
              <var>n</var> − 2
            </span>
          </span>
        </span>
      </div>
      <p>
        La droite logarithmique est ajustée par moindres carrés sur les cinq
        dernières années disponibles, avec le temps en années calendaires, comme
        dans Régression. <var>z</var> est un écart exprimé en écarts-types
        résiduels ; il ne représente pas une probabilité. Un historique plus
        court est utilisé s’il fournit au moins 30 observations ; les dates
        réellement utilisées figurent dans le tableau.
      </p>
      <div
        className="scientific-formula"
        role="math"
        aria-label="Décote D i égale cinquante fois un moins tangente hyperbolique de z i divisé par un virgule cinq ; priorité A i égale zéro virgule sept M i plus zéro virgule trois D i"
      >
        <span className="math-expression">
          <var>D</var>
          <sub>i</sub> = 50 [1 − tanh(<var>z</var>
          <sub>i</sub> / 1,5)]
        </span>
        <span className="math-separator">;</span>
        <span className="math-expression">
          <var>A</var>
          <sub>i</sub> = 0,7 <var>M</var>
          <sub>i</sub> + 0,3 <var>D</var>
          <sub>i</sub>
        </span>
      </div>
      <p>
        <var>D</var> est un score de décote sur 100 : 50 sur la droite,
        supérieur à 50 en dessous et inférieur à 50 au-dessus. C’est l’écart
        signé <var>z</var>, et non la dispersion résiduelle elle-même, qui
        intervient : plus <var>z</var> est négatif, plus la décote favorise
        l’entrée. Une décote sous −2 σ reste favorable, sans limite basse
        bloquante. La fonction tanh borne progressivement la contribution des
        écarts extrêmes.
      </p>
      <p>
        La priorité <var>A</var> ∈ [0, 100] combine 70 % de Momentum et 30 % de
        décote. Elle peut dépasser le Momentum : un score inférieur à 60 peut
        être compensé par une décote suffisante. Les poids 70 / 30, l’échelle
        1,5 σ et le seuil de 60 sont des choix heuristiques, sans calibration
        historique.
      </p>
      <ul>
        <li>
          <strong>Acheter / Renforcer</strong> : <var>A</var>
          <sub>i</sub> ≥ 60. « Renforcer » concerne uniquement les actions
          détenues ; « Acheter », celles de la watchlist.
        </li>
        <li>
          <strong>Vendre</strong> : action détenue et <var>M</var>
          <sub>i</sub> &lt; 40, quel que soit <var>z</var>
          <sub>i</sub>.
        </li>
        <li>
          <strong>Alléger</strong> : action détenue, 40 ≤ <var>M</var>
          <sub>i</sub> &lt; 55 et <var>z</var>
          <sub>i</sub> ≥ 1,5.
        </li>
        <li>
          <strong>Conserver / Attendre</strong> : autres cas selon le statut de
          détention. Données manquantes, non finies, non alignées à sept jours
          près ou trop anciennes dans l’univers : aucune recommandation.
        </li>
      </ul>
      <p>
        Les scénarios contrôlés vérifient que la priorité augmente avec le
        Momentum et avec la décote, ainsi que les cas du tableau présenté. Il
        n’y a plus de seuil indépendant de Momentum à 60 ni de plafond d’écart à
        +0,5 σ pour l’entrée : la décision utilise le score combiné. Les règles
        de vente et d’allègement ci-dessus sont évaluées en premier. Ces tests
        vérifient la cohérence des règles ; ils ne démontrent pas une
        rentabilité future.
      </p>
      <p>
        Indications expérimentales à examiner avant toute décision : ni montant
        d’ordre, ni objectif de cours. Les règles n’intègrent pas les
        fondamentaux, les frais, la fiscalité ou votre besoin de liquidités. Une
        tendance passée et un écart à la droite ne garantissent pas un retour à
        la moyenne.{" "}
        <a
          href="https://www.nber.org/papers/w20439"
          target="_blank"
          rel="noreferrer"
        >
          Daniel et Moskowitz : risques des stratégies momentum
        </a>
        .
      </p>
    </details>
  );
}
