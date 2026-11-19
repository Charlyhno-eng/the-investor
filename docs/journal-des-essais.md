# Journal des essais et des décisions

**Mise à jour instrument/frais :** à la demande de l’utilisateur, l’application
utilise désormais Amundi PEA S&P500 UCITS ETF Acc (PSP5.PA, FR0011871128),
avec 0,12 % de frais par transaction pour la stratégie S&P. La combinaison active
depuis la dernière adoption du 15 novembre est la régression75/25 avec
plancher10%, sans poche passive (`slow_defensive_sharpe_v6`). La v5 65%v4/35%passif
est archivée. Tous les résultats
ESE/frais 0,5 % ci-dessous sont des archives de
recherche ; ils ne décrivent pas la nouvelle combinaison. Un mode de simulation
multiple compare les victoires et moyennes de chaque indicateur en direct,
sans sélection de parcours. Détails : [simulation S&P](sp500-simulation.md).


Dernière mise à jour : **19 novembre 2026**.

Ce document rassemble les recherches disponibles dans le projet, leurs résultats favorables et défavorables, les décisions prises et les liens vers les rapports reproductibles. Il sert de point d’entrée ; les rapports détaillés conservent les paramètres, périodes, critères et contre-exemples de chaque campagne. Les chiffres ne sont pas recalculés à l’occasion de cette synthèse.

## Adoption du filtre de baisses et des cinq modèles · 19 novembre 2026

À la demande de l’utilisateur, « S&P 500 · Filtre de baisses + cinq modèles » remplace la concentration 21 séances dans son entrée native. Validation historique et simulations individuelles ou multiples utilisent la cible d’accord figée, le filtre 32 séances et la bande de cinq points. Les identifiants de sélection et d’API existants sont conservés. La régression v6 reste une stratégie distincte. [Règle, résultats et limites](pea-sharpe-recherche-elargie.md) · [Vérification de production sur copie privée](../scripts/verify_pea_agreement.py).

## Adoption explicite de la concentration des baisses PSP5

L’utilisateur demande l’intégration de la règle 21 séances, seuil strict de 80 %, décision toutes les cinq séances depuis le début du test. Une entrée native dédiée présente la comparaison à PSP5 passif. La régression v6 reste accessible séparément. Les réserves sur 2020 et le jour de départ sont détaillées dans [la recherche PEA](pea-sp500-recherche.md).

La validation historique affiche désormais les courbes quotidiennes nettes, les positions finales, les transactions et les trimestres avec les réglages choisis. Les rendements annualisés et drawdowns des deux séries ont été rapprochés du tableau indépendant sur 1, 3, 5 et 10 ans aux réglages par défaut. Sur 1 000 parcours synthétiques de cinq ans (graine initiale 20261119), la règle obtient simultanément un rendement supérieur et une baisse maximale moins profonde dans 404 cas. Ces parcours rééchantillonnent le même historique PSP5.

## Recherche élargie du Sharpe sur PSP5 · 19 novembre 2026

1 629 configurations couvrant modèles de risque, apprentissage statistique, signaux macrofinanciers, combinaisons et optimisation directe. Piste post-sélection combinant un filtre de baisses et cinq modèles, figée avant 1 500 nouveaux marchés à cinq ans et 500 à dix ans. Sharpe 0,988/0,979 contre 0,970/0,966 pour la concentration active mais 0,980/0,983 pour la variante 32 séances. Critère de supériorité aux deux horizons face à la variante 32 séances non satisfait. Régression v6 en tête sur les fenêtres PSP5 réelles de trois, cinq et dix ans. Plusieurs contre-exemples sur historiques américains longs et marchés à rendements indépendants. Recherche sans adoption. [Rapport, comparaisons appariées et scripts](pea-sharpe-recherche-elargie.md).

