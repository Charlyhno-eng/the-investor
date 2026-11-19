# Quel modèle améliore le Sharpe de PSP5 ?

## Décision au 19 novembre 2026

**La piste à retenir pour un suivi prospectif combine un filtre de baisses et cinq modèles de marché.** Elle améliore le Sharpe moyen de la stratégie « Concentration des baisses » sur deux lots de confirmation. Elle offre le meilleur résultat moyen à cinq ans parmi les finalistes comparés sur les mêmes marchés. À dix ans simulés, la règle simple sur 32 séances conserve une courte avance. Sur cinq et dix ans réels de PSP5, la régression v6 de l’application garde une avance nette. Les calculs concernent la recherche et l’application conserve ses stratégies actuelles.

### Comparaison finale à marchés identiques

Le tableau donne le Sharpe net annuel. Les deux colonnes simulées utilisent 1 500 parcours de cinq ans et 500 de dix ans. Chaque ligne commence avec 10 000 € et chaque concurrent suit exactement les mêmes cours. Les colonnes réelles correspondent aux mêmes clôtures de départ et de fin pour toutes les stratégies évaluées.

| Stratégie | Simulé 5 ans | Simulé 10 ans | Réel 3 ans | Réel 5 ans | Réel 10 ans | Réel depuis janvier 2021 |
|---|---:|---:|---:|---:|---:|---:|
| PSP5 passif | 0,918 | 0,911 | 1,230 | 0,740 | 0,877 | 1,038 |
| Concentration actuelle, 21 séances | 0,970 | 0,966 | 1,502 | 0,857 | 0,948 | 0,998 |
| Concentration, 32 séances | 0,980 | **0,983** | 1,170 | 0,690 | 0,994 | 1,003 |
| Régression v6 de l’application | 0,879 | 0,834 | **1,781** | **1,434** | **1,316** | **1,405** |
| Mélange antérieur de cinq modèles, seul | 0,956 | 0,939 | 1,600 | 1,006 | 1,071 | 1,338 |
| **Filtre de baisses et cinq modèles combinés** | **0,988** | 0,979 | 1,406 | 0,871 | 1,098 | 1,189 |
| Régression prédictive réentraînée sur les cours | 0,793 | 0,803 | 1,252 | 0,602 | 0,952 | 0,923 |
| Signaux macrofinanciers combinés | 0,891 | 0,893 | 1,215 | 0,633 | 0,872 | 0,930 |
| Exposition apprise en maximisant directement le Sharpe | 0,946 | 0,926 | 1,536 | 0,972 | — | 1,145 |

Le modèle d’optimisation directe est figé fin 2020. Son historique réel d’évaluation commence en 2021. La v6 avait déjà été sélectionnée sur ses résultats historiques, notamment à trois, cinq et dix ans. Les simulations à blocs conservent en partie les séquences historiques et restent dépendantes du comportement de PSP5 depuis 2014.

## Fonctionnement de la piste combinée

À chaque clôture, cinq modèles produisent ensemble une première cible d’investissement, **E**, entre 10 % et 100 %. Deux suivent des états de régression, deux détectent des ruptures et des reprises par sommes cumulées, et un cinquième estime un régime de marché. Le poids des modèles évolue avec leurs performances et leur risque sur 252 séances, avec décalage d’exécution et estimation des frais. Ce mélange est le candidat synthétique archivé d’une étude antérieure.

Un second signal, **B**, vaut zéro lorsque les rendements négatifs représentent plus de 80 % de la somme des carrés des rendements logarithmiques des 32 dernières séances. Sinon, B vaut un. La nouvelle cible unique de PSP5 s’écrit

`(0,25 × E + 0,75 × B) × (0,50 + 0,50 × min(E, B))`.

Par exemple, si les cinq modèles proposent 60 % de PSP5, le portefeuille vise **72 %** lorsque le filtre est favorable et **7,5 %** lorsqu’il détecte une concentration des baisses. Ce sont deux signaux appliqués au même compte. La stratégie examine sa cible quotidiennement et passe un ordre à la clôture suivante lors de l’initialisation ou d’un écart d’au moins cinq points avec l’exposition observée. Chaque transaction paie 0,12 %.

### Ampleur du gain

