# Stratégies publiées S&P 500, sans levier — 15 novembre 2026

**Résultat : aucun des 18 candidats ne satisfait le compromis fixé ; v5 reste active.** La réduction supplémentaire du drawdown observée avec certaines combinaisons coûte du rendement. Aucun remplacement de production ni modification de la base utilisateur.

## Recherche internet et périmètre

- [Faber, règle de timing mensuel](https://mebfaber.com/timing-model/) : détenir au-dessus de la moyenne mobile des dix clôtures mensuelles, sinon liquidités. Son auteur précise que le modèle publié décide en fin de mois, et signale le risque des allers-retours. Ici, application au seul PSP5 EUR, exécution ultérieure, frais explicites et liquidités non rémunérées : comparaison adaptée, pas reproduction exacte de son portefeuille multi-actifs.
- [Antonacci, FAQ du momentum absolu](https://www.optimalmomentum.com/faq/) : comparaison de la performance au rendement sans risque ; le mois récent reste inclus pour les indices. Nous adaptons à un rendement de cash nul et au seul ETF sur douze mois. Ni rotation internationale GEM ni poche obligataire. Cela diffère du score momentum natif de la campagne précédente, qui excluait le mois récent.
- [Keller–Keuning, Protective Asset Allocation](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2759734) : recherche consultée, mais la largeur de marché multi-actifs et le refuge obligataire ne sont pas reproduits. Réduire ce système à un seul ETF ne permettrait pas de revendiquer les résultats publiés.
- [Moreira–Muir, gestion par volatilité](https://www.nber.org/papers/w22208) : recherche consultée, variante identique déjà écartée dans le projet, pas de réintroduction. Les stratégies académiques utilisant des positions courtes ou une exposition supérieure à 100 % ne sont pas reproduites.

Six règles fixes : MM10, momentum absolu12 et quatre adaptations de recherche : votes équipondérés MM6/8/10/12, accord MM10 ET momentum12, hystérésis MM10 ±1 %, rendement moyen 1/3/6/12 mois positif. Ces quatre adaptations ne sont pas attribuées aux auteurs comme des stratégies publiées. Chacune est testée seule puis sur 35 % ou 65 % du capital, le complément restant en v4 : **18 configurations**. Les témoins simples peuvent recouper des recherches passées ; ils servent à la comparaison et ne constituent pas des découvertes nouvelles.

## Protocole fixé avant calcul

Le script écrit le protocole dans son rapport avant les résultats. Aucune sélection ni modification des paramètres après examen : tous les candidats passent les mêmes évaluations. Sur chaque historique 3/5/10 ans et chaque moyenne synthétique 5/10 ans : CAGR au moins passif moins 2 points et v5 moins 1 point ; perte maximale au moins 25 % plus faible que le passif et 10 % plus faible que v5 ; volatilité au plus celle du passif. Au moins 75 % des 24 fenêtres cinq ans à départ trimestriel doivent satisfaire les mêmes critères ; tous les stress 3/5/10 ans aussi. Un succès ne déclencherait pas une adoption automatique.

Copie SQLite privée, PSP5 ajusté en EUR du 2014-05-20 au 2026-11-13, 3197 observations. 10 000 €, frais 0,12 % par achat/vente, titres entiers, cash à 0 %, aucune liquidation fictive finale. Trois budgets réels indépendants pour les combinaisons, aucun transfert entre poches. Clôtures mensuelles terminées uniquement ; signal exécuté à la première clôture observée du mois suivant. Initialisation à partir du dernier mois terminé, achat après le début du test. Ajustement mensuel et bande de 5 points. L’hystérésis rejoue seulement les états antérieurs, sans profits antérieurs.

300 parcours cinq ans, graines 1210000–1210299 ; 100 dix ans, 1220000–1220099. Même générateur que l’application, marchés identiques entre candidats, résultats individuels conservés. Bootstrap apparié à 95 % sur 2 000 rééchantillonnages, descriptif et sans correction pour les comparaisons multiples. Frais doublés et retard supplémentaire d’une séance.

## Historiques réels

Chaque cellule présente **CAGR / drawdown maximal**, frais inclus. Les périodes se terminent au 13 novembre 2026.

| Règle | 3 ans | 5 ans | 10 ans |
|---|---:|---:|---:|
| PSP5 passif | 19,08 % / -23,17 % | 11,60 % / -23,18 % | 14,49 % / -33,67 % |
| Régression v5 actuelle | 17,14 % / -12,38 % | 12,06 % / -11,73 % | 13,04 % / -20,45 % |
| Moyenne mobile 10 mois | 14,27 % / -13,36 % | 6,32 % / -18,97 % | 9,81 % / -18,97 % |
| Moyenne mobile 10 mois ; 65 % v4 | 15,44 % / -8,10 % | 10,38 % / -9,13 % | 11,41 % / -12,13 % |
| Moyenne mobile 10 mois ; 35 % v4 | 14,85 % / -10,06 % | 8,56 % / -13,25 % | 10,67 % / -14,07 % |
| Momentum absolu 12 mois | 19,08 % / -23,17 % | 11,44 % / -23,19 % | 11,64 % / -33,68 % |
| Momentum absolu 12 mois ; 65 % v4 | 17,14 % / -12,38 % | 12,03 % / -11,75 % | 12,00 % / -19,76 % |
| Momentum absolu 12 mois ; 35 % v4 | 17,98 % / -17,45 % | 11,72 % / -16,85 % | 11,82 % / -26,57 % |
| Votes MM 6/8/10/12 mois | 15,02 % / -13,34 % | 6,45 % / -20,09 % | 9,91 % / -20,10 % |
| Votes MM 6/8/10/12 mois ; 65 % v4 | 15,70 % / -8,08 % | 10,42 % / -9,76 % | 11,43 % / -12,14 % |
| Votes MM 6/8/10/12 mois ; 35 % v4 | 15,36 % / -10,07 % | 8,64 % / -13,97 % | 10,74 % / -14,38 % |
| MM10 et momentum12 | 14,27 % / -13,36 % | 6,53 % / -15,95 % | 9,92 % / -17,23 % |
| MM10 et momentum12 ; 65 % v4 | 15,44 % / -8,10 % | 10,44 % / -8,83 % | 11,44 % / -12,13 % |
| MM10 et momentum12 ; 35 % v4 | 14,85 % / -10,06 % | 8,70 % / -12,07 % | 10,74 % / -14,07 % |
| MM10, bande ±1 % | 14,27 % / -13,36 % | 6,53 % / -15,95 % | 9,53 % / -17,24 % |
| MM10, bande ±1 % ; 65 % v4 | 15,44 % / -8,10 % | 10,44 % / -8,83 % | 11,32 % / -12,12 % |
| MM10, bande ±1 % ; 35 % v4 | 14,85 % / -10,06 % | 8,70 % / -12,07 % | 10,50 % / -14,10 % |
| Momentum moyen 1/3/6/12 mois | 18,51 % / -13,36 % | 7,48 % / -23,26 % | 11,07 % / -23,27 % |
| Momentum moyen 1/3/6/12 mois ; 65 % v4 | 16,91 % / -8,10 % | 10,74 % / -10,68 % | 11,80 % / -12,14 % |
| Momentum moyen 1/3/6/12 mois ; 35 % v4 | 17,63 % / -10,06 % | 9,28 % / -16,04 % | 11,44 % / -16,69 % |

Le diagnostic MM10 ET momentum12 sur 35 % et v4 sur 65 % réduit la perte maximale cinq ans de 11,73 % à 8,83 %, mais retire 1,62 point de CAGR ; dix ans, le CAGR passe de 13,04 % à 11,44 %. Il ne satisfait donc pas la conservation de rendement fixée. Sur trois ans, le momentum rapide associé à v4 est plus proche en rendement, mais ne conserve pas cet avantage sur cinq/dix ans. Le momentum12 seul n’évite pas le drawdown cinq ans du passif : rendement proche ne signifie pas protection suffisante.

## Parcours simulés

Moyennes de CAGR / drawdown maximal ; aucune trajectoire éliminée.

| Règle | 300 parcours 5 ans | 100 parcours 10 ans | Fenêtres réelles conformes /24 |
|---|---:|---:|---:|
| PSP5 passif | 15,47 % / -24,69 % | 14,96 % / -30,85 % | — |
| Régression v5 actuelle | 12,55 % / -20,50 % | 12,44 % / -25,38 % | — |
| Moyenne mobile 10 mois | 10,64 % / -22,99 % | 9,64 % / -30,40 % | 0 |
| Moyenne mobile 10 mois ; 65 % v4 | 10,85 % / -18,28 % | 10,51 % / -22,88 % | 1 |
| Moyenne mobile 10 mois ; 35 % v4 | 10,77 % / -19,33 % | 10,15 % / -24,96 % | 0 |
| Momentum absolu 12 mois | 12,32 % / -24,29 % | 11,69 % / -29,87 % | 0 |
| Momentum absolu 12 mois ; 65 % v4 | 11,45 % / -19,31 % | 11,21 % / -23,35 % | 0 |
| Momentum absolu 12 mois ; 35 % v4 | 11,87 % / -20,88 % | 11,45 % / -25,30 % | 0 |
| Votes MM 6/8/10/12 mois | 10,36 % / -22,03 % | 9,49 % / -28,61 % | 0 |
| Votes MM 6/8/10/12 mois ; 65 % v4 | 10,74 % / -18,14 % | 10,44 % / -22,34 % | 0 |
| Votes MM 6/8/10/12 mois ; 35 % v4 | 10,57 % / -18,89 % | 10,03 % / -23,89 % | 0 |
| MM10 et momentum12 | 9,98 % / -23,14 % | 9,32 % / -29,49 % | 0 |
| MM10 et momentum12 ; 65 % v4 | 10,63 % / -18,13 % | 10,41 % / -22,32 % | 1 |
| MM10 et momentum12 ; 35 % v4 | 10,36 % / -19,10 % | 9,95 % / -23,86 % | 0 |
| MM10, bande ±1 % | 10,83 % / -23,23 % | 9,82 % / -29,69 % | 0 |
| MM10, bande ±1 % ; 65 % v4 | 10,92 % / -18,44 % | 10,57 % / -22,46 % | 1 |
| MM10, bande ±1 % ; 35 % v4 | 10,89 % / -19,57 % | 10,26 % / -24,25 % | 0 |
| Momentum moyen 1/3/6/12 mois | 11,30 % / -23,41 % | 10,33 % / -30,08 % | 0 |
| Momentum moyen 1/3/6/12 mois ; 65 % v4 | 11,09 % / -18,65 % | 10,73 % / -22,88 % | 1 |
| Momentum moyen 1/3/6/12 mois ; 35 % v4 | 11,20 % / -19,89 % | 10,57 % / -24,90 % | 0 |

Pour le diagnostic MM10 ET momentum12 (35 %) + v4 (65 %), sur cinq ans : seuil des 5 % de pertes maximales les plus profondes **30,34 %**, contre **33,64 %** v5 ; drawdown supérieur à 30 % sur **16/300** parcours, contre **33/300** v5 et **88/300** passif. Sur dix ans : 15/100 contre 27/100 v5. Ces comptes décrivent ce modèle historique, pas des probabilités futures.

Intervalles descriptifs à 95 % de l’écart au v5 pour ce diagnostic : CAGR cinq ans **−2,04 à −1,80 points**, amélioration du drawdown **+2,07 à +2,67 points** ; dix ans, CAGR **−2,17 à −1,89 points**, amélioration du drawdown **+2,50 à +3,63 points**. La perte de rendement ne disparaît pas dans ces tirages. Aucun des 18 candidats ne passe tous les critères ; au mieux **1/24** fenêtres réelles respecte les exigences combinées.

## Vérification et reproduction

57 tests ciblés réussis (nouvelle étude, moteur drawdown, signaux sigma/momentum, régression ETF), dont cinq nouveaux contrôles : clôtures mensuelles exactes, invariance aux cours futurs pour les deux retards, budget indépendant/titres entiers/frais après un écart de cours, et impossibilité pour les prix du nouveau mois de modifier le signal précédent. Ruff backend/scripts et git diff --check réussis. Chaque premier parcours synthétique de chaque horizon vérifie passif et v5 contre le moteur de production à 1e−9. Ces contrôles valident le logiciel, pas une rentabilité future.

```sh
PYTHONPATH=backend:scripts .venv/bin/python scripts/study_sp500_published_rules.py
.venv/bin/python -m pytest backend/tests/unit/test_sp500_published_rules.py backend/tests/unit/test_sp500_drawdown_frontier.py backend/tests/unit/test_sp500_sigma_momentum.py backend/tests/unit/test_etf_switch.py -q
```

Résultats complets : `data/backtests/sp500-published-rules.json`, avec protocole, empreinte SQLite, configurations, chaque marché, frais, ratios, queues de distribution, stress et intervalles. Script : `scripts/study_sp500_published_rules.py`.

## Limites et décision

Historique ETF depuis 2014 : ni bulle internet ni crise 2008 testées ici. Aucun indice USD substitué au PSP5 EUR. Les 24 fenêtres se chevauchent et ont déjà été étudiées ; les nouvelles graines réutilisent le même historique. Le calendrier synthétique en jours de semaine et les métriques en 252 séances restent ceux de l’application. Fiscalité omise et cash supposé non rémunéré. Les règles mensuelles peuvent subir une baisse rapide avant la sortie et manquer le rebond. Les stratégies de sélection d’actions individuelles du S&P 500 ne sont pas couvertes par ce protocole ETF/cash.

**Décision : recherche négative pour le compromis fixé, v5 conservée.** Les combinaisons plus défensives restent des diagnostics, sans adoption implicite ni plafond garanti de pertes.
