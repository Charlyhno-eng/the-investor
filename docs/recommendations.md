# Recommandation action : méthode et comparaison

## Périmètre et signaux

Seules les actions visibles portant une étoile or (détenues) ou argent (watchlist) sont candidates. Aucune autre action de la bibliothèque, aucun ETF ni aucune cryptomonnaie ne reçoit de recommandation. Les données restent en devise de cotation, sans conversion de change. Les poids et la référence sont ceux du Momentum partagé.

- **M** : score Momentum pondéré sur 36, 12 et 6 mois, dernier mois exclu, dans [la méthode Momentum](momentum.md).
- **z** : résidu logarithmique le plus récent divisé par l’erreur standard résiduelle, issu de la même régression OLS que la colonne Régression du Portfolio. Fenêtre : cinq dernières années disponibles ; au moins 30 observations. `ln(P_j) = α̂ + β̂ t_j + ε_j`, `σ̂ = √(Σ ε_j²/(n−2))`, `z = ε_n/σ̂`.

L’écart mesure une distance à une tendance passée, sans garantir un retour à cette droite. Ce n’est pas un z-score à distribution normale garantie ni une probabilité. Le Momentum utilise les horizons disponibles avec des poids recalculés (mention « historique partiel » si nécessaire) et doit avoir des cours récents à la date de l’univers ; la date de régression doit être à moins de sept jours de celle du Momentum. Un écart non fini, une dispersion quasi nulle ou des données absentes rendent la recommandation indisponible.

## Calcul retenu

`D = 50 × [1 − tanh(z / 1,5)]`

`A = 0,7M + 0,3D`

D est un score de décote sur 100 : 50 sur la droite de régression, supérieur à 50 en dessous, inférieur à 50 au-dessus. Plus l’écart signé z est négatif, plus D augmente, sans seuil bloquant sous −2 σ. Il s’agit de la position par rapport à la droite, pas de la valeur de la dispersion résiduelle elle-même. La fonction tanh limite progressivement les valeurs extrêmes.

A est la priorité d’entrée sur 100, combinant 70 % de Momentum et 30 % de décote. À Momentum constant, un z plus négatif favorise toujours l’entrée ; à z constant, un Momentum plus élevé augmente la priorité. La priorité peut dépasser le Momentum, et une décote peut compenser un Momentum inférieur à 60. Par exemple, un Momentum de 25 ne peut jamais dépasser 47,5 de priorité, même avec une décote extrême. Les poids, l’échelle de 1,5 σ et les seuils sont heuristiques, sans calibration historique ; A n’est pas un rendement attendu.

Les règles sont évaluées dans cet ordre :

1. Détenue et M < 40 : **Vendre**.
2. Détenue, 40 ≤ M < 55 et z ≥ 1,5 : **Alléger**.
3. A ≥ 60 : **Renforcer** si détenue, **Acheter** en watchlist.
4. Sinon **Conserver** si détenue, **Attendre** en watchlist.

Il n’y a plus de seuil de Momentum à 60 ni de limite d’entrée à +0,5 σ : l’entrée dépend du score combiné. Les décisions de vente et d’allègement conservent leur priorité. Les seuils créent des transitions franches ; modifier les poids ou la référence du Momentum peut modifier l’indication.

## Vérification sur les exemples fournis

Ces calculs utilisent les valeurs arrondies du tableau de l’utilisateur ; les résultats de l’application utilisent toute la précision disponible.

| Action | Momentum | z | Décote D | Priorité A | Indication |
|---|---:|---:|---:|---:|---|
| GTT | 63.2 | -0.75 | 73.11 | 66.17 | Renforcer |
| Safran | 61.7 | -2.77 | 97.57 | 72.46 | Renforcer |
| Airbus | 51.9 | -0.58 | 68.42 | 56.86 | Conserver |
| Technip Energies | 41.6 | -1.41 | 86.76 | 55.15 | Conserver |
| Schneider Electric | 55.6 | -2.23 | 95.14 | 67.46 | Acheter |
| Thales | 52.0 | -1.68 | 90.38 | 63.51 | Acheter |
| ASML | 64.2 | +0.49 | 34.22 | 55.21 | Attendre |
| Air Liquide | 54.4 | +0.87 | 23.87 | 45.24 | Attendre |
| TotalEnergies | 58.0 | +1.23 | 16.25 | 45.47 | Attendre |

Les tests vérifient ces neuf scénarios, l’absence de seuil bloquant sous −2 σ, la monotonie par rapport aux deux signaux, les bornes sur plus de 5 000 couples (M, z), les règles de détention et les entrées invalides. Les tests navigateur vérifient notamment Schneider avec un Momentum inférieur à 60 et une indication d’achat, le périmètre et l’affichage de la formule sur ordinateur et mobile. Ces tests valident la cohérence de la règle choisie, pas sa rentabilité future.

## Limites

Aucun backtest hors échantillon ni comparaison de performance nette de frais n’a été effectué. Les scénarios testent la logique choisie, pas la rentabilité. Les indications n’intègrent ni valorisation fondamentale, ni diversification, ni frais, fiscalité ou besoin de liquidités ; elles ne fixent aucun montant d’ordre. Le score et le résidu proviennent des mêmes prix et ne sont pas deux preuves indépendantes.

Les stratégies momentum peuvent subir des pertes importantes lors de retournements : [Daniel et Moskowitz, Momentum Crashes, NBER w20439](https://www.nber.org/papers/w20439). Les paramètres restent expérimentaux et sont visibles dans l’application.
