# Recherche quantitative : deux adaptations académiques non retenues

Étude du 13 novembre 2026. **Décision : aucun ajout dans l’application.** Les deux politiques ont été implémentées et évaluées dans un script isolé, mais aucune ne remplit les critères fixés avant les résultats. Les stratégies existantes et leurs réglages restent inchangés. Les fichiers de recherche et les tests sont conservés pour rendre cet échec vérifiable.

## Sources et différence avec les articles

- Moskowitz, Ooi et Pedersen (2012), *Time Series Momentum*, Journal of Financial Economics : [présentation par les auteurs](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum), [données et construction originale](https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Original-Paper-Data). Les auteurs étudient la prévisibilité associée aux rendements propres des douze mois précédents sur des contrats à terme de plusieurs classes d’actifs. Leur portefeuille inclut des positions vendeuses et une normalisation par la volatilité.
- Moreira et Muir (2017), *Volatility-Managed Portfolios*, Journal of Finance : [notice NBER](https://www.nber.org/papers/w22208), [article de travail et formule, section 2.2](https://conference.nber.org/confer/2016/LTAMs16/Moreira_Muir.pdf). L’exposition du mois suivant est proportionnelle à l’inverse de la variance réalisée récente. La constante de normalisation des auteurs est différente de celle fixée ici.

Les politiques locales ci-dessous sont **des adaptations, pas des réplications des résultats publiés**. Elles utilisent des actions individuelles et des cryptos détenues directement, sans levier ni vente à découvert. L’univers, les instruments, la fréquence de cotation commune, les frais et la réserve non rémunérée diffèrent des articles. L’échec de ces adaptations ne réfute pas les articles.

## Règles fixées avant le premier calcul

Aucune grille de paramètres, aucun réglage après consultation des performances. Deux candidats seulement :

1. **Gestion par la variance** : panier équipondéré des actifs éligibles, au maximum 25 % par actif. À chaque révision mensuelle, calcul de la variance journalière de ce panier sur le dernier mois calendaire, annualisée avec 252 séances. Exposition multipliée par `min(1, 0.15² / variance_annuelle)`. La constante de 15 % est choisie avant les tests ; elle ne dépend d’aucune volatilité calculée sur le futur. Cette formule cible la variance dans la règle d’allocation, sans garantir une volatilité réalisée de 15 %.
2. **Momentum temporel** : achat uniquement si le rendement total en EUR sur douze mois est positif (référence de liquidités à 0 %). Poids proportionnels à l’inverse de la volatilité propre sur douze mois, redistribués avec un plafond de 25 %. Réduction globale si la volatilité du portefeuille estimée avec la covariance sur douze mois dépasse 15 % annualisés. Les actifs au signal négatif sont exclus ; les autres se partagent le budget sous les contraintes. Le budget non allouable reste en liquidités.

Les deux modèles utilisent trois ans d’historique propre avant l’admission d’un actif, pour garder la même disponibilité que le moteur actuel. Les décisions interviennent à la dernière clôture commune du mois et les transactions à la suivante, avec une entrée initiale le lendemain du premier signal. Les prix d’exécution ne participent pas aux signaux. Les nouvelles introductions attendent leur historique requis et la révision mensuelle suivante. Quand moins de quatre actifs sont retenus, le plafond de 25 % laisse nécessairement du cash. Les poids sont des cibles à la révision : une position peut ensuite dépasser 25 % par appréciation.

Le contrôle principal est une **équipondération mensuelle** sur les mêmes actifs éligibles, avec le même plafond de 25 %, calendrier, arrondis et frais. Le contrôle trimestriel existant, l’achat-conservation et le S&P 500 sont également conservés. Contrairement aux modèles candidats, les comparateurs existants peuvent investir dans un nouvel actif avant ses trois ans ; cette différence est explicite.

Critère de conservation, enregistré dans le JSON avant les premiers résultats : sur **chacune** des fenêtres 2021–2024 et 2024–2026, Sharpe supérieur d’au moins 0,10 au contrôle mensuel, baisse maximale réduite d’au moins 20 % en valeur absolue et conservation d’au moins 80 % de son CAGR. Ces trois conditions doivent aussi tenir sur 2024–2026 avec 1 % de frais par opération. Sur 2016–2021 et l’ensemble 2021–2026, CAGR positif et baisse maximale au moins aussi contenue que le contrôle. Ces seuils sont des exigences de décision pratiques, pas un test de significativité statistique.

## Données et comptabilité

- Univers principal : les 14 actifs du journal utilisateur (GTT, Euronext, Prysmian, Air Liquide, Technip Energies, Thales, UCB, Airbus, TotalEnergies, ASML, Bitcoin, Safran, Schneider Electric et argenx).
- Capital initial : **10 000 €** au début de chaque simulation ; aucun apport.
- Frais : **0,5 % à chaque achat et vente**, entrée comprise ; stress à 1 %.
- Actions en titres entiers ; cryptos fractionnaires. Actions valorisées aux clôtures hors ajustement des dividendes, distributions créditées en cash ; cryptos en parts fractionnaires. Signaux et estimations du risque sur les cours de rendement total en EUR.
- Transactions aux clôtures communes suivantes, achats financés après ventes, frais séparés des montants. Les réserves de risque restent en cash : aucun achat complémentaire ne vient les réinvestir automatiquement.
- Chaque clôture des 21 simulations expérimentales est reconstruite indépendamment avec quantités détenues, distributions, cash et frais. Vérification des entiers, prix disponibles, absence de crédit et de ventes à découvert, concordance du journal et de la valeur du portefeuille.
- Même copie SQLite figée pour tous les calculs. Les imports éventuels restent dans la copie temporaire, sans modification de la base de l’application.

SHA-256 de la copie : `481fdf08c3a1f5cda3fcc1a4582a97e44d3b63328fbeca04e4cde40fdbfe81e3`.

## Résultats sur cinq ans

Du 15 novembre 2021 au 13 novembre 2026. Le retour à la moyenne utilise bien la configuration actuelle : achat −2 σ, activation +2 σ, repli 1 σ, financement à partir de +0,3 σ. Le Sharpe utilise un taux de référence nul.

| Méthode | Valeur finale | Rendement net | CAGR | Baisse maximale | Sharpe | Frais payés |
|---|---:|---:|---:|---:|---:|---:|
| Retour à la moyenne actuel (2 / 2, repli 1, financement 0,3) | 43 080,84 € | 330,81 % | 33,97 % | -16,22 % | 1,68 | 649,02 € |
| Équipondération trimestrielle | 26 486,20 € | 164,86 % | 21,54 % | -14,12 % | 1,43 | 203,44 € |
| Équipondération mensuelle (contrôle) | 25 321,50 € | 153,21 % | 20,45 % | -14,81 % | 1,34 | 308,93 € |
| Exposition inversement proportionnelle à la variance | 21 746,88 € | 117,47 % | 16,83 % | -11,14 % | 1,41 | 802,19 € |
| Momentum temporel avec contrôle du risque | 21 059,51 € | 110,60 % | 16,08 % | -13,63 % | 1,20 | 980,78 € |
| Achat-conservation | 22 053,87 € | 120,54 % | 17,16 % | -13,57 % | 1,24 | 42,55 € |
| S&P 500, rendement total en EUR | 17 690,79 € | 76,91 % | 12,10 % | -22,32 % | 0,71 | 49,75 € |

La réduction de risque de la gestion par la variance existe ici, mais elle coûte du rendement et des frais. Sur cinq ans, son Sharpe de 1,41 est inférieur à celui de l’équipondération trimestrielle (1,43), malgré une baisse maximale plus faible. Elle ne constitue donc pas une amélioration démontrée du compromis rendement/risque sur ce contrôle. Le momentum testé est moins convaincant sur ce même échantillon.

## Vérification par périodes séparées

Chaque fenêtre recommence avec 10 000 € en liquidités et son historique antérieur ; les rendements des fenêtres ne s’enchaînent pas pour reconstituer le résultat sur cinq ans.

### 14 novembre 2016 – 12 novembre 2021

| Méthode | Valeur finale | Rendement net | CAGR | Baisse maximale | Sharpe | Frais payés |
|---|---:|---:|---:|---:|---:|---:|
| Équipondération mensuelle (contrôle) | 36 942,89 € | 269,43 % | 29,91 % | -39,88 % | 1,47 | 437,07 € |
| Exposition inversement proportionnelle à la variance | 24 909,08 € | 149,09 % | 20,05 % | -20,74 % | 1,49 | 1 344,42 € |
| Momentum temporel avec contrôle du risque | 22 831,57 € | 128,32 % | 17,98 % | -33,72 % | 1,19 | 832,64 € |
| Retour à la moyenne actuel (2 / 2, repli 1, financement 0,3) | 23 872,78 € | 138,73 % | 19,03 % | -42,91 % | 0,92 | 282,54 € |

### 15 novembre 2021 – 14 novembre 2024

| Méthode | Valeur finale | Rendement net | CAGR | Baisse maximale | Sharpe | Frais payés |
|---|---:|---:|---:|---:|---:|---:|
| Équipondération mensuelle (contrôle) | 16 766,08 € | 67,66 % | 18,81 % | -13,92 % | 1,23 | 157,81 € |
| Exposition inversement proportionnelle à la variance | 15 576,70 € | 55,77 % | 15,93 % | -11,14 % | 1,33 | 415,58 € |
| Momentum temporel avec contrôle du risque | 14 764,91 € | 47,65 % | 13,88 % | -13,63 % | 1,05 | 469,59 € |
| Retour à la moyenne actuel (2 / 2, repli 1, financement 0,3) | 19 860,85 € | 98,61 % | 25,72 % | -14,23 % | 1,40 | 180,74 € |

### 15 novembre 2024 – 13 novembre 2026

| Méthode | Valeur finale | Rendement net | CAGR | Baisse maximale | Sharpe | Frais payés |
|---|---:|---:|---:|---:|---:|---:|
| Équipondération mensuelle (contrôle) | 14 754,36 € | 47,54 % | 21,55 % | -14,50 % | 1,55 | 148,83 € |
| Exposition inversement proportionnelle à la variance | 13 129,30 € | 31,29 % | 14,64 % | -6,84 % | 1,35 | 258,85 € |
| Momentum temporel avec contrôle du risque | 13 625,73 € | 36,26 % | 16,79 % | -12,74 % | 1,34 | 345,90 € |
| Retour à la moyenne actuel (2 / 2, repli 1, financement 0,3) | 20 696,66 € | 106,97 % | 44,04 % | -17,14 % | 2,09 | 227,45 € |

Les deux candidats échouent aux critères des deux fenêtres récentes et au stress de frais. Sur la fenêtre récente, la gestion par la variance réduit la baisse maximale à −6,84 %, mais son rendement net est de +31,29 %, contre +47,54 % pour le contrôle mensuel ; son Sharpe recule à 1,35, contre 1,55. Le modèle est défensif, mais le bénéfice de risque ne s’accompagne pas de l’efficacité exigée. Aucune recherche supplémentaire de seuils n’a été effectuée pour le faire gagner a posteriori.

## Robustesse et frais plus élevés

### 14 actifs, 2024–2026, frais de 1 % par achat et vente

| Méthode | Valeur finale | Rendement net | CAGR | Baisse maximale | Sharpe | Frais payés |
|---|---:|---:|---:|---:|---:|---:|
| Équipondération mensuelle (contrôle) | 14 432,89 € | 44,33 % | 20,21 % | -14,54 % | 1,46 | 281,64 € |
| Exposition inversement proportionnelle à la variance | 12 741,59 € | 27,42 % | 12,93 % | -7,21 % | 1,22 | 515,22 € |
| Momentum temporel avec contrôle du risque | 13 286,60 € | 32,87 % | 15,32 % | -13,01 % | 1,23 | 673,46 € |
| Retour à la moyenne actuel (2 / 2, repli 1, financement 0,3) | 20 548,85 € | 105,49 % | 43,53 % | -16,72 % | 2,07 | 453,73 € |

### 11 actions, 2021–2026

| Méthode | Valeur finale | Rendement net | CAGR | Baisse maximale | Sharpe | Frais payés |
|---|---:|---:|---:|---:|---:|---:|
| Équipondération mensuelle (contrôle) | 27 850,94 € | 178,51 % | 22,77 % | -16,40 % | 1,47 | 332,97 € |
| Exposition inversement proportionnelle à la variance | 20 881,74 € | 108,82 % | 15,89 % | -10,63 % | 1,33 | 768,67 € |
| Momentum temporel avec contrôle du risque | 20 164,15 € | 101,64 % | 15,08 % | -13,61 % | 1,12 | 853,45 € |
| Retour à la moyenne actuel (2 / 2, repli 1, financement 0,3) | 40 304,72 € | 303,05 % | 32,20 % | -14,67 % | 1,69 | 558,40 € |

### Bitcoin, Ethereum, Solana et BNB, 2021–2026

| Méthode | Valeur finale | Rendement net | CAGR | Baisse maximale | Sharpe | Frais payés |
|---|---:|---:|---:|---:|---:|---:|
| Équipondération mensuelle (contrôle) | 15 581,32 € | 55,81 % | 9,29 % | -61,46 % | 0,43 | 312,83 € |
| Exposition inversement proportionnelle à la variance | 11 151,62 € | 11,52 % | 2,21 % | -12,27 % | 0,36 | 188,49 € |
| Momentum temporel avec contrôle du risque | 10 794,74 € | 7,95 % | 1,54 % | -19,12 % | 0,19 | 302,86 € |
| Retour à la moyenne actuel (2 / 2, repli 1, financement 0,3) | 11 309,78 € | 13,10 % | 2,50 % | -51,79 % | 0,23 | 140,76 € |

Les résultats ne sont pas homogènes entre univers : le contrôle mensuel est très différent des contrôles trimestriels sur les cryptos, et les deux candidats y conservent un faible rendement. Ces sous-univers servent de diagnostics ; ils n’ont pas servi à choisir les paramètres.

## Portée de la conclusion

Les périodes ont déjà été consultées lors de travaux précédents. Il s’agit d’une séparation chronologique rétrospective, **pas d’une nouvelle période complètement inconnue des développeurs**, ni d’un essai prospectif. L’univers choisi aujourd’hui entraîne des biais de sélection et de survivance ; les prix et changes sont les versions actuelles du fournisseur. Le très bon résultat de la stratégie actuelle ne prouve pas sa robustesse future et ne fait pas disparaître le surajustement possible de ses seuils choisis précédemment. Les frais n’incluent pas fiscalité, spread ni impact de marché ; les liquidités ne sont pas rémunérées. Aucun intervalle de confiance ni alpha statistiquement significatif n’est revendiqué.

**Décision finale : ne pas intégrer ces deux adaptations dans les onglets.** Les performances défensives du premier modèle sont intéressantes à documenter, mais insuffisantes pour le présenter comme meilleur que les solutions existantes. La logique de production n’a pas été modifiée : aucun retour arrière sur les fonctionnalités utilisateur n’est nécessaire.

## Reproduction et contrôles

```bash
PYTHONPATH=backend uv run python scripts/study_quantitative_strategies.py
# Pour travailler à partir d’une archive spécifique : ajouter --snapshot /chemin/investor.sqlite3
uv run pytest -q backend/tests/unit/test_quantitative_research.py
```

Le script réalise **28 simulations principales** : 21 pour les deux candidats et le contrôle mensuel, puis 7 pour la stratégie actuelle avec ses comparateurs. Les simulations de confirmation comptable répètent exactement les mêmes expériences ; elles ne constituent pas de nouveaux essais de paramètres.

- Résultats et journaux : `data/backtests/quantitative-strategies-study.json`.
- Tableau exportable : `data/backtests/quantitative-strategies-study.csv` (export du JSON de cette exécution).
- Code isolé : `scripts/study_quantitative_strategies.py`.
- Six tests : reconstruction indépendante des valeurs quotidiennes, frais, entiers et introductions récentes sur les trois politiques ; mutation des prix futurs sans changement des décisions antérieures pour les deux candidats ; plafonds et préservation de la réserve intentionnelle.
