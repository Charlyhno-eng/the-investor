# Étude des seuils d’écart-type — 13 novembre 2026

**Meilleur seuil symétrique parmi les huit valeurs testées sur 2021–2026 : ±2,0 σ. Réglage retenu par la sélection chronologique : achat à −1,4 σ, activation de la sortie à +1,4 σ, vente après un repli de 0,5 σ depuis le plus haut z-score atteint pendant la détention.** Ces deux conclusions répondent à des critères différents et ne désignent pas un optimum universel.

## Univers et conventions

L’univers est celui du journal reproduit : GTT, Euronext, Prysmian, Air Liquide, Technip Energies, Thales, UCB, Airbus, TotalEnergies, ASML, Bitcoin, Safran, Schneider Electric et argenx. Capital initial : 10 000 €. Frais : 0,5 % à l’achat et à la vente. Actions entières, Bitcoin fractionnaire. Plafond de 25 % à l’entrée et plancher de min(10 %, 1/N), frais d’achat compris. Une seule position finance les achats d’une séance, seulement pour atteindre le plancher. Les signaux restent ceux de la régression logarithmique sur trois ans, avec exécution à la clôture commune suivante. Aucun changement de ces règles de taille n’a servi à améliorer le classement des seuils.

Toutes les simulations utilisent la même copie SQLite des données locales ; les mises à jour des cours ne peuvent pas intervenir entre deux essais. Empreinte SHA-256 de cette copie à sa création : `481fdf08c3a1f5cda3fcc1a4582a97e44d3b63328fbeca04e4cde40fdbfe81e3`.

## Protocole fixé avant les résultats

La grille contient **27 configurations** : huit seuils symétriques (0,8 ; 1,0 ; 1,2 ; 1,4 ; 1,6 ; 1,8 ; 2,0 ; 2,2), douze couples asymétriques (entrées 1,2/1,6/2,0, sorties 0/0,7/1,4/2,1), cinq sorties après repli de 0,5 σ (activation et entrée 1,2/1,4/1,6/1,8/2,0), et deux variantes de financement n’utilisant que des positions à z ≥ 0,5 (seuils 1,4 et 1,6).

1. **Calibration : 14 novembre 2016–12 novembre 2021.** Les 27 configurations sont calculées. Le classement utilise le ratio de Calmar (CAGR / drawdown maximal), avec au moins huit opérations, un CAGR au moins égal au classique ±1,4 et un drawdown au maximum cinq points plus profond. On conserve au plus cinq candidats, plus le classique de référence. Trois configurations passent effectivement cette étape : classique ±1,4, suivi 1,2 et suivi 1,4.
2. **Validation : 15 novembre 2021–14 novembre 2024.** Les trois candidats sont départagés avec les mêmes critères. Le suivi 1,4 est retenu et son identité est enregistrée avant de calculer le test final.
3. **Évaluation finale : 15 novembre 2024–13 novembre 2026.** Seuls le classique ±1,4 et le suivi 1,4 retenu sont évalués. Aucun reclassement n’utilise cette période.
4. **Tableau descriptif sur cinq ans**, calculé après cette sélection : les huit seuils symétriques et la variante retenue. Le gagnant rétrospectif de ce tableau n’est pas utilisé pour réécrire la sélection chronologique.
5. **Sensibilité**, sans changer de réglage : onze actions, quatre cryptomonnaies, puis des frais doublés à 1 % par côté.

Au total : **47 simulations** (27 calibration, 3 validation, 2 évaluation finale, 9 tableau descriptif, 6 sensibilité). Chaque fenêtre repart de 10 000 € en liquidités, avec trois ans de données antérieures pour les signaux et l’éligibilité des actifs. Le portefeuille n’est pas transmis de la calibration à la validation ni au test. La simulation continue sur cinq ans est une expérience séparée : on ne peut pas multiplier les rendements des fenêtres pour la reconstituer.

## Résultats descriptifs 2021–2026

