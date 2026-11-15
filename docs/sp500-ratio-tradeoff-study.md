# Compromis rendement et ratios sur PSP5 — 14 novembre 2026

**Bilan : aucun remplacement démontré supérieur selon l’ensemble des critères ; v4 reste active.**

Recherche demandée après le constat d'une sous-performance de rendement sur 100 parcours. **Aucune modification de la stratégie active sans décision utilisateur.** La colonne « Paires valides » seule est retirée du tableau ; les calculs et dénominateurs restent identiques.

## Ce qui change dans cette recherche

L'objectif n'exige plus de battre le rendement du Buy & Hold. Critères écrits avant les résultats : gain moyen de CAGR d'au moins 1 point par an face à v4, volatilité moyenne au plus 115 % de v4, amplitude moyenne de drawdown au plus 110 % de v4 ; les deux risques doivent rester sous ceux du Buy & Hold. Sharpe, Sortino et Calmar moyens doivent chacun dépasser v4 et Buy & Hold, avec au moins 55 % de victoires appariées face au Buy & Hold pour chacun.

54 paramétrages : 36 allocations graduelles selon la volatilité seule (fenêtres 21/63/126 séances, cibles 12/14/16 %, exposants 1/2, minimum investi 25/50 %), et 18 variantes de régression (minimum investi 40/55/70 %, budgets lents 50/75/100 %, sortie +1,5σ ou continuation par moyenne 50). L'allocation graduelle n'a pas de filtre de tendance : elle laisse l'ETF investi lors d'une hausse calme. Il s'agit d'une nouvelle hypothèse mono-ETF, distincte de l'ancienne stratégie multi-actifs de gestion par variance rejetée ; aucune de ces règles n'est réintroduite en production.

100 parcours cinq ans, graines 20000–20099, servent à choisir un seul candidat. Choix figé avant 300 nouveaux parcours cinq ans (40000–40299) puis 100 dix ans (50000–50099). Les trois méthodes sont comparées sur chaque même marché, avec 10 000 €, frais 0,12 %, titres entiers, liquidités non rémunérées, signal connu puis exécution à la clôture suivante. Pas de levier, vente à découvert, liquidation finale ni filtrage des parcours. Intervalles appariés à 95 % par rééchantillonnage de 5 000 lots. Les ratios présentés sont les moyennes des ratios de chaque parcours.

Les graines réservées séparent les tirages de sélection et d'évaluation ; elles ne créent pas de nouvel historique économique indépendant. Même modèle PSP5 2014–2026 et mêmes états initiaux. Les historiques réels trois/cinq/dix ans, 24 départs trimestriels cinq ans, frais doublés et retard d'une séance supplémentaire restent des contre-épreuves nécessaires. Aucun classement opportuniste après les audits.

## Audit du générateur

1 000 marchés de 1 260 séances (graines 60000–60999), indépendants des lots de recherche. Comparaison des rendements simples quotidiens : volatilité, quantiles, asymétrie, kurtosis, autocorrélation des rendements et des rendements au carré, distributions de volatilité glissante 21/63 séances. Les distributions simulées sont comparées aux mesures historiques PSP5 EUR, sans substitution d'un indice USD.

