# Recherche HMM : détection, exposition et performance nette

> Archive : ce document concerne les versions ou recherches antérieures à la reconstruction du 6 novembre 2026. Le [moteur actif est décrit ici](hmm-rebuilt.md).

Suite de cette étude : [diagnostic de passivité et 298 nouveaux backtests](hmm-passivity.md). Le sixième candidat n’est pas activé ; les modifications de l’application ajoutent uniquement des diagnostics et la visibilité des régimes et positions.

6 novembre 2026. **L’objectif de surperformance dans l’extrême majorité des cas n’est pas atteint. Aucun candidat n’a été installé dans l’application.** Le moteur actif reste celui décrit dans [la revue précédente](hmm-directional.md), qui ne doit pas être présenté comme validé financièrement.

## Diagnostic du moteur actuel

Sur les 22 fenêtres par défaut, l’exposition médiane est de 98,6 %, 16 actifs dépassent 95 % d’exposition et le nombre médian d’ordres est deux. Le constat de l’utilisateur est confirmé : ce résultat ressemble souvent à une conservation presque permanente.

L’audit des paramètres révèle un problème plus précis que le nombre d’ordres : **pour 11 actifs sur 22, aucun état du modèle actuel ne peut déclencher une vente par sa règle de continuation**, même avec une probabilité de 100 % dans cet état. Le calcul de continuation reste au-dessus du seuil de sortie dans tous les états. Pour 3 actifs, toutes les moyennes d’état sont positives. Dans les autres cas concernés, la prévision après transitions et la règle de frais absorbent l’état défavorable. Avec des paramètres figés pendant le test, cette propriété persiste.

Les rendements seuls sont retenus pour 20 actifs sur 22. Séparer des distributions quotidiennes surtout par leur volatilité, puis obtenir une meilleure densité prédictive, ne démontre pas une capacité à anticiper les tendances. Il ne suffit donc pas de supprimer des frais ou de forcer davantage de transactions.

Audit numérique local : `data/backtests/hmm-literature/current_model_audit.json`, avec moyennes, transitions, valeurs de continuation et seuils par actif.

## Recherches et code effectivement examinés

