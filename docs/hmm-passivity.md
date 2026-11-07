# Pourquoi le HMM ressemble à l’achat-conservation

> Archive : ce document concerne les versions ou recherches antérieures à la reconstruction du 6 novembre 2026. Le [moteur actif est décrit ici](hmm-rebuilt.md).

6 novembre 2026. **Le défaut est confirmé, mais aucune version surperformante dans l’extrême majorité des cas n’a été obtenue.** La nouvelle variante de tendance reste une expérience locale ; elle n’a pas remplacé le moteur de simulation. Les modifications actives portent sur le diagnostic, la comparaison nette et la visibilité des régimes et positions.

## Reproduction du cas Air Liquide

La fenêtre par défaut du 28 juin 2024 au 6 novembre 2026 donne +30,68 % contre +29,99 %, deux ordres (un aller-retour), 99,67 % d’exposition. Ce n’est pas un défaut du tracé : la stratégie détient presque constamment le même actif que la référence. Son écart net n’est que de **+0,69 point**, sans preuve de valeur ajoutée répétable.

Le HMM apprend un état négatif (moyenne logarithmique quotidienne −0,0814 %) et un état positif (+0,0870 %). Mais leurs avantages de continuation valent respectivement environ −0,1244 % et +0,5732 %, tandis que le seuil de sortie est −0,5013 %. Toute combinaison probabiliste reste au-dessus de ce seuil : **aucun régime ne peut faire vendre**, même un état défavorable certain. La liquidation finale explique la deuxième transaction. Sur les 22 actifs par défaut, 11 souffrent de cette impossibilité structurelle ; trois ont uniquement des moyennes d’état positives.

Cette règle répond à une approximation d’espérance après frais et transitions ; elle ne traduit pas directement « état négatif ⇒ sortie ». La qualifier simplement de détection de baisse masquait cette différence. De plus, ajuster la densité des rendements ne démontre pas une capacité de prévision directionnelle.

## Deux vérifications supplémentaires

Une correction minimale, exploratoire, conserve le HMM figé et la règle d’entrée précédente, exige un état dominant positif pour entrer et sort dès que l’état dominant est négatif. Les frais ne peuvent pas bloquer cette sortie. Sur Air Liquide, elle produit 18 ordres et 91,23 % d’exposition, mais seulement **+9,23 %** net. Sur BE Semiconductor, elle produit 192 ordres. Elle ne bat la conservation que sur 5 actifs sur 22. Faire respecter mécaniquement l’état négatif ne suffit donc pas à résoudre le problème de frais et de rentabilité. Code exact et résultats conservés localement dans `data/backtests/hmm-direct-policy/`.

