# HMM minimal à deux états — 6 novembre 2026

**Mise à jour : cette règle est maintenant raccordée à l’API et à l’interface. Voir la [correction du moteur actif et l’audit des 24 actions](hmm-live.md). Le rapport ci-dessous conserve les résultats historiques sur 19 actions.**

Cette expérience répond exactement à la demande « haussier ou autre », sans la sélection de un à trois états et sans les règles de rentabilité des versions précédentes. **Elle ne bat la conservation que sur 1 action sur 19 aux frais de l’interface lors de cette première évaluation.**

## Règle fixée avant le test

- Un seul observable : rendement logarithmique quotidien terminé.
- `GaussianHMM(n_components=2, covariance_type="diag")` ; paramètres estimés uniquement sur l’entraînement, puis figés. Normalisation apprise sur l’entraînement.
- Trois initialisations 17/41/83, au plus 500 itérations, choix par vraisemblance d’entraînement uniquement. Aucune sélection sur les performances de test.
- L’état dont la moyenne entraînée est la plus élevée est nommé « haussier » ; l’autre « autre ». Les numéros des états n’ont pas de sens fixe.
- Investi lorsque l’état « haussier » est le plus probable selon le filtre causal ; en liquidités sinon. Aucun indicateur, hystérésis, stop, quota, horizon de gain ou seuil de frais.
- Signal à la clôture t, exécution à la clôture t+1 ; aucun gain attribué avant l’exécution. Le signal précédant le test peut être exécuté à sa première clôture. Liquidation finale.
- Les mêmes positions et ordres sont évalués sans frais puis avec 0,5 % par achat et vente. Les frais ne bloquent aucun ordre. Conservation avec une entrée et une sortie, aux mêmes frais et selon les conventions des audits précédents.

Le nom « haussier » est relatif à la moyenne apprise, pas une contrainte imposée à l’apprentissage. Sur les 19 fenêtres par défaut, cette moyenne supérieure est toujours positive. Sur ASML, NVIDIA et Tesla, **les deux moyennes sont positives** : l’état « autre » ne signifie donc pas nécessairement une baisse. Aucun état n’est renommé en fonction de sa performance en test.

## Résultats complets

19 actions, périodes par défaut de l’interface, puis tests annuels 2024/2025/2026 ; chacun sans frais et avec 50 pb par ordre : **152 simulations, aucune exclusion ni erreur**. Les 76 paires ont été vérifiées : mêmes ordres et expositions ; capital net égal au capital sans frais multiplié par `(1 − 0,005)^nombre_d’ordres`. Même vérification avec deux ordres pour le benchmark.

| Période | Frais par ordre (pb) | Bat la conservation | Écart médian net | Ordres médians |
| --- | ---: | ---: | ---: | ---: |
| interface_default | 0 | 4/19 | -11,78 % points | 36 |
| interface_default | 50 | 1/19 | -30,88 % points | 36 |
| annual_2024 | 0 | 5/19 | -4,43 % points | 12 |
| annual_2024 | 50 | 2/19 | -11,56 % points | 12 |
| annual_2025 | 0 | 5/19 | -6,83 % points | 14 |
| annual_2025 | 50 | 1/19 | -15,14 % points | 14 |
| annual_2026 | 0 | 9/19 | -0,85 % points | 32 |
| annual_2026 | 50 | 3/19 | -13,59 % points | 32 |

Les années et les fenêtres par défaut se chevauchent. Les historiques ont déjà été examinés dans ce dépôt ; il s’agit d’une expérience historique supplémentaire, pas d’un nouvel échantillon totalement vierge. Aucun paramètre n’a été réglé après lecture des résultats.

## Le cas GTT de la capture

Même fenêtre du 28 juin 2024 au 6 novembre 2026 :

| Frais par ordre | HMM minimal | Conservation | Ordres HMM |
| --- | ---: | ---: | ---: |
| 0 % | +66,39 % | +61,80 % | 34 |
| 0,5 % | +40,32 % | +60,19 % | 34 |

L’exposition est de 95,36 %. Les deux moyennes logarithmiques entraînées valent environ −0,2802 % et +0,1242 % par séance. La version minimale prend bien des positions, contrairement à l’ancien seuil de gain. Mais les 34 frais successifs effacent son avantage brut sur GTT. Sur l’ensemble des actions, même sans frais, la majorité demandée n’est pas atteinte : 4/19.

## Chaque action aux frais de l’interface

| Action | HMM minimal net | Conservation nette | Écart | Ordres |
| --- | ---: | ---: | ---: | ---: |
| Apple Inc. | -4,23 % | +64,88 % | -69,12 % points | 40 |
| L'Air Liquide S.A. | +5,98 % | +29,99 % | -24,01 % points | 24 |
| Airbus SE | +23,98 % | +54,87 % | -30,88 % points | 34 |
| ASML Holding N.V. | -54,23 % | +35,32 % | -89,55 % points | 94 |
| BE Semiconductor Industries N.V. | -46,77 % | -6,16 % | -40,60 % points | 80 |
| BNP Paribas SA | +54,48 % | +77,56 % | -23,07 % points | 12 |
| Vinci SA | -0,01 % | +22,20 % | -22,21 % points | 22 |
| Engie SA | +67,15 % | +103,73 % | -36,58 % points | 32 |
| Gaztransport & Technigaz SA | +40,32 % | +60,19 % | -19,87 % points | 34 |
| LVMH Moët Hennessy - Louis Vuitton, Société Européenne | -61,59 % | -40,71 % | -20,87 % points | 128 |
| Microsoft Corporation | -0,12 % | +23,93 % | -24,05 % points | 36 |
| NVIDIA Corporation | +14,56 % | +57,20 % | -42,63 % points | 30 |
| Palantir Technologies Inc. | -10,75 % | +128,02 % | -138,77 % points | 38 |
| Hermès International Société en commandite par actions | -72,98 % | -37,17 % | -35,81 % points | 122 |
| Safran SA | +61,98 % | +49,00 % | +12,98 % points | 34 |
| Schneider Electric S.E. | -33,94 % | +2,95 % | -36,89 % points | 68 |
| Technip Energies N.V. | +2,31 % | +28,53 % | -26,21 % points | 36 |
| Tesla, Inc. | -20,99 % | +107,44 % | -128,43 % points | 74 |
| TotalEnergies SE | +37,31 % | +42,62 % | -5,30 % points | 14 |

[CSV des 152 simulations](hmm-basic-evaluation.csv). Les résultats complets, paramètres, moyennes, matrices et empreintes des données sont conservés dans `data/backtests/hmm-basic/results.json`.

## Reproduire

```sh
PYTHONPATH=backend .venv/bin/python scripts/backtest_hmm_basic.py --output /tmp/hmm-basic-two-states.json --assert-majority
```

Le script écrit aussi le CSV adjacent et retourne le code 1 si la majorité stricte aux frais de l’interface n’est pas atteinte. Le moteur minimal est dans `backend/investor/analysis/basic.py` et alimente désormais le moteur actif de l’API. Ses tests vérifient la récupération de régimes directionnels synthétiques, les dates d’exécution, les frais sans veto et l’indépendance aux numéros d’état.
