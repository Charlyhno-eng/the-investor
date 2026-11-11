# Simulation conditionnelle du portefeuille

L’onglet **Simulation**, sous **Stratégie**, applique les variations historiques de facteurs aux expositions estimées récemment du portefeuille actuel. Il ne rejoue pas les positions de l’investisseur en 2008 et ne prédit pas la prochaine crise. Le portefeuille réel est sélectionné par défaut. Un brouillon sur mesure, indépendant des positions et favoris, est conservé dans `investor-simulation` (stockage local). Le bouton de calcul fige les paramètres ; modifier le formulaire ne modifie pas le dernier résultat.

## Données publiques sans clé

Les imports Yahoo Finance via yfinance utilisent la file durable existante, un cache SQLite et les nouvelles tentatives existantes. Aucun rendement de crise n’est codé en dur. Les références additionnelles SPY, QQQ, EFA, TLT, HYG, GLD et USO utilisent **Adj Close** (dividendes et splits). EURUSD=X utilise Close. Les facteurs sont des proxys de marché, pas des séries macroéconomiques d’inflation, chômage ou PIB. TLT représente les obligations longues, HYG le crédit risqué ; leurs performances combinent plusieurs influences et ne permettent pas une attribution causale pure.

Les historiques ont été effectivement récupérés lors de l’implémentation. Les références téléchargées sont rafraîchies par le worker existant. Le calcul fonctionne sur cache, programme une actualisation des références périmées et refuse une calibration dont le dernier mois est vieux de plus de trois mois. Les prix de valorisation de plus de 45 jours (70 pour les séries mensuelles) sont exclus. Les dates des prix sont affichées. Un fournisseur indisponible renvoie une erreur explicite ; un historique absent n’est jamais remplacé par une trajectoire inventée.

## Modèle et calculs

1. Valorisation existante des quantités en EUR aux derniers prix disponibles, avec les exclusions habituelles : un taux souverain n’est pas un prix d’obligation.
2. Conversion des observations ajustées en EUR avec le dernier change **antérieur ou égal** à la date observée (sept jours maximum). La constante des centimes de livre ne change pas les rendements logarithmiques ; la valorisation initiale utilise bien les unités monétaires normalisées.
3. Dernière observation réelle de chaque mois terminé ; aucun remplissage des mois manquants. Rendements logarithmiques uniquement entre mois consécutifs. La calibration utilise le suffixe commun contigu dans les 61 derniers mois, avec au moins 36 mois.
4. Régression conjointe ridge des rendements EUR sur huit facteurs USD/change ; standardisation et pénalité 3 pour stabiliser la colinéarité. Interception retirée de la projection : pas d’extrapolation d’un alpha historique. Les sensibilités sont constantes pendant le scénario.
5. Application de la succession **observée** des rendements des facteurs du scénario à ces sensibilités récentes, puis capitalisation des rendements logarithmiques par actif, avec quantités initiales fixes et séries ajustées assimilées à des dividendes réinvestis. Ni rééquilibrage ni frais ni fiscalité.
6. Six cents trajectoires : bootstrap circulaire de blocs de trois mois pour réestimer les coefficients ; résidus centrés tirés par blocs synchronisés entre actifs. Les dépendances résiduelles contemporaines et une partie de leur persistance sont préservées. La graine par défaut est 42. La volatilité résiduelle est celle de la calibration, pas une modélisation distincte des défauts ou de la liquidité en crise.
7. Affichage de la réponse centrale, médiane et quantiles ponctuels P5/P95 ; drawdown sur chaque trajectoire **mensuelle**, puis quantile 5 % des drawdowns ; proportion des trajectoires terminant sous le capital initial. Cette proportion n’est ni la probabilité de survenue du scénario ni une fréquence validée dans le monde réel.
8. R² descriptif de calibration et erreur RMSE logarithmique sur les douze derniers mois, avec un ajustement séparé sur les mois précédents. Le modèle final utilise ensuite toute la calibration. Cette validation ne démontre pas une capacité à prédire les crises futures.

Les positions manquant d’historique sont exclues explicitement. Le ratio de couverture est calculé par rapport aux positions **valorisables**, pas aux positions impossibles à valoriser. Les totaux, trajectoires et contributions concernent uniquement le sous-portefeuille couvert. Si l’intersection des historiques restants est trop courte, aucun résultat chiffré n’est produit.

## Fenêtres des scénarios

Le début est le mois servant de base ; les rendements commencent au mois suivant. L’interface utilise un horizon fixe de douze mois à partir du mois courant. L’API conserve la possibilité de demander de trois à douze mois. Les scénarios se choisissent dans la bibliothèque latérale. Le graphique affiche au survol la variation centrale et le capital du mois sélectionné.

