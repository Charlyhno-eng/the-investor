# Régression S&P 500 · compromis examinés le 19 novembre 2026

Étude exploratoire sur PSP5 en EUR. Le témoin est la v6, avec 10 000 € de capital neuf, 0,12 % par ordre, titres entiers, clôture suivante, cash à 0 % et budgets indépendants. Les 3 201 cours du 20 mai 2014 au 19 novembre 2026 proviennent d’une copie en mémoire de SQLite. Les dates de début comptent dans cette stratégie car elles fixent le calendrier de la poche défensive.

## Sélection historique

Les trois fenêtres se terminent le 19 novembre 2026. Le moteur de recherche de study_sp500_deep_search évalue le produit cartésien suivant. Les règles d’entrée, fenêtres de régression et initialisations sont celles de la v6.

| Paramètre | Valeurs |
|---|---|
| Part lente dans le budget actif | 50, 65, 75, 85, 95 % |
| Plancher en ETF de chaque poche active | 0, 5, 10, 15, 25 % |
| Seuil de sortie défensive en σ | 1,25, 1,5, 1,75, 2 |
| Intervalle entre décisions défensives en séances | 3, 5, 10 |
| Seuil de sortie lente en σ | 1,5 ou 2 |
| Budget initial en ETF passif | 0 ou 15 % |

Sur 1 200 combinaisons, aucune amélioration stricte simultanée du rendement annualisé, du drawdown maximal et de la volatilité annualisée sur chacun des trois horizons. Pour la sélection défensive, sept candidats conservent la volatilité au niveau du témoin ou en dessous, avec un retard de rendement limité à un point par an. Le candidat retenu maximise le plus petit gain de drawdown sur les trois horizons. Pour la sélection rendement, 178 candidats limitent la dégradation du drawdown et de la volatilité à un point chacun. Le candidat retenu maximise le plus petit gain de rendement. Les deux sélections sont figées avant les simulations.

| Stratégie | Rendement 3 / 5 / 10 ans (%) | Drawdown 3 / 5 / 10 ans (%) | Volatilité 3 / 5 / 10 ans (%) |
|---|---|---|---|
| v6 | 14,64 / 10,98 / 11,39 | −6,75 / −6,91 / −7,99 | 7,78 / 7,36 / 8,35 |
| Défensive, plancher 5 %, sortie défensive +1,25 σ | 14,29 / 10,92 / 10,45 | −6,64 / −6,84 / −7,98 | 7,57 / 7,18 / 8,12 |
| Rendement, 15 % en ETF passif, 85/15 dans le solde actif, plancher 5 % | 15,83 / 11,64 / 11,61 | −7,48 / −7,55 / −8,84 | 8,61 / 8,21 / 9,00 |
| v6 avec 10 % du capital initial gardé en cash | 13,33 / 10,05 / 10,64 | −6,17 / −6,38 / −7,40 | 7,13 / 6,76 / 7,80 |
| v6 avec 20 % du capital initial gardé en cash | 11,99 / 9,10 / 9,82 | −5,57 / −5,81 / −6,75 | 6,48 / 6,15 / 7,20 |
| v6 avec 30 % du capital initial gardé en cash | 10,61 / 8,12 / 8,96 | −4,95 / −5,22 / −6,08 | 5,79 / 5,49 / 6,57 |

Le diagnostic cash, ajouté après sélection, conserve la somme initiale en euros et laisse dériver son poids. Le moteur exécute les ordres sur le capital effectivement affecté aux deux poches. Les comparaisons synthétiques ci-dessous portent sur les deux candidats sélectionnés.

Une relecture distincte des archives arrêtées au 13 novembre compare les 816 configurations tactiques hors régression de deep-search et online-ensemble à la v6 de cette même date. Canaux, MACD, Markov, Kalman, CUSUM, noyaux, OLMAR, retournement et experts en ligne ne donnent aucune domination simultanée sur les trois horizons. Ces observations réutilisent des résultats historiques connus.

Une autre famille a été recalculée au 19 novembre. Les 162 règles de dimensionnement par volatilité de study_sp500_sharpe croisent fenêtres de 21/63/126 séances, cibles de 8/12/16 %, planchers de 0/25/50 %, exposants 1/2 et budgets indépendants en v4 de 0/35/65 %. Aucune ne domine la v6 sur les neuf comparaisons. Aucune ne passe la sélection défensive. Deux respectent les tolérances de risque de la sélection rendement. Cette vérification complémentaire intervient après le choix des deux candidats en régression.