- Face à la stratégie 21 séances, la combinaison gagne **0,0178 de Sharpe** en moyenne sur cinq ans, avec 859 victoires sur 1 500 et un intervalle apparié à 95 % de [+0,0132 ; +0,0224]. À dix ans, elle gagne **0,0127**, avec 294 victoires sur 500 et un intervalle de [+0,0070 ; +0,0185].
- Face à la règle 32 séances, le gain à cinq ans est de **+0,0079** [+0,0048 ; +0,0109]. À dix ans l’écart est de **−0,0038** [−0,0078 ; +0,0002]. Le critère annoncé de supériorité simulée aux deux horizons face à ce témoin échoue. Ces intervalles estiment uniquement l’incertitude Monte-Carlo de la moyenne dans le générateur choisi.
- Depuis janvier 2021 sur PSP5, le rendement annualisé passe de 14,68 % pour la règle actuelle à **13,91 %** pour la combinaison, la volatilité de 14,54 % à **11,30 %** et le drawdown de −22,51 % à **−14,61 %**. Le Sharpe monte malgré la baisse du rendement. La combinaison passe 46 ordres sur cette période, contre 7 pour la règle actuelle.
- Avec frais doublés et exécution repoussée à la deuxième clôture depuis janvier 2021, le Sharpe de la combinaison descend de 1,189 à **1,071**. Les règles 21 et 32 séances donnent respectivement **0,989** et **0,835** sous le même stress. Sur douze fenêtres réelles de trois ans commençant chaque trimestre de 2021 à 2023, la combinaison bat la règle 21 séances dans **10 cas**. Ces fenêtres se chevauchent.

## Quatre campagnes et une confirmation indépendante par les graines

**1. Huit familles fondées sur les cours, 864 configurations.** Risque asymétrique à mémoire différente pour les hausses et les baisses, décomposition des sauts et de la variation continue, amplitude des pertes extrêmes, alternance suivi de tendance/retour à la moyenne suivant l’autocorrélation, estimation de rendement par régime avec rappel vers une moyenne, régression multivariée régularisée, allocation entre modèles selon leurs Sharpe récents, et médiane de cinq estimations. Les expositions sont continues avec bandes de transaction. La sélection combine à parts égales le Sharpe moyen de trois périodes PSP5 de 2015 à 2020, de quatre épisodes SPY USD de 1998 à 2013 et de 160 marchés construits exclusivement à partir du PSP5 disponible avant 2021.

Le gagnant est une régression qui estime le rendement des cinq séances suivant l’exécution à partir de mouvements à plusieurs horizons, d’une variation de volatilité et de la concentration des baisses. Réentraînement toutes les 21 clôtures sur au plus 504 observations. Seules les étiquettes dont tout le rendement est déjà connu sont utilisées. Son Sharpe réservé initial de 0,783 à cinq ans est inférieur à celui de la règle actuelle de 0,964. Les contrôles avec blocs raccourcis à 21 séances ou prolongés à 126 donnent également un écart défavorable.

**2. Cinq familles macrofinancières, 540 configurations.** Structure à terme VIX/VIX3M, écart de volatilité implicite et réalisée, devises refuges et cycliques, pente et variation des taux, régression sur facteurs externes, estimation de prime conditionnelle et combinaison de ces estimations. Le seul actif négocié est PSP5. Les clôtures étrangères précèdent strictement la séance française, avec un décalage supplémentaire pour les taux. La sélection accorde le même poids aux trois périodes historiques PSP5 et à 160 marchés de sélection antérieurs à 2021. Les états externes historiques observables et les variations de PSP5 correspondantes sont tirés en blocs conjoints. Cela conserve des dépendances locales tout en créant des discontinuités aux jonctions.

Le candidat retenu utilise la médiane de quatre estimations. Son Sharpe moyen sur le premier lot de cinq ans est de **0,881**, contre **0,783** pour le modèle prédictif fondé sur les cours et **0,964** pour la règle actuelle sur les mêmes marchés. Un mélange figé à parts égales des cibles macro et prix donne **0,846**.

**3. Quatre combinaisons de signaux, 144 configurations.** Moyenne simple d’expositions, atténuation en cas de désaccord, limitation de l’exposition du mélange de cinq modèles pendant un signal de baisse, et pondération adaptative selon la performance relative des signaux. Trois poids relatifs, deux horizons du signal de baisses, trois cadences et deux bandes d’exécution. L’ancien mélange à cinq modèles, la règle 21 séances, la règle 32 séances et le passif participent au classement. La sélection pré-2021 sur historique et 160 marchés simulés retient **le témoin 32 séances**. La piste d’accord entre signaux est un représentant de famille remarqué **après lecture de ces résultats**, puis figé pour l’audit séparé ci-dessus. Elle n’était pas la gagnante de la sélection initiale.

