# Recherche de réduction du drawdown après adoption de v5

Le 15 novembre 2026, l'utilisateur autorise une nouvelle exploration et
l'implémentation d'un remplacement si la surperformance résiste aux vérifications.
Référence : **v5, 65 % v4 / 35 % passif**, PSP5 EUR, 10 000 €, titres entiers,
0,12 % par achat/vente, liquidités non rémunérées. Aucun changement de la base
utilisateur, du générateur de l'application ou de la production pendant la recherche.

## Procédure fixée avant les résultats

396 configurations, six familles :

- Risque baissier réalisé sur 10/42/84 séances plutôt que volatilité symétrique.
- Combinaison tendance multi-horizons et risque, graduelle ou par votes.
- Budget de baisse sur maximum glissant 63/126/252 séances, avec ou sans
  réactivation au rebond : le maximum peut redescendre, contrairement au TIPP
  permanent déjà examiné.
- Stop proportionnel à la volatilité, avec seuil borné et réentrée sur rebond.
- Choc de volatilité avec réentrée partielle anticipée sur rebond.
- Taille de position selon un rendement observé ramené vers une hypothèse fixe,
  divisée par le risque : aucune moyenne future utilisée.

Chaque règle est testée seule, puis sur 65 % ou 35 % du capital initial, le
complément restant dans v4. Les comptes actifs et tactiques sont indépendants,
avec leurs vrais budgets, leurs arrondis et leurs propres frais. Aucune moyenne
de deux courbes de 10 000 € pour simuler un seul capital partagé.

150 marchés cinq ans de sélection, graines 210000–210149. Conditions :
CAGR moyen au moins v5 moins 0,25 point ; pertes maximales moyennes **et**
95e percentile des pertes maximales au moins 10 % plus faibles ; volatilité
au plus v5 ; trois ratios moyens au moins v5. Sur les historiques déjà examinés
3/5/10 ans : CAGR au moins v5 moins 0,75 point, drawdown au plus 1 point plus
profond. Parmi les candidats qualifiés, choisir le plus petit 95e percentile,
puis le rendement. Si aucun ne passe, figer un seul diagnostic minimisant la
pire violation normalisée ; cela n'autorise pas son adoption.

Après gel du candidat : **1 000 nouveaux marchés cinq ans** (220000–220999) et
300 dix ans (230000–230299). Même critères synthétiques sur chaque horizon,
borne basse à 95 % de l'écart apparié de CAGR au moins −0,5 point et amélioration
du drawdown moyen dont la borne basse à 95 % reste positive. Auditer également
les historiques 1/3/5/10 ans, les fenêtres cinq ans à départs trimestriels et
les frais doublés/une séance supplémentaire d'exécution. Conservation du
CAGR et du drawdown historique requise comme ci-dessus, sur au moins 75 %
des fenêtres et chaque stress 3/5/10 ans. **Toutes les étapes sont nécessaires
pour implémenter le candidat. Aucun second choix après examen du lot réservé.**

## Exécution et reproductibilité

Signaux connus à la clôture, ordres à la suivante ; l'ordre en attente conserve
la cible décidée avec les seules informations disponibles à sa date. Bande de
5 points pour éviter les petits ajustements. Décisions quotidiennes ou toutes
les cinq séances suivant la règle. Les poches régressives gardent leur calendrier
et leur état initial exacts. Une vente et une réentrée comportent leurs frais.
Pas de liquidation fictive à la fin, pas de levier ni vente à découvert.

```sh
PYTHONPATH=backend:scripts uv run python scripts/study_sp500_drawdown_frontier.py
uv run pytest -q backend/tests/unit/test_sp500_drawdown_frontier.py
```

Sortie distincte : `data/backtests/sp500-drawdown-frontier.json`, avec protocole,
configurations, empreinte de la copie SQLite, résultats de chaque parcours et
contre-exemples. Aucun rapport précédent n'est réécrit. Chaque premier parcours
de lot vérifie exactement les métriques Buy & Hold et v5 contre le moteur actif.
Les tests vérifient l'absence d'utilisation des cours futurs, les titres entiers,
le vrai budget séparé et l'exécution après un écart de cours.

## Origine des pistes et limites