Nouveau lot demandé de 1 000 périodes de cinq ans pour la combinaison figée. Sharpe moyen de 0,9944 contre 0,9779 pour la concentration actuelle, 586 victoires appariées. Rendement annualisé moyen de 13,28 % contre 15,48 %, drawdown moyen de −17,60 % contre −20,51 %. [Détail du lot](pea-sharpe-recherche-elargie.md#nouveau-lot-demandé-de-1-000-périodes-de-cinq-ans).

## Objectif Sharpe seul pour la concentration des baisses · 19 novembre 2026

Sur 2 443 règles, la sélection synthétique retient le seuil 80 % sur 32 séances avec décision quotidienne. Gain moyen de Sharpe réservé face à la règle active de +0,0131 à cinq ans et +0,0085 à dix ans. Le Sharpe historique trois et cinq ans reste inférieur. Le gagnant du classement historique sous-performe en simulation. Recherche sans adoption. [Rapport et protocole](pea-concentration-sharpe.md).

## Affinage de la concentration des baisses · 19 novembre 2026

504 paramétrages, sept représentants figés, puis 1 000 parcours de cinq ans et 300 de dix ans. Aucun représentant n’améliore le rendement moyen de la règle actuelle sur ces deux horizons. Le calcul en rendements de deux séances protège mieux depuis 2021 au prix de 1,10 point de rendement annuel. L’alerte de volatilité protège fortement sur dix ans historiques mais aggrave le drawdown depuis 2021. La règle d’investissement actuelle est conservée. [Rapport complet](pea-concentration-affinage.md).

## Contrainte PEA et recherche de surperformance — 19 novembre 2026

SPMO écarté à la demande de l’utilisateur, stratégie et optimiseur américains retirés de l’application. Recherche sur 3 628 réglages déclarés, principalement PSP5/cash, plus une branche PSP5/PSPH. La part baissière 21 séances/80 % améliore les deux moyennes synthétiques, mais un changement de date de départ inverse le résultat à cinq ans. Aucun remplacement automatique de v6. [Résultats, contre-exemples et reproduction](pea-sp500-recherche.md).

## Adoption SPMO et optimiseur — 19 novembre 2026

Entrée native SPMO MM 200/75 distincte de la régression v6. Deux campagnes sur 54 réglages et 4 000 trajectoires réservées. Le plancher à 85 % perd sur le drawdown moyen cinq ans. La variante à deux moyennes améliore la protection avec moins de rendement. [Optimiseur, séries de résultats et reproduction](spmo-optimiseur.md).

## Surperformance avec drawdown inférieur au S&P 500 — 19 novembre 2026

La référence demandée devient PSP5 passif. Une règle mensuelle SPMO/cash sélectionnée sur 2016–2020 domine historiquement à 3/5/10 ans, avec 16 doubles réussites sur 28 fenêtres glissantes et 114/250 puis 127/250 sur les simulations à cinq et dix ans. Le stress combiné annule le gain de drawdown récent. Aucune adoption. [Détails et contre-exemples](sp500-objectif-indice.md).

## Régression v6 et compromis rendement, drawdown et volatilité — 19 novembre 2026

Aucune des 1 200 combinaisons de régression ni des 162 règles de dimensionnement par volatilité ne domine la v6 sur les trois critères à trois, cinq et dix ans. Les compromis défensif et rendement sont comparés sur 240 parcours synthétiques communs et 24 fenêtres historiques. Une réserve de cash initiale de 10 à 30 % est également chiffrée. Étude sans adoption. [Résultats et contre-exemples](sp500-v6-compromis.md).

## Adoption de la régression orientée Sharpe v6 — 15 novembre 2026

Après présentation des résultats contradictoires et recommandation du candidat
historique, demande utilisateur de mise en place : **`slow_defensive_sharpe_v6`
active**, budgets initiaux indépendants75%lent/25%défensif, plancher10%pour les
deux poches, aucune poche passive. Fenêtres, seuils, calendriers, replay lent,
état initial défensif, PSP5 EUR, frais0,12%, titres entiers et générateur
conservés. Même moteur validation/simulation unitaire/multiple, aucune écriture
dans la base utilisateur. Le Sharpe reste l'unique critère de recherche.

L'adoption ne change pas le bilan : Sharpe historique3/5/10ans
1,8875/1,4873/1,3520 contre1,6121/1,1407/1,1111 v5, mais Sharpe synthétique
réservé inférieur5/10ans0,853/0,803 contre0,919/0,903. Résultats historiques
déjà sélectionnés, aucune validation prospective ni avantage universel.

[Règles, limites et vérification v6](sp500-sharpe-adoption.md) ; vérificateur
`scripts/verify_sp500_sharpe.py`,18cas exacts à1e−9 sur copie privée. Deux JSON
de vérification v6 distincts ; archives inchangées, ancien vérificateur v5
protégé.462tests backend,40tests frontend/build réussis ; E2E29/30au lot,
dernier cas annexe réussi isolément. Ces contrôles vérifient le logiciel.

## Objectif unique : maximiser le Sharpe, recherche avant adoption — 15 novembre 2026

Instruction explicite : **maximiser le ratio de Sharpe uniquement** ; abandon
des filtres de CAGR, drawdown, Sortino et Calmar. Sans levier ni shorts,
PSP5 EUR/liquidités, mêmes frais et exécution. Convention actuelle conservée :
rendements quotidiens simples nets, écart-type échantillonnal, annualisation252,
taux sans risque0 et cash0, hypothèse explicite. Les autres métriques restent
affichées mais ne sélectionnent pas les candidats. Les anciens échecs restent
documentés selon leurs critères initiaux, sans empêcher un examen sous ce
nouvel objectif. Aucun remplacement automatique de la v5 adoptée.

Deux procédures séparées dans [l'étude Sharpe](sp500-sharpe-study.md) :
`study_sp500_sharpe.py` retient11 pistes par famille/source selon les anciens
Sharpe de sélection, ajoute162 règles volatilité/variance, puis classe173
candidats sur200 mêmes parcours nouveaux. Un gagnant figé avant1000cinq ans/
300dix ans réservés. `study_sp500_sharpe_history.py` classe séparément2571
configurations déclarées par moyenne des seuls Sharpe réels3/5/10ans,
optimisation historique explicitement en échantillon ; un gagnant figé
avant300cinq ans/100dix ans réservés. Aucun repli sur un autre candidat après
les audits ; nouvelles graines du même modèle, pas nouvelles données économiques.

Le gagnant synthétique, mélange causal de cinq modèles, **passe le protocole
de gain de Sharpe moyen dans le modèle** : réservé5/10ans0,9962/0,9507 contre
0,9654/0,9183 v5 ; gains+0,03084/+0,03238, IC95 entièrement positifs,
648/1000 et218/300victoires. Paramètres figés252séances/eta2/aversion3/
plancher10%/aucune poche v4, aucune pénalité DD. Réel5/10ans1,010/1,104 contre
1,141/1,111 : aucune domination uniforme ni validation prospective. Les autres
métriques ne sont pas ajoutées comme filtres d'échec après coup. V5 reste active.

Meilleur historique : sans passif, budgets75/25 lent/défensif, plancher10%,
autres règles inchangées. Sharpe3/5/10ans1,888/1,487/1,352 contre
1,612/1,141/1,111 v5 ;24/24fenêtres5ans supérieurs, frais doublés/retard
conservés. Mais Sharpe réservé5/10ans0,853/0,803 contre0,919/0,903 ;98/300 et
14/100victoires, IC95 des gains entièrement négatifs. Désaccord entre réel
optimisé et modèle conservé ; aucune preuve prospective ni adoption implicite.

## Recherche approfondie et contrôle des petits gains — 15 novembre 2026

Recherche internet élargie : canaux, modèles Markov, MACD, Kalman, détection
de rupture CUSUM, OLMAR, prédiction à noyau, retournement conditionnel,
réglages régressifs conjoints, continuation et combinaison causale d'experts.
**2 409 configurations déclarées,2 391 paramétrages distincts**,18 recouvrements
explicites ;600marchés de sélection. Aucun réglage ne satisfait l'objectif
initial de+0,5point annualisé avec conservation du risque. Les diagnostics figés
restent des échecs, sans adoption. Les sources sont des inspirations, aucune
reproduction exacte ou performance publiée transférée à notre ETF unique.

Trois branches principales puis un audit secondaire de quatre petits gains :
**5 200 marchés réservés** au total (4×1 000 cinq ans et4×300 dix ans), mêmes
PSP5/frais0,12%/générateur. Le secondaire a été déclaré après la sélection,
avant ses nouveaux lots, avec objectif moins élevé ; il ne valide pas la
procédure initiale ni de nouvelles observations économiques indépendantes.

Une seule variante passe ce protocole secondaire : conserver v5 et relever
la sortie défensive de+1,5 à+1,75σ. Réel cinq/dix ans : CAGR12,06→12,15% /
13,04→13,14%,DD−11,73→−11,71% /−20,45→−20,37%. Sur nouveaux marchés réservés,
CAGR moyen+0,1074/+0,0934point, mais drawdown moyen aggravé0,1694/0,2522point.
24/24fenêtres dans les tolérances, frais doublés et retard conservés. Cette
sortie avait déjà été étudiée face à v4 ; elle n'est pas une découverte nouvelle.

Le contrôle des contre-exemples interdit une conclusion de domination :
aggravation synthétique du DD jusqu'à5,11points ; un audit supplémentaire sur
**168 départs mensuels PSP5 trois/cinq ans** donne125CAGR meilleurs,40identiques,
3inférieurs, mais **23DD dégradés**, jusqu'à4,09points. Départ septembre2018
sur cinq ans : CAGR11,41→12,44%,DD−19,19→−23,28%. Aucune période spéciale n'est
introduite dans l'application. Le succès du protocole secondaire limité n'efface
pas ces échecs au souhait de drawdown stable. **Aucune adoption : v5 reste active.**

La meilleure piste CUSUM réservée protège davantage mais perd0,14/0,18point
de CAGR moyen sur cinq/dix ans : ce n'est pas la surperformance demandée.
Rapport : [recherche approfondie S&P](sp500-deep-search-study.md). Scripts
`study_sp500_deep_search.py`, `study_sp500_deep_continuation.py`,
`study_sp500_online_ensemble.py`, `study_sp500_modest_edge.py`,
`audit_sp500_modest_edge.py` ; cinq rapports JSON distincts, résultats défavorables
conservés. Aucun changement production/UI/base. 456tests backend puis11tests
ciblés réussis ; Ruff et contrôle du diff. Vérifications logicielles distinctes
d'une validation financière, historique propre PSP5 depuis2014 seulement.

## Stratégies publiées sans levier — 15 novembre 2026

Recherche internet : Faber (moyenne mobile mensuelle), Antonacci (momentum
absolu), PAA et gestion par volatilité examinées avec leurs différences de
périmètre. Deux témoins adaptés ETF/cash et quatre adaptations explicites,
**18 configurations fixes**, sans sélection après résultats. Comparaison à v5
et PSP5 passif : historiques 1/3/5/10 ans,24fenêtres cinq ans, frais doublés,
retard supplémentaire ; **300 parcours cinq ans et100dix ans** pour tous.

Aucun candidat ne satisfait le compromis fixé avant calcul. Diagnostic
65%v4/35%accord MM10–momentum12 : réel cinq ans CAGR12,06→10,44%,
DD−11,73→−8,83% ; dix ans13,04→11,44%,DD−20,45→−12,13%.
Simulé cinq ans CAGR12,55→10,64%,DD−20,50→−18,13%,
baisses>30%33→16/300 ; dix ans12,44→10,41%,DD−25,38→−22,32%.
Au mieux1/24fenêtres respecte les critères combinés. Protection accrue au prix
du rendement, aucune adoption ; **v5 reste active**. Pas de modification de base,
de moteur de production ou d’interface. Les témoins publiés recoupant d’anciens
essais ne sont pas présentés comme de nouvelles découvertes.

Rapport : [stratégies publiées S&P](sp500-published-rules-study.md).
Script `scripts/study_sp500_published_rules.py`,JSON distinct correspondant.
57tests ciblés réussis, Ruff backend/scripts ; contrôles logiciels distincts
d’une validation financière. Historique PSP5 depuis2014 seulement, nouveaux
tirages sans nouvelle preuve économique indépendante.

## Croisement écart-type et momentum — 15 novembre 2026

Demande : croiser l'écart à la régression et le momentum de l'application pour
améliorer le compromis de v5. **288 configurations**, quatre règles
conditionnelles/continues, régressions 18/60 mois et momentum natif 6/12/36 mois,
150 marchés de sélection puis **1 000 cinq ans et 300 dix ans réservés**.
Aucune configuration ne passe la sélection ; aucun remplacement adopté.

Diagnostic figé : 65 % v4, 35 % interaction progressive z18/momentum12,
seuil55/plancher50 %. Sur 1 000 parcours cinq ans, CAGR **12,48→11,59 %**,
drawdown moyen **−20,84→−19,80 %**, trois ratios inférieurs à v5.
Sur dix ans : CAGR12,26→11,21 %, DD−25,61→−24,06 %.
Réel cinq/dix ans : CAGR12,06→11,36 % /13,04→11,94 % ; seulement1/24 fenêtres
respecte les marges fixées. La protection supplémentaire coûte du rendement.
Les variantes à rendement supérieur en sélection ont toutes un drawdown moyen
plus profond que v5. Aucun ancien score fixe multi-actifs70/30 réintroduit.

Rapport et protocole : [écart-type et momentum](sp500-sigma-momentum-study.md).
Script `scripts/study_sp500_sigma_momentum.py`, rapport JSON distinct du même
nom. PSP5/générateur/frais inchangés, base privée,443tests backend et18cas v5
exacts ; vérification logicielle distincte d'une validation financière.

## Réduction des drawdowns après v5 — 15 novembre 2026

Demande : explorer largement, conserver ou améliorer le rendement et réduire
les fortes baisses ; implémentation autorisée seulement en cas d'amélioration.
Trois campagnes pré-déclarées : 396 configurations de risque/tendance/stops,
432 de retour à la moyenne protégé, puis 24 protections sur les trois poches.
**852 configurations**, 450 marchés de sélection, trois lots réservés de
1000 parcours cinq ans et trois de 300 dix ans. Générateur et données conservés,
ordres à la clôture suivante, frais/titres entiers et vrais budgets indépendants.

Aucune des trois campagnes ne justifie de remplacement.
Compromis le plus intéressant : 65 % v4 /35 % stop adaptatif, CAGR synthétique
cinq ans **12,53 →12,15 %**, DD moyen **−20,85 →−19,30 %**, seuil des 5 % pires
**−33,67 →−31,11 %**, baisses supérieures à30 % **145 →68 sur1000**. Les trois
ratios moyens s'améliorent face à v5 cinq ans, mais rendement perdu dans73,7 %
des cas. Sur dix ans : CAGR **12,28 →11,86 %**, DD **−25,86 →−23,59 %** ;
Calmar légèrement sous Buy & Hold. Réel cinq ans **12,06 →11,28 %** ; le coût
de protection ne respecte pas les critères de conservation du rendement.

La variante de retour sur repli perd1,43 point/an cinq ans et ses trois ratios
se dégradent. L'extension aux trois poches perd0,47 point/an dans son lot cinq
ans, et aggrave certains DD réels. Aucun candidat qualifié en sélection dans
les trois campagnes ; aucun remplacement automatique.
Production **v5 conservée**. Détails des critères, échecs, limites et artefacts :
[recherche rendement/drawdown après v5](sp500-drawdown-frontier-study.md).

## Adoption explicite du compromis 65/35 — 15 novembre 2026

Après présentation des résultats et limites, l'utilisateur demande l'implémentation.
**`core35_slow_defensive_v5` active** : 35 % du capital initial en achat-conservation
PSP5, 65 % dans les règles v4 ; budgets initiaux effectifs48,75/16,25/35 %,
sans transfert ni rééquilibrage entre poches. Pas d'adoption du50/50.
La décision remplace la non-adoption initiale de l'étude ci-dessous ; les critères
manqués, la sous-performance historique cinq ans et les drawdowns plus élevés
face à v4 restent conservés. Pas de validation prospective déduite de l'adoption.
[Implémentation et contrôle indépendant](sp500-core35-adoption.md).

## Recherche élargie et risque assoupli — 15 novembre 2026

L'utilisateur autorise de nouvelles voies et davantage de risque que v4, en
visant un risque inférieur au Buy & Hold et un rendement moins éloigné du marché.
62 configurations : cœur passif/v4, expositions constantes, tendance graduelle,
protection lors de chocs, budgets de baisse CPPI/TIPP, accélération du risque,
cœur investi avec poche graduelle. 100 parcours de sélection et 400 réservés.

Piste figée **65 % v4 /35 % achat-conservation PSP5**, budgets indépendants :
CAGR moyen réservé cinq/dix ans12,93/13,34 % contre11,14/11,49 % v4 ; rendement
supérieur à v4 dans87,3/96 % des parcours, risque intermédiaire sous Buy & Hold.
Trois ratios moyens meilleurs que Buy & Hold cinq ans, Calmar légèrement inférieur
dix ans ; pas de domination générale des trois ratios. 23/24 fenêtres et stress
passent le compromis fixé. Échec formel du seuil de retard cinq ans :3,0111points
contre3,0000 maximum. Réel cinq ans : CAGR12,06 % contre12,34 % v4, DD−11,73 %
contre−7,02 % ; dix ans : CAGR13,04 % contre12,20 %, DD−20,45 % contre−10,95 %.

**Décision initiale : piste de compromis, aucune adoption à la fin de l’étude. Adoption explicite ensuite : voir ci-dessus.** Le50/50 est un contrôle plus exposé,
non qualifié historiquement ; ne pas l'appeler candidat validé. Source de recherche
et limites : [recherche élargie PSP5](sp500-broader-compromise-study.md). La nouvelle
graine ne rend pas l'historique source indépendant ; aucune garantie prospective.

## Recherche rendement / Sharpe, Sortino, Calmar — 14 novembre 2026

Nouvelle demande : améliorer le rendement de v4 sans hausse forte du risque,
avec les trois ratios supérieurs au Buy & Hold ; la surperformance de rendement
face au Buy & Hold n'est plus obligatoire. Deux campagnes supplémentaires,
54 puis 144 paramétrages : allocations graduelles selon la volatilité, exposition
défensive accrue et sorties de continuation, puis intervention moins fréquente.
100 parcours de sélection et 400 réservés par campagne, graines distinctes ;
audit séparé du générateur sur 1 000 marchés distincts, sans changement du modèle.

Première campagne : trois réglages qualifiés en sélection, candidat figé à
+1,53 point de CAGR face à v4 sur 300 nouveaux parcours cinq ans, mais Sharpe
et Sortino sous Buy & Hold. Contre-exemple réel cinq ans : CAGR 10,30 % contre
12,34 % pour v4, DD −18,56 % contre −7,02 %. DD plus profond sur les 24 fenêtres
historiques cinq ans. Seconde campagne : aucun réglage qualifié en sélection ; le diagnostic améliore
les trois ratios moyens face au Buy & Hold sur cinq ans, mais pas sur dix ans,
et le gain de CAGR cinq ans (+0,30 point) reste incertain. DD réel cinq ans
−14,47 % contre −7,02 % pour v4.
**Aucune adoption**, stratégie active et générateur conservés. Colonne « Paires
valides » retirée de l'interface uniquement ; dénominateurs de calcul conservés.
Rapport, détails des lots réservés et limites :
[compromis rendement et ratios PSP5](sp500-ratio-tradeoff-study.md).
Les vérifications de logiciel ne constituent pas une validation financière.

## Comment lire les conclusions

| Statut | Signification |
|---|---|
| Retenue dans l’application | Version effectivement conservée, parfois après adoption explicite malgré des critères de recherche non satisfaits. Ce statut ne prouve pas une rentabilité future. |
| Critères de recherche satisfaits | Conditions annoncées pour l’expérience respectées dans les cas testés. Les critères peuvent autoriser de petites dégradations ; ce n’est pas une garantie. |
| Prometteuse mais non retenue | Amélioration sur certaines périodes, avec des contre-exemples ou une robustesse insuffisante. |
| Non concluante pour l’objectif | La procédure de sélection ou ses audits échouent aux critères. Cela ne démontre pas l’impossibilité de toute amélioration. |
| Retirée à la demande de l’utilisateur | Décision de produit ; ne signifie pas, à elle seule, qu’un échec financier a été démontré. |
| Vérifiée techniquement | Calculs et comportement logiciel testés ; aucune conclusion de surperformance à en déduire. |

**Aucune stratégie du projet ne dispose ici d’une validation prospective démontrée.** Les historiques ont déjà été examinés, les univers peuvent être sélectionnés rétrospectivement et les fenêtres se chevauchent. On ne doit ni additionner les tailles de grilles comme autant d’expériences indépendantes, ni transformer un nombre de fenêtres favorables en probabilité de succès futur.

## Décisions actuelles en un regard

| Sujet | Décision conservée |
|---|---|
| S&P 500 · Régression | **Version v5 active : 65 % v4 / 35 % passif**, adoptée explicitement ; seuils internes v4 inchangés. |
| Retour à la moyenne multi-actifs | Conserver les règles actuelles : entrée −2 σ, armement de sortie +2 σ, vente après repli de 1 σ, financement à partir de +0,3 σ. |
| Volatilité minimale | Conserver la méthode empirique et la bande automatique de révision de 3 points. |
| Corrélation minimale | Conserver l’optimisation continue sur tout l’univers éligible et la bande de 3 points. |
| Parité de risque | Conserver le contrôle des poids et des contributions au risque, bandes de 3 points. |
| Gestion par variance, momentum temporel, Momentum + Régression | Ne pas réintroduire les versions rejetées à l’identique. |
| Simulation aléatoire S&P 500 | Outil d’exploration ajouté uniquement à la stratégie native ; ce n’est pas une nouvelle règle d’investissement. |

## 1. Historique de la recherche S&P 500

Les références « actuelle » dans les anciens rapports désignent la version active **au moment de leur rédaction**, pas nécessairement la version active aujourd’hui.

| Campagne | Essais réalisés | Résultat et limites | Décision |
|---|---|---|---|
| Exploration initiale | 31 752 configurations distinctes : fenêtres de 3 à 60 mois, entrées/sorties, franchissements, sorties après repli, filtres de pente ou moyenne mobile, cadences et exposition défensive. | Aucune configuration sélectionnée selon les procédures annoncées ne passe tous les critères. Une régression longue donne un très bon résultat agrégé, mais peu de transactions et une forte dépendance à la période. La variante défensive réduit le risque récent, avec des rendements et diagnostics longs moins convaincants. | Recherche initialement non concluante ; variante défensive ensuite adoptée explicitement. [Rapport](sp500-regression-study.md). |
| Affinage de la variante défensive | 540 configurations autour des fenêtres 12–24 mois, rebond, sortie, cadence et plancher défensif. | Aucune amélioration de volatilité ne conserve au moins 14 % annualisés sur la période complète étudiée, aux frais prévus. Ce seuil ne constitue pas un rendement garanti ni le résultat sur cinq ans. | Pas de remplacement par une variante d’affinage. La règle 18 mois devient ensuite la poche défensive de la combinaison. [Rapport](sp500-defensive-refinement.md). |
| Recherche élargie au-delà des écarts-types | Deux campagnes de 588 puis 624 configurations, largement communes : moyennes mobiles, momentum, cassures, votes multi-horizons, budget de baisse, ciblage de volatilité, sélection adaptative d’experts et contrôles à exposition constante. | Aucun modèle sélectionné ne satisfait tous les objectifs de rendement, risque et robustesse. Les contrôles distinguent une partie de l’effet des liquidités de la sélection des entrées. | Aucun remplacement retenu. La période spéciale de 2018 est supprimée à la demande de l’utilisateur ; choix 1/3/5/10 ans. [Rapport](sp500-adaptive-risk-study.md). |
| Compromis rendement/drawdown | 22 680 règles individuelles, puis 309 combinaisons ; budget de volatilité assoupli à +30 % relatif, drawdown non aggravé. | Les procédures initiales échouent. Un audit exploratoire après résultats trouve 12 combinaisons améliorant les cinq/dix ans avec des gains plus modestes. La combinaison 75/25 ne respecte le compromis que sur 10/14 fenêtres et aggrave certains drawdowns, notamment sur les diagnostics USD. | Combinaison 75 % lente / 25 % défensive adoptée explicitement en v2 malgré ces limites. [Rapport](sp500-return-drawdown-study.md). |
| Sorties et réentrées de la combinaison | 792 configurations : sorties conditionnelles, réentrées, planchers, budgets et calendriers. Diagnostic supplémentaire de sensibilité des seuils. | Aucune ne passe la sélection initiale. Une entrée lente supplémentaire au franchissement haussier de 0 σ améliore les cinq/dix ans, avec les mêmes drawdowns sur ces horizons ; gain absent sur les premières périodes et volatilité relative trop élevée dans certains cas. Le gain disparaît avec plusieurs seuils voisins. | Réentrée à 0 σ adoptée explicitement en v3. [Rapport](sp500-next-iteration-study.md). |
| Retard sur trois ans et état initial | 99 ajustements plus témoin, puis audit de la piste figée sur 166 départs mensuels de trois/cinq ans. | Une cause importante du retard est le redémarrage défensif qui ignore l’état lent acquis auparavant. Le rejouer améliore 59 rendements et laisse 107 identiques face à v3 ; 16 drawdowns sont légèrement aggravés, au plus 0,138 point. Le trois ans reste hors des limites initiales de volatilité et d’écart au témoin. | Initialisation lente reconstituée adoptée explicitement en **v4**, sans créditer aucun gain antérieur. [Rapport](sp500-three-year-study.md). |
| Affinage après adoption de v4 | 72 paramétrages, soit 68 variantes distinctes : poids, planchers, seuils et cadence défensifs, filtres de baisse, combinaisons. Vérification sur 166 fenêtres, frais doublés, retard supplémentaire et indice USD long. | Aucun candidat ne passe tous les critères annoncés. Deux pistes modestes améliorent les trois horizons récents mais présentent des contre-exemples. Voir les tableaux ci-dessous. | **V4 conservée à la demande explicite de l’utilisateur. Pistes 1 et 2 non intégrées.** [Rapport](sp500-v4-refinements-study.md). |

### Règles historiques de v4, désormais conservées dans le budget actif de v5

Identifiant : `slow_defensive_warm_state_v4`.

- ESE.PA uniquement, S&P 500 PEA en EUR, sans levier ni actif inverse.
- Budgets initiaux indépendants : 75 % pour la poche lente et 25 % pour la défensive, sans transfert ni rééquilibrage entre poches.
- Chaque poche vise 25 % d’exposition en état défensif et 100 % en état investi, à l’initialisation ou au changement d’état ; les poids dérivent ensuite.
- Lente : régression logarithmique 60 mois, entrée sous −2 σ ou au franchissement haussier de 0 σ depuis la séance précédente, sortie au-dessus de +1,5 σ, contrôle à la première séance du mois.
- Défensive : régression 18 mois, entrée au franchissement haussier de −0,5 σ, sortie au-dessus de +1,5 σ, contrôle toutes les cinq séances depuis le début de la simulation.
- État initial lent reconstitué avec les décisions strictement antérieures au départ ; poche défensive initialement défensive. Capital neuf et achats ultérieurs avec frais, aucun titre ni profit antérieur offert.
- Exécution à la clôture suivante, frais par poche, titres entiers dans les tableaux ci-dessous, liquidités non rémunérées.

Protocole complet : [validation historique](validation.md). Vérificateur actif : `scripts/verify_sp500_warm_state.py`, **20 cas figés**. Les anciens vérificateurs défensif/compromis/réentrée concernent les versions historiques, pas la production actuelle.

### Comparaison complète des deux dernières pistes

**Piste 1** : seule la sortie de la poche défensive passe de +1,5 à +1,75 σ.

**Piste 2** : même sortie à +1,75 σ et plancher défensif des deux poches réduit de 25 à 15 %. Budgets toujours 75/25.

ESE en EUR, 10 000 € initiaux, frais 0,5 % par achat/vente, titres entiers, fin au **13/11/2026**. Débuts effectifs : 13/11/2023, 15/11/2021 et 14/11/2016. Rendement et volatilité annualisés, Sharpe à taux sans risque nul. Frais déjà déduits des rendements et capitaux.

| Horizon | Variante | CAGR | Volatilité | Drawdown maximal | Sharpe | Capital final | Frais cumulés |
|---|---|---:|---:|---:|---:|---:|---:|
| 3 ans | Actuelle v4 | 15,68 % | 8,37 % | −7,02 % | 1,760 | 15 480,68 € | 139,74 € |
| 3 ans | Piste 1 | 16,13 % | 8,74 % | −7,02 % | 1,733 | 15 661,22 € | 127,77 € |
| 3 ans | Piste 2 | 15,77 % | 8,34 % | −6,84 % | 1,776 | 15 517,77 € | 138,11 € |
| 5 ans | Actuelle v4 | 12,25 % | 8,33 % | −6,99 % | 1,406 | 17 808,54 € | 231,32 € |
| 5 ans | Piste 1 | 12,45 % | 8,47 % | −6,98 % | 1,405 | 17 970,82 € | 203,60 € |
| 5 ans | Piste 2 | 12,57 % | 8,02 % | −6,80 % | 1,493 | 18 063,72 € | 225,46 € |
| 10 ans | Actuelle v4 | 14,06 % | 9,71 % | −8,85 % | 1,382 | 37 248,01 € | 704,01 € |
| 10 ans | Piste 1 | 14,22 % | 9,76 % | −8,80 % | 1,389 | 37 757,97 € | 651,58 € |
| 10 ans | Piste 2 | 14,14 % | 9,30 % | −8,04 % | 1,446 | 37 517,54 € | 728,97 € |

La piste 2 améliore les quatre indicateurs rendement/volatilité/drawdown/Sharpe sur ces trois horizons. Ce constat est réel **sur ces périodes**, mais insuffisant pour conclure à une meilleure protection sur le long terme.

| Audit des 166 fenêtres chevauchantes | Piste 1 | Piste 2 |
|---|---:|---:|
| Rendements annualisés supérieurs | 143 | 86 |
| Rendements annualisés identiques | 19 | 0 |
| Rendements annualisés inférieurs | 4 | 80 |
| Drawdowns plus profonds | 43 | 15 |
| Plus forte aggravation du drawdown | 6,36 points de perte | 3,76 points de perte |

Contre-exemples à conserver :

- **Piste 1, cinq ans depuis janvier 2017** : drawdown −8,84 → **−15,21 %**, malgré un meilleur rendement.
- **Piste 2, cinq ans depuis octobre 2016** : drawdown −8,84 → **−12,60 %**.
- **Piste 2, trois ans depuis février 2016** : CAGR 6,69 → **5,69 %**.
- Diagnostic distinct sur l’indice total-return USD long : piste 2, CAGR 6,87 → 6,69 %, drawdown −57,18 → −58,37 %. Cet indice n’est pas l’historique négociable de l’ETF PEA en EUR.

Les gains récents des deux pistes subsistent sous frais doublés et avec une séance de retard supplémentaire, mais ces stress ne suppriment pas les contre-exemples de période. La piste 2 reste la plus intéressante à approfondir ; **aucune supériorité générale démontrée, aucune adoption**.

### Autres résultats négatifs utiles à ne pas oublier

- Réduire seulement le plancher à 20 % diminue les drawdowns récents, mais baisse le rendement dans 100/166 fenêtres : compromis plus défensif, pas gain de rendement général.
- Contrôler la poche défensive quotidiennement augmente le drawdown trois ans à −9,68 % et réduit le CAGR cinq/dix ans : réactivité supplémentaire non concluante.
- Passer à une décision toutes les dix séances améliore le trois ans, mais diminue le rendement cinq/dix ans.
- Le filtre de baisse MA200 + momentum inférieur à −5 %, plafond 25 % sur les deux poches, réduit fortement les pertes de la crise USD 2007–2009, mais ramène le CAGR ESE dix ans de 14,06 à 12,24 % et perd en rendement dans 158/166 fenêtres. Une seule crise favorable ne suffit pas.
- La combinaison sélectionnée avant l’audit récent, 85/15 avec plancher 15 % et sortie défensive +1,75 σ, est différente des pistes 1/2. Ses gains de rendement récents s’accompagnent de drawdowns trois/cinq ans plus profonds ; elle n’est pas adoptée.

## 2. Simulation aléatoire : ce qui est vérifié, ce qui ne l’est pas

L’onglet ajouté n’optimise pas la stratégie et ne remplace pas la validation historique. Il compare le Buy & Hold et **la v4 inchangée sur le même parcours fictif**, avec les mêmes frais, conventions de titres et dates d’exécution.

Construction : séquences de rendements historiques ESE EUR, blocs de longueur moyenne 63 séances et petit bruit indépendant égal à 5 % de la volatilité quotidienne historique. Départ au dernier cours connu, historique réel pour initialiser les régressions. Un nouveau tirage à chaque demande, sans filtrage pour obtenir un gagnant. Une graine identique reproduit le parcours ; prolonger son horizon conserve son préfixe. Les données fictives ne sont pas enregistrées dans la base utilisateur.

| Contrôle | Résultat | Conclusion autorisée |
|---|---|---|
| Baisses de marché d’au moins 30 % sur 200 tirages par horizon | 9 sur un an ; 40 sur trois ans ; **60 sur cinq ans** ; 113 sur dix ans. | Le générateur permet de fortes baisses sans les imposer à tous les tirages. Ce ne sont pas des probabilités futures. |
| Neuf scénarios avec le moteur réel | Graines 0/1/42, horizons 1/5/10 ans : politique exacte, capital initial en base 100, chronologie des ordres, cash non négatif et métriques finies vérifiés. | Comptabilité et intégration vérifiées dans ces scénarios. |
| Tirages différents et reproductibles | Tests réussis, y compris titres entiers/fractionnaires et conservation des données historiques. | Fonctionnement aléatoire et reproduction contrôlés. |
| Surperformance générale de la stratégie dans ce générateur | **Non établie par un bilan agrégé de rendement/risque.** Les neuf scénarios précédents ne sélectionnent pas de meilleure stratégie. | Ne pas annoncer un taux de réussite ni une validation prospective. |

Les comptes correspondent au générateur final avec flux séparés pour blocs et bruit. Un compte préliminaire communiqué pendant le développement (68/200 sur cinq ans) concernait la version précédente du générateur ; le rapport final reproductible fait foi : **60/200**.

Le modèle reste limité aux régimes présents depuis septembre 2013 dans l’historique ESE disponible. Il ne reconstitue pas fidèlement toutes les crises anciennes. Les dates futures sont fictives, en jours de semaine, sans retrait des jours fériés boursiers.

[Protocole détaillé et limites](sp500-simulation.md) ; script : `scripts/verify_sp500_simulation.py` ; résultat local : `data/backtests/sp500-simulation-verification.json`.

## 3. Autres stratégies et réduction des frais

| Sujet / campagne | Résultats documentés | Bilan et décision | Rapport |
|---|---|---|---|
| Retour à la moyenne multi-actifs | Sur l’univers utilisateur de 14 actifs, 15/11/2021–13/11/2026, 10 000 € → 43 080,84 €, drawdown −16,22 %, Sharpe environ 1,68, frais 0,5 %. Résultats moins bons sur d’autres périodes/univers. | Retenue, sans succès universel démontré. Paramètres actuels à préserver ; les premiers essais aux anciens seuils sont historiques. | [Comparaisons quantitatives](quantitative-strategies-study.md), [anciens essais de seuils](reversion-threshold-study.md), [moteur](validation.md). |
| Variance gérée, adaptation Moreira–Muir | Cinq ans : 21 746,88 € contre 25 321,50 € pour le contrôle équipondéré mensuel comparable. | Non retenue : protection plus défensive, mais critères de rendement/Sharpe/frais non satisfaits. Échec de l’adaptation locale, pas réfutation de l’article. | [Étude](quantitative-strategies-study.md). |
| Momentum temporel avec contrôle du risque | Cinq ans : 21 059,51 € ; critères fixés avant calcul non satisfaits. | Non retenu, recherche seulement. | [Étude](quantitative-strategies-study.md). |
| Momentum + Régression 70/30 | Mémoire de session : 24 567,83 € contre 26 486,20 € pour l’équipondération trimestrielle et 43 080,84 € pour le retour à la moyenne, sur les cinq ans considérés. Fichiers spécifiques supprimés. | Échec pour l’objectif poursuivi ; onglet et simulation retirés. Ne pas présenter ces chiffres comme une étude intégralement reproductible disponible. | Mémoire conservée dans [AGENTS.md](../AGENTS.md). |
| Premier examen des bandes, de la covariance OAS et du filtre AR(1) | 108 calculs. Filtre de retour à la moyenne : drawdown réduit de 16,22 à 14,77 %, mais Sharpe de 1,68 à 1,51 sur les cinq ans du journal. OAS ne domine pas le contrôle. | Filtre automatique non retenu ; diagnostics descriptifs privilégiés. Le premier statut des bandes, alors inactives, est remplacé par les études suivantes. | [Premier bilan](allocation-improvements.md). |
| Bandes de révision et allocations par groupes | 168 simulations. Tolérance volatilité/corrélation : 0 échec sur 24 cas chacune selon les limites fixées ; plafond par groupe : 2 échecs ; allocation par groupes : 12. | Bandes de **3 points retenues** ; plafond et allocation par groupes rejetés. Passer les tolérances ne signifie pas améliorer chaque indicateur dans chaque cas. | [Trois optimisations](three-optimizations-study.md). |
| Parité de risque : bandes sur poids et contributions | 96 simulations. Les trois variantes passent leurs critères ; préférence initiale pour la combinaison. Sur cinq ans du journal : frais 259,30 → 247,94 €, CAGR 22,20 → 22,47 %, drawdown identique −15,22 %. | Combinaison des deux bandes de 3 points retenue. Le réglage poids seuls économise davantage sur cette fenêtre, mais suit moins directement l’objectif de contribution au risque. | [Rééquilibrage et risque](risk-rebalancing-study.md). |
| Corrélation minimale | 288 validations communes volatilité/corrélation. Suppression du plancher de poids et de la cardinalité imposée, optimisation continue sur tout l’univers éligible. | Révision retenue : deux actifs corrélés ne sont plus éliminés par une règle de paire ; aucune indépendance ni surperformance générale promise. | [Révision des allocations](risk-allocations-review.md). |
| Volatilité minimale | Même campagne : nouvelles estimations et variantes réactives ne passent pas les critères préfixés. | Conserver la covariance empirique actuelle. Minimiser une variance estimée ne garantit pas la volatilité réalisée la plus faible. | [Révision des allocations](risk-allocations-review.md). |
| Facteurs santé/biotech dans la simulation macro | Sur six actions examinées, erreur de validation améliorée dans trois cas et dégradée dans trois autres. | Non intégrés : échantillon limité et absence d’amélioration globale démontrée. Ce modèle est distinct de la simulation aléatoire S&P. | [Audit Covid et santé](simulation-health-audit.md). |

Les chiffres de cette section proviennent de campagnes différentes, avec des instantanés et contrôles propres. Ne pas les classer dans un seul palmarès comme s’ils partageaient toutes les mêmes conditions.

### Retraits qui ne constituent pas une conclusion de performance

CVaR, CAC 40 inverse à levier, journal prospectif et contrôles d’exécution/spread ont été retirés ou écartés à la demande de l’utilisateur. Leur retrait ne démontre pas, à lui seul, un échec économique mesuré. Ne pas inventer de statistiques de comparaison pour ces sujets ; les règles produit sont consignées dans [AGENTS.md](../AGENTS.md).

## 4. Sources, résultats bruts et vérifications

Les rapports liés ci-dessus indiquent leurs scripts, configurations, frais, périodes, contrôles et empreintes de copies SQLite. Les expériences utilisent des copies privées ; elles ne doivent pas modifier la base utilisateur.

Les sorties détaillées JSON sont généralement **locales et ignorées par Git** dans `data/backtests/`. Les documents Markdown conservent les conclusions et résultats essentiels ; partager seulement le dépôt ne partage pas nécessairement les sorties brutes ni les données nécessaires pour les régénérer. Certains anciens fichiers ont été supprimés à la demande de l’utilisateur : leur absence est signalée, pas compensée par une reconstruction supposée.

Dernier contrôle global lors de l’intégration de la simulation aléatoire : **417 tests backend, 37 tests frontend et 28 parcours navigateur ordinateur/mobile réussis**, contrôles Ruff, frontend et build réussis. Il s’agit d’un état daté des vérifications, pas d’une exécution automatique à chaque lecture de ce document. Les avertissements de dépendances et de taille de bundle n’ont pas bloqué ces contrôles.

Ces tests vérifient des propriétés logicielles et des scénarios contrôlés. Ils ne prouvent ni la rentabilité, ni l’absence de tout bug, ni la généralisation future des stratégies. Les comparaisons financières doivent conserver les mêmes dates, frais, actifs éligibles, règles de titres entiers, convention de dividendes et disponibilité historique.

## 5. Consigner la prochaine expérience

Ajouter une entrée datée avant de lancer une nouvelle campagne, puis compléter son bilan après calcul :

1. Objectif et changement exact par rapport à une version de référence identifiée.
2. Données, devise, périodes, préparation historique, capital, frais et exécution.
3. Critères de sélection et d’adoption fixés avant les résultats ; liste des variantes.
4. Résultats complets, rendement/volatilité/drawdown/Sharpe/frais et contre-exemples.
5. Stress, sensibilité aux paramètres et dates de départ ; distinguer les fenêtres chevauchantes.
6. Conclusion de recherche, décision utilisateur et statut effectif dans l’application, séparément.
7. Liens vers le rapport détaillé, les scripts, les sorties brutes et les vérifications.

Une hypothèse non encore testée doit rester indiquée comme telle. Une adoption ultérieure ne doit pas effacer les critères échoués ni réécrire la conclusion initiale. Lorsqu’une nouvelle version est intégrée, conserver l’identification de l’ancienne référence pour éviter des comparaisons ambiguës.


## Mise à jour Amundi et vérification de lots — 14 novembre 2026

Remplacement applicatif ESE par PSP5, frais S&P par défaut0,12 %, sans modifier les règles v4. Les anciens chiffres ne sont pas transférés au nouvel instrument. Migration locale des références avec sauvegardes, quantités numériques conservées ; aucune conversion à valeur constante.

Sur1000parcours synthétiques5ans (graines0–999, cours PSP5 propres), le moteur complet termine sans erreur : Régression gagne145fois sur le CAGR,984fois sur le drawdown,1000fois sur la volatilité et506fois sur le Sharpe. Moyennes : CAGR15,15/10,92 %, DD−25,23/−19,17 %, volatilité16,59/12,29 %, Sharpe0,923/0,928 (Buy & Hold/Régression). Ce résultat vérifie l’outil et décrit ce générateur ; il ne valide pas une surperformance prospective et ne déclenche aucune optimisation.

Rapport actuel : `data/backtests/sp500-amundi-simulation-verification.json`. Détail et limites : [simulation S&P](sp500-simulation.md). Source originale BNP conservée dans l’ancien rapport. Vérifications :422tests backend,40tests unitaires frontend et parcours navigateur du nouveau mode sur ordinateur/mobile ; contrôle HTTP réel du flux progressif et de la disponibilité simultanée de l’API.

## Recherche de surperformance Amundi après les lots aléatoires — 14 novembre 2026

Demande : augmenter le rendement au-delà du Buy & Hold, réduire nettement volatilité
et drawdown, sans changer opportunément les horizons cinq/dix ans.

[Étude complète et tableaux](sp500-amundi-upside-study.md) : 405 paramétrages
(dont un équivalent au témoin explicite) : tendances avec hystérésis, votes,
protections de baisse/réentrées, volatilité conditionnelle, replis RSI et
continuation/protection de la régression. Plans persistés avant les résultats,
sélection sur 2016–2020 et 2021–2023, copie privée, PSP5 EUR, 10 000 €, frais
0,12 %, titres entiers, clôture suivante, cash non rémunéré, aucun levier.

**Aucune nouvelle règle ne satisfait les critères.** Aucun paramétrage nouveau
ne bat même le rendement du Buy & Hold dix ans. L’actuelle bat le témoin réel
cinq ans (CAGR12,34 contre11,60 %, DD−7,02 contre−23,18 %), mais sous-performe
dix ans (12,20 contre14,49 %, DD−10,95 contre−33,67 %). La meilleure performance
dix ans observée après calcul monte à13,56 %, avec DD−18,26 % et recul cinq ans :
ce n’est pas une amélioration suffisante ni une sélection valide.

Audits :24fenêtres cinq ans trimestrielles chevauchantes, frais doublés,
retard supplémentaire ; quatre diagnostics sur1000parcours par horizon cinq/dix
ans, puis v4/continuation sur100parcours par horizon. Mêmes graines et mêmes
marchés pour chaque paire, aucun changement du générateur ni filtrage gagnant.
Les variantes ne satisfont pas l’objectif ; production v4 conservée, aucune
nouvelle adoption. JSON et scripts reproductibles liés dans l’étude.

Textes du simulateur retirés selon la demande (explications, résumé du tirage,
légende textuelle des couleurs et ligne Capital final), sans changer les valeurs
ni le modèle. Vérifications :40tests unitaires frontend et30parcours navigateur
ordinateur/mobile, compilation/lint/format/knip et Ruff réussis ; témoins financiers
comparés à la production, causalité des signaux et calcul vectorisé vérifiés.
