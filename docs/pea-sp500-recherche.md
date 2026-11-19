# Battre le S&P 500 dans un PEA · étude du 19 novembre 2026

**Décision.** Retrait de la stratégie américaine SPMO de la bibliothèque et de ses routes d’API. La régression v6 reste disponible. Pour rechercher un rendement supérieur au S&P 500, la piste principale devient une règle de sortie rare sur PSP5, fondée sur la concentration des baisses. Son bénéfice dépend du calendrier et de 2020. Elle reste en recherche.

Sur dix ans au 19 novembre, la v6 déjà présente rapporte 11,39 %/an avec un drawdown de −7,99 %. Sa variante antérieure à 15 % de PSP5 passif rapporte 11,61 %/an avec −8,84 %. Elles restent des points de comparaison pour un objectif plus défensif. [Comparaison v6 et poche passive](sp500-v6-compromis.md).

La référence investissable est **Amundi PEA S&P 500 UCITS ETF Acc, PSP5, FR0011871128**, dividendes capitalisés. Dans une branche distincte, on autorise également **PSPH, FR0011871136**, la part PEA couverte en euros. Le répartiteur n’achète ni indice de volatilité, ni obligation, ni devise. Les ordres portent uniquement sur les parts admissibles. [Prospectus Amundi](https://www.amundietf.fr/pdfDocuments/prospectus/FR0011871128/FRA/FRA/20260416) · [Part couverte](https://www.amundietf.fr/fr/professionnels/produits/equity/amundi-pea-sp-500-ucits-etf-eur-hedged-acc/fr0011871136)

## Ce que la littérature permet de tester

- Le momentum temporel de Moskowitz, Ooi et Pedersen utilise le rendement passé de l’instrument. Leur étude porte sur plusieurs marchés de contrats à terme. Ici, une tendance baissière autorise simplement une réduction de l’exposition. Nous testons aussi les désaccords entre tendances courtes et longues et les reprises après cassure. [Time Series Momentum](https://doi.org/10.1016/j.jfineco.2011.11.003) · [Breaking Bad Trends](https://people.duke.edu/~charvey/Research/Published_Papers/P167_Breaking_bad_trends.pdf)
- Nagel relie les retournements courts des actions à la fourniture de liquidité. L’exercice transpose l’idée à un indice unique par achats après chute, sorties temporaires après rebond et zones de surachat/survente. Les possibilités de sélection transversale de l’étude disparaissent dans un seul ETF. [Evaporating Liquidity](https://www.nber.org/papers/w17653)
- Moreira et Muir modulent l’exposition selon la variance. Barndorff-Nielsen, Kinnebrock et Shephard distinguent les variations négatives pour mesurer le risque. Nos essais comparent volatilité récente/longue et part baissière des carrés des rendements quotidiens. Le seuil 80 % et la cadence de cinq séances proviennent de notre grille. [Volatility Managed Portfolios](https://www.nber.org/papers/w22208) · [Realised Semivariance](https://ora.ox.ac.uk/objects/uuid%3A64e98570-6bdf-4a6a-9067-c8cd5b24d8d5)
- Les travaux sur la prime de variance comparent variance implicite et réalisée, avec des rendements futurs d’horizon trimestriel. Ici la variance réalisée est approximée sur clôtures. La pente 10 ans/3 mois étudiée par la Fed de New York vise les récessions à un an. Nous testons si son information aide à choisir des dates de vente du PSP5. Les devises refuges/cycliques complètent les signaux de stress. [Bollerslev et Zhou](https://www.federalreserve.gov/econres/feds/expected-stock-returns-and-variance-risk-premia.htm) · [Fed de New York](https://www.newyorkfed.org/research/capital_markets/ycfaq) · [Carry Trades and Currency Crashes](https://www.nber.org/papers/w14473)
- Les contraintes de liquidité de fin de mois étudiées par Etula et ses coauteurs motivent trois calendriers confrontés à leurs frais de rotation. Les bornes utilisent les jours de semaine connus à l’avance. [Dash for Cash](https://acris.aalto.fi/ws/portalfiles/portal/40965155/hhz054.pdf)

## Protocole

Base SQLite copiée en mémoire. PSP5 compte 3 201 clôtures du 20 mai 2014 au 19 novembre 2026. Chaque test repart de 10 000 €. Signal en clôture, ordre à la clôture suivante, titres entiers, frais de 0,12 % par achat ou vente, cash à 0 %, sans liquidation finale. Les deux côtés de la comparaison ont les mêmes frais et la même première clôture d’exécution. Le CAGR utilise le temps calendaire. Le drawdown utilise la valeur nette à chaque clôture. Le spread et le glissement réel restent inconnus.

**3 628 réglages déclarés**, avant dédoublonnage entre campagnes. Les 11 familles de la première campagne incluent notamment moyenne mobile, momentum avec ou sans mois récent, contrarian court, achat de repli conditionné, canal, efficacité de tendance, volatilité et proportion des pertes. Chaque famille fige un représentant avant ses trajectoires réservées. Le gagnant global est également figé. Les résultats secondaires demeurent identifiables.

| Campagne | Réglages | Sélection | Résultat déterminant |
|---|---:|---|---|
| Prix de PSP5 et cash | 1 224 | PSP5 2016–2020 et 160 trajectoires à cinq ans générées avec les seules données disponibles fin 2020. Rendement et DD meilleurs sur les deux ensembles, puis meilleur gain de rendement simulé. 43 admissibles. | Gagnant part baissière 21 séances, seuil 80 %, décision toutes les cinq séances, cible de protection 0 %. |
| Signaux externes | 675 | Deux sous-périodes historiques 2016–2018 et 2019–2020 et 200 trajectoires de sélection pré-2021. Cinq admissibles. | Le gagnant pente des taux + moyenne mobile rapporte 9,67 %/an depuis 2021 contre 15,57 %, DD −24,03 % contre −23,19 %. |
| Retournements et affinage des sorties | 1 552 | Branche ouverte après la première campagne. Deux périodes SPY USD 1998–2005 et 2006–2013, puis PSP5 2016–2020. 52 admissibles. | Le gagnant 30 séances/80 %/décision toutes les 3 séances échoue depuis 2021 avec 12,64 %/an et −28,40 %. |
| Calendrier mensuel | 81 | SPY USD 1995–2013 et PSP5 2016–2020. Aucun admissible. | La meilleure approximation conserve 85 % d’exposition pendant la fenêtre de vente. Depuis 2021, 13,82 %/an, DD −22,59 %. |
| Arbitrage PSP5/PSPH | 96 | Cours communs réels depuis novembre 2018. Sélection sur fin 2019–2020 et 2021, zéro admissible. | Depuis début 2022, rotation selon performance relative 21 séances : 10,24 %/an et −21,81 %, contre 10,76 % et −23,15 % passifs. |

Chaque campagne examine 1 000 trajectoires réservées à cinq ans et 1 000 à dix ans. L’audit de décalage ajoute ses propres lots de 1 000 + 1 000. Les séries de risque-prix utilisent le générateur de l’application, blocs moyens de 63 séances et bruit à 5 % de volatilité quotidienne. Les signaux macro sont prélevés conjointement avec les rendements du marché. Les clôtures étrangères sont strictement antérieures au jour du signal français, avec une séance supplémentaire pour les taux. Le modèle raccorde les niveaux de VIX et des taux aux jonctions de blocs. Les simulations calendaires rééchantillonnent des mois complets, par groupes de trois mois en moyenne, puis répètent le même test en décalant les étiquettes de calendrier. La rotation de devises rééchantillonne ensemble les rendements en euros des deux parts. Les dix ans synthétiques PSPH dépassent l’historique réel disponible.

## La règle PSP5 qui mérite d’être suivie

Tous les cinq jours de cotation depuis le début du test, calculer, sur les 21 dernières séances, la somme des carrés des rendements logarithmiques négatifs divisée par la somme des carrés de tous les rendements logarithmiques. Si le ratio dépasse strictement 80 %, viser 100 % espèces. Sinon viser 100 % PSP5. Acheter ou vendre à la clôture suivante lors de l’initialisation ou d’un changement de cible. Sur dix ans, 21 ordres en tout, 96,8 % d’exposition moyenne, 545,60 € de frais cumulés sur le capital évolutif.

| Jusqu’au 19/11/2026 | CAGR règle | CAGR PSP5 | DD règle | DD PSP5 |
|---|---:|---:|---:|---:|
| 1 an | 12,31 % | 15,35 % | −7,44 % | −7,08 % |
| 3 ans | 19,61 % | 18,02 % | −14,75 % | −23,19 % |
| 5 ans | 11,91 % | 10,71 % | −16,96 % | −23,15 % |
| 10 ans | 14,06 % | 13,92 % | −26,65 % | −33,67 % |
| Depuis début 2021 | 14,64 % | 15,57 % | −22,51 % | −23,19 % |

| Simulation réservée | CAGR moyen règle / passif | DD moyen règle / passif | Gains de rendement | DD améliorés | Les deux |
|---|---|---|---:|---:|---:|
| 5 ans | 15,26 / 15,02 % | −21,20 / −24,95 % | 425 | 619 | 384/1 000 |
| 10 ans | 15,38 / 15,07 % | −24,22 / −30,06 % | 502 | 753 | 485/1 000 |

À cinq ans, IC bootstrap apparié à 95 % des gains moyens de rendement et de DD en points : [0,09 ; 0,39] et [3,33 ; 4,20]. À dix ans : [0,21 ; 0,41] et [5,42 ; 6,28]. Les intervalles mesurent la dispersion des moyennes dans ce modèle. Avec des blocs de 21 séances plutôt que 63, 500 nouveaux parcours de cinq ans donnent un retard de CAGR de 0,39 point, malgré un drawdown amélioré. Avec des blocs de 126 séances, l’avance atteint 0,55 point.

## Les contre-exemples qui changent la décision

- **Décalage d’une séance.** Sur cinq ans, le gain de rendement de 1,20 point et le gain de DD de 6,19 points deviennent des pertes de 3,22 et 3,44 points. Quatre des cinq départs consécutifs perdent en rendement à trois et cinq ans. Les cinq départs gagnent sur les deux mesures à dix ans. Sur 71 départs mensuels chevauchants de cinq ans, 55 doubles victoires. La fenêtre de mai 2020 perd 3,02 points de rendement par an et 3,43 points de DD.
- **Rôle de 2020.** Sur la trajectoire continue de dix ans, la contribution relative logarithmique de 2020 est +0,1381. Sur cette trajectoire, la sortie se fait le 28 février à 21,578 € et le rachat le 27 mars à 18,750 €. Les 50 fenêtres de cinq ans englobant entièrement cet intervalle gagnent sur les deux critères. Parmi les 21 autres, seulement cinq y parviennent, avec un retard moyen de rendement de 1,13 point/an. Cette ventilation est un diagnostic après calcul. La somme des contributions logarithmiques des années hors 2020 est −0,1264. Le faible avantage final sur dix ans dépend donc fortement de cet épisode. Sur le proxy USD 1995–2013, 8,19 %/an contre 9,51 % passif. Sur 2000–2003, le drawdown atteint −50,84 % contre −47,51 %. Ce proxy sert de stress historique et n’est jamais acheté dans un PEA.
- **Répartir les décisions sur cinq phases.** Cinq poches indépendantes de 2 000 € réduisent le DD à −20,64 % sur dix ans avec 15,00 %/an, mais rapportent seulement 9,66 % sur cinq ans contre 10,71 % pour PSP5. Un compte unique ajusté par cinq votes donne 9,66 %/an et −20,73 % sur cinq ans. Ajouter une poche passive de 15 % à ce dernier donne 9,80 % et −20,87 %. Un second moteur de comptabilité reproduit le contrôle et la règle initiale aux quatre horizons.
- **Retard et frais.** Depuis 2021 avec frais de 0,24 % et deuxième clôture, la règle initiale rapporte 14,48 % contre 15,23 % pour PSP5, avec DD −22,47 % contre −23,18 %. Une piste secondaire réduisant l’exposition à 85 % si VIX/VIX3M dépasse 1,2 gagne seulement 0,06 point/an depuis 2021 ; elle perd 0,18 point/an et 0,03 point de DD sous ce stress. Elle ne passe que trois ordres sur la période, achat initial compris.
- **Réoptimiser en continu.** À chaque trimestre ou année depuis 2021, choisir parmi les 1 224 règles à partir des cinq années révolues (trois ans puis deux ans, domination requise sur les deux tranches, classement selon le pire gain de rendement). Conserver le compte, payer les changements, revenir à PSP5 si aucun admissible. Résultat trimestriel 13,20 %/an et DD −23,20 %, annuel 10,81 % et −23,65 %, contre 15,57 % et −23,19 % passifs.
- **Mini-inversion.** La règle secondaire achetant pour cinq séances après une chute standardisée, sur une base d’exposition de 90 %, rapporte 13,96 %/an depuis 2021, DD −22,82 %. La sortie après surachat sur deux séances et réentrée après survente donne 14,69 % et −22,48 %. Elles économisent un peu de risque au prix d’un rendement global inférieur.

Les mêmes cours ont servi à de nombreux essais. Les fenêtres chevauchantes, la sélection de familles et les simulations sur une même histoire économique empêchent d’interpréter ces fréquences comme des probabilités futures. Pour un objectif de surperformance avec drawdown moindre, les variantes restent au journal de recherche. PSP5 passif est la référence opérationnelle et la v6 conserve son rôle de stratégie nettement plus défensive.

## Reproduction

Depuis la racine, lancer successivement avec `PYTHONPATH=backend .venv/bin/python scripts/` les programmes `study_pea_timing.py`, `study_pea_cross_signals.py`, `study_pea_reentries.py`, `study_pea_calendar.py`, `audit_pea_phase.py`, `study_pea_hedge.py` et `audit_pea_walkforward.py`. Le petit moteur C de recherche est compilé en répertoire temporaire par le compilateur système. Les sorties `data/backtests/pea-*.json` conservent grilles, représentants, choix figés, observations historiques et agrégats.

Contrôle logiciel supplémentaire : pour 301 combinaisons distinctes famille/fenêtre/seuil, les signaux calculés sur deux préfixes de 403 et 2 011 observations sont identiques aux signaux des mêmes dates du calcul complet. Cela vérifie la causalité des transformations étudiées, tout en laissant subsister les limites du prix d’exécution et des données disponibles.

Les instantanés externes sont dans `data/backtests/pea-inputs/`. Les fichiers `VIX.csv` et `VIX3M.csv` proviennent des clôtures quotidiennes Cboe, jusqu’au 18/11/2026. Les empreintes figurent dans le JSON de la campagne. La série de prix de PSPH.PA provient de Yahoo Finance Chart, obtenue le 19/11/2026, symbole, devise et égalité des clôtures ajustées vérifiés. [Données Cboe](https://www.cboe.com/tradable_products/vix/vix_historical_data) · [Historique quotidien PSPH](https://query2.finance.yahoo.com/v8/finance/chart/PSPH.PA?period1=1388534400&period2=1795132800&interval=1d)
