# HMM actif à deux régimes — correction du 6 novembre 2026

Le moteur utilisé par l’API et l’interface est désormais `hmm-two-state-dominant-filtered-live-v3`. L’ancienne règle de prévision à cinq séances comparée aux frais est retirée du parcours actif. Les caches de résultats antérieurs sont invalidés par la version.

Deux états gaussiens sur les rendements logarithmiques quotidiens, normalisation apprise sur l’entraînement, trois initialisations et sélection par vraisemblance d’entraînement. L’état à moyenne entraînée supérieure est « haussier », l’autre « autre ». Ces noms sont relatifs : les deux moyennes peuvent être positives ou négatives. Le nombre d’états est fixé à deux, sans validation comparative de 1/2/3 états.

Investi lorsque l’état supérieur domine, en liquidités sinon. Filtrage causal, paramètres figés sur le test, signal à t exécuté à la clôture t+1. Les frais réduisent le capital à chaque ordre et ne changent jamais les décisions ou le nombre d’ordres. Le dernier jour liquide toute position, sans nouvel achat. Le benchmark historique conserve ses conventions d’entrée et ses deux frais ; le [rapport sur les régimes persistants](hmm-persistent.md) documente aussi un contrôle à entrée identique.

## Vérification sur le catalogue réel

Le catalogue contient maintenant **24 actions**. Toutes sont évaluées sur leurs périodes par défaut, à **0,5 % par achat et vente**. **24 calculs réussis, aucune exclusion, aucune erreur, 24 actions avec des ordres**, soit 1 108 transactions. Les résultats ne sont pas forcés : une autre période sans régime haussier dominant peut légitimement rester en liquidités.

Sur GTT, même fenêtre que la capture (28 juin 2024–6 novembre 2026) : **34 ordres, exposition 95,36 %, stratégie +40,32 %, conservation +60,19 %**. Il n’y a plus de blocage des achats sous le seuil de frais.

**La correction du fonctionnement ne valide pas la rentabilité : 1/24 actions bat la conservation sur cet audit.** Le contrôle de majorité stricte reste en échec et n’a pas été assoupli. Les anciennes évaluations sur 19 actions restent des résultats historiques ; elles ne décrivent pas ce catalogue élargi.

| Action | Stratégie nette | Conservation nette | Ordres |
| --- | ---: | ---: | ---: |
| Apple Inc. | -4.23 % | +64.88 % | 40 |
| Crédit Agricole S.A. | +30.00 % | +43.54 % | 16 |
| L'Air Liquide S.A. | +5.98 % | +29.99 % | 24 |
| Airbus SE | +23.98 % | +54.87 % | 34 |
| ASML Holding N.V. | -54.23 % | +35.32 % | 94 |
| BE Semiconductor Industries N.V. | -46.77 % | -6.16 % | 80 |
| BNP Paribas SA | +54.48 % | +77.56 % | 12 |
| COFACE SA | +12.92 % | +42.22 % | 22 |
| AXA SA | +35.25 % | +62.64 % | 16 |
| Vinci SA | -0.01 % | +22.20 % | 22 |
| Engie SA | +67.15 % | +103.73 % | 32 |
| Gaztransport & Technigaz SA | +40.32 % | +60.19 % | 34 |
| LVMH Moët Hennessy - Louis Vuitton, Société Européenne | -61.59 % | -40.71 % | 128 |
| Microsoft Corporation | -0.12 % | +23.93 % | 36 |
| NVIDIA Corporation | +14.56 % | +57.20 % | 30 |
| Orange S.A. | +31.52 % | +79.56 % | 70 |
| Palantir Technologies Inc. | -10.75 % | +128.02 % | 38 |
| Hermès International Société en commandite par actions | -72.98 % | -37.17 % | 122 |
| Safran SA | +61.98 % | +49.00 % | 34 |
| Sanofi | -16.31 % | +1.71 % | 32 |
| Schneider Electric S.E. | -33.94 % | +2.95 % | 68 |
| Technip Energies N.V. | +2.31 % | +28.53 % | 36 |
| Tesla, Inc. | -20.99 % | +107.44 % | 74 |
| TotalEnergies SE | +37.31 % | +42.62 % | 14 |

[CSV complet](hmm-live.csv). Source, paramètres, diagnostics, empreintes des données et reçus : `data/backtests/hmm-live-v3/results.json`.

```sh
PYTHONPATH=backend .venv/bin/python scripts/audit_hmm_stocks.py --output /tmp/hmm-live-v3-audit.json
```

Ajouter `--assert-majority` vérifie le critère financier séparément et retourne le code 1 tant qu’il n’est pas atteint. Les tests de fonctionnement vérifient notamment que des frais élevés ne bloquent ni achat ni vente, les décisions sont causales, la liquidation et les frais sont corrects, et les anciens résultats ne sont pas réutilisés.