**4. Apprentissage direct du Sharpe, 81 configurations.** Trois architectures de variables explicatives, trois degrés de régularisation, trois sources d’apprentissage (PSP5, PSP5/SPY, moyenne de deux politiques apprises séparément) et trois conventions de cadence et de bande. Une fonction logistique transforme les données en exposition entre 5 et 100 %. Le modèle ajuste ses coefficients pour maximiser le Sharpe net avec pénalité de régularisation, frais de rotation lissés et exécution décalée. La sélection entre configurations utilise le Sharpe du compte exact en actions entières. Deux tests chronologiques entraînent respectivement jusqu’à fin 2016 et fin 2018, puis mesurent 2017–2018 et 2019–2020. Les coefficients du gagnant sont réestimés jusqu’à fin 2020 et figés.

Le meilleur utilise des variables linéaires dans la fonction logistique, une décision toutes les cinq séances et une bande de dix points. Depuis 2021 son Sharpe réel de **1,145** dépasse celui de la concentration actuelle de **0,998**. Son Sharpe moyen sur son premier lot de simulations à dix ans est **0,923**, inférieur de **0,049** à celui de la règle actuelle. Cette performance varie avec la source des trajectoires. Sur 300 simulations de cinq ans tirées des seules observations postérieures à 2020, l’écart devient **+0,080**.

**Confirmation finale.** 1 629 configurations de recherche déclarées au total, en plus des témoins. Classement par Sharpe seul. Les campagnes prix et macro partagent leurs marchés standards. Les campagnes de combinaison et d’apprentissage direct ont leurs propres graines. L’audit final évalue la combinaison figée sur 1 500 nouveaux parcours de cinq ans et 500 de dix ans, puis sur deux générateurs distincts. Les autres finalistes sont aussi recalculés sur ces mêmes 2 000 marchés pour le tableau principal. Toute cette campagne utilise des prix passés déjà explorés dans le projet. Les nouvelles graines testent la stabilité de simulation.

## Quand le classement change

| Marchés synthétiques, 400 parcours de cinq ans par modèle | PSP5 passif | Concentration 21 | Concentration 32 | Cinq modèles seuls | Combinaison |
|---|---:|---:|---:|---:|---:|
| Journées historiques tirées indépendamment | **0,935** | 0,836 | 0,861 | 0,921 | 0,869 |
| Volatilité asymétrique GJR avec innovations de Student | 0,995 | 0,985 | 0,983 | **1,024** | 1,012 |

Le premier stress supprime la succession historique de journées favorables ou défavorables. Le passif prend la tête. Le second reproduit des chocs persistants et asymétriques avec une dérive constante. La combinaison gagne contre les règles de concentration et cède la première place aux cinq modèles seuls. Les paramètres sont calibrés sur le même historique PSP5. Le Sharpe dépend fortement de la forme supposée de la prévisibilité.

### Crises antérieures à PSP5

| Série et période | Passif | Concentration 21 | Concentration 32 | Combinaison |
|---|---:|---:|---:|---:|
| Indice de prix américain, dollars, 1929–1932 | −0,580 | −0,582 | −0,691 | −0,705 |
| Même série, 1973–1974 | −1,367 | −1,356 | −1,526 | −1,649 |
| Même série, 1987 | 0,102 | −0,126 | 0,265 | 0,620 |
| S&P 500 dividendes réinvestis, dollars, 1994–2013 | 0,553 | 0,530 | 0,573 | 0,491 |
| Même série, 2000–2002 | −0,497 | −0,526 | −0,432 | −0,503 |
| SPY ajusté converti en euros, 2007–2009 | −0,127 | −0,266 | −0,141 | −0,072 |

Ces séries de substitution ont des horaires, une devise ou un traitement des dividendes différents de PSP5. Les périodes américaines les plus anciennes proviennent de l’historique rétrospectif de la série de prix. Au début de 1929, seuls 251 cours de préhistorique sont disponibles pour réchauffer les signaux. Pour SPY en euros, les dates retenues sont communes aux clôtures SPY et EUR/USD disponibles localement. Les prix de substitution sont ramenés à 30 par unité à la première date de chaque test pour simuler l’arrondi des titres. Ce montant est une convention de calcul. Sur vingt ans de total return USD et pendant plusieurs crises, la piste combinée perd son avantage.

## Conventions, vérifications et reproduction

