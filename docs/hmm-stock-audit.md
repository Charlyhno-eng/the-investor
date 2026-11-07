# Audit économique du HMM sur toutes les actions — 6 novembre 2026

**Critère demandé non atteint. Modèle actif rejeté financièrement, prototype également rejeté. Aucun prototype n’a été activé.**

L’audit précédent à 10 pb sur huit actifs ne vérifiait pas le comportement aux frais par défaut de l’interface. L’audit présent couvre les **19 actions du catalogue**, sans filtrage des perdants, à **50 pb = 0,5 % par achat et par vente**. La réussite technique des tests ne vaut pas réussite financière.

## Critère d’acceptation

Pour chaque action, rendement total net de stratégie strictement supérieur à celui du même actif en achat-conservation, sur la même fenêtre et avec les mêmes frais. Une égalité n’est pas une victoire. Il faut **au moins 10 actions sur 19**, sans erreur, omission ou doublon. Le dénominateur vient du catalogue SQLite, pas des seuls résultats réussis. Les métriques de risque ne remplacent pas ce critère de rendement.

- Moteur actif : **3/19** gagnants, 16 perdants, 17 simulations sans aucun ordre. **ÉCHEC**.
- Prototype choisi avant la vérification récente : **5/19** gagnants, 14 perdants, 0 simulation sans ordre. **ÉCHEC**.
- Résultat machine : [hmm-stock-acceptance.json](hmm-stock-acceptance.json), avec empreintes du code. Le contrôle `--assert-majority` sort volontairement avec le code **1**.

## Reproduction de la capture GTT

Du 28 juin 2024 au 6 novembre 2026, après entraînement du 24 décembre 2018 au 27 juin 2024 : **0 % contre +60,19 %**, aucun ordre. La meilleure prévision logarithmique à cinq observations parmi tous les états vaut **+0,35 %**, tandis que le seuil de frais aller-retour vaut **+1,00 %**. Aucun mélange de probabilités ne peut atteindre ce seuil. La règle bloque donc les achats, indépendamment de la qualité de classification des régimes.

Le diagnostic `entry_reachable` expose désormais cette impossibilité. L’interface affiche « Aucun achat possible » et l’échec face à la conservation ; elle ne parle plus d’impossibilité de vente pour une simulation restée entièrement en liquidités. Les calculs de performance du moteur actif ne sont pas modifiés pour rendre les résultats plus favorables.

Le prototype entre bien sur GTT : **+55,81 %**, deux ordres et environ 89,90 % d’exposition. Cela reste inférieur aux **+60,19 %** de la conservation : supprimer le blocage ne suffit pas.

## Comparaison action par action aux périodes par défaut

Les périodes reproduisent exactement le sélecteur de l’interface : au plus 2 016 cours, séparation 70/30. Les historiques plus courts de Palantir et Technip Energies sont conservés. Les dates effectives, métriques, expositions et empreintes des données figurent dans [le CSV du moteur actif](hmm-stock-audit.csv) et [le CSV complet du prototype](hmm-stock-candidate-evaluation.csv).