Le maintien de dépendances temporelles et des regroupements de volatilité motive le rééchantillonnage par blocs ; cela ne reproduit pas toute l'économie d'un marché. Voir [Ruiz et Pascual, Bootstrapping Financial Time Series](https://e-archivo.uc3m.es/bitstream/handle/10016/4727/bootstrapping_ruiz_JES_2002_ps.pdf). Les limites liées à une volatilité persistante ou non stationnaire sont également exposées dans [Cavaliere et Georgiev](https://arxiv.org/abs/2101.03562).

## Reproduction et vérification logicielle

`PYTHONPATH=backend:scripts uv run python scripts/study_sp500_ratio_tradeoff.py`

Le plan et toutes les configurations sont écrits avant calcul dans `data/backtests/sp500-ratio-tradeoff.json`. Snapshot SQLite privé, source ouverte en lecture seule, empreinte SHA256 conservée. Aucun changement des données utilisateur et aucun remplacement du générateur ou de v4.

Contrôles : métriques Buy & Hold et v4 confrontées au moteur de production sur le premier parcours de chaque lot, huit mesures à 1e−9 ; préfixes de signaux inchangés lorsqu'on retire le futur ; test explicite d'un choc avant la clôture d'exécution, avec frais et unités entières. Ce sont des vérifications logicielles, pas une validation financière.

### Diagnostic statistique du générateur inchangé

| Mesure | Historique PSP5 | Médiane des 1 000 marchés |
|---|---:|---:|
| Volatilité annualisée | 16,59 % | 16,47 % |
| Quantile quotidien 1 % | −3,09 % | −2,93 % |
| Quantile quotidien 99 % | +2,64 % | +2,64 % |
| Volatilité glissante 21 séances, médiane | 12,70 % | 13,09 % |
| Volatilité glissante 63 séances, médiane | 13,70 % | 14,22 % |
| Autocorrélation des rendements au carré, retard 1 | 0,305 | 0,293 |
| Autocorrélation des rendements au carré, retard 21 | 0,107 | 0,058 |

La volatilité annuelle des marchés simulés se situe entre 13,80 et 19,82 % pour les quantiles 5/95 % des tirages. Le modèle conserve les ordres de grandeur, l'asymétrie et les extrêmes historiques ainsi qu'une part des regroupements de volatilité. Les raccords de blocs réduisent les dépendances longues ; l'autocorrélation des carrés à 21 séances en donne un exemple. Il n'est donc pas calibré pour reproduire toute la structure temporelle du S&P 500.

Le bruit ajouté vaut 5 % de l'écart-type quotidien, soit seulement 0,125 % d'augmentation relative théorique de l'écart-type total si indépendant : il ne transforme pas les rendements en bruit gaussien pur. Les changements de blocs peuvent néanmoins assembler des épisodes inédits.

Limite de calendrier : 1 304 rendements sur l'horizon cinq ans, soit 260,8 par an ; les métriques utilisent √252 et un CAGR calendaire. Il y a donc environ 3,5 % d'incréments de plus que 252/an. Cet effet concerne les deux méthodes et peut augmenter leur rendement annuel simulé ; il ne doit pas être attribué au talent d'une stratégie. Le générateur n'a pas été ajusté pendant cette recherche pour favoriser le candidat. Toute correction du calendrier nécessiterait de nouveaux lots comparables.

Le modèle reste conditionné à PSP5 EUR depuis 2014, sans crises 2000/2008 ni régime de change futur nouveaux. Ces tirages ne sont pas des prévisions et ne rendent pas leurs fréquences de victoire prospectives.

## Première campagne : résultat du lot réservé cinq ans

Trois configurations sur 54 passent la sélection. Le candidat choisi pour son CAGR moyen : fenêtre 21 séances, cible 14 %, exposant 1, plancher 50 %, décision toutes les cinq séances et bande de cinq points. Allocation cible `clip(14 % / volatilité réalisée, 50 %, 100 %)`. Les poids dérivent entre interventions ; le plancher est une cible d'allocation, pas une protection des pertes. V4 et le Buy & Hold sont calculés sur chaque même parcours.

Sur les **300 parcours réservés cinq ans**, il échoue aux critères malgré un gain de rendement :

| Indicateur moyen | Buy & Hold | V4 active | Candidat 1 | Candidat 1 gagne contre Buy & Hold |
|---|---:|---:|---:|---:|
| Rendement total net | 108,73 % | 70,50 % | 84,30 % | 5,3 % |
| CAGR net | 15,16 % | 10,96 % | 12,49 % | 5,3 % |
| Drawdown maximal | −24,54 % | −18,72 % | −19,18 % | 96,0 % |
| Volatilité annualisée | 16,52 % | 12,31 % | 13,47 % | 100 % |
| Volatilité baissière | 11,75 % | 8,70 % | 9,63 % | 100 % |
| Sharpe | 0,926 | 0,927 | 0,916 | 43,3 % |
| Sortino | 1,319 | 1,338 | 1,296 | 41,0 % |
| Calmar | 0,751 | 0,765 | 0,762 | 55,7 % |
| Frais payés | 11,95 € | 43,60 € | 159,70 € | 0 % |

CAGR contre v4 : +1,53 point/an, intervalle apparié 95 % [+1,15 ; +1,91] point. Gain de CAGR sur 65 % des parcours. Volatilité moyenne +9,36 % relatif, amplitude moyenne de perte +2,43 % relatif. Le Sharpe et le Sortino restent inférieurs au Buy & Hold : intervalles des écarts [−0,0208 ; −0,0011] et [−0,0396 ; −0,0081]. L'écart Calmar [+0,0105 en moyenne] a un intervalle [−0,0062 ; +0,0265]. Ce candidat n'est donc pas « meilleur sur les trois ratios ».

## Seconde campagne : coût des interventions

Après cet échec réservé, une nouvelle hypothèse est déclarée avant ses résultats : conserver les mêmes 36 allocations selon la volatilité, mais décider toutes les 10/21 séances avec une bande de non-intervention de 10/20 points. Soit 144 paramétrages. On cherche à réduire le coût des ajustements, sans changer le modèle de marché ni recycler les tirages réservés de la première campagne.

100 parcours de sélection cinq ans, graines 70000–70099 ; puis un seul candidat figé, 300 parcours réservés cinq ans (90000–90299) et 100 dix ans (100000–100099). Les exigences sont identiques à la première campagne. C'est une recherche supplémentaire motivée par l'échec précédent, pas un test économique vierge. Reproduction : `PYTHONPATH=backend:scripts uv run python scripts/study_sp500_ratio_costs.py`, sortie `data/backtests/sp500-ratio-costs.json`.

### Contre-épreuves du candidat 1

Sur 100 parcours réservés dix ans : CAGR 12,58 % contre 10,77 % pour v4 et 15,13 % pour le Buy & Hold ; volatilité 13,41/11,95/16,46 %, drawdown moyen −22,08/−22,56/−28,94 %. Sharpe 0,923/0,910/0,920, Sortino 1,304/1,304/1,304 (valeurs proches, le candidat reste légèrement sous Buy & Hold), Calmar 0,634/0,560/0,596. Le candidat échoue encore aux conditions combinées.

Les cours réels sont un contre-exemple plus net :

| Horizon réel | CAGR v4 | CAGR candidat 1 | DD v4 | DD candidat 1 | Volatilité v4 | Volatilité candidat 1 |
|---|---:|---:|---:|---:|---:|---:|
| 3 ans | 16,10 % | 17,70 % | −7,03 % | −18,85 % | 8,35 % | 12,28 % |
| 5 ans | 12,34 % | 10,30 % | −7,02 % | −18,56 % | 8,61 % | 12,77 % |
| 10 ans | 12,20 % | 12,14 % | −10,95 % | −24,79 % | 9,20 % | 13,07 % |

Ce recul de la protection réelle exclut de présenter le candidat 1 comme une amélioration générale à risque modéré. Tous les stress et fenêtres glissantes, y compris défavorables, sont conservés dans le JSON. Pas d'adoption.

Complément de risque candidat 1 : le quantile 95 % de l'amplitude des drawdowns des parcours synthétiques est de 27,83 % contre 32,07 % pour v4 sur cinq ans ; 32,83 % contre 33,87 % sur dix ans. Le risque de queue synthétique ne raconte donc pas exactement la même chose que les moyennes. En revanche, le drawdown historique du candidat est plus profond que v4 dans les **24/24 fenêtres cinq ans** à départ trimestriel examinées. Frais doublés et exécution retardée ne résolvent pas ce contre-exemple ; les valeurs détaillées restent archivées.

### Candidat 2 : résultat réservé cinq ans

Aucun des 144 réglages ne passe la sélection. Le diagnostic, choisi selon le plus faible avantage relatif parmi les trois ratios moyens contre Buy & Hold, est figé : fenêtre 21 séances, cible 12 %, exposant 2, plancher 50 %, décision toutes les 10 séances, bande de 10 points. Allocation cible `clip((12 % / volatilité réalisée)², 50 %, 100 %)`. **Ce diagnostic n'est pas un candidat qualifié** ; il ne remplace pas le candidat 1 après examen du lot de celui-ci.

Sur ses 300 parcours cinq ans réservés :

| Indicateur moyen | Buy & Hold | V4 active | Candidat 2 | Candidat 2 gagne contre Buy & Hold |
|---|---:|---:|---:|---:|
| Rendement total net | 109,03 % | 70,12 % | 73,50 % | 3,7 % |
| CAGR net | 15,14 % | 10,89 % | 11,19 % | 3,7 % |
| Drawdown maximal | −25,52 % | −19,42 % | −17,30 % | 99,3 % |
| Volatilité annualisée | 16,68 % | 12,37 % | 11,89 % | 100 % |
| Volatilité baissière | 11,90 % | 8,75 % | 8,48 % | 100 % |
| Sharpe | 0,918 | 0,915 | 0,923 | 52,3 % |
| Sortino | 1,305 | 1,318 | 1,311 | 51,3 % |
| Calmar | 0,730 | 0,723 | 0,779 | 65,7 % |
| Frais payés | 11,95 € | 42,87 € | 202,27 € | 0 % |

Les trois ratios moyens dépassent Buy & Hold sur ce lot, mais le Sortino reste sous celui de v4, les victoires Sharpe/Sortino n'atteignent pas les 55 % requis et le gain de CAGR n'atteint pas le point annuel demandé dans le protocole. Le gain de CAGR moyen vaut seulement +0,303 point, IC95 [−0,094 ; +0,718] point : le signe positif n'est pas confirmé. Les IC95 des écarts Sharpe/Sortino contre Buy & Hold incluent zéro : [−0,0076 ; +0,0169] et [−0,0138 ; +0,0254]. Seul le Calmar présente ici un avantage moyen plus net : +0,0496, IC95 [+0,0277 ; +0,0705].

La diminution de fréquence et l'élargissement des bandes ne suffisent donc pas à établir une stratégie meilleure. Pour ce diagnostic d'exposant 2, les changements d'exposition restent importants et le coût total dépasse même celui du candidat 1, sur des lots distincts : il faut mesurer les frais plutôt que supposer qu'ils diminuent. Les deux tableaux ne partagent pas leurs graines ; comparer chaque candidat à ses propres témoins appariés.

### Dix ans et contre-épreuves réelles du candidat 2

Sur les 100 parcours dix ans réservés : CAGR moyen 11,33 % contre 10,68 % pour v4 et 15,51 % pour Buy & Hold ; volatilité 11,90/11,95/16,58 %, drawdown moyen −20,57/−23,52/−29,88 %. Sharpe 0,931 contre 0,934 Buy & Hold, Sortino 1,312 contre 1,319, Calmar 0,610 contre 0,578. L'avantage des trois ratios constaté sur cinq ans ne se retrouve donc pas à dix ans.

| Horizon réel | CAGR v4 | CAGR candidat 2 | DD v4 | DD candidat 2 | Volatilité v4 | Volatilité candidat 2 |
|---|---:|---:|---:|---:|---:|---:|
| 3 ans | 16,10 % | 17,48 % | −7,03 % | −14,50 % | 8,35 % | 11,39 % |
| 5 ans | 12,34 % | 10,62 % | −7,02 % | −14,47 % | 8,61 % | 11,30 % |
| 10 ans | 12,20 % | 11,57 % | −10,95 % | −22,05 % | 9,20 % | 11,73 % |

Ce second diagnostic réduit aussi nettement la protection historique de v4. Les 24 fenêtres glissantes et les frais doublés / retard supplémentaire sont intégralement conservés dans son JSON.

## Bilan et décision

198 paramétrages supplémentaires, 200 marchés de sélection (100 par campagne), 800 marchés réservés (300 cinq ans et 100 dix ans par campagne), soit 1 000 parcours de comparaison distincts ; audit du générateur sur 1 000 autres marchés distincts. Les 54/144 variantes sont toutes évaluées sur leurs 100 parcours de sélection respectifs ; seuls les deux candidats figés sont ensuite évalués sur les lots réservés. Il ne s'agit pas de 198 variantes testées sur chacun des 1 000 marchés.

**Aucun candidat ne satisfait la procédure complète.** Le premier améliore le rendement moyen synthétique, avec des concessions sur les ratios et une dégradation historique importante du risque. Le second améliore les trois ratios moyens face au Buy & Hold sur cinq ans seulement ; le gain de CAGR n'est pas confirmé, les trois ratios ne passent pas à dix ans et la protection historique recule. Pas de remplacement recommandé au vu de ces résultats, ni adoption implicite d'un des deux candidats. V4 et le générateur restent inchangés. Aucun plafond de pertes ou succès futur déduit des tirages.

Modification de produit réalisée : retrait de la colonne « Paires valides », sans changer les dénominateurs, moyennes, graines ni calculs. Vérification logicielle finale : 15 tests backend ciblés réussis (13 du simulateur et 2 du nouveau registre de recherche), `npm run check` (40 tests unitaires et compilation), 6 parcours navigateur S&P sur ordinateur/mobile, Ruff backend/scripts et contrôle des espaces. Les scénarios financiers ci-dessus constituent une recherche distincte de ces tests logiciels.
