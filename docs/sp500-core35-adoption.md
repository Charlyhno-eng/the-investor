# Adoption de la combinaison 65/35 — 15 novembre 2026

**Archive v5 :** remplacée ensuite par [la régression orientée Sharpe v6](sp500-sharpe-adoption.md). Les règles, chiffres et vérifications ci-dessous concernent l'adoption historique v5 uniquement.

L'utilisateur a explicitement demandé l'implémentation après présentation des résultats et limites de la [recherche élargie](sp500-broader-compromise-study.md). La version alors adoptée était **`core35_slow_defensive_v5`**. Adoption explicite ne signifie pas réussite de tous les critères : seuil de retard cinq ans manqué de peu, Calmar légèrement inférieur au marché dix ans, et protection historique moins forte que v4 restent documentés.

## Politique v5 archivée

Capital initial séparé en trois budgets indépendants :

- **35 % achat-conservation PSP5**, achat à la première clôture admissible après le début ; quantité ensuite constante, reliquat de titres entiers et dividendes éventuels dans cette poche.
- **48,75 % règle lente**, soit 75 % du budget actif de 65 % : régression logarithmique 60 mois, état initial reconstitué uniquement avec les signaux mensuels strictement antérieurs au début ; mêmes entrées/sorties que v4.
- **16,25 % règle défensive**, soit 25 % du budget actif : 18 mois, état initial défensif, mêmes seuils et cadence de cinq séances ancrée au test.

Les deux poches de régression ciblent toujours 25 % d'ETF en état défensif et 100 % sinon, à l'initialisation ou au changement d'état uniquement. Les poids dérivent ensuite. Pas de transfert, rééquilibrage entre budgets, compensation des ordres opposés, levier ni substitution d'instrument. Les seuils et le replay de v4 restent identiques ; seule la répartition du capital et la poche passive sont ajoutées. La variante 50/50 n'est pas adoptée.

PSP5.PA EUR uniquement, référence identique. Frais par défaut 0,12 % par achat/vente, paramètres explicites respectés ; titres entiers et frais par poche, exécution à la clôture suivante. Minimum 18 mois pour la simulation admissible, cinq ans par défaut et choix 1/3/5/10 ans. Aucun changement du générateur, des graines, des paramètres de bruit/blocs, des données utilisateur ou des quantités enregistrées.

Même moteur pour validation historique, simulation unitaire et lots. Le journal distingue « Poche passive · achat-conservation ». Les trois poches, leurs liquidités et quantités finales sont exposées dans l'API ; le protocole décrit leurs budgets et le caractère initial uniquement de la poche passive. La stratégie conserve son nom et son entrée native dans l'application, sans nouveau badge ni onglet personnel.

## Vérification contre la recherche

`PYTHONPATH=backend:scripts uv run python scripts/verify_sp500_core35.py`

Sur copie SQLite privée : **18 cas** — historique 1/3/5/10 ans avec frais 0/0,12/0,24 %, six parcours synthétiques figés cinq/dix ans. Métriques identiques à la recherche indépendante à 1e−9, frais à 1e−6 €. Les comparaisons historiques 3/5/10 et synthétiques utilisent aussi les résultats archivés avant implémentation. Source PSP5 propre, livres par poche non négatifs, une seule entrée passive et aucun bénéfice antérieur ajouté. Sortie nouvelle `data/backtests/sp500-core35-production-verification.json`.

`PYTHONPATH=backend uv run python scripts/verify_sp500_simulation.py --batch-count 100`

Ce vérificateur courant utilise désormais v5 et écrit `data/backtests/sp500-core35-simulation-verification.json` ; l'ancien rapport Amundi/v4 reste intact. Les vérificateurs ESE figés et les contrôles de production v4 incorporés dans les anciens scripts d'étude sont des archives : ils ne vérifient pas v5. Les fonctions de recherche gardent leur témoin v4 pour reproduire les anciennes comparaisons.

Ces contrôles prouvent la correspondance logicielle avec la variante adoptée, pas une supériorité financière prospective.

## Résultat des contrôles d'intégration

- Backend : **429 tests réussis**, Ruff backend/scripts sans erreur.
- Frontend : `npm run check` réussi (40 tests unitaires, contrôles et compilation).
- Navigateur : **30 parcours ordinateur/mobile** validation, stratégies et simulation S&P ; l'affichage de la poche passive est vérifié explicitement dans les deux formats.
- Correspondance financière du moteur : les **18 cas** reproduisent la recherche indépendante ; **9 scénarios unitaires et 100 parcours cinq ans consécutifs** passent le vérificateur de simulation courant, sans exclusion d'échec.

Aucun rapport historique ESE ou Amundi/v4 n'est réécrit. Le test de comparaison comptable historique confronte désormais la production à un vrai budget v4 de 6 500 € complété d'un achat passif de 3 500 €, en titres entiers et fractionnaires, plutôt qu'à l'ancienne règle appliquée aux 10 000 € entiers.
