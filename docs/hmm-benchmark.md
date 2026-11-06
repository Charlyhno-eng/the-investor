# Benchmark HMM : toutes les actions et cryptomonnaies locales

## Décision

Le candidat sélectionné en validation réduit fortement les ordres, mais ne constitue pas une amélioration générale : le rendement moyen des cryptos baisse, le Sharpe moyen baisse dans les deux catégories et plusieurs drawdowns augmentent. Les réglages et le modèle de production sont donc conservés. Le candidat reste une piste expérimentale, sans nouvelle sélection sur les résultats de test. Aucun réglage ne domine sur tous les actifs.

Le HMM est désormais accessible uniquement aux actions et cryptomonnaies. Les matières premières et obligations restent consultables dans la vue marché ; l’API refuse leur analyse avant lecture du cache ou entraînement.

## Protocole arrêté avant la recherche

- Périmètre : les 5 actions et les 6 cryptomonnaies présentes dans SQLite. Aucun actif exclu, aucun téléchargement ni modification des cours. Une transaction SQLite en lecture seule assure un instantané cohérent. L’univers correspond aux titres présents aujourd’hui : absence de garantie contre le biais de sélection ou de survivance.
- Historique : les 2 016 dernières clôtures de chaque actif. Tous possèdent ce minimum. Les jours sans observation ne sont pas interpolés ; une même fraction de données ne représente pas la même durée calendaire pour une action et une crypto.
- Trois fenêtres de validation : 50–60 %, 60–70 %, 70–80 % des variations. À chaque fenêtre, entraînement uniquement sur le passé, normalisation recalculée sur cet entraînement, puis paramètres figés pendant la fenêtre. Les variantes glissantes limitent ce passé à 504 ou 1 008 observations. Ce protocole ne teste pas un réentraînement quotidien.
- Test final : les derniers 20 %, avec nouvel ajustement sur les premiers 80 % (ou leur sous-fenêtre glissante). Le candidat est choisi et écrit sur disque avant évaluation de ce test. Le candidat et la référence sont les seules configurations évaluées sur le test final.
- Limite : ces historiques ont déjà été consultés dans des diagnostics antérieurs. Cette séparation empêche la sélection à partir du test dans cette expérience ; elle ne rend pas ces données entièrement nouvelles pour le processus de recherche.
- Exécution : moteur causal de l’application, position initiale en liquidités à chaque fenêtre, signal décalé d’une clôture, liquidation finale, taux sans risque nul, aucune vente à découvert ni levier. Momentum strictement positif obligatoire à l’entrée.
- Coût principal : 10 pb de frais + 5 pb de glissement par ordre, identiques pour toutes les configurations et le benchmark. Stress : coût total de 30 pb par ordre. Le défaut de glissement dans l’interface reste nul ; ces hypothèses de recherche ne le modifient pas.
- Huit variantes : modèle actuel ; momentum 5 ; momentum 20 ; rendement seul ; covariance complète ; trois états ; entraînement glissant 504 ; entraînement glissant 1 008. Sauf exception indiquée : deux états, momentum 10, covariance diagonale, entraînement croissant. Dans la variante trois états, seul celui de meilleure moyenne est porteur.
- 54 politiques : entrée 65/80/90 %, sortie 35/50 %, confirmation d’achat 1/3/5, confirmation de vente 1/3/5. Pas de détention minimale supplémentaire ni plafond d’ordres.
- Ajustement : trois initialisations 17/41/83, 150 itérations maximum, sélection par vraisemblance d’entraînement. Les échecs de convergence sont enregistrés dans le rapport brut. Le candidat retenu converge sur les 33 ajustements de validation et les 11 ajustements finaux.
- Volume : **432 configurations**, **14 256 simulations de validation**, puis **44 simulations finales** (référence/candidat, deux hypothèses de coûts, 11 actifs). Les frais ne sont pas optimisés.

Le score exprime un compromis explicite, sans prétention à un optimum financier universel :

