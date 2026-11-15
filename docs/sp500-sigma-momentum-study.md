# Écart à la régression et momentum sur PSP5

Recherche du 15 novembre 2026, demandée après les campagnes de réduction du
drawdown. Référence active : `core35_slow_defensive_v5`, soit 65 % v4 et 35 %
passif. Aucun ancien score multi-actifs 70/30 n'est réintroduit.

## Protocole déclaré avant les résultats

**288 configurations** : quatre règles × deux régressions (18/60 mois) × trois
momentums (6 mois, 12 mois, moyenne des horizons disponibles 6/12/36 mois) × deux
seuils (50/55) × deux expositions défensives (25/50 %) × trois budgets v4
(0/35/65 %). Le complément est un compte tactique indépendant ; aucun transfert
entre comptes. Capital total 10 000 €, PSP5 EUR uniquement, titres entiers,
0,12 % par ordre, liquidités non rémunérées, sans levier.

Le momentum reproduit la formule de `investor.assets.momentum.analyze`, ses
bornes calendaires, son mois récent exclu, son minimum de 60 observations et
ses contrôles de couverture. PSP5 étant sa propre référence, le rendement
relatif est nul. Aucun indice USD n'est ajouté. L'ensemble moyenne les scores
disponibles ; aucun horizon exploitable signifie exposition défensive.

L'écart z utilise la régression logarithmique calendaire, les résidus et leur
écart-type avec deux degrés de liberté consommés, 18 ou 60 mois, minimum
251/501 observations. Il s'agit de l'écart à la tendance, pas de la volatilité
quotidienne du rendement.

Quatre règles, dont les conditions précises restent dans le script et le JSON :

- Confirmation : entrer lorsque le momentum confirme une décote ou une reprise ;
  sortir si le momentum faiblit ou si l'écart devient trop élevé.
- Repli dans la tendance : acheter sous +0,5 σ avec momentum favorable ;
  vendre sur faiblesse ou sur extension accompagnée d'un momentum moins fort.
- Sortie différée : autoriser la poursuite d'une tendance malgré un z élevé ;
  vendre quand l'extension s'accompagne d'un momentum insuffisant.
- Interaction continue : exposition graduelle selon la tendance, la décote et
  leur interaction, bornée entre le plancher et 100 %.

Décisions toutes les cinq séances depuis le début, bande de cinq points,
exécution à la clôture suivante. Pour les règles conditionnelles, reconstruire
seulement l'état sur la même grille antérieure ; aucun capital, gain ou frais
antérieur ajouté. Une sortie ne peut exécuter avant la clôture suivante.

Sélection : **150 parcours cinq ans, graines 1110000–1110149**, plus les
historiques 3/5/10 ans déjà examinés. Critères identiques à la campagne précédente :
CAGR moyen ≥ v5 −0,25 point ; pertes maximales moyennes et 95e percentile au
moins 10 % plus faibles ; volatilité et trois ratios moyens au moins aussi
favorables. Historique : CAGR ≥ v5 −0,75 point, perte maximale au plus 1 point
plus profonde. Choisir le candidat admissible au plus petit 95e percentile,
puis au meilleur CAGR. Si aucun ne passe, figer un seul diagnostic minimisant
la pire violation normalisée, sans autoriser son adoption.

Après gel : **1 000 parcours cinq ans (1120000–1120999)** et **300 dix ans
(1130000–1130299)**. Même critères sur chaque horizon, intervalle apparié à 95 %
du gain de drawdown strictement positif, borne basse du différentiel de CAGR
≥ −0,5 point. Vérifier aussi 1/3/5/10 ans réels, au moins 75 % de 24 fenêtres
trimestrielles cinq ans, frais doublés et exécution retardée d'une séance.
Toutes les conditions doivent passer avant remplacement, aucun second choix
après examen des audits.

## Reproduction et limites

