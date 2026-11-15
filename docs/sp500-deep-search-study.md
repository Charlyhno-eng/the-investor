# Recherche approfondie face à la régression v5 — 15 novembre 2026

Demande : poursuivre la recherche internet et trouver davantage de rendement
avec un drawdown comparable ou inférieur à la stratégie actuelle. Référence :
**v5, 65 % v4 / 35 % PSP5 passif**, titres entiers, frais 0,12 % par ordre.
Aucun levier, vente à découvert, dérivé ou changement de base utilisateur.
Recherche isolée, aucune adoption automatique.

**Bilan : aucune réussite de l'objectif initial de +0,5 point annualisé.**
Une piste passe le protocole secondaire de petit gain : **v5 inchangée sauf
sortie défensive portée de +1,5 à +1,75 sigma** (variante 1250). Cette piste,
déjà observée face à v4, est réexaminée face à v5 ; ce n'est pas une nouvelle
découverte de ce seuil. Elle n'est pas adoptée.

| Historique PSP5 jusqu'au 13/11/2026 | CAGR v5 → piste | DD v5 → piste |
|---|---:|---:|
| Trois ans |17,14→17,41 %|−12,38→−12,38 %|
| Cinq ans |12,06→12,15 %|−11,73→−11,71 %|
| Dix ans |13,04→13,14 %|−20,45→−20,37 %|

Sur les nouveaux lots secondaires : gain moyen de CAGR +0,1074/+0,0934 point
sur cinq/dix ans, mais DD moyen **plus profond de 0,1694/0,2522 point**.
24/24 fenêtres respectent les tolérances ; 22 ont un meilleur CAGR et 2 sont
identiques, 17 un meilleur DD et 7 identiques. Frais doublés et retard supplémentaire
conservent les critères secondaires. Ce succès tolère une petite aggravation
moyenne du risque et ne signifie pas surperformance ou protection sur tout parcours.

