# Momentum des actions, ETF et cryptomonnaies

L’onglet Momentum combine trois fenêtres terminées un mois avant l’analyse : de t−36 à t−1, t−12 à t−1 et t−6 à t−1 mois. Le dernier mois est exclu du rendement, de la régression et de la force relative pour les trois horizons. Les mois sont calendaires, avec écrêtage au dernier jour du mois. Le rendement à 12 mois couvre donc environ onze mois. Poids initiaux : 40 %, 35 %, 25 %. Les poids modifiables sont normalisés ; une somme nulle ne produit aucun score.

L’exclusion du dernier mois reprend la convention de [Kenneth French](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library/det_mom_factor.html). Le score combiné sur trois horizons reste propre à l’application et n’est pas validé comme modèle prédictif.

## Référence et données

`GET /api/assets/{id}/momentum?benchmark={référence}` fournit le détail d’une action et le classement global. `GET /api/momentum?benchmark={référence}` fournit les mêmes scores sans les graphiques, pour les tableaux Portfolio et Watchlist. La date commune est la dernière date disponible parmi les actions importées. Les prix sont les observations locales ajustées.

Toutes les devises sont admises dans un seul classement. Chaque série est analysée dans sa devise de cotation ; rendement, pente logarithmique, R² et dispersion sont invariants à un changement constant d’unité. Aucun cours de change n’entre dans le calcul. Il s’agit du momentum des actions sur leur marché de cotation, et non du rendement d’un portefeuille converti en euros. La force relative compare les progressions en pourcentage de l’action et de la référence, dans leurs devises respectives.

La référence par défaut reste le S&P 500 dividendes réinvestis (`^SP500TR`). Le CAC 40 (`^FCHI`, hors dividendes) est aussi disponible. La différence de traitement des dividendes est indiquée dans l’aide de la force relative. Les indices sont importés par le worker existant et conservés dans le cache local ; l’interface attend leur disponibilité pendant une minute. Un ETF local de n’importe quelle devise peut aussi servir de référence. L’ETF Amundi CAC 40 UCITS ETF Dist (`CAC.PA`) est ajouté au catalogue ETF et à la bibliothèque locale.

Un historique de référence déjà présent reste utilisable pendant son actualisation en arrière-plan, y compris si le fournisseur échoue. L’expiration du délai d’actualisation d’une heure ne masque plus les scores locaux. Les contrôles de dates et de couverture de chaque horizon restent appliqués : un historique trop ancien ne produit pas de score artificiel. Seule l’absence de données locales impose d’attendre l’import initial.

L’ajustement de chaque fenêtre utilise les dates communes effectivement observées, sans interpolation. Il exige 60 observations, des bornes à moins de 7 jours des dates théoriques et aucun trou supérieur à 14 jours (pour accepter les fermetures prolongées des places boursières). Un historique incomplet ne produit pas de score pour cet horizon.

Les poids et la référence choisis sont conservés dans le navigateur et partagés entre la fiche action et les tableaux Portfolio/Watchlist. Les colonnes du tableau des horizons disposent d’aides au survol ou au focus. Les détails de méthode restent documentés ici.

## Formule

Sur une fenêtre de durée D en années de 365,25 jours :

- r = ln(P_fin / P_début) / D.
- b = pente OLS de ln(P) sur les années calendaires écoulées.
- f = ln[(P_fin / P_début) / (B_fin / B_début)] / D.
- σ = √[Σ(ln(P) − ln(P_ajusté))² / (n − 2)].
- R² = 1 − SSE / SST, borné entre 0 et 1 ; zéro pour une série constante.

Force = 0,4 tanh(r / 0,30) + 0,3 tanh(b / 0,30) + 0,3 tanh(f / 0,20).

Qualité = √R² / (1 + σ / 0,10).

Score = 50 + 50 × Force × Qualité, puis moyenne des trois scores selon les poids normalisés.

Les échelles 0,30, 0,20 et 0,10 sont des choix fixes non calibrés. Le score est borné entre 0 et 100 et n’est pas un percentile. La neutralité est à 50 ; une baisse régulière reste une contribution négative. La qualité amortit les contributions positives comme négatives vers la neutralité. Les rendements et forces relatives affichés sont cumulés ; la pente affichée est exp(b) − 1, annualisée. Les graphiques montrent les cours en échelle logarithmique et les résidus logarithmiques multipliés par 100 autour de zéro.

## Classement et corrections

L’univers affiché correspond à toutes les actions visibles dans la bibliothèque, sans filtre de pays ou de devise. Toutes sont évaluées à la date commune de l’univers, avec la même référence et les mêmes poids. Le classement exige au moins un horizon exploitable avec un poids positif et une dernière cotation datant de sept jours au maximum. Les horizons indisponibles reçoivent un poids effectif nul ; les poids restants sont renormalisés. Le score et les tableaux signalent explicitement « historique partiel » si un horizon manque. Les durées couvertes peuvent donc différer entre actifs : un score sur 12/6 mois ne décrit pas le même recul historique qu’un score sur 36/12/6 mois. Les actions retirées dans le navigateur sont exclues du classement affiché.

La variation du dernier mois et l’écart entre le dernier cours et le plus haut cours ajusté des 36 derniers mois restent visibles. Les prix du dernier mois ne participent pas aux trois scores ; ces deux mesures restent des diagnostics séparés. Ainsi, une forte hausse ancienne peut coexister avec un horizon court négatif et une correction récente. La combinaison peut encore donner un score élevé : elle ne constitue pas un filtre de retournement.

Le R² et les résidus décrivent le passé et ne prédisent pas la poursuite d’une tendance. Le classement de la bibliothèque actuelle comporte un biais de survivance et ne constitue pas un backtest.

## ETF

Les ETF proposent le même onglet Momentum que les actions : fenêtres de 36, 12 et 6 mois, exclusion du dernier mois, poids initiaux de 40/35/25, régression logarithmique, résidus et force relative. La référence par défaut est le S&P 500 ; le CAC 40 et les ETF locaux sont aussi disponibles. `GET /api/momentum?category=etf` renvoie uniquement les ETF, avec leur propre date d’analyse et leur propre classement. Les réglages sont enregistrés séparément de ceux des actions et des cryptomonnaies.

Le Portfolio et la Watchlist affichent les scores ETF avec ces mêmes réglages, y compris la mention d’historique partiel et la renormalisation des poids disponibles. Ils affichent également leur écart normalisé à la régression logarithmique, calculé comme pour les actions. L’onglet Régression reste accessible dans chaque fiche ETF.

## Cryptomonnaies

Les fiches des cryptomonnaies proposent le même onglet, avec les mêmes formules, exclusions et poids initiaux. `GET /api/momentum?category=crypto` fournit uniquement l’univers crypto ; la route par actif déduit sa catégorie. La date d’analyse est propre à chaque univers. Les cours crypto sont quotidiens, week-ends compris lorsque disponibles, sans annualisation à 252 séances : le temps est mesuré en années de 365,25 jours.

La référence crypto par défaut est Bitcoin (`BTC-USD`), avec priorité à son historique local ; le worker importe une référence Bitcoin indépendante si la bibliothèque n’en contient pas. Une autre cryptomonnaie de la bibliothèque peut servir de référence. Les classements actions et crypto restent séparés et les paramètres sont conservés séparément dans le navigateur. Les tableaux Portfolio et Watchlist affichent aussi les scores crypto. L’onglet Recommandation action conserve son périmètre actions uniquement. Les échelles numériques n’ont pas été recalibrées sur les cryptomonnaies ; une même note n’est pas une mesure de risque comparable entre les deux univers.