```sh
PYTHONPATH=backend:scripts uv run python scripts/study_sp500_sigma_momentum.py --workers 4
uv run pytest -q backend/tests/unit/test_sp500_sigma_momentum.py
```

Rapport : `data/backtests/sp500-sigma-momentum.json`. Copie privée SQLite,
empreinte conservée, aucun changement de base utilisateur ni du générateur.
Chaque premier parcours de lot vérifie Buy & Hold et v5 contre la production.
Tests : égalité du momentum avec l'application, égalité du z avec la régression
historique, absence d'anticipation, arrondis, budgets et clôture suivante.

Le [momentum temporel étudié par Moskowitz, Ooi et Pedersen](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum)
motive une famille de signaux ; cette étude ne reproduit pas leur portefeuille
diversifié de contrats à terme et ne peut en reprendre les conclusions.
Les graines réservées ne créent pas de nouveaux régimes économiques : le même
historique PSP5 depuis 2014 et les mêmes blocs simulés sont réutilisés. La
recherche répétée et les fenêtres chevauchantes limitent toute conclusion.

## Résultats

Sélection terminée : **0/288 configurations admissibles**. Même sans exiger
10 % de protection, aucune ne combine un CAGR moyen au moins égal à v5 et un
drawdown moyen au moins aussi favorable sur les 150 parcours de sélection.

La règle figée pour diagnostic est l'interaction continue : régression 18 mois,
momentum 12 mois, seuil 55, plancher 50 %, budget v4 65 % et tactique 35 %.
Le candidat n'est pas présenté comme « le meilleur » au sens général : il
minimise la pire violation normalisée des critères annoncés.

| Sélection, 150 parcours cinq ans | Buy & Hold | v5 | Interaction figée |
|---|---:|---:|---:|
| CAGR moyen | 14,87 % | 12,19 % | 11,32 % |
| Drawdown maximal moyen | −25,83 % | −21,46 % | −20,36 % |
| Seuil des 5 % pires drawdowns | −38,35 % | −34,81 % | −32,59 % |

Le rendement maximal observé parmi les variantes est 14,75 %, avec un drawdown
moyen de −25,81 %, contre 12,19 % et −21,46 % pour v5 : c'est une augmentation
du risque vers le Buy & Hold. Sur dix ans réels, cette même variante ne produit
que 12,96 % de CAGR avec un drawdown de −33,67 %, contre 13,04 % et −20,45 % v5.
Elle n'est donc pas une solution de rendement équivalent à risque moindre.

## Audit réservé cinq ans : 1 000 parcours

| Indicateur moyen, frais inclus | Buy & Hold | v5 | Interaction figée |
|---|---:|---:|---:|
| Rendement cumulé net | 109,86 % | 83,40 % | 76,16 % |
| CAGR net | 15,21 % | 12,48 % | 11,59 % |
| Drawdown maximal | −25,07 % | −20,84 % | −19,80 % |
| Volatilité annualisée | 16,53 % | 13,58 % | 12,70 % |
| Volatilité baissière | 11,78 % | 9,64 % | 9,02 % |
| Sharpe | 0,926 | 0,939 | 0,927 |
| Sortino | 1,318 | 1,344 | 1,326 |
| Calmar | 0,740 | 0,751 | 0,733 |
| Frais payés | 11,95 € | 32,79 € | 53,06 € |
| Seuil des 5 % pires drawdowns | −37,98 % | −33,80 % | −32,98 % |
| Pire drawdown observé | −52,51 % | −46,52 % | −42,43 % |
| Parcours avec drawdown supérieur à 30 % | 337 | 153 | 102 |

Comparaisons appariées au même v5 : **−0,886 point de CAGR**, intervalle à 95 %
[−0,914 ; −0,859] point ; gain de drawdown moyen de **1,043 point**, intervalle
[0,980 ; 1,110] point. La perte maximale moyenne diminue de 5,00 %, en dessous
des 10 % demandés par le protocole ; son 95e percentile ne s'améliore que de
0,82 point. La règle réduit le drawdown dans 95 % des parcours, mais ne gagne
en rendement que dans 2,4 %. Les trois ratios moyens reculent face à v5 ; le
Calmar reste aussi inférieur au Buy & Hold. Le lot cinq ans échoue.