- Sharpe de l’application, moyenne des rendements quotidiens simples nets divisée par leur écart-type échantillonnal, multipliée par √252. Cash et taux sans risque à zéro. Cours PSP5 en EUR, frais de 0,12 % à l’achat et à la vente, titres entiers, capital de 10 000 €, exécution à la clôture suivante. Absence de levier et de vente à découvert. Le protocole ne comporte aucun filtre sur le rendement ou le drawdown.
- Le générateur principal rééchantillonne des blocs historiques d’une longueur moyenne de 63 séances, avec une perturbation de 5 % de la volatilité quotidienne. Le premier lot prix/macro inclut aussi 400 parcours de cinq ans tirés du PSP5 depuis 2021 et deux lots de 300 à longueurs de blocs différentes. Les comparaisons de stratégies utilisent des différences appariées. Les fréquences et intervalles ne constituent pas des probabilités prospectives.
- Calcul sur copies SQLite en mémoire. Les Sharpe historiques des deux témoins sont rapprochés du moteur indépendant de la règle actuelle. La régression utilise les moteurs historique et multi-parcours de l’application. Le passif est rapproché trajectoire par trajectoire lors des comparaisons au moteur de production. Les caractéristiques sont vérifiées sur des préfixes de données, le gradient de l’objectif direct par différences finies et les cibles des cinq modèles contre le code de l’étude archivée. Deux comptes historiques de la combinaison sont contrôlés avec un second moteur de transactions, dont un avec frais doublés et exécution différée.
- Ces pistes s’inspirent notamment des travaux sur les portefeuilles gérés selon la volatilité et sur la réponse asymétrique de la volatilité aux nouvelles de marché. Les modèles, les frais et les restrictions de placement sont propres à cette étude. [Moreira et Muir](https://www.nber.org/papers/w22208) · [Engle et Ng](https://www.nber.org/papers/w3681).

Depuis la racine, utiliser le préfixe `OPENBLAS_NUM_THREADS=1 PYTHONPATH=backend:scripts .venv/bin/python scripts/` pour lancer les scripts suivants, dans l’ordre.

1. [Familles fondées sur les cours](../scripts/study_pea_sharpe_models.py) · [Résultats](../data/backtests/pea-sharpe-models.json)
2. [Familles macrofinancières](../scripts/study_pea_sharpe_macro.py) · [Résultats](../data/backtests/pea-sharpe-macro.json)
3. [Combinaisons avec les cinq modèles](../scripts/study_pea_sharpe_hybrid.py) · [Résultats](../data/backtests/pea-sharpe-hybrid.json)
4. [Optimisation directe](../scripts/study_pea_direct_sharpe.py) · [Résultats](../data/backtests/pea-direct-sharpe.json)
5. [Audit de confirmation](../scripts/audit_pea_sharpe_hybrid.py) · [Résultats](../data/backtests/pea-sharpe-agreement-audit.json)
6. [Comparaison finale à marchés identiques](../scripts/compare_pea_sharpe_finalists.py) · [Résultats](../data/backtests/pea-sharpe-finalists.json)
7. [Crises sur séries de substitution](../scripts/audit_pea_sharpe_crises.py) · [Résultats](../data/backtests/pea-sharpe-proxy-crises.json)

## Nouveau lot demandé de 1 000 périodes de cinq ans

La combinaison figée est la stratégie testée. Les 1 000 graines consécutives de 197032000 à 197032999 utilisent le générateur standard et les mêmes cours pour tous les concurrents. L’historique source comprend 3 201 clôtures du 20 mai 2014 au 19 novembre 2026. Capital initial de 10 000 €, parts entières, frais de 0,12 % et exécution à la clôture suivante.

| Moyennes des 1 000 parcours | Sharpe net | Rendement annualisé | Drawdown maximal | Volatilité annualisée |
|---|---:|---:|---:|---:|
| Filtre de baisses + cinq modèles | 0,9944 | 13,28 % | −17,60 % | 13,22 % |
| Concentration actuelle, 21 séances | 0,9779 | 15,48 % | −20,51 % | 15,56 % |
| Filtre 32 séances seul | 0,9887 | 15,78 % | −20,75 % | 15,66 % |
| PSP5 passif | 0,9238 | 15,07 % | −24,87 % | 16,50 % |

Face à la règle actuelle, le gain moyen de Sharpe atteint +0,0165, intervalle apparié Monte-Carlo à 95 % [+0,0110 ; +0,0220]. La combinaison gagne en Sharpe 586 fois, en rendement 139 fois et en drawdown 884 fois. Face à PSP5 passif, elle gagne en Sharpe 637 fois et obtient à la fois un meilleur rendement et un drawdown moins profond 247 fois. La régression v6 donne un Sharpe moyen de 0,8852 ; la combinaison la dépasse sur 701 parcours. Pour la combinaison, 23 parcours présentent une chute supérieure à 30 % et 8 terminent sous le capital initial. [Données individuelles et agrégats du lot](../data/backtests/pea-agreement-1000.json).
