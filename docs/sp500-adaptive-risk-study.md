# S&P 500 : recherche élargie et stabilité des périodes

La période de début septembre 2018 imposée dans l’interface est supprimée, à la
demande de l’utilisateur. Cinq ans par défaut ; choix 1/3/5/10 ans seulement, aucun
`start_date` injecté. Le rendement de 14,33 % de l’étude précédente ne décrit pas
la simulation actuelle sur cinq ans. La variante de régression existante reste
expérimentale, sans nouveau modèle de remplacement retenu par cette recherche.

## Recherche effectivement réalisée

Deux campagnes : **588 configurations**, puis **648 configurations**, largement
communes, cette dernière ajoutant les combinaisons adaptatives et les contrôles
à exposition constante. Ce ne sont pas 1 236 stratégies indépendantes. Certaines
combinaisons de paramètres sont économiquement identiques (par exemple le
plancher défensif d’un modèle toujours exposé avant son contrôle de volatilité).

Familles :

- Cours au-dessus de moyennes mobiles 100/150/200/250 séances.
- Vote de plusieurs horizons : 50/100/200 ou 100/150/200/250 séances.
- Momentum signé sur 63/126/252 ou 126/252/504 séances ; exposition selon le nombre
  de signaux positifs, plutôt qu’un signal binaire unique.
- Cassure de plus haut 126/252 séances avec sortie au plus bas sur un horizon
  moitié plus court ; calcul des seuils sur les seules séances précédentes.
- Moyenne mobile 200 séances avec bandes d’hystérésis ±1 % ou ±3 %.
- Exposition décroissante avec la baisse depuis le maximum des 252 séances,
  budget de baisse 10/15/20 %. Ce modèle ne garantit pas un plafond de perte.
- Ciblage de volatilité ou de volatilité baissière, estimée sur 63 séances,
  cible 10/15 % ; absence de levier, poids plafonné à 100 %.
- Combinaisons : plancher défensif 0/25/50 %, cadences 5/21 séances, bandes
  d’intervention 5/15 points pour limiter les frais.
- Modèle adaptatif : neuf experts de tendance/momentum, sélection des trois
  meilleurs Sharpe sur les 126/252/504 séances passées, moyenne de leurs signaux,
  avec ou sans contrôle de volatilité. Les performances fictives des experts
  utilisent leurs expositions retardées de deux séances, sans observation future.
  Leur classement ignore leurs commissions individuelles ; le portefeuille réel
  combiné paie les commissions de toutes ses transactions. Cette limite demeure.
- Contrôles simples avec exposition cible constante de 60/80 %, pour ne pas
  confondre effet des liquidités et qualité de choix des entrées.

Les adaptations mono-indice, les votes multi-horizons et les bandes de transaction
changent les modèles variance/momentum multi-actifs précédemment rejetés. Aucun
modèle rejeté n’a été réintroduit à l’identique dans l’application.

## Méthode et critères

Protocoles écrits dans les sorties avant calcul de chaque campagne. Copie privée
SQLite depuis connexion en lecture seule, aucune écriture dans la base utilisateur.
Empreinte : `3828d8f2e06fa105c15379ab28b7959e2deb34f373d1a8dd82e75fd013da724a`.

Choix des paramètres sur **l’indice américain total-return USD** : apprentissage
1993–2002, validation 2003–2012. Condition : sur chacune, perte maximale au plus
75 % du témoin, volatilité au plus 85 %, rendement annualisé au moins 80 % du
rendement positif du témoin et Sharpe au moins égal. Classement par le moins bon
des deux scores combinant réduction de drawdown, volatilité et rétention du
rendement. Pas de sélection sur la courbe ESE récente.

Le proxy USD est un diagnostic, pas un historique inventé de l’ETF PEA en EUR.
Les observations étaient déjà disponibles et étudiées ; cette séparation ne
constitue pas une période future inconnue.

Vérifications **après choix figé** :

- Indice USD 2013–2026, autre période séparée du choix.
- ETF ESE en EUR sur cinq et dix ans jusqu’au 13/11/2026.
- Quatorze fenêtres de trois/cinq ans avec débuts annuels de 2016 à 2023 selon
  l’horizon. Elles se chevauchent ; elles ne sont pas des échantillons indépendants.
- Frais de 1 % par montant acheté/vendu et retard d’exécution d’une séance
  supplémentaire sur les deux horizons ESE, sans nouvelle optimisation.

Critères d’adoption : sur cinq **et** dix ans, rendement annualisé au moins 14 %,
perte maximale au plus 80 % de celle d’ESE, volatilité au plus 90 %, Sharpe
supérieur d’au moins 0,10. Sur au moins 75 % des fenêtres annuelles : mêmes
réductions de risque et conservation d’au moins 80 % du rendement positif du
témoin. Vérification des critères d’horizon également sous frais/délai dégradés.
Ces exigences répondent à la demande utilisateur ; leur échec ne signifie pas
qu’aucun compromis moins exigeant soit utile.