## Historique réel

| Horizon | CAGR v5 | CAGR interaction | Drawdown v5 | Drawdown interaction |
|---|---:|---:|---:|---:|
| 3 ans | 17,14 % | 16,20 % | −12,38 % | −12,05 % |
| 5 ans | 12,06 % | 11,36 % | −11,73 % | −11,29 % |
| 10 ans | 13,04 % | 11,94 % | −20,45 % | −19,51 % |

Le recul de CAGR dépasse les 0,75 point permis sur trois et dix ans.
La légère réduction du drawdown ne compense pas ce recul selon l'objectif.

## Audit dix ans, fenêtres et stress

| Indicateur moyen, 300 parcours dix ans | Buy & Hold | v5 | Interaction figée |
|---|---:|---:|---:|
| CAGR net | 14,88 % | 12,26 % | 11,21 % |
| Drawdown maximal | −30,45 % | −25,61 % | −24,06 % |
| Seuil des 5 % pires drawdowns | −42,28 % | −37,53 % | −35,28 % |
| Pire drawdown observé | −48,28 % | −44,31 % | −41,15 % |
| Sharpe | 0,897 | 0,897 | 0,884 |
| Sortino | 1,265 | 1,270 | 1,251 |
| Calmar | 0,547 | 0,544 | 0,527 |
| Frais moyens | 11,95 € | 65,47 € | 122,16 € |

Écart de CAGR : −1,046 point, intervalle à 95 % [−1,090 ; −1,002] point.
Gain de drawdown moyen : 1,552 point, intervalle [1,411 ; 1,699] point.
Le lot dix ans échoue aussi. **Une seule des 24 fenêtres historiques cinq ans**
respecte le compromis rendement/drawdown annoncé ; ce nombre ne signifie pas
une seule fenêtre à rendement positif.

| Stress : écart de CAGR interaction − v5 | 3 ans | 5 ans | 10 ans |
|---|---:|---:|---:|
| Frais doublés | −0,945 point | −0,751 point | −1,086 point |
| Exécution une séance plus tard | −0,952 point | −0,679 point | −1,084 point |

L'année récente seule est plus favorable aux ratios : CAGR 15,42 % contre
15,80 % v5, drawdown −5,05 % contre −5,33 %. Elle ne renverse pas les échecs
sur les autres périodes et ne justifie pas de choisir une période avantageuse.

## Décision et contrôles

**Aucun remplacement : v5 reste active.** Les 288 configurations, les 150
marchés de sélection et les 1 300 réservés ont été intégralement calculés,
sans filtrage de parcours ni choix alternatif après audit. La combinaison
écart/momentum diminue le risque dans le diagnostic retenu, mais ne maintient
pas le rendement et n'améliore pas les trois ratios. Il ne s'agit pas d'une
preuve qu'aucune combinaison possible ne peut réussir.

Historique : 3 197 observations PSP5 du 20/05/2014 au 13/11/2026 ; SHA256 de la
copie SQLite `79f0b69e585145793b557d6ca926d944fe539e5e2f1f1f589523dc99d9ae6dca`.
Tous les lots ont vérifié leur première paire Buy & Hold/v5 contre le moteur
de production, tolérance absolue 1e−9. Le vérificateur v5 conserve ses **18 cas
exacts**. **443 tests backend réussis**, Ruff et format des fichiers concernés
réussis. Ces contrôles portent sur le logiciel, pas sur la rentabilité future.
Le moteur de recherche accepte désormais des cibles exogènes optionnelles ;
son fonctionnement antérieur par défaut et le moteur de production restent
inchangés. Aucun changement d'interface ou de base utilisateur.
