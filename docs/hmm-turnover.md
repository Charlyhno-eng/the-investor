# Réduction des allers-retours HMM

> Étude historique : la méthode actuelle est décrite dans [la revue FrenchQuant](hmm-video.md).

Comparaison locale du 6 novembre 2026, sur BTC, ETH, Apple, Microsoft et or. Même modèle et mêmes coûts : 10 pb de frais et 5 pb de glissement par ordre. Dernières 2 016 observations quotidiennes, historique complet mensuel. Entraînement sur 60 %, comparaison de 12 réglages (entrée 65/75/85 %, sortie 25/35 %, confirmation 2/3) sur les 20 % suivants, évaluation sur les derniers 20 %. Le score de validation est le rendement annualisé borné à [−100 %, 200 %], moins 0,3 fois l’exposition et 0,5 fois le drawdown. Les données ont déjà servi à d’autres diagnostics ; ces essais ne constituent pas une preuve indépendante de généralisation.

Ancienne politique : 75/35 %, une confirmation à l’entrée, sortie immédiate et forcée dès que le momentum devient non positif. Nouvelle politique sélectionnée : 75/35 %, deux confirmations sur achat et vente ; le momentum positif conditionne seulement les entrées. Aucune détention minimale imposée ni plafond d’ordres dans les deux politiques.

| Actif | Ordres avant / après | Rendement net avant / après | Exposition avant / après | Drawdown avant / après |
| --- | ---: | ---: | ---: | ---: |
| yf-btc-usd | 64 / 14 | -26.60 % / -26.24 % | 45.66 % / 75.68 % | 30.54 % / 40.68 % |
| yf-eth-usd | 76 / 10 | -50.13 % / -6.52 % | 43.18 % / 78.41 % | 51.90 % / 37.16 % |
| yf-aapl | 44 / 22 | -16.17 % / 16.64 % | 55.58 % / 64.27 % | 28.21 % / 16.27 % |
| yf-msft | 40 / 18 | 25.01 % / 47.68 % | 50.87 % / 65.51 % | 19.33 % / 20.04 % |
| wb-gold | 34 / 2 | 102.70 % / 220.74 % | 59.38 % / 96.88 % | 27.29 % / 19.46 % |

Le nombre d’ordres baisse sur les cinq essais et les rendements nets augmentent sur ces fenêtres. L’exposition augmente également, et le drawdown du Bitcoin se dégrade ; BTC et ETH restent en perte. Cette politique corrige les ventes/rachats fréquents, sans garantir une hausse du rendement ou une baisse du risque sur d’autres périodes. Les coûts restent appliqués à chaque ordre réellement exécuté, liquidation finale comprise.

Régressions couvertes : un marché synthétique alternant les signaux brefs génère moins d’ordres et moins de frais avec deux confirmations ; les sorties doivent elles aussi être confirmées. Les signaux n’utilisent que les clôtures passées et leur exécution reste décalée.
