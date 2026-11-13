# Audit du retour à la moyenne — 13 novembre 2026

Ce document conserve les résultats du premier audit à 25 %, avant l’ajout du plancher de taille des positions. Les règles actuelles et la reproduction du journal de 46 opérations sont décrites dans [l’audit du dimensionnement](validation-position-sizing.md).

## Pourquoi une vente intervenait au troisième achat

Les trois achats cités représentent 3 225,60 + 3 285,70 + 3 668,54 = **10 179,84 €**, soit **10 230,74 € frais d’achat compris** à 0,5 %. Les trois montants ne rentrent donc pas dans les 10 000 € initiaux, avant prise en compte des autres opérations et dividendes. Le plafond précédent était calculé sur la **valeur courante** du portefeuille : son appréciation augmentait la taille du nouvel achat, sans augmenter les liquidités. Ce n’était pas une réserve de trois enveloppes fixes.

Le défaut de gestion était de vendre pour compléter la taille cible, même lorsqu’un achat légèrement plus petit était déjà possible avec les liquidités. Cela explique les petites ventes de financement répétées ; respecter un plafond ne suffit pas à les éviter.

## Règles corrigées

- Chaque entrée est limitée à **25 % de la valeur courante totale, frais d’achat compris**, dès le premier ordre. Les quantités entières sont arrondies vers le bas. Une position qui dépasse ensuite le plafond par appréciation n’est pas automatiquement vendue.
- Les liquidités déterminent la taille de l’achat lorsqu’elles permettent son exécution. Le moteur ne vend plus pour simplement compléter la cible. Pour plusieurs signaux, il réserve au moins une unité à chaque entrée retenue en mode titres entiers, puis partage le budget.
- À défaut, **une seule ligne** peut financer les achats de la séance : celle dont le z-score connu est le plus élevé parmi les valeurs positives ou nulles. Les positions encore sous leur tendance et les scores inconnus ne financent pas d’entrée. Cela évite de liquider une position encore sous le seuil d’achat et de la racheter aussitôt sur un signal toujours actif.
- Les achats impossibles sont réduits ou ignorés, sans deuxième vente ni apport de liquidités implicite. Les signaux simultanés les plus négatifs passent en premier pour les unités minimales disponibles.
- Le seuil reste fixé à ±1,4 σ. Les signaux utilisent les informations de la clôture précédente ; les ordres sont exécutés à la clôture commune suivante. Aucun seuil n’a été choisi pour maximiser le résultat sur ces historiques.
- Le journal expose maintenant les liquidités après chaque opération. L’API fournit aussi les liquidités avant l’ordre et la valeur du portefeuille avant les opérations de la séance.
- Le calcul historique peut utiliser les références déjà stockées pendant leur rafraîchissement horaire : une actualisation en attente ne bloque plus un historique exploitable. Les conversions restent limitées aux taux de change connus à la date considérée et datant de sept jours au maximum.
- Le plan de financement n’effectue plus 60 itérations lorsque le budget cible est immédiatement réalisable. Les itérations restent réservées aux financements contraints.

## Vérifications

Les tests reconstruisent indépendamment les quantités, les liquidités, les frais, les valeurs quotidiennes et les gains nets réalisés, incluant le coût moyen d’achat et les dividendes. Ils couvrent les actions entières, les cryptomonnaies fractionnaires, les actifs passifs, leurs budgets réservés, les introductions récentes et les modifications de cours futurs. Des scénarios ciblés vérifient les quatre premières entrées lorsque la valeur du portefeuille augmente, l’absence de vente pour compléter un ordre abordable, le plafond frais compris, les positions négatives protégées et l’unique ligne de financement.

Le script `scripts/audit_validation.py` ajoute des vérifications sur les données locales : chronologie des ordres, identité des liquidités, frais, plafond d’entrée, score et nombre de ventes de financement. Il calcule aussi séparément les performances des deux dernières années ; ce découpage descriptif ne constitue pas un nouvel échantillon indépendant.