## Contrôles des candidats figés

Le générateur de l’application tire des blocs de rendements PSP5 avec bruit. Chaque candidat et la v6 reçoivent exactement les mêmes prix. Les graines vont de 2 324 000 à 2 324 119 sur cinq ans et de 2 329 000 à 2 329 119 sur dix ans. Les fenêtres historiques glissantes durent cinq ans et se terminent les 13 février, mai, août et novembre de 2021 à 2026. Elles se chevauchent. Le stress de frais double chaque commission à 0,24 %. Le stress de délai exécute les ordres à la deuxième clôture suivante. Chaque stress est appliqué séparément.

| Horizon | Stratégie | Rendement annuel moyen | Drawdown maximal moyen | Volatilité moyenne | Parcours avec drawdown aggravé |
|---|---|---:|---:|---:|---:|
| 5 ans simulés | v6 | 10,05 % | −18,47 % | 11,84 % | 0 / 120 |
| 5 ans simulés | Défensive | 9,58 % | −18,01 % | 11,47 % | 29 / 120 |
| 5 ans simulés | Rendement | 10,94 % | −19,62 % | 12,66 % | 90 / 120 |
| 10 ans simulés | v6 | 9,76 % | −22,47 % | 11,40 % | 0 / 120 |
| 10 ans simulés | Défensive | 9,17 % | −22,12 % | 11,11 % | 34 / 120 |
| 10 ans simulés | Rendement | 10,78 % | −23,67 % | 12,21 % | 99 / 120 |
| 5 ans glissants | v6 | 11,43 % | −7,38 % | 8,67 % | 0 / 24 |
| 5 ans glissants | Défensive | 10,74 % | −7,37 % | 8,43 % | 8 / 24 |
| 5 ans glissants | Rendement | 12,14 % | −8,30 % | 9,44 % | 19 / 24 |

Chaque drawdown du tableau mesure la pire baisse sur un parcours avant calcul de la moyenne. L’aggravation maximale observée face à la v6 atteint 4,62 points pour la variante rendement sur les parcours de dix ans.

| Stress historique | Horizon | Stratégie | Rendement annuel | Drawdown maximal | Volatilité |
|---|---|---|---:|---:|---:|
| Frais doubles | 3 ans | v6 | 14,52 % | −6,75 % | 7,78 % |
| Frais doubles | 3 ans | Défensive | 14,19 % | −6,65 % | 7,59 % |
| Frais doubles | 3 ans | Rendement | 15,68 % | −7,47 % | 8,60 % |
| Frais doubles | 5 ans | v6 | 10,91 % | −6,92 % | 7,37 % |
| Frais doubles | 5 ans | Défensive | 10,87 % | −6,84 % | 7,20 % |
| Frais doubles | 5 ans | Rendement | 11,58 % | −7,56 % | 8,21 % |
| Frais doubles | 10 ans | v6 | 11,31 % | −8,00 % | 8,36 % |
| Frais doubles | 10 ans | Défensive | 10,36 % | −7,99 % | 8,13 % |
| Frais doubles | 10 ans | Rendement | 11,54 % | −8,85 % | 9,01 % |
| Deuxième clôture | 3 ans | v6 | 14,03 % | −6,71 % | 7,72 % |
| Deuxième clôture | 3 ans | Défensive | 13,80 % | −6,64 % | 7,54 % |
| Deuxième clôture | 3 ans | Rendement | 15,19 % | −7,44 % | 8,55 % |
| Deuxième clôture | 5 ans | v6 | 10,73 % | −6,91 % | 7,35 % |
| Deuxième clôture | 5 ans | Défensive | 10,68 % | −6,82 % | 7,15 % |
| Deuxième clôture | 5 ans | Rendement | 11,43 % | −7,55 % | 8,20 % |
| Deuxième clôture | 10 ans | v6 | 11,23 % | −7,98 % | 8,34 % |
| Deuxième clôture | 10 ans | Défensive | 10,22 % | −8,00 % | 8,12 % |
| Deuxième clôture | 10 ans | Rendement | 11,44 % | −8,76 % | 8,98 % |

Les quatre indicateurs du témoin (rendement annualisé, drawdown maximal, volatilité et Sharpe) reproduisent les chiffres archivés au 13 novembre aux trois horizons. La recherche sur des périodes déjà étudiées favorise les meilleurs réglages historiques. Les nouvelles graines recyclent le même historique économique et l’instrument commence en 2014, après les crises de 2000 et 2008.
