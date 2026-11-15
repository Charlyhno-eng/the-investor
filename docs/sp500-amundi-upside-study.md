# Recherche de surperformance S&P 500 Amundi — 14 novembre 2026

**Conclusion : aucune nouvelle règle ne remplit la demande de surperformance avec une nette réduction simultanée de volatilité et de drawdown. La production reste v4.**

## Données et protocole

PSP5.PA, Amundi PEA S&P 500 UCITS ETF Acc, EUR ; 3 197 cours locaux du 20/05/2014 au 13/11/2026. Aucun cours BNP renommé ni indice USD substitué. Prix ajustés et prix bruts strictement identiques sur cette copie. Chaque expérience utilise une sauvegarde privée de SQLite ouverte en lecture seule. Empreinte : `34ed8b4132406f93e553e1ca8046e92aab47804ddf0b6dae7342d9e4a95d07f5`.

10 000 € de capital neuf, titres entiers, 0,12 % par achat/vente, liquidités non rémunérées, pas de levier ni de vente à découvert. Signal à la clôture, exécution à une clôture ultérieure. Aucune liquidation finale artificielle. Rendement total net et CAGR calendaire ; volatilité quotidienne annualisée par √252, Sharpe à taux de référence 0 %. Dates des tests inchangées : 13/11/2021–13/11/2026 et 13/11/2016–13/11/2026 (première cotation suivante si départ non ouvré).

Les plans complets et les grilles sont écrits dans les JSON avant le calcul des résultats. Sélection uniquement sur 2016–2020 et 2021–2023, puis gel avant les tableaux cinq/dix ans. Ces fenêtres sont déjà connues et chevauchent les audits : aucune prétention de validation indépendante. Critères : CAGR supérieur au Buy & Hold, volatilité et amplitude de drawdown au plus 80 % du témoin, Sharpe supérieur, sur chacune des périodes requises. Puis au moins 75 % des fenêtres cinq ans à départ trimestriel, frais doublés, retard supplémentaire et contrôle synthétique. Aucune règle ne passe même les deux horizons récents.

## Hypothèses et nombre de paramétrages

| Famille | Paramétrages | Changement testé |
|---|---:|---|
| Tendance avec hystérésis | 36 | Moyennes 100/150/200 séances, bandes 1/3 %, planchers 0/25/50 %, décisions quotidiennes ou tous les cinq jours |
| Votes de tendances | 12 | Deux ensembles de moyennes ; exposition progressive et bande de non-intervention de cinq points |
| Protection baisse et réentrée | 54 | Baisse 6/10/15 % depuis le sommet glissant 252 séances ET rupture de moyenne 200 ; réentrée au-dessus de moyenne 20/50/100 |
| Volatilité conditionnée à la tendance | 36 | Risque estimé 21/63 séances, cibles 10/12,5/15 %, filtre moyenne 200 et bande de cinq points |
| Achat de repli en tendance | 24 | RSI de cinq séances, seuils 20/30 et 60/80, filtre moyenne 200 |
| Régression avec poursuite de tendance/protection | 243 | Entrées actuelles ou tendance 100/200, sorties actuelles ou après rupture 50/100 une fois +1,5 σ atteint ; planchers, budgets et filtres de crise |

Au total **405 paramétrages**, dont un paramétrage de la seconde grille équivalent au témoin v4 ; le témoin explicite est ajouté séparément. Il ne s’agit pas de 405 hypothèses indépendantes. Les familles mono-ETF et leurs protections diffèrent des anciennes allocations multi-actifs rejetées ; cela ne réhabilite pas ces dernières.