- [Werge, 2021, sections 4 et 5](https://arxiv.org/html/2107.05535v1) : HMM à trois états sur moments exponentiellement lissés, normalisation sur entraînement, espérance d’un ratio rendement/risque par état. L’auteur examine notamment des spans 15, 30 et 60 et souligne que l’amélioration du risque ne garantit pas celle du rendement cumulé. Ici, span 30 fixé pour tous les actifs, moyenne et écart-type central exponentiels, sans recherche du meilleur span. C’est une adaptation, pas une reproduction de ses résultats.
- [Code Python de recalibration causale](https://github.com/mehmetoaltekin/hmm-regime-detection/blob/main/src/hmm_model.py) : lecture de l’ajustement multi-initialisations, de `predict_filtered_proba` et de `WalkForwardHMM`. Idée retenue : réajuster sur le passé, réinitialiser la croyance avec l’historique du nouveau modèle et ne jamais transporter aveuglément les indices des anciens états.
- [Exemple Python officiel QuantConnect](https://www.quantconnect.com/docs/v2/research-environment/machine-learning/popular-libraries/hmmlearn) et [notebook](https://github.com/QuantConnect/Research/blob/master/Research2Production/Python/07%20Hidden%20Markov%20Models.ipynb) : rendements quotidiens, deux états, réajustement. Les graphiques à base de `predict` ne constituent pas à eux seuls des signaux causaux de backtest. Nous testons aussi un filtre de risque fondé sur l’état de plus faible variance.
- [Autre moteur Python et son backtest](https://github.com/az9713/hmm-regime-trader) : son moteur utilise un filtre forward et des réentraînements. Dans le fichier `backtest/backtester.py` consulté, `_simulate_oos` multiplie les allocations par des rendements logarithmiques, puis compose `1 + strategy_returns`. Le traitement des coûts dans cette fonction ne justifie pas de reprendre ses chiffres affichés comme preuve de rentabilité.
- [Implémentation annonçant un CAGR de 24,14 %](https://github.com/ayaanzeeshan514/systematic-regime-switching-trading-strategy/blob/main/strategy.py) : le fichier consulté utilise `hmm.predict` sur des blocs de test, puis un filtre hybride calculé avec les prix du jour pour sélectionner les rendements de ce même jour. Il combine également Random Forest, règles techniques et positions courtes. Ces résultats ne démontrent donc pas la surperformance d’un HMM long/liquidités causal comparable à notre demande.
- [Allocation HMM publiée sur le Nifty](https://github.com/SahilMotyar/Dynamic-Regime-Allocation) : ce projet rapporte lui-même un rendement inférieur au benchmark, malgré une exposition réduite. Cela constitue une limite utile à vérifier, pas une preuve universelle d’échec ou de réussite des HMM.

La [documentation hmmlearn](https://hmmlearn.readthedocs.io/en/stable/tutorial.html) sert de référence pour l’API, les initialisations et les paramètres. Aucun code distant n’a été exécuté. Les sources consultées ont été lues ; les candidats locaux sont des implémentations indépendantes.

## Hypothèses testées

Trois premières variantes spécifiées ensemble : moments lissés avec modèle figé, mêmes moments avec réentraînement, puis mêmes réentraînements avec décision tenant compte des frais. Trois états, covariance complète, initialisations 17/41/83 départagées par vraisemblance d’entraînement, 29 observations de mise en place. Normalisation et estimation utilisent uniquement les données disponibles avant chaque segment.

Le signal PESR pondère les ratios par état par les probabilités filtrées et deux transitions, pour respecter le délai d’exécution. Le modèle avec frais reprend l’approximation de continuation existante, appliquée cette fois aux moyennes de rendement lissé. Les deux ne constituent pas des espérances de rendement garanties calibrées.

Les réentraînements surviennent toutes les 63 observations, sur au plus 1 260 observations précédentes. Ce calendrier de calcul ne limite pas les transactions : un nouveau signal est évalué chaque jour. La première calibration respecte la période d’entraînement demandée ; les suivantes apprennent au fil du passé déjà observé. Aucun ancien signal n’est réécrit.

Deux variantes supplémentaires évaluent le filtre de volatilité classique : deux états sur rendement quotidien, investissement lorsque l’état de plus faible variance est le plus probable, sinon liquidités ; paramètres figés ou mêmes réentraînements. Le seuil 0,5 correspond au choix entre deux états, sans optimisation d’un seuil de trading. Les frais sont appliqués à chaque ordre. **Cette seconde expérience a été définie après lecture des résultats de la première**, et ne constitue pas une confirmation indépendante.

Il n’y a ni quota de transactions, ni cible d’exposition imposée, ni stop, ni MACD, ni position courte, ni levier. Seuls les frais sont ceux demandés : **0,5 % par ordre pour les actions, 0,01 % pour les cryptos**, puis scénario doublé. Signal à la clôture t, exécution à la clôture t+1, premier rendement perçu à t+2. Liquidation finale et frais du benchmark inclus. Liquidités non rémunérées, glissement et fiscalité exclus.

## Protocole et verdict

22 actifs actuels, Cardano et XRP exclus ; 149 fenêtres admissibles : continu 2022–2025, années 2022 à 2026 séparées, fenêtres par défaut de l’interface. Les cinq fenêtres indisponibles d’Hyperliquid sont exclues explicitement. Les dates par défaut varient selon l’actif et ne constituent pas uniformément cinq ans de test.

**1788 comparaisons modèle/fenêtre/frais** : 298 références archivées du moteur actuel, 894 nouveaux calculs sur moments lissés et 596 nouveaux calculs du filtre de volatilité. 0 échec de simulation. Les comparaisons utilisent les mêmes prix et dates, avec vérification des empreintes des données et de l’égalité des performances du benchmark. Les plans et empreintes du code ont été écrits avant chaque série. 1 rafraîchissement du candidat lissé avec frais a échoué au scénario normal ; le dernier modèle utilisable a été conservé, et l’échec figure dans le journal.

Le critère d’acceptation interprète « extrême majorité » comme au moins 80 % de surperformances nettes, dans chaque famille de fenêtres et chaque scénario de frais, avec au plus 20 % d’expositions dégénérées (≥95 % en actif ou ≤5 % en actif), et zéro erreur. Ces seuils évaluent les résultats et ne modifient jamais les ordres. **Aucun candidat ne passe ce critère.**

## Fenêtres par défaut : performance face à la conservation

Conservation : rendement médian +32,65 %. Les écarts médians sont calculés actif par actif, avant la médiane : ils diffèrent généralement de la différence entre deux médianes.

| Modèle | Bat conservation | Gain net médian | Écart médian apparié | Exposition médiane | Ordres médians | Exposition ≥95 % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| HMM actuel | 7 / 22 | +27,33 % | -4,07 points | 98,6 % | 2 | 16 / 22 |
| Moments lissés, figé | 6 / 22 | +17,99 % | -16,98 points | 74,7 % | 13 | 3 / 22 |
| Moments lissés, réentraîné | 7 / 22 | +14,79 % | -9,97 points | 74,6 % | 16 | 0 / 22 |
| Moments lissés, réentraîné, frais | 10 / 22 | +22,03 % | -3,87 points | 74,6 % | 12 | 2 / 22 |
| Filtre volatilité, figé | 5 / 22 | +8,00 % | -23,09 points | 86,0 % | 36 | 5 / 22 |
| Filtre volatilité, réentraîné | 3 / 22 | +3,79 % | -29,51 points | 84,7 % | 54 | 2 / 22 |

Le candidat lissé réentraîné avec frais répond au problème de passivité, mais **ne démontre pas la surperformance demandée**. L’augmentation des sorties et réentrées ne suffit pas. Sur les rendements réellement accessibles deux observations après le signal, sa séparation moyenne favorable/défavorable est positive pour 9 actifs sur 22 seulement. C’est un diagnostic descriptif sur les tests réutilisés, sans preuve de calibration ou de causalité économique.

## Nombre d’actifs battant la conservation, par fenêtre

| Fenêtre | Actifs | Actuel | Lissé figé | Lissé réentraîné | Lissé réentraîné + frais | Volatilité figée | Volatilité réentraînée |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| continuous_2022_2025 | 21 | 4 | 5 | 3 | 3 | 2 | 2 |
| walk_2022 | 21 | 4 | 10 | 11 | 12 | 8 | 7 |
| walk_2023 | 21 | 3 | 1 | 3 | 3 | 2 | 4 |
| walk_2024 | 21 | 12 | 8 | 5 | 7 | 3 | 2 |
| walk_2025 | 21 | 5 | 6 | 5 | 5 | 2 | 2 |
| walk_2026 | 22 | 11 | 10 | 7 | 9 | 5 | 5 |
| interface_default | 22 | 7 | 6 | 7 | 10 | 5 | 3 |

Sur les 149 fenêtres, aux frais normaux : HMM actuel 46/149, Moments lissés, figé 46/149, Moments lissés, réentraîné 41/149, Moments lissés, réentraîné, frais 49/149, Filtre volatilité, figé 27/149, Filtre volatilité, réentraîné 25/149. Ces fenêtres se chevauchent : ce ne sont pas 149 expériences indépendantes.

## Détail par actif, candidat lissé avec frais

Cette variante est détaillée parce qu’elle est la plus directement comparable au moteur actuel tenant compte des coûts ; elle n’est pas déclarée gagnante ni choisie pour l’application sur la base de ces résultats.

| Actif | Conservation | Actuel | Lissé réentraîné + frais | Exposition actuel → candidat | Ordres actuel → candidat |
| --- | ---: | ---: | ---: | ---: | ---: |
| Apple Inc. | +64,88 % | +43,84 % | -0,45 % | 96,4 % → 75,0 % | 4 → 18 |
| L'Air Liquide S.A. | +29,99 % | +30,68 % | +19,87 % | 99,7 % → 96,2 % | 2 → 8 |
| Airbus SE | +54,87 % | +37,61 % | +47,86 % | 96,5 % → 83,8 % | 4 → 6 |
| ASML Holding N.V. | +35,32 % | +8,55 % | +0,05 % | 67,4 % → 53,6 % | 10 → 24 |
| BE Semiconductor Industries N.V. | -6,16 % | -5,86 % | +68,69 % | 99,7 % → 46,4 % | 2 → 22 |
| BNB | +21,75 % | +66,99 % | +51,33 % | 87,1 % → 66,1 % | 44 → 24 |
| Bitcoin | -9,15 % | -9,42 % | +24,19 % | 99,7 % → 26,3 % | 2 → 14 |
| Ethereum | +17,10 % | +3,50 % | +35,53 % | 61,8 % → 48,5 % | 104 → 22 |
| Gaztransport & Technigaz SA | +60,19 % | +72,73 % | +47,67 % | 96,7 % → 81,8 % | 4 → 8 |
| Hyperliquid | +101,93 % | +87,85 % | +17,53 % | 99,1 % → 45,8 % | 2 → 12 |
| LVMH Moët Hennessy - Louis Vuitton, Société Européenne | -40,71 % | -40,42 % | -29,41 % | 99,7 % → 33,9 % | 2 → 18 |
| Microsoft Corporation | +23,93 % | +21,43 % | +1,99 % | 99,7 % → 84,1 % | 2 → 8 |
| NVIDIA Corporation | +57,20 % | +46,64 % | +18,51 % | 99,7 % → 80,6 % | 2 → 8 |
| Palantir Technologies Inc. | +128,02 % | +57,45 % | +8,64 % | 95,9 % → 74,1 % | 2 → 12 |
| Hermès International Société en commandite par actions | -37,17 % | -35,05 % | -34,10 % | 99,7 % → 42,7 % | 2 → 16 |
| Safran SA | +49,00 % | +17,02 % | +33,85 % | 88,1 % → 77,2 % | 6 → 4 |
| Solana | -28,93 % | -32,52 % | -15,84 % | 99,7 % → 40,4 % | 2 → 16 |
| Schneider Electric S.E. | +2,95 % | -10,49 % | +9,94 % | 60,3 % → 64,1 % | 20 → 8 |
| Technip Energies N.V. | +28,53 % | +23,98 % | +27,79 % | 98,2 % → 85,7 % | 6 → 10 |
| Tesla, Inc. | +107,44 % | +94,02 % | +121,41 % | 99,7 % → 85,3 % | 2 → 12 |
| TotalEnergies SE | +42,62 % | +39,10 % | +26,43 % | 99,7 % → 96,0 % | 2 → 4 |
| Monero | +196,55 % | +352,56 % | +251,75 % | 79,1 % → 88,1 % | 40 → 16 |

## Frais doublés, fenêtres par défaut

| Modèle, frais doublés | Bat conservation | Gain médian | Exposition médiane | Ordres médians |
| --- | ---: | ---: | ---: | ---: |
| HMM actuel | 10 / 22 | +26,84 % | 99,6 % | 2 |
| Moments lissés, figé | 6 / 22 | +10,67 % | 74,7 % | 13 |
| Moments lissés, réentraîné | 7 / 22 | +10,00 % | 74,6 % | 16 |
| Moments lissés, réentraîné, frais | 10 / 22 | +19,09 % | 75,1 % | 11 |
| Filtre volatilité, figé | 4 / 22 | -4,07 % | 86,0 % | 36 |
| Filtre volatilité, réentraîné | 3 / 22 | -15,44 % | 84,7 % | 54 |

## Livrables et vérifications

Les scripts `scripts/hmm_regime_candidates.py`, `scripts/backtest_hmm_literature.py`, `scripts/backtest_hmm_volatility.py` et `scripts/report_hmm_literature.py` restent locaux. Les deux premiers moteurs de recherche sont séparés de l’API : **aucun changement du modèle actif de l’application dans cette recherche**.

Les données, plans, résultats complets, ordres, courbes, calendriers de calibration et tableaux CSV se trouvent dans `data/backtests/hmm-literature/` et `data/backtests/hmm-volatility/`, ignorés par Git. `comparison.csv` réunit les six modèles, toutes fenêtres et tous frais. Le générateur de ce rapport refuse une différence entre le code numérique courant et ses empreintes d’expérience. Les scripts de calcul refusent d’écraser une expérience déjà gelée.

Commandes :

```sh
PYTHONPATH=backend .venv/bin/python scripts/backtest_hmm_literature.py
PYTHONPATH=backend .venv/bin/python scripts/backtest_hmm_volatility.py
.venv/bin/python scripts/report_hmm_literature.py
.venv/bin/pytest -q
```

98 tests backend réussis, dont six nouveaux tests vérifiant les moments exponentiels contre des poids explicites, l’invariance des signaux passés après modification du futur y compris lors des recalibrations, la continuité après échec de calibration, la parité des ordres/coûts avec le moteur actif, l’exposition sur les barres réellement détenues et le rejet d’une stratégie presque toujours investie ou perdante par le critère d’évaluation. Les tests synthétiques ne démontrent pas la rentabilité sur les actifs réels. Une reconstruction indépendante par comptabilité de liquidités et de quantités de titres, à partir des seuls prix et ordres, concorde avec les 1 788 courbes et expositions : écart absolu maximal de capital inférieur à 5 × 10⁻¹⁴. Ruff et la vérification des espaces du diff passent. Le frontend n’a pas changé dans cette recherche.

Les données ont déjà servi à la recherche, les fenêtres se recouvrent et le catalogue actuel comporte un biais de survivance. Les covariables lissées chevauchent le passé et ne satisfont pas exactement l’indépendance conditionnelle supposée par le HMM. Les cinq nouvelles variantes s’ajoutent aux essais précédents : une sélection du meilleur résultat de cette recherche demanderait une nouvelle validation indépendante. **Aucune absence de surapprentissage n’est affirmée. Aucune version rentable dans l’extrême majorité des cas n’a été obtenue. Aucun push GitHub.**