Une seconde expérience cherche explicitement des régimes de tendance : trois états gaussiens sur le ratio moyenne/écart-type exponentiels des rendements logarithmiques, span 30 fixé. L’idée des moments lissés vient de [Werge, sections 4–5](https://arxiv.org/html/2107.05535v1), mais **placer le ratio lui-même dans les observations est notre adaptation**, pas une reproduction de ses résultats. Ajustement avec [GaussianHMM de hmmlearn](https://hmmlearn.readthedocs.io/en/stable/tutorial.html), trois graines 17/41/83 départagées par vraisemblance d’entraînement. Normalisation apprise sur le passé. Réentraînement toutes les 63 observations, sur au plus 1 260 observations antérieures au signal.

États réordonnés à chaque ajustement, filtre forward causal, aucune réécriture des probabilités passées. État défavorable dominant et centre négatif : sortie, sans veto des frais. État favorable dominant et centre positif : entrée seulement si le mouvement indicatif sur sa durée moyenne apprise couvre les deux frais. État intermédiaire : maintien. Cette estimation des coûts est une heuristique, sans promesse de gain. Pas de MACD, de stop, de quota de transactions, de cible d’exposition, de position courte ou de levier. Les noms d’état désignent la tendance observée, pas une prévision garantie.

## Comparaison nette sur toutes les fenêtres

22 actifs, 149 fenêtres admissibles, chacun aux frais normaux puis doublés : **298 nouveaux backtests**. Les fenêtres sont les mêmes que dans [l’étude précédente](hmm-literature.md) : continu 2022–2025, tests annuels 2022–2026, périodes par défaut de l’interface. Les cinq fenêtres sans historique suffisant d’Hyperliquid restent exclues. Crypto : 0,01 % par achat et par vente ; action : 0,5 %. Signal à la clôture t, ordre à la clôture t+1, premier rendement t+2 ; liquidation finale et frais de la référence inclus.

| Fenêtre, frais normaux | Actifs | Bat conservation | Rendement médian | Conservation médiane | Exposition médiane | Ordres médians |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| continuous_2022_2025 | 21 | 3 | +13,68 % | +58,18 % | 41,45 % | 24 |
| walk_2022 | 21 | 14 | -8,27 % | -27,14 % | 24,11 % | 6 |
| walk_2023 | 21 | 0 | +13,96 % | +40,46 % | 59,73 % | 8 |
| walk_2024 | 21 | 1 | -0,75 % | +23,24 % | 43,75 % | 6 |
| walk_2025 | 21 | 7 | +3,73 % | +11,24 % | 43,84 % | 6 |
| walk_2026 | 22 | 8 | -1,77 % | +0,80 % | 42,01 % | 6 |
| interface_default | 22 | 6 | -2,78 % | +32,65 % | 39,40 % | 14 |

**39/149 surperformances aux frais normaux**, sur des fenêtres qui se chevauchent. Sur les fenêtres par défaut : 6/22, rendement médian −2,78 % contre +32,65 %, exposition médiane 39,40 %, 14 ordres médians. Aucun actif n’y reste investi à ≥95 % ou en liquidités à ≥95 %. Les courbes diffèrent, mais le résultat financier se dégrade. Avec les frais doublés : 5/22, rendement médian −8,27 %. Aucun groupe ne passe le critère de 80 % de surperformances. **Cette variante est rejetée.**

## Détail des fenêtres par défaut, frais normaux

| Actif | Stratégie candidate | Conservation | Exposition | Ordres |
| --- | ---: | ---: | ---: | ---: |
| Apple Inc. | +2,49 % | +64,88 % | 43,21 % | 16 |
| L'Air Liquide S.A. | -9,64 % | +29,99 % | 38,74 % | 16 |
| Airbus SE | +9,83 % | +54,87 % | 59,27 % | 12 |
| ASML Holding N.V. | -11,87 % | +35,32 % | 41,39 % | 16 |
| BE Semiconductor Industries N.V. | +8,18 % | -6,16 % | 36,42 % | 12 |
| BNB | +28,87 % | +21,75 % | 46,19 % | 10 |
| Bitcoin | -14,36 % | -9,15 % | 24,01 % | 12 |
| Ethereum | +139,51 % | +17,10 % | 31,13 % | 6 |
| Gaztransport & Technigaz SA | -14,56 % | +60,19 % | 60,76 % | 20 |
| Hyperliquid | +36,75 % | +101,93 % | 66,51 % | 6 |
| LVMH Moët Hennessy - Louis Vuitton, Société Européenne | -16,43 % | -40,71 % | 37,42 % | 12 |
| Microsoft Corporation | -2,44 % | +23,93 % | 39,40 % | 14 |
| NVIDIA Corporation | +20,88 % | +57,20 % | 28,31 % | 10 |
| Palantir Technologies Inc. | -0,88 % | +128,02 % | 43,48 % | 10 |
| Hermès International Société en commandite par actions | -36,73 % | -37,17 % | 27,15 % | 14 |
| Safran SA | -3,13 % | +49,00 % | 46,36 % | 16 |
| Solana | -7,33 % | -28,93 % | 34,60 % | 14 |
| Schneider Electric S.E. | -18,11 % | +2,95 % | 35,60 % | 16 |
| Technip Energies N.V. | -0,93 % | +28,53 % | 41,36 % | 10 |
| Tesla, Inc. | -54,15 % | +107,44 % | 32,62 % | 16 |
| TotalEnergies SE | -24,29 % | +42,62 % | 39,40 % | 20 |
| Monero | +111,68 % | +196,55 % | 48,18 % | 16 |

## Vérifications et conséquence pour l’application

Zéro erreur de simulation et zéro recalibration abandonnée. Les rendements nets de la conservation correspondent à ceux de l’expérience archivée sur les mêmes prix. Une reconstruction indépendante par liquidités et quantités détenues, depuis les prix et ordres, retrouve les **298 courbes et expositions** ; écart maximal de capital 1.42e-14 pour une base initiale 1.

Le moteur numérique actif conserve ses règles antérieures : **aucune amélioration financière n’est annoncée**. En revanche, le résultat signale désormais une sortie structurellement impossible et l’exposition quasi permanente ; le cache est versionné à nouveau pour ajouter ces diagnostics. L’interface montre l’écart net en points et une chronologie séparant le régime dominant de la position réellement détenue après clôture. Une moyenne d’état négative ne signifie pas que la règle de continuation vende, et une probabilité d’état favorable n’est pas une probabilité de gain.

Les seuils de 95 % pour le diagnostic d’exposition et de 80 % pour l’évaluation ne changent aucun ordre. Il n’y a aucun objectif forcé de transactions.

Vérifications logicielles : 105 tests backend réussis, dont les invariants de causalité à travers les recalibrations, le réordonnancement des états, la conservation du dernier modèle après échec et la réentrée sans verrou. 22 tests navigateur de l’espace de travail réussis sur ordinateur et mobile, dont le diagnostic d’une exposition presque permanente et la séparation des régimes et positions. Build de production, Ruff et vérification des espaces du diff réussis. Les tests navigateur utilisent le binaire Chromium déjà disponible via `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` ; le binaire attendu par défaut par la version installée de Playwright est absent. Ces tests ne démontrent pas la rentabilité.

Données et résultats complets : `data/backtests/hmm-adaptive/`, ignoré par Git. `plan.json` et `sources/` conservent le code exact de l’expérience, y compris le script avant sa correction ultérieure de liaison de variable signalée par Ruff et l’ajout de l’archivage automatique des sources. Ces modifications du lanceur ne changent pas les calculs ; le résumé a été recalculé à l’identique. `comparison.csv` permet les comparaisons actif par actif. Le moteur candidat se trouve dans `backend/investor/analysis/adaptive.py`, sans connexion à l’API.

Les paramètres sont fixés pour cette expérience, sans grille de recherche sur les performances de test. **Ce nouvel essai intervient après les cinq variantes précédentes et après lecture de trois cas de contrôle** ; l’historique est réutilisé, les fenêtres se recouvrent et l’univers actuel comporte un biais de survivance. Les observations lissées se chevauchent et les probabilités ne sont pas validées comme probabilités de prévision. Ni l’absence de surapprentissage ni la rentabilité future ne sont établies. Ces résultats négatifs ne justifient pas d’ajuster encore les paramètres jusqu’à embellir les mêmes tests.

Aucun push GitHub.