```text
utilité = 0,35 × Sharpe borné à [−3 ; 3]
        + 0,35 × rendement annualisé borné à [−1 ; 1]
        − 0,50 × drawdown maximal
        − 0,15 × exposition
        − 0,001 × nombre annualisé d’ordres
score actif = moyenne des 3 utilités − 0,15 × leur écart-type
score global = 50 % × moyenne des actions + 50 % × moyenne des cryptos
```

Les bornes concernent uniquement le score de sélection ; les tableaux exposent les performances réelles non bornées. Le Sharpe d’une stratégie entièrement en liquidités est indéfini et contribue zéro au score. Le risque et l’exposition faibles d’une stratégie inactive peuvent ainsi être récompensés ; l’absence d’ordres doit être examinée avec les rendements.

## Candidat retenu avant le test

- Deux états gaussiens, covariance diagonale, **rendement seul dans le HMM**. Momentum 10 conservé comme filtre d’entrée dans la stratégie.
- Entrée **90 %**, sortie **50 %**, **3** confirmations à l’achat, **5** à la vente.
- Référence : rendement + momentum 10, entrée 80 %, sortie 50 %, confirmations 5/3.
- Score de validation : **0,070861** pour le candidat, **−0,178594** pour la référence. Le deuxième candidat atteint 0,069946 : l’écart de tête est faible, sans test de significativité.

## Comparaison des variantes en validation

Le meilleur réglage de chaque variante est présenté ci-dessous. Ces scores sont des utilités sans unité, pas des pourcentages de rendement. Seul le premier candidat global a été évalué sur le test final.

| Variante | Meilleur score | Entrée / sortie | Confirmations achat / vente |
| --- | ---: | --- | --- |
| Modèle actuel | -0.039825 | 80% / 50% | 1 / 1 |
| Momentum 5 | 0.069433 | 90% / 50% | 5 / 5 |
| Momentum 20 | -0.008153 | 65% / 50% | 1 / 5 |
| Rendement seul | 0.070861 | 90% / 50% | 3 / 5 |
| Covariance complète | -0.003857 | 80% / 35% | 1 / 5 |
| Trois états | 0.045444 | 80% / 50% | 3 / 1 |
| Fenêtre glissante 504 | 0.013751 | 65% / 35% | 1 / 3 |
| Fenêtre glissante 1 008 | -0.032151 | 65% / 35% | 1 / 5 |

## Dernière fenêtre : résultats par actif

Rendement total net et drawdown maximal. « Réf. → candidat » compare les mêmes dates et les mêmes coûts de 15 pb. L’achat-conservation supporte ses coûts d’entrée/sortie.

| Actif | Période de test | Rendement réf. → candidat | Achat-conservation | Drawdown réf. → candidat | Exposition réf. → candidat | Ordres réf. → candidat |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Apple | 2025-04-01 – 2026-11-05 | 24.80 % → 82.85 % | 55.43 % | 11.94 % → 13.80 % | 56.33 % → 66.75 % | 18 → 8 |
| Cardano | 2025-09-30 – 2026-11-06 | -13.25 % → 0.00 % | -77.08 % | 24.55 % → 0.00 % | 8.68 % → 0.00 % | 10 → 0 |
| Air Liquide | 2025-04-10 – 2026-11-06 | 13.18 % → 17.94 % | 32.50 % | 17.24 % → 16.26 % | 40.20 % → 96.77 % | 16 → 2 |
| ASML | 2025-04-10 – 2026-11-06 | 18.93 % → 20.78 % | 134.74 % | 25.57 % → 17.23 % | 58.81 % → 18.61 % | 16 → 4 |
| BNB | 2025-09-30 – 2026-11-06 | -10.26 % → -21.81 % | -32.87 % | 30.79 % → 42.42 % | 65.51 % → 79.40 % | 6 → 4 |
| Bitcoin | 2025-09-30 – 2026-11-06 | -11.52 % → 0.67 % | -33.70 % | 27.50 % → 3.17 % | 66.50 % → 1.49 % | 12 → 2 |
| Ethereum | 2025-09-30 – 2026-11-06 | 9.36 % → -28.37 % | -47.14 % | 27.46 % → 50.60 % | 54.34 % → 65.76 % | 14 → 4 |
| LVMH | 2025-04-10 – 2026-11-06 | 13.23 % → -19.83 % | -15.62 % | 18.27 % → 26.38 % | 40.20 % → 19.60 % | 16 → 4 |
| Microsoft | 2025-04-01 – 2026-11-05 | 12.57 % → 20.23 % | 44.01 % | 31.74 % → 36.79 % | 55.09 % → 76.18 % | 16 → 8 |
| Solana | 2025-09-30 – 2026-11-06 | -11.38 % → 0.00 % | -57.89 % | 25.45 % → 0.00 % | 16.13 % → 0.00 % | 14 → 0 |
| XRP | 2025-09-30 – 2026-11-06 | 0.96 % → -5.79 % | -58.59 % | 7.10 % → 9.27 % | 2.23 % → 1.49 % | 2 → 2 |

