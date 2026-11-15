# Variantes expérimentales d’allocation

Trois options API désactivées par défaut conservent les décisions actuelles :

- `rebalance_tolerance=0.03` : aux révisions trimestrielles des trois allocations de risque, ne pas échanger si chaque poids et la part de cash sont à moins de trois points de leur cible. Comparaison aux valeurs à la clôture du signal, jamais aux prix d’exécution. L’entrée initiale reste obligatoire. Une révision ignorée conserve les quantités et ne paie aucun frais.
- `regularize_covariance=true` : volatilité minimale seulement, estimation OAS vers une matrice identité multipliée par la variance moyenne. Intensité analytique, sans grille de paramètres ; contraintes inchangées. C’est une autre régularisation que Ledoit–Wolf à corrélation constante. La dérivation gaussienne limite son interprétation pour les queues épaisses.
- `reversion_quality_filter=true` : nouvelles entrées seulement ; régression historique inchangée. Régression AR(1) des résidus, coefficient entre 0 et 1, demi-vie estimée au plus 63 observations, moyenne des 63 derniers résidus à au plus un écart type de zéro. Cela ne prouve ni stationnarité ni retour futur. Sorties, financement et seuils restent inchangés.

Le script `PYTHONPATH=backend uv run python scripts/study_allocation_improvements.py` compare séparément chaque option au contrôle, sur une copie SQLite figée, trois univers et quatre périodes. Les résultats sont dans `data/backtests/allocation-improvements.json`, avec empreinte des données et paramètres. Les métriques comprennent rendement net, drawdown, volatilité, Sharpe, frais et rotation. Les anciens comparateurs restent disponibles dans chaque résultat.

Ces périodes ont déjà été examinées : elles ne constituent pas un échantillon inédit. Aucun réglage automatique, aucune activation par défaut ni affirmation de supériorité. Avant adoption, examiner la stabilité entre périodes, le risque, les frais à 1 %, les décalages d’exécution et un futur échantillon réservé. Le filtre est un candidat fixé a priori pour cette étude, pas un résultat sélectionné sur les gains individuels.

## Premier bilan local

108 calculs terminés (3 univers × 4 fenêtres × 9 contrôles/variantes). Sur journal_14, cinq ans, frais 0,5 %, titres entiers :

| Méthode | Rendement contrôle → variante | Frais contrôle → variante |
|---|---:|---:|
| Volatilité, tolérance | 149,15 % → 153,79 % | 253,63 € → 245,92 € |
| Corrélation, tolérance | 168,32 % → 169,01 % | 328,11 € → 312,05 € |
| Parité, tolérance | 172,16 % → 174,02 % | 259,30 € → 196,44 € |
| Volatilité, OAS | 149,15 % → 145,52 % | 253,63 € → 264,07 € |
| Retour à la moyenne, filtre | 330,62 % → 272,05 % | 649,02 € → 556,77 € |

La tolérance est encourageante sur cette fenêtre. OAS dégrade ici le rendement et le Sharpe. Le filtre réduit le drawdown de 16,22 % à 14,77 %, mais diminue le Sharpe de 1,68 à 1,51. Aucune option n’est activée par défaut. Ce bilan ne remplace pas l’examen des autres fenêtres et les stress de frais. Les transactions avec diagnostics seront incluses lors de la prochaine exécution du script ; le premier rapport contient les métriques et paramètres.
