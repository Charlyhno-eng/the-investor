# Recherche élargie : rendement proche du marché, risque réduit — 15 novembre 2026

La demande autorise une hausse du risque face à v4 et des stratégies différentes. Priorité : améliorer son rendement, tout en restant moins risqué que Buy & Hold avec un retard de rendement limité. Le souhait d'améliorer Sharpe, Sortino et Calmar face au marché est mesuré séparément ; une réussite partielle ne sera pas présentée comme une réussite des trois ratios. Aucun changement de stratégie en production sans décision utilisateur.

## Protocole fixé avant les résultats

Le plan et les 62 configurations sont enregistrés avant calcul dans `data/backtests/sp500-broader-compromise.json`.

Compromis principal, sur chacun des horizons synthétiques : gain de CAGR moyen ≥1 point par an face à v4, retard ≤3 points face au Buy & Hold ; volatilité et amplitude moyenne de drawdown ≤90 % de Buy & Hold ; quantile 95 % des pertes maximales ≤Buy & Hold ; chacun des trois ratios moyens ≥97 % de celui de Buy & Hold. Objectif idéal supplémentaire : les trois ratios moyens strictement supérieurs à Buy & Hold et ≥55 % de victoires appariées pour chacun. La tolérance de 3 % sur les ratios appartient au compromis principal, pas à l'objectif idéal demandé initialement.

Filtre historique 3/5/10 ans : CAGR sur chaque période ≥v4−0,75 point et gain moyen sur les trois horizons ≥0,25 point ; volatilité ≤1,75×v4 et ≤90 % Buy & Hold ; amplitude DD ≤90 % Buy & Hold et ≤DD v4+12 points. Ces bornes permettent une hausse sensible du risque actuel, affichée explicitement. Au moins 75 % des 24 fenêtres cinq ans doivent préserver CAGR≥v4−0,75 point et les limites de risque. Frais doublés et retard d'exécution supplémentaire : maintien des limites de risque et gain historique moyen positif.

Toute l'histoire est déjà examinée : les historiques 3/5/10 ans servent **au filtrage**, pas de preuve indépendante. 100 marchés cinq ans, graines 120000–120099, pour sélectionner un candidat qualifié, classé par le plus faible avantage relatif parmi les trois ratios moyens, puis son CAGR. Gel avant 300 nouveaux marchés cinq ans (130000–130299) et 100 dix ans (140000–140099). Témoins figés supplémentaires : moitié v4 / moitié passive et allocation constante 80 % révisée trimestriellement. Si zéro candidat qualifié, un diagnostic est explicitement identifié et ne devient pas une sélection réussie.

## Voies explorées

| Famille | Nombre | Différence par rapport aux essais précédents |
|---|---:|---|
| Cœur passif et règle v4 | 4 | 20/35/50/65 % du capital toujours investi, reste en v4 sur son propre budget ; aucun transfert ni rééquilibrage entre poches |
| Exposition constante, témoins | 6 | 70/80/90 % investi, soit maintien des titres après entrée, soit révision toutes les 63 séances |
| Tendance graduelle | 9 | Score logarithmique prix/moyenne 100/200/300 normalisé par le risque, exposition progressive avec plancher 50/65/80 % ; aucune bascule tout-ou-rien |
| Protection lors d'un choc | 9 | Forte accélération volatilité 21/126 ET baisse récente ; exposition 40/60/80 %, retour avec hystérésis ou reprise ; reste investi hors choc |
| Budget de baisse CPPI/TIPP | 18 | Budget fondé sur le capital initial ou le sommet propre du portefeuille ; niveaux 80/85/90 %, multiplicateurs 3/5/8 ; plancher d'exposition 35 % |
| Accélération du risque | 8 | Réduction seulement quand le risque court accélère et le marché baisse, deux références et deux cibles |
| Cœur investi et poche de risque graduelle | 8 | Cœur 50/70 % investi, contrôle de volatilité uniquement sur le solde |

Les budgets de baisse ne garantissent aucun plancher de capital : les gaps, le délai d'exécution et le minimum investi peuvent le franchir. Les familles ne réhabilitent pas les stratégies multi-actifs rejetées et ne reprennent pas à l'identique leurs réglages. Les comparateurs constants sont des contrôles simples, sans promesse d'alpha.