## Comparaison sur les historiques locaux

Période : **15 novembre 2021 au 13 novembre 2026**. Capital : 10 000 €. Frais : 0,5 % à chaque achat/vente. Titres entiers activés pour les actions ; cryptomonnaies fractionnaires. Comparaison entre la règle précédente à 33 % et l’ensemble des règles corrigées ci-dessus. Ces univers illustratifs ne reconstituent pas la simulation complète de l’utilisateur, dont seule une partie du journal est connue.

| Univers | Rendement net avant → après | Drawdown avant → après | Frais avant → après | Ventes de financement avant → après |
|---|---:|---:|---:|---:|
| UCB, argenx, TotalEnergies | 91.44 → 65.38 % | -11.71 → -9.15 % | 202.55 → 146.64 € | 0 → 0 |
| 11 actions européennes | 183.65 → 188.31 % | -20.70 → -18.81 % | 588.87 → 497.09 € | 11 → 2 |
| BTC, ETH, SOL, BNB | 9.41 → 9.25 % | -44.33 → -37.01 % | 244.07 → 180.65 € | 1 → 0 |

Les 11 actions sont Airbus, ASML, GTT, Euronext, Air Liquide, Safran, argenx, Prysmian, UCB, TotalEnergies et Technip Energies. Le détail des identifiants se trouve dans le script. Les trois premiers titres de l’extrait forment un univers distinct, pas une reconstitution de toutes les lignes du portefeuille.

La correction ne garantit pas une amélioration du rendement brut : sur l’univers de trois actions, le rendement baisse avec l’exposition moyenne (47,76 % auparavant, 37,31 % après), et le drawdown diminue aussi. L’achat-conservation de ces trois actions gagne 175,71 % avec un drawdown de −23,79 %, contre +65,38 % et −9,15 % pour la stratégie corrigée. Même **sans frais**, celle-ci ne gagne que 67,57 % : sa sous-performance ne provient donc pas uniquement des frais. Les périodes en liquidités, la sélection des signaux et les sorties anticipées des longues hausses restent des explications possibles ; le test ne permet pas de les attribuer précisément sans analyses contrefactuelles supplémentaires.

Sur les 11 actions, les ventes de financement passent de 11 à 2 et les frais de 588,87 à 497,09 €. Le rendement net passe de 183,65 % à 188,31 %, avec un drawdown moins profond. Ce résultat ne s’étend pas systématiquement aux autres univers : les quatre cryptomonnaies ont un rendement légèrement inférieur après correction, et un drawdown moins profond.

Les résultats dépendent fortement de l’univers et de la période. La bibliothèque contient des actifs choisis aujourd’hui et les compositions historiques ne sont pas reconstituées. Modifier des seuils à répétition pour améliorer ce même historique augmenterait le risque de surajustement décrit par [Bailey et al., The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf). Les corrections retenues portent sur la cohérence des règles, les frais évitables et la traçabilité ; elles ne démontrent pas une performance future.

## Reproduire l’audit

Depuis la racine du projet :

```sh
PYTHONPATH=backend uv run python scripts/audit_validation.py --output /tmp/validation-audit.json
```

Pour le seul univers des trois lignes citées :

```sh
PYTHONPATH=backend uv run python scripts/audit_validation.py --assets yf-ucb.br yf-argx.br yf-tte.pa --output /tmp/validation-extrait.json
```

Le script teste par défaut 0,5 % puis 0 % de frais. Options : `--years 1|3|5|10`, `--capital`, `--fees`, `--no-whole-shares`. Les résultats sont recalculés sur les données locales disponibles et peuvent changer après leur actualisation. Une référence totalement absente produit `pending` plutôt qu’une simulation inventée. Le script ne recherche aucun paramètre gagnant et ne conserve pas la meilleure combinaison a posteriori.
