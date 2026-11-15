# Trois pistes d’optimisation — 14 novembre 2026

Décision : activer les bandes de tolérance de 3 points dans les validations des stratégies volatilité minimale et corrélation minimale. Ne pas intégrer le plafond par groupe ni l’allocation par groupes. La parité de risque conserve son réglage préexistant. Portfolio reste sans les quatre onglets retirés.

## Protocole avant calcul

Le script écrit le protocole avant le premier résultat. Trois univers (journal de 14 actifs, 11 actions, 4 cryptos), quatre fenêtres (2016–2021, 2021–2024, 2024–2026, 2021–2026), frais de 0,5 % et 1 % par opération. 168 simulations, contrôles compris. Chaque fenêtre recommence avec 10 000 €, actions/ETF entiers et cryptos fractionnaires. Signaux disponibles au moment de la décision, exécution ultérieure, mêmes données et comparateurs. Les paramètres actuels du retour à la moyenne restent 2 / 2 / repli 1 / financement 0,3.

- Tolérance : ignorer la révision trimestrielle si tous les poids et le cash restent à moins de 3 points de leur cible. Entrée initiale obligatoire.
- Plafond : limiter les nouveaux ordres de retour à la moyenne à 40 % de la valeur totale par groupe. Les groupes sont les composantes connexes des corrélations positives d’au moins 0,70 sur les 252 dernières variations disponibles. Les sorties restent autorisées ; les dépassements dus aux prix ne déclenchent pas une vente forcée.
- Allocation : budget égal entre ces groupes, puis équipondération au sein de chaque groupe, révision trimestrielle. Comparaison principale à la volatilité minimale, remplacée par cette règle pour l’expérience. Les liens sont recalculés exclusivement avec l’historique du signal ; les secteurs actuels ne sont pas utilisés rétroactivement.

Critères communs sur chacun des 24 cas par candidat : perte de CAGR au plus 0,5 point, perte de Sharpe au plus 0,03, dégradation de baisse maximale au plus 1 point. Tolérance : baisse supplémentaire de la somme descriptive des frais et rotations. Deux autres candidats : gain moyen de Sharpe d’au moins 0,05 et réduction relative moyenne de baisse maximale d’au moins 10 %. Aucun ajustement après résultats.

## Résultats et décisions

| Candidat | Cas hors limites communes | Décision |
|---|---:|---|
| Tolérance, volatilité | 0 / 24 | Conservée |
| Tolérance, corrélation | 0 / 24 | Conservée |
| Plafond, retour à la moyenne | 2 / 24 | Rejeté |
| Allocation par groupes | 12 / 24 | Rejetée |

Le plafond échoue sur les cryptos en 2021–2024 aux deux niveaux de frais. Son gain moyen de Sharpe (0,040) et sa réduction moyenne de baisse maximale (8,2 %) sont également insuffisants. L’allocation par groupes augmente les frais et ne réduit la baisse maximale que de 0,8 % en moyenne, malgré un gain moyen de Sharpe de 0,111. Ces moyennes descriptives ne compensent pas les échecs individuels.

Sur le journal de 14 actifs, 2021–2026, frais 0,5 % :

| Candidat | Capital contrôle → variante | Sharpe contrôle → variante | Frais contrôle → variante |
|---|---:|---:|---:|
| Tolérance volatilité | 24 915,31 € → 25 379,03 € | 1,423 → 1,451 | 253,63 € → 245,92 € |
| Tolérance corrélation | 26 832,27 € → 26 900,69 € | 1,265 → 1,269 | 328,11 € → 312,05 € |
| Plafond retour à la moyenne | 43 062,10 € → 43 062,10 € | 1,682 → 1,682 | 649,02 € → 649,02 € |
| Allocation par groupes | 24 915,31 € → 26 878,43 € | 1,423 → 1,348 | 253,63 € → 283,37 € |

Les montants exacts sont ceux du JSON de cette exécution ; ils peuvent différer légèrement des anciennes études. Les bandes retenues tolèrent de petites dégradations dans certains cas : elles ne gagnent pas systématiquement.

## Reproduction et limites

`PYTHONPATH=backend uv run python scripts/study_three_optimizations.py`

Rapport : `data/backtests/three-optimizations.json`, protocole, empreinte SHA-256 SQLite, métriques individuelles et décisions. Le script sauvegarde une copie depuis une connexion en lecture seule ; aucun changement de la base utilisateur. Les deux règles rejetées existent uniquement dans le script de recherche, qui construit des copies isolées du moteur. Aucun paramètre API ou contrôle d’interface n’est ajouté pour elles.

Cinq tests couvrent le traitement des actifs dupliqués, les frais et titres entiers, le plafond, les sorties et l’absence d’effet de cours futurs sur les transactions antérieures. Les historiques ont déjà été examinés, les fenêtres se recouvrent et les univers sont sélectionnés aujourd’hui : aucune validation prospective ni garantie de rendement. Fiscalité, spreads et impact de marché non simulés. Les sommes et moyennes entre cas ne représentent pas un portefeuille indépendant.