## Moyennes par catégorie et stress des coûts

Ces chiffres sont des **moyennes arithmétiques de statistiques par actif**, pas les performances d’un portefeuille négociable. Les drawdowns moyens ne sont pas le drawdown d’un portefeuille. Les périodes se chevauchent et les actifs sont corrélés : onze actifs ne constituent pas onze expériences indépendantes.

| Catégorie | Coût par ordre | Rendement total réf. → candidat | Drawdown réf. → candidat | Sharpe réf. → candidat | Ordres moyens réf. → candidat |
| --- | ---: | ---: | ---: | ---: | ---: |
| Actions | 15 pb | 16.54 % → 24.39 % | 20.95 % → 22.09 % | 0.609 → 0.589 | 16.40 → 5.20 |
| Actions | 30 pb | 13.70 % → 23.36 % | 21.64 % → 22.22 % | 0.523 → 0.563 | 16.40 → 5.20 |
| Cryptos | 15 pb | -6.01 % → -9.22 % | 23.81 % → 17.58 % | -0.143 → -0.218 | 9.67 → 2.00 |
| Cryptos | 30 pb | -7.37 % → -9.46 % | 24.50 % → 17.68 % | -0.196 → -0.239 | 9.67 → 2.00 |

Pour le Sharpe, les stratégies sans transaction sont indéfinies : ces moyennes reprennent la convention zéro du score, sans transformer ce zéro conventionnel en ratio estimé.

Sur les 11 actifs : **140 → 38 ordres (−72,9 %)**. La réduction des frais est réelle dans ces simulations ; elle ne compense pas toutes les erreurs de direction. Ethereum passe notamment de +9,36 % à −28,37 %, et LVMH de +13,23 % à −19,83 %. Cardano et Solana restent entièrement en liquidités avec le candidat : leur rendement nul correspond à une absence d’exposition, pas à une prévision parfaite.

Le candidat améliore le rendement de 7 actifs sur 11, mais seulement de 3 cryptos sur 6. Son Sharpe moyen est inférieur dans les deux catégories. Il n’y a donc pas de preuve suffisante pour remplacer les défauts de production par cette seule configuration. Une nouvelle recherche après lecture de ce tableau devra être considérée comme exploratoire et validée ultérieurement sur de nouvelles données.

## Reproduction et sources

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend .venv/bin/python -B backend/research/hmm_benchmark.py
```

Le [script](../backend/research/hmm_benchmark.py) ne modifie que son fichier de sortie, par défaut [hmm-benchmark.json](hmm-benchmark.json). Le rapport contient le classement des 432 configurations, les diagnostics de convergence, les fenêtres, les métriques par actif et les versions numériques. Relancer la commande remplace le rapport et utilise les cours alors présents ; conserver son empreinte pour comparer les instantanés.

Empreinte SHA-256 des métadonnées, dates et valeurs : `b095fc4d1700b760d91b501ef5cc785f04fb1138a0653e2d05cf22295082b2b6`.

- [Bailey et al., The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) : risque de sélection lié à la multiplication des essais. Ce benchmark ne calcule pas une PBO.
- [Pohle et al., Selecting the Number of States in Hidden Markov Models](https://arxiv.org/abs/1701.08673) : augmenter le nombre d’états ne garantit pas des régimes plus pertinents.
- [Oelschläger, Adam et Michels, fHMM (2024)](https://www.jstatsoft.org/article/view/v109i09) : estimation et diagnostics des HMM financiers.