| Réglage | Rendement net | Valeur finale pour 10 000 € | Drawdown maximal | Frais | Opérations |
|---|---:|---:|---:|---:|---:|
| symmetric_0.8 | +124,55 % | 22 454,50 € | -18,04 % | 650,86 € | 80 |
| symmetric_1 | +151,43 % | 25 142,86 € | -19,18 % | 605,94 € | 66 |
| symmetric_1.2 | +127,34 % | 22 734,36 € | -24,29 % | 510,58 € | 58 |
| symmetric_1.4 | +139,09 % | 23 909,47 € | -22,58 % | 456,91 € | 50 |
| symmetric_1.6 | +191,92 % | 29 192,31 € | -19,25 % | 565,38 € | 49 |
| symmetric_1.8 | +206,88 % | 30 688,40 € | -20,56 % | 598,50 € | 49 |
| symmetric_2 | +229,30 % | 32 930,41 € | -16,83 % | 556,14 € | 40 |
| symmetric_2.2 | +218,36 % | 31 836,17 € | -18,25 % | 418,35 € | 39 |
| trailing_1.4 | +161,07 % | 26 107,06 € | -22,58 % | 473,84 € | 49 |

Les seuils profonds 1,8 / 2,0 / 2,2 produisent tous de bons résultats sur cette période ; le point 2,0 n’est donc pas isolé entre deux résultats très faibles. Le classique ±2,0 fournit aussi un drawdown moins profond que ±1,4 sur ces cinq ans. Il n’a cependant pas passé la calibration : en 2016–2021, il ne gagnait que **58,01 %**, contre **133,10 %** pour ±1,4, avec un drawdown de −41,87 % contre −33,73 %. Le choisir après lecture des cinq dernières années reste un choix rétrospectif.

Sur la fenêtre complète, l’équipondération trimestrielle de l’univers rapporte +164,86 % avec un drawdown de −14,12 %, l’achat-conservation +120,54 % avec −13,57 %, et le S&P 500 en euros +76,91 % avec −22,32 %. Le suivi 1,4 ne domine donc pas toutes les références sur cinq ans : son rendement y reste légèrement inférieur à l’équipondération, avec un drawdown plus profond. Le classique ±2,0 dépasse ces références en rendement sur cette seule fenêtre.

## Vérification chronologique de la nouvelle sortie

| Fenêtre et réglage | Rendement net | Valeur finale pour 10 000 € | Drawdown maximal | Frais | Opérations |
|---|---:|---:|---:|---:|---:|
| calibration · symmetric_1.4 | +133,10 % | 23 310,17 € | -33,73 % | 425,04 € | 47 |
| calibration · trailing_1.4 | +197,17 % | 29 717,37 € | -37,57 % | 431,30 € | 45 |
| validation · symmetric_1.4 | +52,40 % | 15 240,24 € | -22,58 % | 199,74 € | 26 |
| validation · trailing_1.4 | +60,98 % | 16 098,10 € | -22,58 % | 191,30 € | 26 |
| test · symmetric_1.4 | +60,63 % | 16 062,56 € | -19,74 % | 225,15 € | 24 |
| test · trailing_1.4 | +68,69 % | 16 868,75 € | -14,42 % | 215,82 € | 27 |

Le suivi 1,4 améliore le rendement dans les trois fenêtres face au classique 1,4. Il a un drawdown plus profond en calibration, identique en validation et moins profond dans l’évaluation finale. Sur cette dernière fenêtre, il produit +68,69 % contre +60,63 %, pour un drawdown de −14,42 % contre −19,74 %. L’équipondération y gagne +50,24 % avec −14,20 %, l’achat-conservation +45,85 % avec −13,95 % et le S&P 500 +24,79 % avec −22,32 %.

## Fonctionnement de la sortie après repli

L’achat reste déclenché à z ≤ −1,4. Une fois détenue, la position n’est pas vendue dès z ≥ +1,4 : ce franchissement arme le suivi. Le moteur mémorise le plus haut z-score connu depuis l’entrée et vend si z recule d’au moins 0,5 depuis ce plus haut. Exemple : +1,4 arme le suivi, +2,1 établit un nouveau maximum, +1,6 ou moins déclenche la vente à la clôture commune suivante. Le plus haut est réinitialisé après liquidation ; une nouvelle position ne peut pas hériter du maximum d’une position précédente. Une réduction de financement conserve le plus haut de la quantité encore détenue.