| Action | Conservation nette | Moteur actif net | Ordres actifs | Prototype net | Ordres prototype |
| --- | ---: | ---: | ---: | ---: | ---: |
| Apple Inc. | +64,88 % | +0,00 % | 0 | +60,30 % | 2 |
| L'Air Liquide S.A. | +29,99 % | +0,00 % | 0 | +31,76 % | 2 |
| Airbus SE | +54,87 % | +0,00 % | 0 | +34,35 % | 6 |
| ASML Holding N.V. | +35,32 % | +0,00 % | 0 | +34,73 % | 2 |
| BE Semiconductor Industries N.V. | -6,16 % | +0,00 % | 0 | -6,34 % | 2 |
| BNP Paribas SA | +77,56 % | +0,00 % | 0 | +48,88 % | 2 |
| Vinci SA | +22,20 % | +0,00 % | 0 | +11,02 % | 2 |
| Engie SA | +103,73 % | +0,00 % | 0 | +44,93 % | 16 |
| Gaztransport & Technigaz SA | +60,19 % | +0,00 % | 0 | +55,81 % | 2 |
| LVMH Moët Hennessy - Louis Vuitton, Société Européenne | -40,71 % | +0,00 % | 0 | -35,91 % | 2 |
| Microsoft Corporation | +23,93 % | +0,00 % | 0 | +21,57 % | 2 |
| NVIDIA Corporation | +57,20 % | +45,11 % | 2 | +51,81 % | 2 |
| Palantir Technologies Inc. | +128,02 % | +57,45 % | 2 | +46,63 % | 10 |
| Hermès International Société en commandite par actions | -37,17 % | +0,00 % | 0 | -36,21 % | 2 |
| Safran SA | +49,00 % | +0,00 % | 0 | +10,69 % | 14 |
| Schneider Electric S.E. | +2,95 % | +0,00 % | 0 | +3,86 % | 2 |
| Technip Energies N.V. | +28,53 % | +0,00 % | 0 | +27,32 % | 2 |
| Tesla, Inc. | +107,44 % | +0,00 % | 0 | +40,75 % | 2 |
| TotalEnergies SE | +42,62 % | +0,00 % | 0 | +75,99 % | 2 |

## Recherche séparée de l’évaluation récente

**16 variantes, 71 fenêtres de développement chacune : 1 136 simulations**, portant uniquement sur les années de test 2020, 2021, 2022 et 2023, avec cinq années antérieures pour l’entraînement lorsque disponibles. Les cinq couples actif/année sans historique suffisant sont Palantir 2020–2021 et Technip Energies 2020–2022. Les 19 actions sont toutes évaluées aux périodes finales par défaut ; aucune n’en est exclue.

Huit politiques conservent le HMM de rendements : prévisions sur 21/63/126 observations ou décisions par probabilités de régime, avec hystérésis et révision quotidienne, toutes les cinq observations ou toutes les 21 observations. Huit autres variantes ajustent un HMM de tendance/volatilité sur des observations causales et apprennent les rendements futurs associés aux probabilités filtrées **sur des résultats d’entraînement déjà réalisés**. Un embargo du nombre d’observations prévu plus une observation exclut les cibles qui déborderaient de l’entraînement. Horizon de tendance 21/63, horizon prévu 21/63, seuil nul ou frais aller-retour ; trois initialisations, révision toutes les cinq observations. Ces variantes sont des expériences, pas des méthodes validées.

Le prototype `predictive_w63_h21_cost1` est choisi par proportion de surperformances en développement, puis écart médian pour départager les égalités. Il ne dépasse déjà pas **20/71** en développement. Il est figé avant lecture des résultats de la vérification récente, puis néanmoins évalué intégralement pour documenter l’échec. Aucun paramètre n’est changé après cette vérification.

| Variante de développement | Bat la conservation | Écart médian net |
| --- | ---: | ---: |
| `forecast_126` | 14/71 | -1,80 % point(s) |
| `forecast_21` | 14/71 | -2,22 % point(s) |
| `forecast_63` | 14/71 | -1,86 % point(s) |
| `regime_daily_80` | 18/71 | -3,75 % point(s) |
| `regime_monthly_80` | 14/71 | -3,15 % point(s) |
| `regime_monthly_95` | 15/71 | -2,85 % point(s) |
| `regime_weekly_80` | 20/71 | -3,15 % point(s) |
| `regime_weekly_95` | 18/71 | -3,15 % point(s) |
| `predictive_w21_h21_cost0` | 15/71 | -2,22 % point(s) |
| `predictive_w21_h21_cost1` | 14/71 | -1,86 % point(s) |
| `predictive_w21_h63_cost0` | 14/71 | -2,14 % point(s) |
| `predictive_w21_h63_cost1` | 14/71 | -1,91 % point(s) |
| `predictive_w63_h21_cost0` | 15/71 | -2,65 % point(s) |
| `predictive_w63_h21_cost1` | 20/71 | -2,24 % point(s) |
| `predictive_w63_h63_cost0` | 19/71 | -1,78 % point(s) |
| `predictive_w63_h63_cost1` | 18/71 | -1,80 % point(s) |

