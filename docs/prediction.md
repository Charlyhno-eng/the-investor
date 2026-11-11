# Prédiction : régression et GARCH

Les actions et cryptomonnaies utilisent au maximum trois ans d’historique quotidien, terminés au dernier cours connu, puis six mois de projection. Si l’actif dispose de moins de trois ans, tout son historique disponible est utilisé et la période réellement couverte est indiquée. Aucun réglage n’est exposé. Le calcul reste local au navigateur. Une série non positive, non finie, désordonnée ou avec un trou de plus de dix jours pour les cryptomonnaies ou vingt jours pour les actions est refusée. Au moins 61 cours doivent être présents dans la fenêtre pour ajuster la régression et les 60 innovations nécessaires à GARCH. Un historique court rend les paramètres moins stables.

## Tendance et écarts à la régression

`fitRegression(history, "log", 2)` est partagé avec l’onglet Régression : moindres carrés du logarithme du prix sur le temps calendaire, et écart-type résiduel avec N − 2 degrés de liberté. On note T(t) la tendance logarithmique et σ cet écart-type.

L’écart normalisé uᵢ = (log(Pᵢ) − T(tᵢ)) / σ est modélisé par uᵢ = φ uᵢ₋₁ + εᵢ. Le coefficient φ est estimé sans constante par moindres carrés, contraint entre 0 et 1. La pente historique se prolonge, avec retour progressif de l’écart vers zéro si φ < 1. Cette hypothèse de retour vers la tendance est une hypothèse supplémentaire, non une propriété garantie par la régression. À φ = 1, l’écart initial persiste.

L’origine de toutes les projections est le dernier prix observé. Les bandes descriptives historiques ±1σ ou ±2σ ne sont pas présentées comme des intervalles de probabilité futurs. L’écart normalisé affiché reprend celui de l’onglet Régression sur la même période disponible (au maximum trois ans).

## Volatilité GARCH(1,1)

Les innovations εᵢ sont modélisées avec une variance conditionnelle :

```
hᵢ₊₁ = ω + α εᵢ² + β hᵢ
ω = v × (1 − α − β)
v = moyenne(εᵢ²)
```

Le ciblage de variance fixe la variance de long terme à v. α et β minimisent une quasi-vraisemblance gaussienne conditionnelle, avec α ≥ 0, β ≥ 0 et α + β < 0,995. Les innovations sont mises à l’échelle pour stabiliser l’optimisation. Une grille de départ suivie d’un raffinement local inclut la variance constante, sans garantie d’optimum global. Le filtrage part de v et utilise toutes les innovations, y compris la dernière, pour obtenir la première variance future.

Pour une série de prix constants ou exactement exponentiels, la dispersion résiduelle est quasi nulle : la volatilité simulée devient nulle et l’écart normalisé est absent.

## Distribution projetée

4 096 trajectoires simulent les écarts u, avec innovations normales conditionnelles, chocs opposés par paires et graine fixe. Pour chaque trajectoire : log(Pₜ) = T(t) + σ uₜ. Les quantiles P5, P25, P75 et P95 sont obtenus en interpolant les écarts simulés triés, puis en revenant aux prix. La symétrie des chocs donne la médiane analytique exp(T(t) + σ φᵏ u₀), avec k étapes futures. Les bandes de simulation ont une erreur Monte-Carlo, même si l’affichage est reproductible.

Une étape correspond à une séance observée pour les actions et à un jour pour les cryptomonnaies. Les actions sont projetées les jours de semaine, sans calendrier des jours fériés ; l’échéance calendaire de six mois est ramenée au vendredi si elle tombe un week-end. La régression utilise toujours le temps calendaire. La volatilité conditionnelle des innovations est annualisée avec 252 séances ou 365,25 jours ; ce n’est pas la dispersion du prix à six mois.

## Limites

Les zones centrales couvrent 50 % et 90 % de la distribution à une date donnée sous ce modèle, et ne sont pas des probabilités de rester dans la bande pendant toute la trajectoire. Les paramètres, la pente et le retour à la tendance sont estimés puis supposés connus. Leur incertitude, les sauts, les ruptures de régime et l’asymétrie ne sont pas intégrés. Une dispersion qui se stabilise est possible avec un retour à la tendance ; les zones ne s’élargissent pas nécessairement à chaque étape.

Aucune qualité prédictive hors échantillon n’est revendiquée. Les tests couvrent les calculs, l’ajustement sur un GARCH synthétique, la reproductibilité, les invariances et l’interface ; ils ne valident pas la couverture sur les marchés. Les actions utilisent les cours ajustés du graphique de marché, avec dividendes réinvestis, pas un futur cours brut hors dividendes.

Références : [prévisions et simulations GARCH, projet arch](https://arch.readthedocs.io/en/stable/univariate/forecasting.html), [Francq, Horváth et Zakoïan : ciblage de variance dans GARCH](https://mpra.ub.uni-muenchen.de/15143/).

## Portefeuille

La projection du portefeuille conserve le modèle individuel de chaque actif : historique natif ajusté, jusqu’à trois ans propres à cet actif, régression logarithmique, AR(1) et GARCH. Un actif récent ne raccourcit jamais la fenêtre des autres. Le backend fournit les historiques séparés et la valeur actuelle de chaque quantité en euros.

4 096 trajectoires conjointes utilisent des innovations normales corrélées. Les innovations historiques sont standardisées par leur variance GARCH filtrée et alignées par date. Une matrice de Gram sur l’union des dates (zéro pour les innovations absentes), normalisée puis rétrécie de 5 % vers l’identité, fournit une corrélation positive définie et une factorisation de Cholesky. Les recouvrements courts sont ainsi ramenés vers une dépendance faible ; les modèles marginaux conservent tout leur historique. Cette estimation reste approximative, notamment entre marchés aux calendriers différents.

Les trajectoires conservent les étapes propres à chaque actif : jours calendaires pour les cryptos, jours de semaine pour les autres, sans jours fériés. Les valeurs sont conservées les jours sans étape. À chaque date et pour chaque simulation, les valeurs individuelles sont multipliées par les quantités et additionnées en euros. Le change reste constant au taux de valorisation de chaque position : aucun modèle de change futur n’est ajouté implicitement. Les quantiles sont calculés après l’addition ; ni les médianes ni les bornes individuelles ne sont additionnées.

Un historique de moins de 61 observations est inclus dès sa première cotation via un modèle provisoire sans tendance (marche aléatoire logarithmique), avec variance empirique des rendements ramenée au temps calendaire. Une ou deux cotations ne suffisent pas à estimer cette variance : la contribution reste constante et une explication visible signale que son risque n’est pas estimé. Ce modèle provisoire n’est pas un ajustement GARCH. La fiche individuelle conserve son minimum de 61 observations pour GARCH.

Le graphique historique utilise les dates communes uniquement pour afficher une valeur reconstituée, jamais pour ajuster les modèles. Les cours ajustés sont normalisés à la valeur actuelle de chaque quantité ; cette courbe ne représente pas les transactions réelles. Les quantités et le change sont conservés, sans apport, retrait ni rééquilibrage. Les paramètres et dépendances sont estimés puis supposés connus ; la simulation n’intègre pas leur incertitude et sa couverture hors échantillon n’est pas validée.