Le repli porte sur le **z-score**, pas sur le prix. La régression et son écart-type changent avec les observations : cette règle n’est pas un stop de prix et ne garantit pas un gain acquis. Les ventes pour financer un nouveau signal restent possibles avant le repli ; cette sortie ne bloque pas les règles de liquidités.

## Sensibilité du réglage figé

| Univers ou frais et réglage | Rendement net | Valeur finale pour 10 000 € | Drawdown maximal | Frais | Opérations |
|---|---:|---:|---:|---:|---:|
| actions_11:symmetric_1.4 | +188,74 % | 28 873,79 € | -18,96 % | 505,50 € | 40 |
| actions_11:trailing_1.4 | +202,09 % | 30 208,62 € | -18,95 % | 520,18 € | 40 |
| crypto_4:symmetric_1.4 | +9,62 % | 10 962,39 € | -37,01 % | 180,65 € | 12 |
| crypto_4:trailing_1.4 | +24,65 % | 12 464,94 € | -37,34 % | 203,92 € | 12 |
| fee_1pct:symmetric_1.4 | +133,91 % | 23 391,40 € | -22,69 % | 904,06 € | 50 |
| fee_1pct:trailing_1.4 | +155,73 % | 25 573,44 € | -22,69 % | 938,71 € | 49 |

L’univers de onze actions est un sous-ensemble de celui de quatorze actifs ; l’univers crypto contient aussi Bitcoin. Ce sont des contrôles de sensibilité, pas des échantillons entièrement indépendants. Les frais de 1 % sont une simulation séparée : le portefeuille et ses quantités changent avec les frais, il ne suffit pas de soustraire une facture supplémentaire à la courbe de référence.

## Utilisation dans l’application

Dans **Validation historique → Retour à la moyenne → Réglage des écarts-types**, trois préréglages sont disponibles : classique ±1,4, suivi de l’écart-type 1,4 / repli 0,5, et classique ±2,0. Les valeurs d’achat, de vente/activation, de repli et de financement sont également modifiables séparément. La règle classique ±1,4 reste le réglage par défaut pour conserver les comparaisons précédentes. Le journal identifie les sorties de suivi par « Repli de l’écart-type ».

## Limites de la conclusion

Cette étude ne prouve pas une performance future. L’univers a été choisi aujourd’hui, avec un biais de sélection et de survivance. La période 2024–2026 n’a pas servi au classement du script, mais ses données et les résultats de la stratégie actuelle avaient déjà été consultés au cours du développement et dans le journal fourni : ce n’est donc pas un test futur totalement inédit. Les trois années de régression permettent de calculer un signal ; elles ne démontrent pas à elles seules que les résidus vont revenir à la moyenne.

Le classement dépend de la préférence explicite pour le Calmar, de la tolérance de cinq points de drawdown et de cette grille finie. Il n’établit ni un optimum continu de seuil, ni une supériorité pour tous les portefeuilles. La sélection de paramètres parmi plusieurs essais expose au surajustement, comme l’expliquent [Bailey et al., The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf). Les frais de courtage sont inclus ; impôts, spread, impact de marché et rémunération des liquidités ne sont pas modélisés.

## Reproduire

```sh
PYTHONPATH=backend uv run python scripts/study_reversion_thresholds.py
```

Le script crée une copie temporaire de la base avant les essais et enregistre progressivement la sélection et les résultats dans `data/backtests/reversion-threshold-study.json`. Pour utiliser une archive SQLite existante : `--snapshot /chemin/archive.sqlite3`. Pour un autre chemin de rapport : `--output /tmp/etude.json`. Les résultats peuvent changer si les cours ont été révisés depuis cette étude. Les décisions restent calculées uniquement avec les informations antérieures à leur exécution.

Le fichier `data/backtests/reversion-threshold-study.csv` contient aussi les 47 résultats de cette exécution pour une comparaison dans un tableur.