Contre-exemples essentiels : sur cinq ans, 129/1000 parcours ont un CAGR inférieur,
84 un DD aggravé de plus de 0,5 point, 44 de plus de 2 points. Sur dix ans : 36/300
ont un CAGR inférieur, 34 un DD aggravé de plus de 0,5 point, 22 de plus de 2 points.
Graine 1620017 : DD −38,04→−42,91 %, CAGR 8,34→7,68 % ; graine 1630274 :
DD −37,74→−42,85 %, CAGR 6,43→5,99 %. **Une aggravation du DD de 5,11 points
existe donc dans ce lot malgré une faible aggravation moyenne.** Les anciens
43/166 DD dégradés de la même sortie sous v4, sur l'ancien ESE à frais 0,5 %,
restent documentés dans
[l'affinage v4](sp500-v4-refinements-study.md) ; ce n'est pas le même compte v5.
L'historique répété et le générateur commun limitent toute conclusion prospective.

**Le contrôle mensuel plus dense empêche de conclure à une amélioration stable.**
Déclaré après le succès secondaire, il porte sur tous les 168 départs mensuels
admissibles PSP5 de trois/cinq ans, sans changer le candidat : 96 fenêtres trois
ans et 72 cinq ans. Trois ans : 64 CAGR meilleurs, 29 identiques, 3 inférieurs,
13 DD plus profonds. Cinq ans : 61 CAGR meilleurs, 11 identiques, aucun inférieur,
mais 10 DD plus profonds. Au total **23/168 DD dégradés**, aggravation maximale
**4,09 points**. Le passage du contrôle trimestriel ne résiste donc pas à une
affirmation de préservation du drawdown sur tous les départs.

Exemple parmi cette grille complète, 13/09/2018–13/09/2023 : CAGR 11,41→12,44 %,
mais DD −19,19→−23,28 % ; sur les trois premières années du même départ,
CAGR 14,58→16,23 %, même aggravation du DD. Ce n'est pas une période spéciale
de l'application : les dates viennent de l'audit exhaustif des départs mensuels.
Les états lents sont réchauffés, capital neuf et état défensif initial restent
ceux du moteur courant pour chaque départ ; il s'agit de comptes nouvellement
initialisés, pas de segments d'un unique compte continu.

Rapport distinct : `data/backtests/sp500-modest-edge-monthly.json`, script
`scripts/audit_sp500_modest_edge.py` (exécution avec `PYTHONPATH=backend:scripts`
et `.venv/bin/python`). Les caractéristiques causales sont
calculées une fois et réutilisées uniquement pour les mêmes dates/prix ; cela
ne change pas les valeurs ni les règles d'exécution. Ces résultats restent
distincts du succès conditionnel au protocole secondaire de 24 fenêtres : ils
ne l'effacent pas, mais rendent une adoption injustifiée pour l'objectif de
drawdown stable. **La production reste v5 sans modification.**

## Sources consultées et adaptations

| Source primaire | Piste étudiée et différence d'implémentation |
|---|---|
| [Zarattini–Antonacci, Industry Trends](https://concretumgroup.com/wp-content/uploads/2026/02/A-Century-of-Profitable-Industry-Trends.pdf) | Canaux de prix et sorties asymétriques. Ici : clôtures PSP5 seules, pas de rotation sectorielle, Keltner intrajournalier ni levier. Les 18,2 % mis en avant concernent la version à plafond d'exposition 200 %. Le tableau 4 distingue une version sans levier : ne pas transférer les résultats publiés à notre adaptation. |
| [Ang–Bekaert, régimes et allocation](https://www.nber.org/papers/w10080), [Ang–Timmermann](https://www.nber.org/papers/w17182) | Probabilité de régime de marché et exposition graduelle. Paramètres de transition et de distribution fixés avant les résultats, volatilité causale ; pas de probabilités révisées avec le futur ni de reproduction exacte des portefeuilles internationaux des auteurs. |
| [Zakamulin–Giner, règles optimales en modèles à deux états](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4217513) | La théorie semi-markovienne motive l'examen d'un signal de type MACD ; notre règle de confiance sur deux EMA est une adaptation, pas une estimation du modèle semi-markovien ni sa reproduction. |
| [Benhamou, filtre de Kalman](https://arxiv.org/abs/1811.11618) | État niveau logarithmique/vitesse, estimation récursive. Un filtre causal est utilisé ; un lisseur qui regarderait les observations ultérieures serait inadmissible. |
| [Page, Continuous Inspection Schemes](https://doi.org/10.1093/biomet/41.1-2.100) | Somme cumulative de rendements négatifs standardisés pour détecter une rupture, avec réentrée sur reprise. Page propose une méthode statistique de détection, pas une preuve de rendement financier de cette adaptation. |
| [Li–Hoi, OLMAR, ICML 2012](https://icml.cc/2012/papers/168.pdf) | Apprentissage du retour à la moyenne, adapté à deux composantes ETF/cash. Plafond du changement de cible et frais réels à l'exécution suivante ; poids théoriques indicatifs distincts du compte d'exécution avec titres entiers. |
| [Györfi–Lugosi–Udina, stratégies séquentielles à noyau](https://onlinelibrary.wiley.com/doi/10.1111/j.1467-9965.2006.00274.x) | Apprendre les réponses de marché à partir de situations passées similaires. Notre estimateur conditionnel régularisé, sur trois caractéristiques et horizon cinq séances, est une adaptation. Les seules étiquettes d'entraînement autorisées sont entièrement réalisées à la date du signal. |
| [Moon et al., réexamen empirique du retour à la moyenne](https://arxiv.org/abs/1909.04327) | Contrepoint : résultats très dépendants des données et des coûts. Les frais ne sont pas omis pour favoriser les méthodes d'apprentissage. |
| [Busseti–Ryu–Boyd, Kelly contraint en risque](https://www.web.stanford.edu/~boyd/papers/kelly.html) | Source examinée pour le dimensionnement croissance/risque ; aucune garantie de drawdown de ce modèle théorique n'est attribuée aux règles étudiées. Pas de réintroduction de CVaR. |
| [Asness–Ilmanen–Maloney, Market Timing: Sin a Little](https://www.aqr.com/Insights/Research/Journal-Article/Market-Timing-Sin-a-Little) | Complémentarité possible entre signaux contraires et momentum. CAPE non testé ici faute d'historique daté de publication correctement intégré ; aucune valorisation reconstruite avec le futur. |

Huit familles tactiques : canaux, Markov, MACD, Kalman, CUSUM, OLMAR,
prédiction conditionnelle à noyau, retournement court conditionné par Markov.
Chacune est testée seule et avec des budgets v4 indépendants de 35 % ou 65 %.
La neuvième famille recherche conjointement le poids passif, le partage interne
lent/défensif, le plancher, la sortie et la cadence défensives, et la sortie lente.
Certaines valeurs ont déjà été explorées face à v4 ; leur combinaison contre v5
est une nouvelle comparaison, pas la découverte de ces paramètres.

**1 356 configurations :** 60 canaux, 72 Markov, 48 MACD, 72 Kalman,
36 CUSUM, 108 OLMAR, 48 noyau, 48 retournement conditionnel, 864 régressives.
Les paramètres complets sont écrits dans le JSON avant les résultats.

## Critères fixés avant calcul

Sur les **200 marchés de sélection cinq ans**, CAGR moyen au moins v5 +0,5 point,
perte maximale moyenne au plus v5 +0,5 point, 95e percentile des pertes maximales
au plus v5 +1 point, volatilité au plus 110 % de v5, Sharpe et Sortino au moins
v5 −0,03. Les historiques 3/5/10 ans sont déjà examinés : pour chacun, CAGR au
moins v5 −0,25 point, drawdown au plus 1 point plus profond, volatilité au plus
110 % v5 ; gain de CAGR moyen sur ces horizons au moins 0,5 point.

Sélection parmi les admissibles par CAGR moyen puis perte du 95e percentile.
Si aucun n'est admissible, figer un diagnostic minimisant la pire violation
normalisée ; ce mécanisme ne transforme pas un échec en adoption. Un champion
par famille est également figé, avec la même procédure. Aucun nouveau choix
selon les lots réservés.

Audit des seuls champions figés : **1 000 marchés cinq ans et 300 dix ans**,
mêmes critères synthétiques sur chaque horizon. En plus : borne basse à 95 %
du gain apparié de CAGR strictement positive et borne basse de l'amélioration
du drawdown au moins −0,5 point. Au moins 75 % des 24 fenêtres cinq ans à
départs trimestriels conservent le CAGR à 0,5 point près, le drawdown à 1 point
près et la volatilité sous 115 % v5. Les frais doublés et une séance de retard
supplémentaire doivent conserver les critères historiques 3/5/10 ans.
Tous les critères sont nécessaires pour un succès de procédure.

Graines sélection : 1310000–1310199 ; audit cinq ans : 1320000–1320999 ;
dix ans : 1330000–1330299. Bootstrap apparié descriptif, 2 000 rééchantillonnages,
sans correction pour la multiplicité. Les nouveaux tirages proviennent du même
historique et ne constituent pas de nouvelles observations économiques.

## Exécution et vérification

Copie SQLite privée, historique propre PSP5 ajusté en EUR, 10 000 €, cash à 0 %,
titres entiers et frais sur chaque opération. Signal connu à la clôture puis
exécution à la suivante. Comptes séparés avec leurs vrais budgets : aucune
moyenne artificielle de courbes à 10 000 €. Pas de liquidation finale fictive.
Les états antérieurs sont rejoués sans profits antérieurs. Aucun transfert
entre poches. Bande de 5 points pour les ajustements tactiques.

Les ratios indéfinis d'un parcours entièrement en cash sont conservés comme
`null`, avec leurs dénominateurs valides ; le parcours n'est jamais supprimé.
Chaque ratio conditionnant l'admissibilité doit être défini sur au moins 95 %
des parcours. Pendant l'amorçage des fenêtres de volatilité, hypothèse fixe
16 % annualisés, jamais remplissage depuis des données futures.

Le moteur de recherche trois ans accepte `keep_trace=False` pour ne pas
conserver les journaux d'exécution volumineux pendant cette grille. Le défaut
reste inchangé ; courbes et métriques doivent rester exactement identiques.
Aucun fichier du moteur de production n'est modifié.

```sh
PYTHONPATH=backend:scripts .venv/bin/python scripts/study_sp500_deep_search.py --workers 4
# Reprise : protocole, grille, empreinte et choix figés doivent rester identiques.
PYTHONPATH=backend:scripts .venv/bin/python scripts/study_sp500_deep_search.py --resume --workers 4
```

Sortie distincte : `data/backtests/sp500-deep-search.json`, incluant tous les
candidats de sélection, tous les parcours des champions, critères et échecs.

## Limites

Historique PSP5 depuis 2014 : ni crise 2000 ni crise 2008 observée sur cet ETF.
Pas de substitution silencieuse par un indice USD. Fenêtres chevauchantes,
multiples campagnes déjà effectuées, biais de sélection accru. Fiscalité omise,
cash non rémunéré, calendrier synthétique en jours de semaine et convention
métrique 252 séances inchangés. Les filtres supposent des modèles qui peuvent
être faux et les ordres peuvent subir un écart de cours. Les tests logiciels
ne constituent pas une validation financière.

## Résultats

**Aucun des 2 409 réglages ne réussit la sélection initiale.** Les neuf
champions de familles de la première branche et les deux champions des autres
branches sont des diagnostics figés, sans qualification ni adoption.
Les quatre variantes de l’audit secondaire restent distinctes de cette procédure.
Les trois branches et cet audit ont été entièrement terminés : 600 marchés de
sélection,5 200 réservés ; historiques, fenêtres et stress conservés.

### Neuf familles : résultats réservés

Chaque cellule montre le **gain de CAGR / variation du drawdown signé**,
en points, face à v5 sur les mêmes parcours. Une variation de drawdown positive
est une amélioration ; négative, une perte plus profonde. Moyennes de 1 000
parcours cinq ans et 300 dix ans. Aucun résultat de ce tableau ne réussit toute
la procédure ; un gain de rendement seul ne suffit pas.

| Famille figée | Cinq ans : ΔCAGR / ΔDD | Dix ans : ΔCAGR / ΔDD | Fenêtres acceptables |
|---|---:|---:|---:|
| regression_joint | 0,47 / -0,76 | 0,36 / -0,75 | 23/24 |
| channel | -1,26 / 2,45 | -1,41 / 3,14 | 0/24 |
| cusum | -0,14 / 1,60 | -0,18 / 2,27 | 24/24 |
| kalman | -1,08 / 1,55 | -1,21 / 1,89 | 0/24 |
| kernel | -0,75 / 0,68 | -0,88 / 0,99 | 2/24 |
| macd | -0,64 / 0,72 | -0,76 / 1,06 | 0/24 |
| markov | -0,68 / 2,03 | -0,66 / 2,90 | 8/24 |
| olmar | -3,50 / 5,31 | -3,49 / 5,90 | 0/24 |
| regime_reversal | -1,63 / 2,74 | -1,76 / 3,33 | 0/24 |

### Champions des deux branches supplémentaires

| Branche | Horizon | CAGR v5 → diagnostic | DD moyen v5 → diagnostic | Fenêtres |
|---|---:|---:|---:|---:|
| Continuation | 5 ans | 12,67 → 13,04 % | -20,83 → -21,47 % | 24/24 |
| Continuation | 10 ans | 12,59 → 12,82 % | -25,53 → -26,25 % | 24/24 |
| Experts séquentiels | 5 ans | 12,63 → 12,51 % | -20,80 → -18,06 % | 16/24 |
| Experts séquentiels | 10 ans | 12,18 → 11,97 % | -25,05 → -21,29 % | 16/24 |

### Audit secondaire des petits gains

Ces quatre variantes étaient choisies après examen des sélections, puis figées
avant leurs nouveaux lots réservés. Elles ne deviennent pas des stratégies validées
grâce à un objectif abaissé. Le seuil de +0,5 point initial reste un échec.

| Indice initial | Cinq ans : ΔCAGR / ΔDD | Dix ans : ΔCAGR / ΔDD | Fenêtres | Procédure secondaire |
|---|---:|---:|---:|---|
| 1056 | 0,28 / -0,48 | 0,16 / -0,57 | 24/24 | Échec |
| 1322 | 0,24 / -0,41 | 0,18 / -0,57 | 24/24 | Échec |
| 1316 | 0,17 / -0,31 | 0,13 / -0,43 | 24/24 | Échec |
| 1250 | 0,11 / -0,17 | 0,09 / -0,25 | 24/24 | Réussie |

**Variante 1056 :** passif 20 %, partage lent/défensif interne 85/15, plancher 35 %, sortie défensive +1,75 sigma, cadence 1 séance.

- 5 ans réservé : CAGR 12,64→12,93 %, DD -20,49→-20,97 %, pertes du 95e percentile 33,94→34,72 %. IC95 du gain CAGR [0,26;0,31] point ; amélioration du DD [-0,55;-0,41] point. Rendement supérieur sur 747/1000 parcours. Critères synthétiques secondaires : échec.
- 10 ans réservé : CAGR 12,95→13,11 %, DD -24,70→-25,27 %, pertes du 95e percentile 36,65→38,36 %. IC95 du gain CAGR [0,12;0,19] point ; amélioration du DD [-0,73;-0,42] point. Rendement supérieur sur 207/300 parcours. Critères synthétiques secondaires : échec.
- Historiques : 3 ans CAGR 17,14→17,78 %, DD -12,38→-12,76 % ; 5 ans CAGR 12,06→12,26 %, DD -11,73→-12,57 % ; 10 ans CAGR 13,04→12,85 %, DD -20,45→-19,59 %.
- Stress `double_fees` : échec aux horizons 5, 10 ans.
- Stress `delay2` : échec aux horizons 5, 10 ans.

**Variante 1322 :** passif 35 %, partage lent/défensif interne 85/15, plancher 25 %, sortie défensive +1,75 sigma, cadence 5 séances.

- 5 ans réservé : CAGR 12,64→12,88 %, DD -20,49→-20,90 %, pertes du 95e percentile 33,94→34,18 %. IC95 du gain CAGR [0,22;0,25] point ; amélioration du DD [-0,46;-0,36] point. Rendement supérieur sur 808/1000 parcours. Critères synthétiques secondaires : réussis.
- 10 ans réservé : CAGR 12,95→13,13 %, DD -24,70→-25,27 %, pertes du 95e percentile 36,65→38,02 %. IC95 du gain CAGR [0,16;0,20] point ; amélioration du DD [-0,69;-0,47] point. Rendement supérieur sur 263/300 parcours. Critères synthétiques secondaires : échec.
- Historiques : 3 ans CAGR 17,14→17,82 %, DD -12,38→-12,13 % ; 5 ans CAGR 12,06→12,37 %, DD -11,73→-11,63 % ; 10 ans CAGR 13,04→13,06 %, DD -20,45→-20,72 %.
- Stress `double_fees` : critères historiques secondaires conservés.
- Stress `delay2` : critères historiques secondaires conservés.

**Variante 1316 :** passif 35 %, partage lent/défensif interne 85/15, plancher 25 %, sortie défensive +1,5 sigma, cadence 5 séances.

- 5 ans réservé : CAGR 12,64→12,81 %, DD -20,49→-20,80 %, pertes du 95e percentile 33,94→34,18 %. IC95 du gain CAGR [0,16;0,19] point ; amélioration du DD [-0,35;-0,27] point. Rendement supérieur sur 767/1000 parcours. Critères synthétiques secondaires : réussis.
- 10 ans réservé : CAGR 12,95→13,08 %, DD -24,70→-25,13 %, pertes du 95e percentile 36,65→37,34 %. IC95 du gain CAGR [0,11;0,14] point ; amélioration du DD [-0,51;-0,36] point. Rendement supérieur sur 241/300 parcours. Critères synthétiques secondaires : échec.
- Historiques : 3 ans CAGR 17,14→17,66 %, DD -12,38→-12,13 % ; 5 ans CAGR 12,06→12,32 %, DD -11,73→-11,64 % ; 10 ans CAGR 13,04→13,00 %, DD -20,45→-20,76 %.
- Stress `double_fees` : échec aux horizons 10 ans.
- Stress `delay2` : échec aux horizons 10 ans.

**Variante 1250 :** passif 35 %, partage lent/défensif interne 75/25, plancher 25 %, sortie défensive +1,75 sigma, cadence 5 séances.

- 5 ans réservé : CAGR 12,64→12,75 %, DD -20,49→-20,66 %, pertes du 95e percentile 33,94→34,03 %. IC95 du gain CAGR [0,10;0,12] point ; amélioration du DD [-0,22;-0,13] point. Rendement supérieur sur 738/1000 parcours. Critères synthétiques secondaires : réussis.
- 10 ans réservé : CAGR 12,95→13,05 %, DD -24,70→-24,95 %, pertes du 95e percentile 36,65→36,68 %. IC95 du gain CAGR [0,08;0,11] point ; amélioration du DD [-0,36;-0,16] point. Rendement supérieur sur 261/300 parcours. Critères synthétiques secondaires : réussis.
- Historiques : 3 ans CAGR 17,14→17,41 %, DD -12,38→-12,38 % ; 5 ans CAGR 12,06→12,15 %, DD -11,73→-11,71 % ; 10 ans CAGR 13,04→13,14 %, DD -20,45→-20,37 %.
- Stress `double_fees` : critères historiques secondaires conservés.
- Stress `delay2` : critères historiques secondaires conservés.

### Décision et vérification

Aucune adoption automatique : **la production v5 reste active**. Aucun
changement du moteur de production, de l’interface ou de la base utilisateur.
Les pistes à gain modeste sont des résultats exploratoires ; les nouveaux
tirages du même historique ne les valident pas prospectivement.

456 tests backend ont réussi avant ajout des trois contrôles des experts ;
le fichier ciblé complet termine ensuite avec 11 tests réussis. Les contrôles
couvrent causalité sur tous les réglages tactiques et séquentiels, scores
d’experts après exécution ultérieure, budgets réels, frais/retard et identité
du témoin. Chaque premier parcours de chaque lot a également été confronté
au moteur de production à 1e−9. Ruff backend/scripts et contrôle des espaces
du diff réussis. Ces vérifications logicielles ne valident pas les hypothèses
financières.

## Seconde branche déclarée pendant la première sélection

Après constat d'échec du seul écran historique de la première campagne,
alors que ses 200 marchés de sélection étaient encore en calcul, une seconde
branche a été déclarée : **729 configurations de continuation**. L'ancienne
recherche Amundi sur ces mécanismes cherchait à battre le passif et avait échoué ;
elle ne répondait pas à la comparaison conjointe des budgets contre v5 avec
drawdown proche. Ce changement de référence est explicite, aucune piste ancienne
n'est adoptée à l'identique.

Grille : entrée lente actuelle ou tendance MM100/MM200, sortie lente actuelle
ou sortie MM50/MM100 après activation au-dessus de +1,5 sigma, plancher
10/25/40 %, budget lent interne 50/75/90 %, sortie défensive +1,5/+1,75/+2 sigma,
poche passive 0/20/35 %. Mêmes autres règles de replay et d'exécution.
Les critères restent exactement ceux de la première campagne, sans assouplir
les seuils après résultats. **2 085 configurations au total** pour ces deux
campagnes ; les recouvrements de paramètres ne sont pas des découvertes nouvelles.

Sélection : 200 marchés, graines 1410000–1410199 ; audit : 1 000 cinq ans
1420000–1420999 et 300 dix ans 1430000–1430299. Un seul champion pour cette
famille homogène, figé avant ses lots réservés. Le code et les critères sont
partagés ; rapport séparé, sans réécriture du premier :
`data/backtests/sp500-deep-continuation.json`.

```sh
PYTHONPATH=backend:scripts .venv/bin/python scripts/study_sp500_deep_continuation.py --workers 2
```

## Troisième branche : combinaison séquentielle d'experts

Après les deux écrans historiques négatifs, avant consultation de la sélection
de la première branche et de tous les audits réservés, une troisième hypothèse
a été déclarée : adapter les poids de règles complémentaires avec leurs seuls
résultats passés. Source supplémentaire :
[Uziel–El-Yaniv, Online Learning of Portfolio Ensembles](https://arxiv.org/abs/1604.03266).
Notre combinaison exponentielle régularisée est une adaptation ; elle ne
reproduit pas les portefeuilles sectoriels ni les garanties du papier.

Cinq experts indicatifs : deux cibles issues des états de régression, deux
détecteurs CUSUM avec réentrée et un filtre Markov. Les experts indicatifs
calculent des rendements fractionnaires avec deux clôtures de retard entre
cible et rendement, et une approximation de frais sur rotation. Le premier
expert est inspiré des budgets v5 mais ne reproduit pas sa dérive de poids ni
ses arrondis ; le vrai témoin v5 est calculé séparément. Le compte investi
paie ses propres frais exacts et utilise des titres entiers. Aucun profit
antérieur des experts n'est crédité au compte neuf.

**324 configurations** : fenêtres63/126/252 séances, vitesse2/5/10,
pénalité de variance0/3/6, pénalité de baisse0/1, plancher10/25 %,
budget v4 indépendant0/35/65 %. Score causal de rendement logarithmique,
variance et recul depuis le maximum passé ; décision toutes les cinq séances.
Critères inchangés. Au total : **2 409 configurations déclarées**,
**2 391 paramétrages distincts** après normalisation de la cadence défensive
par défaut :18 recouvrements entre les deux premières branches. Le témoin v5
figure dans ces grilles. Ce total ne mesure pas des idées indépendantes.

Sélection : 200 marchés, graines1510000–1510199. Audit :1 000 cinq ans
1520000–1520999 et300 dix ans1530000–1530299. Rapport distinct
`data/backtests/sp500-online-ensemble.json` ; un seul champion figé.

```sh
PYTHONPATH=backend:scripts .venv/bin/python scripts/study_sp500_online_ensemble.py --workers 2
```

## Audit secondaire des gains modestes : décision après sélection

Le gain minimal de 0,5 point vient du protocole de recherche, pas d'une exigence
chiffrée de l'utilisateur. Après lecture des historiques et des 200 marchés
de sélection de la première branche, quatre variantes restent intéressantes
avec un gain inférieur. Un audit distinct a été déclaré avant consultation de
tous les lots réservés : indices1056/1322/1316/1250 de la première grille,
aucun nouveau paramètre, toutes les quatre conservées. Aucun gagnant n'est
choisi selon cet audit. Cette analyse secondaire ne réécrit pas les échecs du
protocole initial et n'est pas une validation économique indépendante.

Objectif secondaire : sur chacun des deux horizons réservés, gain moyen de
CAGR positif, borne basse appariée95 % positive, aggravation moyenne du DD
et borne haute95 % de cette aggravation au plus0,5 point, aggravation du
95e percentile des pertes au plus1 point. Sur chaque historique3/5/10 ans,
CAGR au moins égal à v5 et DD au plus0,5 point plus profond. Même condition
historique avec frais doublés et retard supplémentaire ; au moins18/24 fenêtres
avec CAGR à0,5 point près, DD à1 point près et volatilité sous115 %v5.
Tous ces critères sont nécessaires, sans adoption automatique.

Les quatre variantes modifient le budget régressif et/ou la sortie défensive ;
la variante 1250 ne change que cette sortie de +1,5 à +1,75 sigma, piste déjà
observée dans l'affinage de v4. Son nouvel audit face à v5 ne constitue pas
une découverte de ce seuil. Sélection réutilisée, puis **1 000 cinq ans**
(1620000–1620999) et **300 dix ans** (1630000–1630299) supplémentaires.
Sortie : `data/backtests/sp500-modest-edge.json`.

```sh
PYTHONPATH=backend:scripts .venv/bin/python scripts/study_sp500_modest_edge.py
```

Total des quatre audits : **600 marchés de sélection, 5 200 réservés** ;
toujours le même historique PSP5 et le même générateur, pas5 800 observations
économiques indépendantes.
