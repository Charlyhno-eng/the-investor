# Dimensionnement des entrées de retour à la moyenne

Le journal fourni a été reproduit avec les mêmes 46 opérations, sur les 14 actifs suivants : GTT, Euronext, Prysmian, Air Liquide, Technip Energies, Thales, UCB, Airbus, TotalEnergies, ASML, Bitcoin, Safran, Schneider Electric et argenx. Les petits achats de 83 €, 89,88 €, 90,10 €, 106,62 € et 218,30 € provenaient bien de la consommation des liquidités restantes. L’ancienne règle considérait toute quantité exécutable comme suffisante et interdisait ensuite les renforcements, figeant ces petites positions jusqu’à leur sortie.

## Nouvelle règle

Chaque entrée doit atteindre un budget minimal de **min(10 %, 1/N) de la valeur courante totale du portefeuille**, frais d’achat compris. N compte les actions et cryptomonnaies de l’univers négociables à cette séance, hors lignes passives et avant filtrage des seuls signaux négatifs. Cela donne 10 % pour dix actifs ou moins, environ 7,14 % pour 14 actifs, et 5 % pour 20. Le plancher suit la valeur du portefeuille et n’est pas un montant fixe en euros. Cette règle est une décision de dimensionnement, pas un paramètre choisi pour maximiser le rendement du backtest.

En titres entiers, le minimum est arrondi au nombre de titres supérieur. Le plafond de 25 %, frais d’achat compris, continue de s’appliquer. Avec 10 000 €, un minimum de 10 % et des titres à 80 €, il faut ainsi 13 titres (1 040 € hors frais) ; acheter un seul titre à 80 € ne suffit plus. Les cryptomonnaies conservent les quantités fractionnaires.

- Lorsque les liquidités financent des entrées suffisamment grandes, elles sont utilisées sans vente supplémentaire, même si la taille obtenue est inférieure à la cible d’allocation.
- Sinon, une seule position peut financer les achats de la séance : celle dont l’écart-type connu est le plus élevé parmi les valeurs positives ou nulles. La vente couvre seulement le complément nécessaire pour atteindre les minimums des entrées retenues, frais compris. Elle ne finance pas automatiquement des positions au plafond de 25 %.
- Si l’ensemble des signaux simultanés ne peut pas atteindre son minimum, les écarts-types les plus négatifs sont prioritaires. Le moteur préfère une véritable position à plusieurs petites lignes.
- Une entrée impossible est ignorée sans vente inutile. Le moteur peut la reconsidérer à une séance suivante tant que le signal est toujours actif ; il n’utilise aucune information future pour la date initiale.
- Les positions encore sous leur tendance, les scores inconnus, les lignes passives et leurs budgets réservés ne financent pas ces achats. Aucun deuxième actif n’est vendu pour compléter le financement.
- Les positions déjà ouvertes ne sont pas automatiquement renforcées, même si leur valeur devient ensuite inférieure au plancher. Le seuil de ±1,4 σ reste inchangé.

## Vérifications sur le journal reproduit

Paramètres : capital initial 10 000 €, frais de 0,5 % à l’achat et à la vente, titres entiers pour les actions et quantités fractionnaires pour Bitcoin. Période : 15 novembre 2021 au 13 novembre 2026. Données locales lors de cet audit.

| Mesure | Avant | Après |
|---|---:|---:|
| Nombre d’opérations | 46 | 50 |
| Plus petit achat, hors frais | 83,00 € | 647,52 € |
| Plus petite entrée / valeur du portefeuille, frais compris | 0,89 % | 7,15 % |
| Exposition moyenne au marché | 74,34 % | 81,79 % |
| Ventes de financement | 2 | 7 |
| Frais payés | 423,67 € | 456,91 € |
| Rendement net sur la période | +124,85 % | +139,09 % |
| Drawdown maximal | −23,66 % | −22,58 % |

Par exemple, Prysmian passe de 3 titres / 89,88 € à 23 titres / 689,08 € le 26 janvier 2022. Les achats minuscules UCB et Schneider ne sont plus réalisés à leur date initiale faute de financement suffisant. Le 24 juin 2022, une réduction unique d’argenx finance des entrées UCB (647,52 €), Air Liquide (668,93 €) et Schneider (700,44 €). Chaque entrée respecte le plancher de la valeur du portefeuille à cette date. Les montants peuvent donc être inférieurs à 1 000 € sans redevenir des positions symboliques.

Le financement plus fréquent augmente les frais : cette règle ne cherche pas à minimiser le nombre de ventes à tout prix. Le rendement observé s’améliore ici, mais cela ne démontre pas une supériorité générale ou future. Il faut relancer la validation pour obtenir le nouveau journal ; un ancien résultat affiché n’est pas recalculé automatiquement.

Les tests couvrent les reliquats de 80 €, le financement du seul complément, les arrondis de titres entiers, l’impossibilité de financement, les signaux simultanés, les grands univers et la protection des budgets passifs. Les tests de comptabilité indépendante et de causalité restent actifs : frais, liquidités, positions, dividendes et valeurs quotidiennes doivent concorder.

## Reproduire

```sh
PYTHONPATH=backend uv run python scripts/audit_validation.py --assets yf-gtt.pa yf-enx.pa yf-pry.mi yf-ai.pa yf-te.pa yf-ho.pa yf-ucb.br yf-air.pa yf-tte.pa yf-asml.as yf-btc-usd yf-saf.pa yf-su.pa yf-argx.br --output /tmp/validation-journal.json
```

L’univers figure aussi dans les audits par défaut sous le nom `journal_14`. Le rapport JSON expose le plus petit montant d’entrée et sa plus petite part de portefeuille frais compris. Les résultats peuvent changer avec les données disponibles ; les règles de taille sont décrites dans le protocole de la réponse API.