Les [1 136 lignes de développement](hmm-stock-development.csv) sont conservées, pas seulement celles du prototype choisi. Les commandes et sorties détaillées sont disponibles sous `data/backtests/hmm-stock-audit/` dans l’espace de travail.

## Vérification annuelle du prototype figé

En plus des 19 périodes par défaut, tests annuels 2024, 2025 et 2026 sur toutes les actions : **57 simulations**, sans erreur ni exclusion. L’année 2026 est arrêtée au dernier cours disponible du 6 novembre. Les défauts et les fenêtres annuelles se chevauchent et ne sont pas indépendants.

| Période | Bat la conservation | Écart médian net |
| --- | ---: | ---: |
| annual_2024 | 12/19 | +0,65 % point(s) |
| annual_2025 | 6/19 | -1,98 % point(s) |
| annual_2026 | 7/19 | -1,27 % point(s) |

L’année 2024 atteint la majorité, les années 2025 et 2026 ainsi que les périodes par défaut échouent. Choisir uniquement 2024 masquerait ces échecs. Ces historiques ont déjà été étudiés dans ce dépôt : cette séparation des nouveaux réglages ne crée pas rétroactivement un échantillon totalement vierge. Le catalogue actuel comporte aussi un biais de sélection/survie.

## Exécution et limites

Modèles sans levier et sans vente à découvert. Signal à la clôture, exécution à la clôture suivante, rendement gagné à partir de la clôture encore suivante. Liquidation finale et frais symétriques inclus, liquidités non rémunérées, sans glissement ni impôts. Le benchmark achète à la clôture de référence précédant le premier rendement de test et vend à la dernière clôture. Cette convention reste identique à celle de la capture ; elle n’a pas été changée pour faire passer le contrôle. Aucun cours de test ne sert à entraîner les paramètres ou les cibles du prototype.

La recherche de nombreuses variantes peut produire des succès historiques fortuits ; [Bailey et al., probabilité de surajustement des backtests](https://escholarship.org/uc/item/4w1110bb) en décrit le problème. Ici les résultats échouent déjà aux critères demandés. Ils ne permettent pas de déclarer la stratégie corrigée ou surperformante.

## Reproduire

Depuis la racine du dépôt :

```sh
PYTHONPATH=backend .venv/bin/python scripts/audit_hmm_stocks.py --output /tmp/hmm-all-stocks.json --assert-majority
PYTHONPATH=backend .venv/bin/python scripts/research_hmm_stock_policies.py --output /tmp/hmm-development-policy.json
PYTHONPATH=backend .venv/bin/python scripts/research_hmm_predictive.py --output /tmp/hmm-development-predictive.json
PYTHONPATH=backend .venv/bin/python scripts/evaluate_hmm_predictive.py --policy-development /tmp/hmm-development-policy.json --predictive-development /tmp/hmm-development-predictive.json --output /tmp/hmm-candidate.json
PYTHONPATH=backend .venv/bin/python scripts/report_hmm_stock_audit.py --assert-majority
```

Le dernier script lit les quatre fichiers JSON sous `data/backtests/hmm-stock-audit/` (option `--input` pour un autre dossier) et reconstruit les CSV et la décision d’acceptation. Le prototype rejeté reste hors API. Le moteur actif conserve son calcul pour rendre son échec reproductible ; ses diagnostics et l’avertissement expérimental sont corrigés. **L’objectif de surperformance sur la majorité des actions reste non atteint.**
