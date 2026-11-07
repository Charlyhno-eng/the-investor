# HMM de FrenchQuant : méthode et résultats

> Archive : ce document concerne les versions ou recherches antérieures à la reconstruction du 6 novembre 2026. Le [moteur actif est décrit ici](hmm-rebuilt.md).

> Version historique : voir la [correction de rotation et de protection](hmm-risk-review.md) pour la politique actuelle.

Source : [Modèles de Markov cachés : Application en Trading Algorithmique](https://www.youtube.com/watch?v=Eix0xaQmgYk), FrenchQuant, 15 min 08. Analyse du 6 novembre 2026 à partir des sous-titres automatiques français récupérés sur YouTube. Le code à l’écran n’a pas pu être vérifié : cette adaptation reprend la méthode orale, sans prétendre reproduire exactement son notebook.

## Méthode de la vidéo

- 00:58–01:46 : deux régimes gaussiens, marché normal et marché très volatil.
- 01:48–02:12 : pandas, NumPy, yfinance, TA-Lib, hmmlearn/GaussianHMM, matplotlib/seaborn, vectorbt et pyfolio.
- 02:20–03:16 : séparation chronologique entraînement/test, rendements journaliers seuls, deux composantes, covariance complète, 1 000 itérations.
- 04:25–05:02 : interprétation des distributions par leur volatilité.
- 06:17–06:39 et 09:50–14:41 : stratégie HMM seule, investie dans le régime normal, liquidités dans le régime extrême. Les performances annoncées concernent le CAC 40, principalement 2010–2023.

Les variantes MACD et moyennes mobiles ne sont pas intégrées.

## Adaptation

Une variable : rendement simple journalier. Deux états, covariance complète, 1 000 itérations maximales, tolérance 0,01. Normalisation sur l’entraînement uniquement. Trois initialisations fixes (17, 41, 83), sélection par vraisemblance d’entraînement, suivant la recommandation de [hmmlearn](https://hmmlearn.readthedocs.io/en/stable/tutorial.html#training-hmm-parameters-and-inferring-the-hidden-states). Aucun résultat du test ne sélectionne le modèle.

Les régimes « Calme » et « Extrême » sont classés par volatilité entraînée, indépendamment des numéros bruts de la bibliothèque. La cible suit le régime filtré le plus probable ; une égalité laisse en liquidités. Aucun momentum, confirmation, seuil configurable, plafond ou détention minimale.

Le seul paramètre de stratégie dans l’interface et l’API est le taux proportionnel de frais, identique à l’achat, à la vente et pour le benchmark. Les périodes restent sélectionnables. L’API refuse explicitement les anciens paramètres (422).

Le moteur existant remplace vectorbt/pyfolio pour conserver les conventions d’exécution et métriques testées. TA-Lib n’est pas nécessaire sans indicateur technique. Les graphiques de l’application remplacent matplotlib/seaborn. Aucune dépendance ajoutée.

La détection reste causale : filtre forward, aucun Viterbi ou lissage sur l’ensemble du test. Séparer entraînement et test ne garantit pas, à lui seul, une détection causale à l’intérieur du test ; la transcription ne permet pas de vérifier ce point dans son code. Un signal de clôture s’exécute à la clôture suivante, après son rendement. Liquidation finale et frais inclus. Les actifs locaux diffèrent du CAC 40 de la vidéo : une égalité des performances n’est pas attendue.

## Comparaison à la version précédente

23 cas sur huit actifs : AAPL, MSFT, NVDA, Air Liquide, LVMH, BTC, ETH, SOL. Trois fenêtres de cinq ans terminant début 2020, 2022 et 2024 ; découpage chronologique à 70 %. Un cas SOL exclu faute de données. Frais de 0,1 % par ordre. Référence : ancienne version directionnelle à momentum et confirmations 5/3.

| Mesure sur les 23 cas | Précédente | Adaptation vidéo |
| --- | ---: | ---: |
| Rendement médian net du test, non annualisé | 9,37 % | 39,78 % |
| Sharpe médian | 0,506 | 0,962 |
| Perte maximale médiane | 19,10 % | 25,87 % |
| Cas dépassant l’achat-conservation | 4 / 23 | 4 / 23 |

Le rendement médian augmente, mais la protection n’est pas systématiquement meilleure et les transactions sont souvent plus nombreuses. Ces médianes ne sont pas les performances d’un portefeuille.

## Années complètes et frais

31 couples actif/année : tests sur 2020, 2022, 2024, 2025. Entraînement sur les données précédentes, à partir respectivement de 2015, 2017, 2019 et 2020. SOL/2020 exclu faute de 500 prix sur la fenêtre complète. Trois taux fixes : **93 évaluations**, sans ajustement en fonction des résultats.

| Frais par ordre | Rendement médian net | Sharpe médian | Perte maximale médiane | Surperformance | Perte maximale inférieure au benchmark |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 % | 3,67 % | 0,284 | 28,17 % | 12 / 31 | 24 / 31 |
| 0,1 % | 0,00 % | 0,127 | 29,65 % | 10 / 31 | 21 / 31 |
| 0,5 % | −8,45 % | −0,228 | 36,56 % | 2 / 31 | 16 / 31 |

À 0,1 % par ordre :

| Année | Cas | Rendement médian HMM / conservation | Perte maximale médiane HMM / conservation |
| --- | ---: | ---: | ---: |
| 2020 | 7 | 35,95 % / 81,94 % | 15,75 % / 34,42 % |
| 2022 | 8 | −39,57 % / −39,27 % | 46,97 % / 49,32 % |
| 2024 | 8 | 22,41 % / 38,11 % | 29,48 % / 26,61 % |
| 2025 | 8 | −0,33 % / 3,74 % | 33,06 % / 34,51 % |

La méthode retrouve la logique de la vidéo, mais ne garantit pas de bons résultats sur chaque actif. Elle protège souvent des fortes baisses, peut manquer les rebonds et reste sensible à la rotation et aux frais. Aucun paramètre n’a été modifié après lecture de ces tableaux. Les fenêtres et les actifs sont corrélés : ces comptes ne constituent pas un test statistique d’alpha.

Détail : [CSV d’évaluation](hmm-evaluation.csv), rendements et drawdowns en valeurs décimales. Les lignes calendrier comportent une empreinte SHA-256 des observations ; les lignes de comparaison historique n’ont pas d’empreinte enregistrée.

Reproduction en lecture seule sur SQLite :

```sh
PYTHONPATH=backend .venv/bin/python scripts/benchmark_hmm.py --output /tmp/hmm-calendar.json
PYTHONPATH=backend .venv/bin/python scripts/benchmark_hmm.py --mode split --output /tmp/hmm-split.json
```

Une correction fournisseur ou une mise à jour des bibliothèques peut modifier les résultats. Aucun téléchargement de données pour cette étude.

## Vérifications

Tests des rendements connus, causalité des régimes et des performances, classement par volatilité, probabilités normalisées, filtre comparé aux préfixes, cache, délai d’exécution, frais symétriques, liquidation finale, cohérence positions/journal et refus des anciens réglages. Les tests navigateur vérifient le champ unique, le corps de requête, les dates, l’actualisation et la sérialisation des calculs sur ordinateur et mobile.
