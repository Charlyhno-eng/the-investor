# Revue du HMM et passage à deux états

> Archive : ce document concerne les versions ou recherches antérieures à la reconstruction du 6 novembre 2026. Le [moteur actif est décrit ici](hmm-rebuilt.md).

> Étude historique : la méthode actuelle est décrite dans [la revue FrenchQuant](hmm-video.md).

## Dépôt examiné

Référence : [crypto-trend-following-strategy](https://github.com/Charlyhno-eng/crypto-trend-following-strategy), commit `bb899d9219731cec71a1f877c0da06f4df9fec2b`, consulté le 6 novembre 2026. Lecture des scripts sources ; aucun modèle pickle externe n’a été chargé.

Le [script quotidien d’entraînement](https://github.com/Charlyhno-eng/crypto-trend-following-strategy/blob/bb899d9219731cec71a1f877c0da06f4df9fec2b/scripts/1d_HMM_model.py) utilise GaussianHMM et des rendements logarithmiques accompagnés de momentum sur plusieurs horizons. Il sépare chronologiquement ajustement et validation, normalise avec l’ajustement et réserve une seconde période au test. Ces principes sont pertinents. Il explore deux, trois ou quatre états cachés : le nombre de régimes internes ne correspond pas nécessairement au nombre de positions possibles.

En revanche, le score de validation multiplie le signal à t, qui dépend déjà de la clôture t, par le rendement se terminant à t. Le [script de backtest quotidien](https://github.com/Charlyhno-eng/crypto-trend-following-strategy/blob/bb899d9219731cec71a1f877c0da06f4df9fec2b/scripts/1d_generate_plot.py) applique aussi la position du jour au rendement du même jour. Ce biais peut surestimer les performances. Les prédictions sur chaque préfixe évitent de consulter les observations suivantes, mais ne corrigent pas ce problème d’exécution. Elles répètent aussi les calculs avec un coût quadratique dans la longueur de l’historique.

## Adaptation retenue

Deux états GaussianHMM à covariance diagonale, trois initialisations déterministes. Les variables sont désormais le rendement logarithmique et le momentum cumulé sur dix observations quotidiennes ou trois mensuelles, calculé par sommes cumulées. Cela remplace le couple rendement/volatilité et donne au modèle une information directe sur la direction récente. Aucun réglage automatique sur la période de test n’a été ajouté.

L’état ayant la meilleure variation moyenne sur l’entraînement est le candidat « Hausse » ; l’autre est nommé « Neutre / baisse ». Cette dénomination reste une estimation statistique, pas une classification parfaite des marchés. Si le meilleur état ne dépasse pas le seuil de rentabilité entraîné, aucune position n’est ouverte. Les seuils de probabilité et les contraintes de détention peuvent retarder la sortie : on ne garantit donc pas l’absence d’exposition à chaque observation baissière.

La stratégie demeure binaire, actif ou liquidités. La chronologie montre les positions réellement exécutées après clôture ; elle ne confond plus les régimes estimés avec les positions. Coûts, décalage d’exécution, confirmation et plafond de transactions sont conservés. Le filtre causal compilé traite la série en temps linéaire. Le cache de résultats est versionné pour exclure les anciens résultats à trois états.

## Comparaison locale

Données SQLite locales, lues sans les modifier le 6 novembre 2026. Comparaison à la version à trois états et variables rendement/volatilité du dépôt local avant ces modifications. Pour chaque actif quotidien : dernières 2 016 observations disponibles ; pour l’or mensuel : historique complet. Découpage chronologique à 70 %, index de coupure inclus dans l’entraînement ; les observations initialisant les variables sont exclues de l’ajustement. Les deux versions utilisent exactement les mêmes dates, les paramètres API par défaut (10 pb de frais, 5 pb de glissement, confirmation 3, détention minimale 10, plafond 30 ordres), et le même moteur d’exécution causal. Ces réglages sont aussi utilisés pour l’or dans ce comparatif, indépendamment des défauts mensuels de l’interface.

| Actif | Test | Ancien rendement net | Nouveau rendement net | Achat-conservation net | Drawdown ancien / nouveau | Ordres ancien / nouveau |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| BTC-USD | 13/03/2025–06/11/2026 | −12,70 % | +14,36 % | −9,41 % | 46,58 % / 36,22 % | 22 / 18 |
| ETH-USD | 13/03/2025–06/11/2026 | +5,81 % | +84,53 % | +16,78 % | 58,47 % / 51,43 % | 28 / 18 |
| AAPL | 11/06/2024–05/11/2026 | −13,77 % | +18,28 % | +79,38 % | 43,69 % / 25,13 % | 26 / 30 |
| Or mensuel | 01/11/2006–01/10/2026 | −1,56 % | +431,51 % | +598,41 % | 19,04 % / 21,38 % | 6 / 12 |

L’amélioration sur ces quatre essais ne prouve pas une supériorité générale. Apple et l’or restent derrière l’achat-conservation ; le drawdown de l’or augmente et celui d’Ethereum reste supérieur à 50 %. Un seul découpage est évalué par actif ; il faut d’autres fenêtres intactes pour évaluer la robustesse. Aucun paramètre n’a été choisi à partir de ce tableau.

## Vérifications

Tests automatisés : causalité des variables et des régimes, momentum connu, deux états et probabilités normalisées, positions cohérentes avec le journal d’ordres, sortie sur tendance baissière synthétique, absence d’achat si les deux états entraînés sont perdants, délai d’exécution et coûts, cache et invalidation après correction d’historique. Les cas numériques extrêmes et la comparaison du filtre compilé aux préfixes de l’API publique restent couverts.
