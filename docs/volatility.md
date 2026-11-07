# Frontière de Markowitz

Les onglets Frontières d’efficience affichent un point par actif et le S&P 500
en étoile bleue.
Aucun nuage aléatoire, point agrégé du portefeuille, minimum/Sharpe simulé,
panneau de composition ou sélection d’actifs. Les noms et valeurs apparaissent au survol, au focus clavier ou au toucher.
Le tableau de détail est replié par défaut. Le graphique est plus haut, sans
légende ni étiquettes permanentes. Les axes s’ajustent aux données.

## Données

Historiques ajustés des actions et S&P 500 total return (`^SP500TR`) convertis
en EUR avant calcul. Change connu à la date du prix, vieux de sept jours au plus.
Prix non interpolés. Dates communes sur 1/3/5/10 ans jusqu’à la dernière date
commune disponible. Si un actif est mensuel, toutes les séries utilisent le
dernier prix de chaque mois terminé. Minimum : 21 variations quotidiennes ou
12 mensuelles. Les séries de taux sans prix obligataire sont signalées hors
graphique. Les références manquantes passent par la file d’import existante.

À partir des rendements simples `R[t] = P[t]/P[t-1] - 1`, estimer
`μ = moyenne(R) × A` et `Σ = covariance(R, ddof=1) × A`, avec A = 252 sur les
séances communes du S&P 500 et A = 12 en mensuel. Chaque actif est placé en
`(sqrt(Σ[i,i]), μ[i])`, en pourcentage. Le rendement moyen historique estime
le rendement attendu : il ne s’agit ni d’un CAGR ni d’une prévision.

## Optimisation

Pour chaque rendement cible, minimiser `wᵀΣw` sous les contraintes
`1ᵀw = 1`, `μᵀw = cible` et `0 ≤ w ≤ 1` (sans vente à découvert).
Calcul du minimum global de variance puis 81 cibles entre ce minimum et chacun
des deux extrêmes de rendement. SLSQP avec gradient analytique, covariance
mise à l’échelle et rendements normalisés. La convergence, la finitude et le
respect des contraintes sont contrôlés. Pour deux actifs à rendements distincts,
les égalités déterminent directement la solution analytique. Pas de simulation
aléatoire ni d’inversion de covariance ; matrices singulières acceptées.

La branche supérieure efficiente est en trait plein. La branche inférieure
à variance minimale pour un rendement imposé, mais dominée par le minimum
global, est en pointillés. Les échantillons sont reliés sans marqueurs.

Dans le portefeuille, l’univers optimisé contient uniquement les actifs détenus
valorisables. Le S&P 500 est un comparatif extérieur. Sur une fiche individuelle,
l’univers contient l’actif et le S&P 500. Un portefeuille à un seul actif n’a
pas de courbe de diversification. Avec des rendements égaux, l’ensemble efficient
se réduit au minimum de variance. Avec des rendements proches, la courbe peut
être presque horizontale ; sa forme dépend des données.

## Références et vérification

[MOSEK — Markowitz portfolio optimization](https://docs.mosek.com/portfolio-cookbook/markowitz.html)
et [CVX Group — Portfolio optimization](https://www.cvxgrp.org/cvx_short_course/docs/applications/notebooks/portfolio_optimization.html).

Tests backend : comparaison à une solution analytique connue, covariance
singulière, rendements négatifs/identiques, variance nulle, séparation du
comparatif, dates et EUR. Tests navigateur ordinateur/mobile : nombre exact
de points, noms au survol, tableau repliable, courbe, absence de simulations/contrôles,
périodes et erreurs.
