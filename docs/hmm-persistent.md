# Recherche HMM à régimes persistants — 6 novembre 2026

**Des améliorations existent par rapport au HMM minimal, mais aucune majorité robuste n’est validée. Aucune variante n’est promue dans l’API.**

## Protocole

Deux états dans tous les HMM. Cinq représentations : rendement quotidien, blocs non chevauchants de 5 ou 21 séances, tendance normalisée et volatilité sur 21 ou 63 séances. Les observations sont disponibles seulement une fois leur fenêtre terminée. Trois règles : état dominant ; hystérésis (entrée à 70 %, sortie sous 30 %) ; défensive (sortie sous 20 % de probabilité haussière, seulement si l’autre état a une moyenne négative, réentrée à 50 %). Décision quotidienne ou toutes les 21 séances. **30 variantes HMM et deux témoins de tendance sans HMM**, tous évalués sur les mêmes actions.

Normalisation, moyennes et paramètres appris sur l’entraînement uniquement ; trois initialisations choisies par vraisemblance d’entraînement. Filtre causal, paramètres figés pendant le test. Signal à t, exécution à la clôture t+1. Frais de 0,5 % à chaque achat et vente, liquidation finale, aucun levier ni rendement des liquidités.

Sélection globale par taux de victoire puis écart médian sur 2020–2023 : `trend63_hysteresis_c1` (20/68 cas de développement gagnants). Sur 76 cas action/année possibles, 8 ont un historique insuffisant (Palantir et Technip Energies, quatre années chacun) ; ils sont conservés explicitement dans le fichier source. Les 68 cas admissibles sont identiques pour les 32 règles. Évaluation ultérieure : les 19 actions sur les fenêtres de l’interface et chacune des années 2024–2026, soit 2 432 simulations et aucune exclusion pour cette grille.

Une extension adaptative sélectionne, pour chaque action, la règle qui aurait dépassé la conservation d’au moins deux points nets sur les 252 dernières séances de son entraînement. Sinon elle conserve l’actif. Elle réestime ensuite le HMM sur tout l’entraînement. Cette extension est exploratoire ; elle ne choisit jamais sur la fenêtre de test correspondante. Les erreurs de validation pour historique insuffisant restent visibles, sans substitution silencieuse.

Ces historiques ont déjà été consultés dans plusieurs expériences. Les périodes annuelles et celles de l’interface se chevauchent. Les gagnants repérés après inspection sont **exploratoires**, sans valeur de validation indépendante.

## Vérification qui évite une fausse victoire

Le benchmark historique entre à la clôture précédant le premier rendement de test ; le HMM ne peut exécuter son premier ordre qu’à la première clôture de test. Une stratégie pratiquement toujours investie peut donc sembler meilleure simplement parce qu’elle évite la première séance. Nous conservons le benchmark historique pour comparer les anciens chiffres, et ajoutons un témoin passif qui entre à la **même première clôture exécutable** que le HMM. Même prix de sortie et deux frais dans les deux cas. Les égalités numériques (tolérance 10⁻¹⁰) ne comptent pas comme victoires.

## Fenêtres par défaut — 19 actions, frais inclus

La sélection globale est fixée sur le développement. Les deux autres variantes présentées sont des diagnostics exploratoires : ne pas les confondre avec une sélection validée.

| Règle | Victoires / benchmark historique | Victoires / entrée identique | Égalités / entrée identique | Écart médian historique (points) | Ordres médians |
| --- | ---: | ---: | ---: | ---: | ---: |
| basic | 1/19 | 1/19 | 0 | -30,88 | 36 |
| trend63_hysteresis_c1 | 4/19 | 4/19 | 0 | -40,52 | 8 |
| trend63_dominant_c21 | 6/19 | 6/19 | 0 | -26,22 | 6 |
| return5_hysteresis_c21 | 10/19 | 4/19 | 8 | +0,16 | 2 |
| return21_defensive_c1 | 10/19 | 1/19 | 15 | +0,30 | 2 |
| adaptive | 9/19 | 2/19 | 12 | -0,18 | 2 |
| control_momentum21 | 1/19 | 1/19 | 0 | -63,82 | 54 |
| control_momentum63 | 2/19 | 2/19 | 0 | -50,96 | 32 |

## Vérification annuelle