Idées de risque conditionnel : [Moreira–Muir, NBER](https://www.nber.org/papers/w22208).
Tendances : [Hurst–Ooi–Pedersen, AQR](https://www.aqr.com/insights/research/journal-article/a-century-of-evidence-on-trend-following-investing).
Les variantes ici sont des adaptations long/cash sur un ETF, pas une reproduction
des stratégies académiques multi-actifs. Ces publications ne démontrent pas la
supériorité des variantes essayées dans ce projet.

La répétition des recherches accroît le risque de sélection opportuniste. Les
nouveaux tirages réutilisent le même historique PSP5 depuis 2014 ; ils ne sont
pas de nouveaux régimes économiques indépendants. Les fenêtres historiques se
chevauchent. Les stops peuvent subir un écart de cours et les reprises rapides
peuvent coûter cher. Aucune règle n'établit un plafond garanti de drawdown.

## Résultats

Campagnes terminées : **aucun remplacement retenu, v5 reste active**. Les trois sélections échouent aux critères et les audits confirment un coût de rendement ou des contre-exemples historiques. Résultats détaillés ci-dessous.

## Extension déclarée avant examen des lots réservés

Après échec de la sélection initiale, une seconde campagne indépendante de
**432 configurations** examine trois familles complémentaires : exposition
continue contrariante sur écarts de cours normalisés par le risque, déséquilibre
des hausses/baisses de type RSI, puis combinaison de tendance longue et achats
sur repli court. Avec ou sans filtre de tendance/choc, seuls ou dans les mêmes
budgets indépendants que la première campagne. Cette règle continue mono-ETF
diffère du retour à la moyenne multi-actifs existant (pas de financement par
vente d'une autre ligne, ni de règles d'entrées/sorties copiées).

Critères et exécution identiques ; 150 parcours de sélection 510000–510149,
puis 1 000 cinq ans 520000–520999 et 300 dix ans 530000–530299, sans choisir
un candidat dans les résultats réservés d'une autre campagne. Au total,
**828 configurations**, 300 marchés de sélection, 2 600 marchés réservés.

```sh
PYTHONPATH=backend:scripts uv run python scripts/study_sp500_drawdown_reversal.py
```

Sortie séparée `data/backtests/sp500-drawdown-reversal.json` ; moteur comptable
commun, nouveau protocole conservé avant les résultats. Le test de causalité
couvre les neuf familles des deux campagnes et le retard d'une/deux séances.

Les calculs peuvent être parallélisés avec `--workers 4`. Après gel enregistré,
`--resume --workers 4` conserve le lot de sélection, vérifie que les configurations,
l'empreinte SQLite et le candidat figé sont identiques, puis reprend les audits
non terminés avec exactement les mêmes graines. Le test de parallélisation
compare chaque résultat et leur ordre au calcul séquentiel. Les parcours d'un
lot interrompu avant enregistrement sont recalculés intégralement, sans filtrage.

### Gel des deux diagnostics

Aucune configuration ne passe la sélection complète dans les deux campagnes.
Première piste figée : conserver 65 % v4, remplacer 35 % passif par une règle de
stop adaptatif (1,5 volatilité mensuelle, bornée entre 4 et 25 %), exposition
défensive 50 %, rebond de réentrée 6 %, décisions cinq séances. Seconde : 65 % v4
et 35 % retour sur repli (moyenne dix séances, amplitude 0,3, plancher 50 %,
filtre de tendance longue, cinq séances).

| Historique PSP5 | v5 CAGR | Stop CAGR | Repli CAGR | v5 DD | Stop DD | Repli DD |
|---|---:|---:|---:|---:|---:|---:|
| 3 ans | 17,14 % | 17,21 % | 15,59 % | −12,38 % | −10,24 % | −10,54 % |
| 5 ans | 12,06 % | 11,28 % | 10,72 % | −11,73 % | −10,27 % | −9,76 % |
| 10 ans | 13,04 % | 12,54 % | 11,56 % | −20,45 % | −16,40 % | −18,06 % |

Sur la sélection initiale, 23 variantes de la première campagne gagnent à la
fois en CAGR et en drawdown moyens face à v5 ; aucune ne conserve les limites
historiques sur les trois horizons. Exemple instructif : contrôle du risque
baissier dix séances, cible 10 %, puissance deux, plancher 50 %, sans v4.
Sélection synthétique : CAGR 12,90 % contre 12,69 %, DD −17,91 % contre −20,13 %.
Historique cinq ans : CAGR **8,83 % contre 12,06 %**, DD **−17,60 % contre −11,73 %**.
Il n'est donc pas promu en remplacement sur la foi de ses seuls tirages favorables.

## Dernière extension ciblée : protéger l'ensemble de v5

Déclarée après réception des deux lots cinq ans précédents, sans les présenter
comme des données inconnues pour cette nouvelle hypothèse. **24 configurations** :
le stop adaptatif plafonne maintenant les cibles des trois poches à 25 ou 50 %
pendant l'alerte ; les expositions défensives normales des deux poches actives
sont testées à 25/35/50 %, pour tenter de compenser le coût des sorties.
Multiples 1,5/2,5 ; rebonds 3/6 %, décisions toutes les cinq séances.
Budgets4875/1625/3500 € inchangés ; toutes les cibles modifiées restent des
ordres indépendants à la clôture suivante, sans rééquilibrage entre budgets.

La régression conserve ses états, ses seuils, son calendrier et son replay ;
la protection est une couche distincte et les paramètres d'exposition changent
explicitement. Les poches se réajustent seulement quand leur cible change,
sans bande de cinq points dans cette extension. Le moteur de recherche reçoit
une limite d'exposition optionnelle ; son défaut reste inchangé pour les archives.

Même procédure et mêmes seuils que précédemment ; **150 nouveaux marchés de
sélection 810000–810149**, puis **1000 cinq ans 820000–820999 et 300 dix ans
830000–830299**. Une seule sélection figée avant ces deux nouveaux lots,
aucun recyclage des lots réservés précédents pour la qualifier. C'est la dernière
campagne de cette recherche, pas une procédure qui s'arrête au premier lot gagnant.

```sh
PYTHONPATH=backend:scripts uv run python scripts/study_sp500_drawdown_overlay.py --workers 4
```

Sortie `data/backtests/sp500-drawdown-overlay.json`. Les tests vérifient la
correspondance exacte de la référence et d'une protection neutre avec v5,
l'absence de cours futurs et une vente protectrice après un écart de cours.
Total réalisé des trois campagnes : **852 configurations, 450 parcours de
sélection et 3900 réservés**, plus historiques et stress.

## Audits réservés des deux premières campagnes

Le diagnostic avec stop réduit le risque, mais ne conserve pas assez de rendement pour remplir la procédure. **Aucune adoption.** Les moyennes suivantes portent sur les mêmes 1000 marchés cinq ans ; chaque drawdown est calculé par parcours avant la moyenne.

| Indicateur | Buy & Hold | v5 active | 65 % v4 / 35 % stop |
|---|---:|---:|---:|
| Rendement net | 109,67 % | 83,80 % | 80,58 % |
| CAGR net | 15,21 % | 12,53 % | 12,15 % |
| Drawdown maximal moyen | -25,07 % | -20,85 % | -19,30 % |
| Volatilité annualisée | 16,56 % | 13,61 % | 12,99 % |
| Volatilité baissière | 11,81 % | 9,66 % | 9,20 % |
| Sharpe | 0,927 | 0,944 | 0,950 |
| Sortino | 1,319 | 1,352 | 1,364 |
| Calmar | 0,741 | 0,755 | 0,774 |
| Frais payés | 11,95 € | 32,64 € | 68,16 € |
| Seuil de drawdown des 5 % pires parcours | -37,85 % | -33,67 % | -31,11 % |
| Pire drawdown observé | -59,38 % | -54,72 % | -49,80 % |

Les baisses supérieures à 30 % concernent **145/1000** marchés pour v5 et **68/1000** avec stop. Le drawdown est meilleur dans 78,4 % des parcours, le rendement dans 26,2 % seulement.

Écart de CAGR moyen : **−0,384 point/an**, intervalle apparié à 95 % **[−0,425 ; −0,343] point**. La perte de rendement n’est donc pas expliquée seulement par le bruit de ce lot. Amélioration du drawdown moyen : **1,544 point**, intervalle **[1,436 ; 1,645] point**. Perte maximale moyenne réduite de **7,41 % relatif**, 95e percentile réduit de **7,61 %** ; les objectifs de 10 % ne sont pas atteints.

Sur 300 marchés dix ans : CAGR **12,28 → 11,86 %**, DD moyen **−25,86 → −23,59 %**, seuil des 5 % pires **−39,43 → −35,52 %**, pire observé **−48,39 → −44,16 %**. Sharpe/Sortino/Calmar meilleurs que v5 en moyenne ; le Calmar reste légèrement sous Buy & Hold (0,569 contre 0,572).

Historique : 23/24 fenêtres respectent les marges fixées. Ce compte ne signifie pas 23 gains de rendement. L’écart réel cinq ans −0,782 point dépasse les −0,75 permis ; frais doublés, il atteint −0,835 point. La bonne protection ne fait pas disparaître ces échecs.

Deuxième diagnostic, sur ses propres 1000 marchés cinq ans : CAGR **12,65 → 11,22 %**, DD moyen **−20,94 → −18,88 %**, frais **32,79 → 182,63 €** ; trois ratios moyens inférieurs à v5. Dix ans : CAGR **12,42 → 10,82 %**, DD **−25,64 → −22,99 %**. Seulement **1/24** fenêtres historiques respecte les marges combinées. Cette variante n’est pas retenue.

Les intervalles mesurent la variabilité des tirages conditionnellement au modèle historique, pas l’incertitude économique complète. Le pire observé ne constitue pas un plafond de pertes.

## Audit final de la protection sur les trois poches

Le candidat figé protège les trois poches à 50 % pendant l'alerte et relève le
plancher actif normal à 35 %, multiple1,5, rebond3 %. Sur1000 nouveaux parcours
cinq ans : CAGR **12,68 →12,21 %**, DD moyen **−20,55 →−19,79 %**, seuil des
5 % pires **−33,65 →−30,80 %**, pire observé **−47,81 →−43,23 %**.
Sharpe **0,958 →0,936**, Sortino **1,374 →1,338**, Calmar **0,777 →0,748** ;
frais **32,91 →104,35 €**. Le DD n'est meilleur que dans42,7 % des parcours,
malgré sa meilleure moyenne. Le gain moyen est concentré dans certains chocs.

Sur300 marchés dix ans : CAGR **12,45 →12,05 %**, DD **−25,94 →−24,08 %**,
seuil des5 % pires **−38,10 →−34,69 %**. Seulement **11/24** fenêtres respectent
les marges historiques. Réel cinq ans : CAGR **12,06 →10,86 %**,
DD **−11,73 →−13,15 %** ; dix ans : CAGR **13,04 →12,39 %**,
DD **−20,45 →−22,09 %**. Relever l'exposition pour compenser le coût des
protections n'apporte donc pas l'amélioration recherchée.

## Décision et contrôles

**V5 reste active**, aucun nouveau paramètre de stratégie ni générateur modifié.
L'autorisation d'implémentation était conditionnée à une amélioration ; aucune
des trois procédures ne satisfait toutes ses conditions. Les résultats de
risque seuls ne sont pas présentés comme une conservation du rendement.
Cela ne prouve pas l'impossibilité d'une meilleure stratégie.

Les trois copies SQLite ont exactement la même empreinte ; chaque lot
synthétique garde tous ses parcours et ses dénominateurs. **852 configurations**,
450 marchés de sélection et3900 marchés réservés : trois fois1000 cinq ans et
trois fois300 dix ans. Historiques1/3/5/10 ans,24 fenêtres cinq ans et deux stress
(frais doublés, retard supplémentaire) pour chacun des trois diagnostics.
Aucune nouvelle donnée économique indépendante créée par ces graines.

**438 tests backend réussis** ; les neuf nouveaux tests repassent après
ajustement du test de parallélisation pour éviter de lancer fork depuis le
processus de tests multithread. Ruff backend/scripts et formatage réussis.
**18 cas** du vérificateur de production v5 reproduisent toujours exactement
la recherche indépendante. Les références historiques3/5/10 de la première
campagne concordent également avec ces résultats figés à1e−9.

Le moteur de recherche accepte maintenant une limite d'exposition optionnelle
(défaut inchangé). Son replay ignore les jours où aucun calendrier ne peut
changer d'état, sans modifier les résultats. Les archives financières des
anciennes campagnes ne sont pas recalculées. Le code de production et
l'interface restent ceux de l'adoption v5. Ces tests vérifient le logiciel,
pas une rentabilité future.