| Scénario | Mois de base | Dernier mois à 12 mois |
| --- | --- | --- |
| Covid-like | 2020-01 | 2021-01 |
| Crise bancaire | 2008-08 | 2009-08 |
| Guerre / énergie / inflation | 2022-01 | 2023-01 |
| Dettes européennes | 2011-06 | 2012-06 |
| Resserrement monétaire | 2018-01 | 2019-01 |
| Réouverture et relance | 2020-10 | 2021-10 |
| Désinflation et reprise | 2022-12 | 2023-12 |

Les fenêtres incluent les réponses monétaires et budgétaires ainsi que les reprises effectivement observées ; une crise peut donc produire un rendement final positif tout en ayant un drawdown important. « Positif » désigne le régime historique, pas une garantie de gain pour chaque portefeuille.

## Limites d’interprétation

Le modèle est linéaire, mensuel et fondé sur une seule fenêtre par scénario. Il ne capture pas les creux intramensuels (crucial pour Covid), l’évolution des sensibilités en crise, les défauts, les fermetures de marché, les ventes contraintes, les effets sectoriels idiosyncratiques, ni les politiques futures. Les quantiles sont conditionnels à une trajectoire de facteurs fixée ; ils ne couvrent pas l’incertitude de sélection de cette trajectoire. Les facteurs ETF peuvent embarquer des coûts ou effets de roulement (USO), et les matières premières locales sont des proxys de prix. Les biais de survivance, la qualité des données et les ruptures structurelles limitent toute prétention de réalisme.

Ces limites et les historiques sont visibles dans l’interface et l’export JSON. Ce moteur constitue un stress test empirique transparent, pas une estimation objective de « ce qui arrivera ».

## API et vérification

- `GET /api/simulation/scenarios` : catalogue documenté.
- `POST /api/simulation/run` : `holdings`, `scenario`, `months`, `seed` ; cent positions maximum ; statuts `pending`, `insufficient`, `ready`.
- Tests : scénarios, reproductibilité, dépendances résiduelles, couverture partielle, données manquantes, validation des paramètres et navigation mobile / desktop avec brouillon indépendant.

Références : [yfinance download](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html), [scénarios conditionnels de la Federal Reserve](https://www.federalreserve.gov/publications/2026-stress-test-scenarios.htm). Le moteur n’utilise pas les modèles bancaires de la Fed.

Les tableaux d’impact, de facteurs et de sensibilités sont affichés dans trois sections distinctes. Les définitions sont accessibles au survol, au focus ou au clic sur les points d’interrogation. Les sensibilités utilisent du cuivré pour le sens direct, du bleu pour le sens inverse et du gris près de zéro : ces couleurs ne sont pas des notes de performance. Les explications détaillées des limites restent disponibles dans ce document et dans les données exportées.

## Watchlist et scénario IA

Le changement de scénario réinitialise le panneau et annule les téléchargements côté interface. Après un calcul réussi, la page défile vers le graphique (sans animation si le système réduit les mouvements).

`POST /api/simulation/watchlist` accepte `asset_ids`, `scenario` et `seed` (100 actifs maximum). Il applique le même moteur séparément à chaque actif. L’interface normalise les résultats à 10 000 € par actif, trie par rendement central et affiche les quantiles, drawdowns, fréquence conditionnelle de perte, R², erreur de validation et écart de rendement avec le portefeuille. La watchlist présente uniquement le tableau comparatif ; le graphique individuel et le détail des contributions ne sont plus affichés. Une meilleure performance finale ne signifie pas nécessairement un moindre drawdown. Les périodes de calibration peuvent différer entre actifs ; elles sont indiquées. Les exclusions et les erreurs de données sont explicites.

Le huitième facteur est QQQ, clôtures ajustées du Nasdaq-100. Le scénario **Crise de l’IA · dégonflement des valorisations** utilise les facteurs observés entre décembre 2021 et décembre 2022 comme analogue d’une réévaluation des valeurs technologiques. C’est une hypothèse de crise IA, pas une crise IA historique, ni un modèle de revenus ou dépenses d’IA. Aucun choc spécifique IA n’est inventé ou présenté comme observé. Ce facteur est également utilisé dans les autres scénarios. Sources : [composition du QQQ (Invesco)](https://www.invesco.com/qqq-etf/en/about.html), [performances historiques (Invesco)](https://www.invesco.com/qqq-etf/en/performance.html).

Un [audit santé et Covid](simulation-health-audit.md) compare le modèle aux performances historiques et teste expérimentalement des facteurs sectoriels, sans modifier le moteur.