| Période | Règle | Victoires historiques | Victoires à entrée identique | Erreurs |
| --- | --- | ---: | ---: | ---: |
| annual_2024 | basic | 2/19 | 3/19 | 0 |
| annual_2024 | trend63_hysteresis_c1 | 3/19 | 3/19 | 0 |
| annual_2024 | trend63_dominant_c21 | 2/19 | 2/19 | 0 |
| annual_2024 | adaptive | 10/19 | 3/19 | 2 |
| annual_2025 | basic | 1/19 | 2/19 | 0 |
| annual_2025 | trend63_hysteresis_c1 | 5/19 | 3/19 | 0 |
| annual_2025 | trend63_dominant_c21 | 3/19 | 3/19 | 0 |
| annual_2025 | adaptive | 6/19 | 2/19 | 0 |
| annual_2026 | basic | 3/19 | 3/19 | 0 |
| annual_2026 | trend63_hysteresis_c1 | 6/19 | 7/19 | 0 |
| annual_2026 | trend63_dominant_c21 | 8/19 | 7/19 | 0 |
| annual_2026 | adaptive | 7/19 | 6/19 | 0 |

## Chaque action — diagnostic exploratoire à tendance de 63 séances

Ce diagnostic réduit la fréquence des décisions à 21 séances ; il a été repéré après lecture des résultats et n’est pas une preuve de généralisation.

| Action | Stratégie nette | Conservation historique | Conservation à entrée identique | Ordres |
| --- | ---: | ---: | ---: | ---: |
| Apple Inc. | +13,54 % | +64,88 % | +60,30 % | 6 |
| L'Air Liquide S.A. | +11,60 % | +29,99 % | +31,76 % | 8 |
| Airbus SE | -11,68 % | +54,87 % | +57,74 % | 8 |
| ASML Holding N.V. | +15,49 % | +35,32 % | +34,73 % | 4 |
| BE Semiconductor Industries N.V. | -32,38 % | -6,16 % | -6,34 % | 10 |
| BNP Paribas SA | +29,12 % | +77,56 % | +79,02 % | 6 |
| Vinci SA | +35,45 % | +22,20 % | +22,85 % | 8 |
| Engie SA | +118,14 % | +103,73 % | +104,95 % | 4 |
| Gaztransport & Technigaz SA | -3,56 % | +60,19 % | +63,61 % | 8 |
| LVMH Moët Hennessy - Louis Vuitton, Société Européenne | -29,04 % | -40,71 % | -40,56 % | 6 |
| Microsoft Corporation | -6,73 % | +23,93 % | +21,57 % | 8 |
| NVIDIA Corporation | -12,70 % | +57,20 % | +51,81 % | 6 |
| Palantir Technologies Inc. | +147,33 % | +128,02 % | +133,90 % | 4 |
| Hermès International Société en commandite par actions | -23,64 % | -37,17 % | -36,21 % | 6 |
| Safran SA | -12,30 % | +49,00 % | +49,30 % | 8 |
| Schneider Electric S.E. | +7,58 % | +2,95 % | +3,86 % | 6 |
| Technip Energies N.V. | +10,06 % | +28,53 % | +27,32 % | 4 |
| Tesla, Inc. | -13,02 % | +107,44 % | +99,69 % | 8 |
| TotalEnergies SE | +13,91 % | +42,62 % | +41,95 % | 8 |

## Tous les résultats

Le [CSV exhaustif](hmm-persistent.csv) contient toutes les règles sur chaque action et période, ainsi que le HMM minimal et la variante adaptative. Le [reçu JSON](hmm-persistent.json) contient le classement complet, les erreurs et les contrôles de majorité stricte. Les résultats sources, réglages et empreintes de code/données sont dans `data/backtests/hmm-persistent/`.

```sh
PYTHONPATH=backend .venv/bin/python scripts/research_hmm_persistent.py --output data/backtests/hmm-persistent/results.json
PYTHONPATH=backend .venv/bin/python scripts/evaluate_hmm_persistent_adaptive.py --source data/backtests/hmm-persistent/results.json --output data/backtests/hmm-persistent/adaptive.json
PYTHONPATH=backend .venv/bin/python scripts/report_hmm_persistent.py --source data/backtests/hmm-persistent/results.json --adaptive data/backtests/hmm-persistent/adaptive.json
```