Les travaux sur la [gestion par volatilité](https://www.nber.org/papers/w22208) et la [poursuite de tendance](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/AQR-JPM-Fall-2017.pdf) motivent des hypothèses, pas une promesse de surperformance de ce seul ETF sans levier.

## Résultats historiques comparables

La variante « continuation » est le diagnostic figé sur les premières périodes malgré zéro candidat qualifié : budgets 75/25, plancher 25 %, règles d’entrée actuelles, sortie lente après armement à +1,5 σ puis rupture de moyenne 50 lors de la décision mensuelle. Les autres règles restent celles de v4. Elle est étudiée, **pas adoptée**.

La variante « rendement dix ans maximal » est une observation **après examen des résultats**, pas une sélection valide : poche lente seule, entrée sous −2 σ ou au-dessus de moyenne 200 avec momentum 63 positif, sortie après armement à +1,5 σ et rupture moyenne 100, plancher 25 %, mensuel. Elle reste inférieure au Buy & Hold dix ans et perd face à l’actuelle sur cinq ans.

### Cinq ans

| Méthode | Capital final | Rendement total | CAGR net | Volatilité | DD maximal | Sharpe | Frais |
|---|---:|---:|---:|---:|---:|---:|---:|
| Buy & Hold | 17302,94 € | 73,03 % | 11,60 % | 15,15 % | -23,18 % | 0,79 | 11,98 € |
| Régression actuelle v4 | 17882,36 € | 78,82 % | 12,34 % | 8,61 % | -7,02 % | 1,37 | 55,14 € |
| Continuation mensuelle | 17379,84 € | 73,80 % | 11,70 % | 8,99 % | -10,14 % | 1,26 | 54,13 € |
| Meilleur rendement dix ans observé* | 16874,16 € | 68,74 % | 11,05 % | 12,37 % | -16,33 % | 0,89 | 53,26 € |
| Tendance 200 + hystérésis | 14331,40 € | 43,31 % | 7,47 % | 11,65 % | -18,23 % | 0,67 | 152,41 € |
| Protection baisse / réentrée 50 | 13073,97 € | 30,74 % | 5,51 % | 11,91 % | -29,64 % | 0,50 | 272,97 € |
| Volatilité cible 12,5 % | 14451,19 € | 44,51 % | 7,65 % | 10,55 % | -15,43 % | 0,74 | 144,55 € |
| Replis RSI / plancher 50 % | 14283,75 € | 42,84 % | 7,40 % | 10,24 % | -15,26 % | 0,74 | 548,63 € |

*Observation postérieure au calcul ; les paramètres sont identiques dans les deux tableaux.

### Dix ans

| Méthode | Capital final | Rendement total | CAGR net | Volatilité | DD maximal | Sharpe | Frais |
|---|---:|---:|---:|---:|---:|---:|---:|
| Buy & Hold | 38684,67 € | 286,85 % | 14,49 % | 16,14 % | -33,67 % | 0,91 | 11,97 € |
| Régression actuelle v4 | 31612,00 € | 216,12 % | 12,20 % | 9,20 % | -10,95 % | 1,28 | 136,10 € |
| Continuation mensuelle | 32042,38 € | 220,42 % | 12,36 % | 9,59 % | -10,95 % | 1,24 | 138,05 € |
| Meilleur rendement dix ans observé* | 35653,45 € | 256,53 % | 13,56 % | 12,12 % | -18,26 % | 1,09 | 120,48 € |
| Tendance 200 + hystérésis | 26564,30 € | 165,64 % | 10,27 % | 12,71 % | -18,46 % | 0,82 | 452,09 € |
| Protection baisse / réentrée 50 | 26735,02 € | 167,35 % | 10,34 % | 12,88 % | -29,65 % | 0,82 | 740,08 € |
| Volatilité cible 12,5 % | 23186,68 € | 131,87 % | 8,78 % | 11,37 % | -23,82 % | 0,79 | 345,21 € |
| Replis RSI / plancher 50 % | 23242,38 € | 132,42 % | 8,80 % | 11,20 % | -26,12 % | 0,80 | 1559,59 € |

*Observation postérieure au calcul ; les paramètres sont identiques dans les deux tableaux.

## Robustesse et contrôles

Zéro candidat qualifié dans chaque sélection initiale. Zéro paramétrage nouveau ne bat le rendement du Buy & Hold sur dix ans, même avant les autres exigences. Dix-neuf paramétrages de régression battent son rendement cinq ans, mais aucun ne répond aux deux horizons. Ce constat n’établit pas une impossibilité mathématique pour toutes les stratégies.

Vingt-quatre fenêtres cinq ans à départ trimestriel sont vérifiées, ainsi que frais 0,24 % et retard de deux séances, pour les diagnostics figés. Les fenêtres chevauchantes ne sont pas indépendantes. Les configurations et résultats de toutes les variantes, y compris leurs échecs, sont conservés dans les JSON.

Vérifications financières : Buy & Hold du moteur de recherche reproduit les métriques de production cinq/dix ans à 1e−9 ; témoin v4 reproduit CAGR, volatilité, DD et Sharpe à 1e−9, frais à 1e−6 €. Le préfixe des signaux reste identique après suppression du futur. Le calcul vectorisé reproduit les parcours calculés séparément sur trois marchés, quatre méthodes et douze indicateurs ; un choc après entrée reste bien perdu avant la vente à la clôture suivante. Contrôle synthétique indépendant du Buy & Hold contre la production, graine 0/cinq ans/six métriques.

## Parcours synthétiques

La première étude évalue les quatre diagnostics figés sur **1 000 parcours par horizon**, graines 0–999, cinq et dix ans, même générateur en blocs moyens 63 séances et bruit 5 % que l’application. Les quatre approches sous-performent en rendement moyen ; aucune ne passe les critères. Le générateur n’est pas modifié pour favoriser les méthodes.

La seconde étude vérifie v4 et la continuation sur **100 parcours par horizon**, graines 0–99. Ce nombre est distinct des 1 000 de la première étude et des 1 000 du lot fourni par l’utilisateur.

### Régression : 5 ans / 100 parcours

| Méthode | CAGR moyen | Volatilité moyenne | DD maximal moyen | Sharpe moyen | Victoires rendement | Victoires DD |
|---|---:|---:|---:|---:|---:|---:|
| Buy & Hold | 15,07 % | 16,33 % | -24,15 % | 0,93 | — | — |
| Actuelle v4 | 10,41 % | 11,99 % | -18,41 % | 0,91 | 13 % | 97 % |
| Continuation | 11,01 % | 12,50 % | -18,99 % | 0,92 | 13 % | 96 % |

### Régression : 10 ans / 100 parcours

| Méthode | CAGR moyen | Volatilité moyenne | DD maximal moyen | Sharpe moyen | Victoires rendement | Victoires DD |
|---|---:|---:|---:|---:|---:|---:|
| Buy & Hold | 14,56 % | 16,50 % | -29,28 % | 0,89 | — | — |
| Actuelle v4 | 10,03 % | 12,11 % | -23,22 % | 0,84 | 4 % | 99 % |
| Continuation | 10,50 % | 12,59 % | -23,92 % | 0,84 | 6 % | 98 % |

## Décision et interface

**Conserver v4 et ses périodes.** Aucun remplacement ne satisfait l’objectif demandé. La stratégie n’a aucun plafond de pertes : les poches peuvent être investies à 100 %, la lente décide mensuellement et toutes exécutent après le signal ; une chute brutale ou des allers-retours défavorables peuvent donc produire de gros drawdowns. Réduire la volatilité moyenne ne les interdit pas.

À la demande de l’utilisateur, suppression des paragraphes explicatifs du simulateur, du récapitulatif du tirage unitaire, de la légende textuelle du tableau unitaire et de la ligne séparée Capital final. Courbes, valeurs et mécanisme du modèle conservés. Documentation des limites conservée hors de l’écran.

Verifications interface : `npm run check` (40 tests unitaires, compilation et contrôles), 30 parcours navigateur ordinateur/mobile (simulation S&P, validation, stratégies). Ruff backend/scripts et diff whitespace vérifiés. Aucun nouveau moteur de stratégie intégré.

## Reproduction

```sh
PYTHONPATH=backend:scripts uv run python scripts/study_sp500_amundi_upside.py
PYTHONPATH=backend:scripts uv run python scripts/study_sp500_amundi_regression.py
```

Sorties locales ignorées par Git : `data/backtests/sp500-amundi-upside.json` et `data/backtests/sp500-amundi-regression.json`. Pas de réécriture des études BNP historiques. Voir aussi le [journal central](journal-des-essais.md) et la [documentation du simulateur](sp500-simulation.md).
