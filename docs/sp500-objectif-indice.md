# Battre PSP5 avec un drawdown plus faible · 19 novembre 2026

Le succès exige strictement plus de rendement annualisé net et un drawdown maximal moins profond que PSP5 acheté une fois. La référence est en euros. La comparaison des 2 409 configurations déclarées des archives deep-search, deep-continuation et online-ensemble (2 391 distinctes) à leur propre benchmark au 13 novembre donne zéro réussite simultanée sur 3, 5 et 10 ans. Ce reclassement exploite des simulations déjà effectuées.

## Expérience hors régression

Une copie SQLite en mémoire fournit 2 765 dates communes à PSP5, SPMO et EUR/USD entre le 12 octobre 2015 et le 19 novembre 2026. SPMO est le fonds américain répliquant le S&P 500 Momentum Index. Les prix et les distributions implicites du fonds sont convertis en euros. Les distributions brutes sont approchées par l’écart entre rendement ajusté et rendement du prix, et créditées en cash. Hypothèses communes de 10 000 €, titres entiers, frais de 0,12 % par transaction, liquidités à 0 %, absence de fiscalité, de spread et de commission de change distincte. Les frais et l’accès effectifs au fonds américain dépendent du compte. Les horaires de clôture et le fixing de change diffèrent.

Les 80 règles croisent actif détenu (PSP5 ou SPMO), moyenne mobile simple du PSP5 en séances communes (50, 100, 150, 200, 250), exposition sous la moyenne (0, 25, 50, 75 %) et au-dessus (85, 100 %). Décision initiale puis première séance commune du mois, exécution à la clôture commune suivante, ajustement seulement lors d’un changement de cible. Première séance de test à compter du 19 novembre 2016. Classement jusqu’au 31 décembre 2020 selon le plus petit des deux gains en points face à PSP5, départage par ordre de grille. Treize règles dominent le témoin sur cette période. Une seule est retenue pour la suite, SPMO à 100 % au-dessus de la moyenne 200 et 75 % sinon. Apprentissage 14,19 %/an et DD −26,96 %, contre 11,78 % et −33,67 %. Période 2021+ séparée pour ce classement, déjà étudiée dans le projet.

| Période | SPMO filtré, rendement / DD | PSP5 passif | SPMO passif |
|---|---|---|---|
| 2021 au 19/11/2026 | 18,93 / −22,62 % | 15,57 / −23,19 % | 19,34 / −24,54 % |
| 3 ans | 26,92 / −22,62 % | 18,02 / −23,19 % | 28,20 / −25,05 % |
| 5 ans | 15,42 / −22,57 % | 10,71 / −23,15 % | 15,93 / −24,53 % |
| 10 ans | 16,92 / −26,96 % | 13,92 / −33,67 % | 17,41 / −30,98 % |
| 2021+, frais doubles et exécution à la 2e clôture | 18,81 / −23,33 % | 15,23 / −23,18 % | 19,69 / −24,53 % |

La mesure des drawdowns sur l’union des dates en reportant le dernier cours disponible pour chaque marché reproduit les quatre drawdowns historiques du candidat et du témoin. Sur 28 fenêtres de trois ans démarrant les 19 février, mai, août et novembre 2017 à 2023, 16 réussites conjointes. Départ août 2020, retard de 3,88 points/an. Départ février 2017, baisse plus profonde de 4,43 points. Les fenêtres se chevauchent.

## Tests de trajectoires

250 tirages à cinq ans et 250 à dix ans, graines initiales respectives 87005 et 87010. Bootstrap circulaire par blocs géométriques de moyenne 63 séances sur la série jointe des rendements EUR ajustés et de prix des deux ETF, 250 séances fictives par an, initialisation aux derniers cours avec 250 séances antérieures réelles. Ordres et signaux recalculés sur chaque trajectoire. Les simulations conservent la prime momentum réalisée dans l’échantillon source.

| Horizon | Candidat rendement / DD moyens | PSP5 rendement / DD moyens | Rendement supérieur | DD amélioré | Les deux |
|---|---|---|---:|---:|---:|
| 5 ans | 16,90 / −24,86 % | 14,88 / −25,23 % | 168 | 141 | 114/250 |
| 10 ans | 16,50 / −28,87 % | 15,18 / −30,32 % | 166 | 175 | 127/250 |

Diagnostic distinct, 1 000 recompositions de cinq ans des rendements de portefeuille déjà réalisés sur 2021+, blocs moyens de 63 séances, graine 481119, sans recalcul des signaux. Double réussite dans 345 cas. Les deux modèles reposent sur une histoire économique commune.

## Combinaison avec la v6 et décision

Après examen du premier candidat, autre famille exploratoire. Neuf budgets initiaux de 10 à 90 % du capital sur SPMO passif, solde en v6, sans transfert. Même classement sur 2016–2020. Le mélange retenu affecte 90 % à SPMO et 10 % à v6. Sur 2021+, 18,64 %/an et DD −22,88 %. Double réussite sur 16/28 fenêtres. Sur trois ans récents le DD atteint −23,24 % contre −23,19 % pour PSP5. Sélection secondaire postérieure à la lecture du premier audit.

Le témoin utilisateur à 15 % de PSP5 passif conserve un drawdown de −8,84 % sur dix ans et rapporte 11,61 %/an. La v6 rapporte 11,39 %/an avec −7,99 % de drawdown. SPMO filtré réalise le meilleur compromis historique des deux nouvelles pistes étudiées, avec une protection récente sensible aux conditions d’exécution. Aucun remplacement en production.

[Description du fonds et de son indice par Invesco](https://www.invesco.com/us/en/financial-products/etfs/invesco-sp-500-momentum-etf.html).