Les publications sur la [tendance diversifiée](https://www.aqr.com/insights/research/journal-article/a-century-of-evidence-on-trend-following-investing) et la [gestion de volatilité](https://www.nber.org/papers/w22208) motivent des hypothèses ; elles ne prouvent pas l'efficacité de ces adaptations mono-ETF sans levier.

## Données et exécution

PSP5.PA EUR, propres cours ajustés et bruts vérifiés identiques, 20/05/2014–13/11/2026, 3 197 observations. Snapshot SQLite privé, source ouverte en lecture seule, empreinte conservée. Aucune écriture de cours synthétiques, aucun historique BNP renommé ni indice USD de substitution. Les séries locales de taux et matières premières ne sont pas transformées en cours d'ETF investissables pour inventer une diversification.

10 000 €, titres entiers, 0,12 % par achat/vente, liquidités à 0 %, aucune liquidation finale forcée ni levier. Signaux en clôture, ordres mis en attente pour une clôture ultérieure, jamais à la clôture du signal. Moteur v4 de recherche reproduisant la production, étendu uniquement pour accepter le budget initial réel de chaque variante hybride ; arrondis et frais séparés dans ses deux sous-poches. Le complément passif paie lui aussi ses frais et ses titres entiers, sans simple combinaison de courbes ayant chacune 10 000 € fictifs.

Même générateur que l'application pour toutes les méthodes, jamais modifié afin de favoriser un candidat. Même marché pour tous les comparateurs d'un parcours. Les graines réservées créent de nouveaux tirages du modèle 2014–2026, pas une nouvelle expérience économique indépendante. Les limites du calendrier et du rééchantillonnage restent celles de l'[audit précédent](sp500-ratio-tradeoff-study.md).

## Sélection

Deux variantes franchissent les filtres historiques. Une seule franchit aussi le compromis sur le lot de sélection : **35 % du capital initial en achat-conservation PSP5, 65 % dans v4**. Le candidat est figé avant les 400 marchés réservés. Les poches ne se rééquilibrent pas entre elles ; leurs poids dérivent ensuite. Le budget v4 se répartit 75/25 : cela représente initialement 48,75 % du capital pour la règle lente, 16,25 % pour la défensive et 35 % pour la poche passive. Le risque minimal visé est plus élevé que v4 ; ce n'est pas une protection gratuite.

## Reproduction et contrôles logiciels

`PYTHONPATH=backend:scripts uv run python scripts/study_sp500_broader_compromise.py`

Vérification indépendante contre le moteur actif sur le premier marché de chaque lot : huit mesures de Buy & Hold et v4 à 1e−9, sans tolérance relative. Tests de capital initial réellement séparé, frais et titres entiers, causalité par retrait des prix futurs, et chute franchissant un budget de baisse avant l'exécution suivante. Les tests ne démontrent aucune rentabilité future. Les sorties complètes, y compris les échecs des 62 configurations et les contrôles fixes, sont conservées dans le JSON local.

## Lot réservé cinq ans — 300 marchés

Les deux hybrides et les témoins sont calculés sur les mêmes 300 marchés, sans nouvelle sélection. La variante 50/50 est un comparateur fixé avant le lot, pas le gagnant de la procédure de sélection.

| Indicateur moyen | Buy & Hold | V4 actuelle | 65 % v4 / 35 % passif | 50 % v4 / 50 % passif |
|---|---:|---:|---:|---:|
| Rendement total net | 116,13 % | 71,79 % | 86,77 % | 93,38 % |
| CAGR net | 15,94 % | 11,14 % | 12,93 % | 13,65 % |
| Drawdown maximal | −24,16 % | −18,22 % | −19,88 % | −20,77 % |
| Volatilité annualisée | 16,45 % | 11,88 % | 13,31 % | 13,99 % |
| Volatilité baissière | 11,70 % | 8,38 % | 9,42 % | 9,92 % |
| Sharpe | 0,971 | 0,973 | 0,988 | 0,987 |
| Sortino | 1,384 | 1,408 | 1,418 | 1,413 |
| Calmar | 0,798 | 0,804 | 0,816 | 0,814 |
| Frais payés | 11,95 € | 45,00 € | 33,32 € | 28,37 € |

65/35 : gain de CAGR moyen de **1,79 point/an**, IC95 apparié [+1,60 ; +1,99] point. Rendement supérieur à v4 sur **87,3 %** des parcours. Volatilité moyenne +12,0 % face à v4, amplitude moyenne du DD +9,1 % ; réduction de 19,1 % et 17,7 % respectivement face au Buy & Hold. Gain de capital final moyen d'environ 1 499 € sur 10 000 € initiaux à cinq ans. Les titres entiers et budgets séparés sont inclus.

Les trois ratios moyens dépassent Buy & Hold. IC95 des écarts : Sharpe [+0,0067 ; +0,0294], Sortino [+0,0153 ; +0,0529], Calmar [−0,0043 ; +0,0418]. L'avantage moyen Calmar n'est pas confirmé au même niveau. Fréquences de victoire contre Buy & Hold : Sharpe/Sortino 52,7 %, Calmar 48,0 %. Une moyenne supérieure ne signifie donc pas une majorité de parcours gagnants sur tous les ratios.

Le compromis principal manque **très légèrement** son critère de rendement : écart de CAGR avec Buy & Hold de 3,0111 points contre 3,0000 maximum fixé avant les résultats. Les autres conditions synthétiques principales de ce lot sont satisfaites. Le seuil n'est pas déplacé après calcul et ce lot n'est pas déclaré entièrement réussi. L'objectif idéal des trois taux de victoire ≥55 % n'est pas rempli non plus.

50/50 : gain de CAGR moyen de **2,52 points/an** face à v4 ; retard de 2,28 points face au Buy & Hold ; volatilité et amplitude moyenne du drawdown encore environ 15 % et 14 % sous Buy & Hold. Contrepartie : risque actuel accru davantage. Cette variante échoue déjà au filtre historique préétabli de drawdown dix ans : −23,92 % contre −10,95 % pour v4, soit environ +12,97 points de perte, au-delà des +12 points permis. Elle est donc présentée comme une option plus exposée, jamais comme la sélection qualifiée.

Contrôle constant 80 % : CAGR 13,01 %, volatilité 13,38 %, DD −19,98 %, Sharpe 0,968, Sortino 1,380, Calmar 0,787, frais 11,26 €. Le 65/35 a un rendement proche, mais des ratios moyens plus élevés sur ce lot. Cela permet de distinguer l'apport de la gestion active d'un simple changement d'exposition.

## Lot réservé dix ans — 100 marchés

| Indicateur moyen | Buy & Hold | V4 actuelle | 65 % v4 / 35 % passif | 50 % v4 / 50 % passif |
|---|---:|---:|---:|---:|
| Rendement total net | 382,40 % | 208,15 % | 267,42 % | 292,99 % |
| CAGR net | 16,13 % | 11,49 % | 13,34 % | 14,03 % |
| Drawdown maximal | −28,62 % | −22,25 % | −24,12 % | −25,05 % |
| Volatilité annualisée | 16,45 % | 12,11 % | 13,52 % | 14,17 % |
| Volatilité baissière | 11,69 % | 8,53 % | 9,56 % | 10,04 % |
| Sharpe | 0,970 | 0,944 | 0,974 | 0,976 |
| Sortino | 1,376 | 1,352 | 1,387 | 1,389 |
| Calmar | 0,643 | 0,599 | 0,635 | 0,640 |
| Frais payés | 11,95 € | 99,51 € | 68,54 € | 55,37 € |

65/35 : gain de CAGR **+1,84 point/an**, IC95 [+1,60 ; +2,10] point, supérieur à v4 sur **96 %** des marchés. Le compromis principal de ce lot passe. Les trois ratios sont supérieurs à v4, mais le Calmar reste légèrement sous Buy & Hold. IC95 des écarts des trois ratios face à Buy & Hold incluent tous zéro (valeurs complètes dans le JSON). L'objectif idéal ne passe pas ; aucune prétention de domination sur les trois ratios à tous les horizons.

## Cours réels et robustesse du candidat 65/35

| Horizon réel | CAGR Buy & Hold | CAGR v4 | CAGR 65/35 | DD Buy & Hold | DD v4 | DD 65/35 |
|---|---:|---:|---:|---:|---:|---:|
| 3 ans | 19,08 % | 16,10 % | 17,14 % | −23,17 % | −7,03 % | −12,38 % |
| 5 ans | 11,60 % | 12,34 % | 12,06 % | −23,18 % | −7,02 % | −11,73 % |
| 10 ans | 14,49 % | 12,20 % | 13,04 % | −33,67 % | −10,95 % | −20,45 % |

Volatilités 65/35 : 10,00/10,28/11,45 % sur 3/5/10 ans, contre 8,35/8,61/9,20 % pour v4 et 14,09/15,15/16,14 % pour Buy & Hold. Le drawdown historique augmente sensiblement face à la protection exceptionnellement forte de v4 : +4,71 points de perte cinq ans, +9,50 points dix ans. Il reste nettement inférieur au Buy & Hold. La moindre volatilité synthétique relative au marché n'est pas une garantie de perte maximale.

La fenêtre défavorable démarre le 13/02/2020 : CAGR inférieur de 0,942 point/an à v4 (tolérance 0,75), DD −17,24 % contre −8,33 %.

23/24 fenêtres historiques cinq ans passent le filtre prévu ; leurs périodes se chevauchent et ne constituent pas 24 expériences indépendantes. Les stress frais 0,24 % et exécution à deux clôtures passent également les conditions prévues, avec un gain moyen de CAGR historique positif. Le détail de la fenêtre défavorable, de chaque stress et de toutes les variantes rejetées reste dans le JSON.

## Conclusion et décision

**La combinaison 65/35 est une piste crédible de compromis face à v4**, avec gain de rendement moyen confirmé sur les deux lots synthétiques réservés et risque intermédiaire entre v4 et Buy & Hold. Elle obtient les trois meilleurs ratios moyens contre Buy & Hold sur cinq ans ; sur dix ans seuls Sharpe et Sortino restent au-dessus, sans avantage statistique établi des trois ratios. Elle perd légèrement en CAGR historique cinq ans. Elle ne promet ni surperformance future ni plafond de pertes.

**La procédure complète reste formellement non satisfaite** : retard cinq ans de 3,0111 points contre le seuil de 3,0000, et objectif idéal des trois ratios non atteint. Ce résultat proche du compromis fixé est plus informatif qu'une déclaration de succès universel ou d'échec absolu. Aucun seuil n'est déplacé pour lui donner un succès rétrospectif.

La variante 50/50, contrôle figé, offre davantage de rendement et se rapproche plus du Buy & Hold, mais augmente davantage le risque ; elle n'a pas passé la sélection historique. Les règles complètement différentes testées n'ont pas franchi les conditions combinées de cette campagne. Cela ne prouve pas qu'aucune autre méthode ne pourrait faire mieux.

**Aucune adoption en production.** Les règles actives v4, le générateur et l'interface restent inchangés. Le code ajouté concerne la recherche uniquement, avec budgets correctement simulés. 62 configurations évaluées sur 100 marchés de sélection, puis le candidat et deux contrôles figés sur 400 marchés réservés : 500 marchés distincts au total. Les résultats de toutes les configurations et les contre-exemples sont conservés.

Vérification logicielle : 22 tests ciblés du moteur de recherche et des nouveaux livres comptables réussis, Ruff backend/scripts et contrôle des espaces. Les métriques des témoins confrontées à la production passent les trois contrôles sur les premiers marchés des lots. Ces vérifications sont distinctes du bilan financier.


## Adoption explicite après présentation des limites

Le 15 novembre 2026, l’utilisateur demande l’implémentation de la piste65/35. La production est désormais `core35_slow_defensive_v5`. Cette décision remplace la décision initiale de non-adoption, sans changer les critères, résultats ni contre-exemples de la recherche. Le contrôle50/50 reste non adopté. Voir [la mise en œuvre et ses vérifications](sp500-core35-adoption.md).
