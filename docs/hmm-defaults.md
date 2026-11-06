# Réglages orientés vers une exposition réduite

> Étude historique : la méthode actuelle est décrite dans [la revue FrenchQuant](hmm-video.md).

Étude de la version précédente. Ces réglages sont remplacés par [la politique réduisant les allers-retours](hmm-turnover.md).

Comparaison locale du 6 novembre 2026. Cinq actifs prédéfinis : BTC, ETH, Apple, Microsoft et or mensuel. Dernières 2 016 observations quotidiennes, historique entier pour le mensuel. Modèle entraîné sur les premiers 60 %, sélection sur les 20 % suivants, évaluation sur les derniers 20 %, sans réentraînement. Les périodes de test ne participent pas au score de sélection. Les données ont déjà servi à des diagnostics précédents : il ne s’agit pas d’une validation indépendante définitive.

18 combinaisons : entrée 65/75/85 %, sortie 35/50/60 %, confirmation avant achat 1/2. Momentum positif obligatoire, sortie sans confirmation supplémentaire, pas de détention imposée ni de plafond. Score moyen de validation : rendement annualisé borné entre −100 % et +200 %, moins exposition, moins la moitié du drawdown maximal. Les pondérations expriment une préférence pour une faible exposition ; elles ne définissent pas un optimum financier universel. Frais 10 pb et écart de prix 5 pb conservés, car ils représentent un coût supposé, pas une variable à minimiser artificiellement.

Sélection : `(0.75, 0.35, 1, 1, None)` (entrée, sortie, confirmation, détention, plafond). Comparaison avec la politique de référence 65/35 %, trois confirmations, détention 10, plafond 30 et sans filtre de momentum. Même HMM pour isoler les règles de stratégie.

| Actif | Exposition référence / nouvelle | Rendement net référence / nouveau | Drawdown référence / nouveau |
| --- | ---: | ---: | ---: |
| yf-btc-usd | 78.41 % / 45.66 % | -23.08 % / -26.60 % | 38.14 % / 30.54 % |
| yf-eth-usd | 82.38 % / 43.18 % | -13.98 % / -50.13 % | 42.17 % / 51.90 % |
| yf-aapl | 69.98 % / 55.58 % | 33.80 % / -16.17 % | 13.86 % / 28.21 % |
| yf-msft | 66.25 % / 50.87 % | 48.61 % / 25.01 % | 22.37 % / 19.33 % |
| wb-gold | 97.50 % / 59.38 % | 210.76 % / 102.70 % | 19.46 % / 27.29 % |

Le temps investi baisse pour tous ces essais. Les rendements diminuent aussi : ce réglage ne satisfait donc pas simultanément une hausse des gains et une baisse d’exposition. Le drawdown se dégrade pour plusieurs actifs. Le résultat doit être présenté comme un choix plus sélectif, pas comme une amélioration prouvée du rendement ou du risque.

Les tests de régression couvrent notamment la sortie sans attendre les confirmations d’achat et le refus d’achat sur momentum négatif malgré un modèle haussier.