Chaque nouvelle simulation débute avec 10 000 € en cash, titres entiers pour ESE,
fractions pour l’indice, commissions 0,5 % de chaque montant acheté/vendu,
liquidités non rémunérées. Aucun levier ni position inverse. Signal à une clôture
connue, exécution à la clôture suivante. Comparaison au même support conservé,
mêmes dates, capital et frais. Volatilité annualisée sur 252 séances, CAGR
calendaire, Sharpe à taux de référence nul. Pas de vente imposée au terme.

## Cadence et indépendance du zoom

La première campagne utilise des cadences ancrées sur le début de simulation.
La seconde corrige cette source de variation : vendredi pour la cadence
hebdomadaire, première séance observée du mois pour la mensuelle. La première
allocation est possible dès le signal initial ; les révisions suivantes suivent
le calendrier. Aucun besoin de connaître la séance future pour détecter ces dates.

Tous les indicateurs sont calculés à partir de l’historique antérieur au signal,
indépendamment de la période affichée. Une date de départ différente implique
néanmoins un capital et des positions différents, donc une performance différente
reste normale. Aucun algorithme ne peut rendre une performance de cinq ans
identique à celle de dix ans.

La cadence calendaire est une piste de cohérence testée en recherche ; elle n’est
pas appliquée silencieusement à la régression défensive existante. Le changement
de modèle n’est pas retenu : les résultats financiers ci-dessous sont insuffisants.

## Résultats, sans éliminer les échecs

La première campagne a 112 configurations satisfaisant les critères sur les deux
anciennes périodes. Celle sélectionnée est une moyenne mobile 200 séances avec
bande ±3 %, cible de volatilité 15 %, cadence cinq séances et bande de révision
15 points. Elle obtient seulement **7,19 % annualisés sur cinq ans et 7,87 % sur
dix ans**, contre 11,51 % et 14,52 % pour ESE. Rejetée malgré le bon apprentissage.

La seconde a 141 configurations qualifiées sur les anciennes données. Le choix
figé est une moyenne mobile 200 séances, contrôle de volatilité 10 %, décisions
mensuelles, bande de révision cinq points, phase défensive en cash :

| Horizon ESE | Méthode sélectionnée | ESE conservé |
|---|---:|---:|
| CAGR cinq ans | 4,96 % | 11,51 % |
| Volatilité cinq ans | 9,34 % | 15,15 % |
| Perte maximale cinq ans | −13,53 % | −23,25 % |
| Sharpe cinq ans | 0,56 | 0,78 |
| CAGR dix ans | 6,33 % | 14,52 % |
| Volatilité dix ans | 9,93 % | 16,09 % |
| Perte maximale dix ans | −14,22 % | −33,62 % |
| Sharpe dix ans | 0,66 | 0,91 |

Elle réduit les pertes, mais sacrifie trop de rendement. Aucune des quatorze
fenêtres ne satisfait simultanément le critère de risque et de conservation du
rendement. Frais doublés : 3,87 % annualisés sur cinq ans et 5,28 % sur dix ans.
Retard supplémentaire : 3,49 % et 5,69 %. Sur l’indice USD 2013–2026 : 6,10 %
contre 14,57 %. **Ce modèle n’est pas adopté.**

Le nombre de configurations satisfaisant simultanément tous les critères
rendement/risque sur les deux horizons ESE, même en examinant toute la grille à
titre descriptif, est **zéro dans les deux campagnes**. Ce contrôle ne sert pas à
choisir a posteriori un autre gagnant. Il ne prouve pas l’impossibilité mathématique
d’une stratégie meilleure : seules les familles effectivement décrites ont été
explorées, avec les données et hypothèses présentes.

## Conclusion pratique

La recherche n’a pas produit la stratégie de long terme demandée. La baisse du
risque observée est obtenue surtout par la réduction d’exposition et peut coûter
beaucoup de rendement, notamment lors des reprises. Aucun signal testé ne doit
être présenté comme une indication future correcte démontrée. Les résultats
agrégés séduisants de la régression longue antérieure ne changent pas ce constat.

Changement appliqué : suppression de la période spéciale et retour à cinq ans
par défaut. Aucune nouvelle méthode promue en production faute de résultats
suffisants. La régression défensive existante reste un outil expérimental ; son
existence dans l’application ne constitue pas une recommandation d’adoption.

## Reproduction et contrôles

```sh
PYTHONPATH=backend uv run python scripts/study_sp500_adaptive_risk.py
PYTHONPATH=backend:scripts uv run python scripts/study_sp500_adaptive_extension.py
uv run pytest -q backend/tests/unit/test_sp500_adaptive_risk.py
```

Sorties locales ignorées : `data/backtests/sp500-adaptive-risk.json`,
`data/backtests/sp500-adaptive-calendar.json`. Elles conservent protocoles, grilles,
résultats complets par horizon, benchmarks et stress, y compris tous les échecs.

Tests : invariance des signaux en supprimant les données futures, poids bornés,
comptabilité indépendante avec frais/arrondis/délai, stabilité des dates de décision
calendaires après changement de début. Les tests navigateur vérifient le retour
à cinq ans, la disparition de la période spéciale et la sélection de dix ans.
