# HMM reconstruit — 6 novembre 2026

> **Rejet financier confirmé sur le catalogue complet : 3 actions sur 19 battent la conservation aux frais par défaut, 17 simulations sans ordre.** Le [nouvel audit complet](hmm-stock-audit.md) remplace l’évaluation partielle ci-dessous comme critère d’acceptation. Le moteur conserve ses calculs, avec un diagnostic d’entrée impossible ajouté dans la version `v2-entry-diagnostics`.

Version active : `hmm-rebuilt-return-only-expanding-validation-v1`.

Le moteur de production remplace les observations de contexte et la politique de continuation précédentes. Les anciens travaux sont des archives : `research_legacy.py`, `legacy.py`, `adaptive.py` et les scripts de recherche ne choisissent pas les modèles de l’API. Aucun résultat de leurs backtests n’a servi à régler cette reconstruction. Les anciennes entrées de cache sont ignorées grâce à la nouvelle version ; les cours locaux sont conservés.

## Observation et estimation

Une seule variable : `r[t] = log(prix[t] / prix[t−1])`. Aucune moyenne glissante, volatilité glissante, padding ou sélection de variables. Au moins 100 rendements d’entraînement non constants et 20 de test. Dates uniques croissantes, prix finis strictement positifs ; maximum 40 000 prix.

Candidats : une gaussienne sans régimes, HMM gaussiens à deux et trois états. Pour chaque ajustement, normalisation sur le préfixe d’entraînement correspondant uniquement. Le modèle à un état utilise les estimateurs gaussiens de moyenne et variance. Les autres utilisent cinq initialisations déterministes, dont deux initialisations persistantes par moyennes/variances différentes, puis trois initialisations aléatoires (`17, 41, 83, 127, 191`), EM limité à 500 itérations, tolérance 0,001. Les transitions et covariances sont légèrement régularisées, la distribution initiale uniforme est fixe. Occupation minimale : `max(10, 2 % du préfixe)`. Les ajustements non finis, dégénérés ou sans stabilisation sont exclus. La stabilisation admet une baisse numérique de log-vraisemblance au plus égale à 0,01 avec la régularisation ; cette tolérance ne garantit pas un optimum global.

Deux validations croissantes **dans l’entraînement uniquement** : ajustement sur les premiers 60 %, prévision sur les 20 % suivants ; ajustement sur les premiers 80 %, prévision sur les 20 % restants. Pour chaque observation validée : log-densité du rendement avant de l’observer, depuis le posterior filtré précédent multiplié par la matrice de transition. Les scores quotidiens sont concaténés. La sélection retient le plus petit nombre d’états dont le score est à une erreur standard appariée du meilleur candidat ; erreur calculée sur dix blocs successifs de validation, ou moins pour les petits échantillons. Cette préférence de parcimonie est une heuristique, pas un test de significativité.

Le candidat retenu est ajusté de nouveau sur tout l’entraînement. En cas d’échec, les autres candidats sont essayés ; la gaussienne simple reste disponible. La période de test, les frais et les profits simulés ne participent à aucun choix. Le nombre d’états retenu et les scores sont exposés par `model_selection`.

## Filtrage et interprétation

Récursion forward écrite en espace logarithmique avec NumPy/SciPy, sans noyau privé hmmlearn, Viterbi ni lissage du test. Les états très improbables restent récupérables après de nouvelles observations. Les paramètres restent fixes pendant le test ; une éventuelle période intermédiaire met seulement à jour les probabilités. Les états sont ordonnés par moyenne logarithmique apprise. Les libellés décrivent le signe de cette moyenne, sans imposer un état haussier et un état baissier. `mean_change = exp(mu) − 1` est une moyenne géométrique par observation ; `volatility` est l’écart-type logarithmique. Une validation favorable peut seulement identifier des distributions de volatilité différentes ; elle ne prouve pas un signal directionnel.

Le modèle à un état est affiché « Sans régimes ». Il peut produire une position constante selon sa moyenne et les frais. Cela n’est pas une stratégie de changements de régime validée.

## Simulation explicite

Long ou liquidités, sans levier. À la clôture t, pour les probabilités filtrées p, matrice P et moyennes logarithmiques mu :

`prévision = p × (P² + P³ + P⁴ + P⁵ + P⁶) × mu`

Le premier rendement gagné après une exécution à la clôture t+1 est celui de t+2. Cinq observations constituent un horizon de prévision fixe, choisi avant l’évaluation locale, sans durée minimale de détention ni optimisation sur le test.

`seuil = −2 × log(1 − frais)`

Achat si la prévision dépasse le seuil ; vente si elle est sous son opposé ; maintien autrement. Ce sont des seuils symétriques comparés aux frais aller-retour, une règle explicite et conservatrice, pas une politique optimale. Il n’y a plus de valeur de continuation à horizon infini. Un signal précédant le test peut être exécuté à la première clôture du test ; aucun rendement antérieur à l’exécution n’est gagné. Toute position est liquidée à la dernière clôture, sans nouvel achat.

Les frais réels sont débités à chaque ordre. Le benchmark achète à la clôture de référence précédant le premier rendement de test et vend à sa dernière clôture, avec les mêmes frais. Défauts inchangés : actions 50 pb, cryptos 1 pb, valeur explicite zéro respectée. Liquidités non rémunérées, hors glissement et fiscalité. Exposition presque permanente et impossibilité mathématique d’une sortie avec ces paramètres restent signalées ; aucune transaction n’est fabriquée pour améliorer ces diagnostics.

## Évaluation locale, sans réglage ultérieur

Commande : `PYTHONPATH=backend .venv/bin/python scripts/benchmark_hmm.py --mode split --output /tmp/hmm-rebuilt-benchmark.json`.

23 simulations sur huit actifs, trois fenêtres par actif quand l’historique le permet, séparation chronologique 70/30, frais de **10 pb par ordre** pour cette évaluation comparative. SOL sur la première fenêtre est exclu faute de 500 cours. Les fenêtres se chevauchent : ce ne sont pas 23 expériences indépendantes. Les empreintes des données et les dates effectives figurent dans [le CSV](hmm-rebuilt-evaluation.csv). Ce benchmark n’utilise pas les frais par défaut de chaque catégorie.

- Nombre d’états : 1 modèle à un état, 10 à deux, 12 à trois.
- Rendement net supérieur à la conservation dans 12 simulations sur 23 ; écart médian **+0,52 point**.
- Exposition ≥95 % dans **16 cas sur 23** ; ≤5 % dans 2 cas. Médiane de quatre ordres, liquidation comprise.
- Écart médian pour ETH : **−28,95 points**, pour SOL : **−331,52 points**. Les importantes hausses manquées restent un échec économique.

Ces résultats ne démontrent **aucune surperformance robuste**. La reconstruction apporte une méthode contrôlable et une absence explicite de régimes quand la validation l’indique ; elle ne résout pas la difficulté de prédire les rendements ni la sensibilité aux frais. Aucun paramètre n’a été modifié après lecture de ces résultats.

## Sources et reproductibilité

[Documentation officielle hmmlearn 0.3.3](https://hmmlearn.readthedocs.io/en/0.3.3/tutorial.html) pour les ajustements multiples et leurs optimums locaux ; [Dynamax, sélection par validation](https://probml.github.io/dynamax/notebooks/hmm/gaussian_hmm.html) pour l’évaluation prédictive de HMM. La règle de transaction et la règle de parcimonie sont les conventions explicites de cette application.

Empreintes SHA-256 du moteur évalué :

- `model.py` : `27e1289c83f88ad9bc404a9f54781345f4c006107d87604b9dede21d92e81b65`
- `regimes.py` : `fdff72efb7aafe382dcb535b7bcd130c8322bc791c6a3a2932abc5bd56a009cb`
- `service.py` : `b5733446bdcb5a6696103863491e2b9ae44a3a1c5d1cdabd04ddffaf22de80ae`
- `switching.py` : `896bbc4044e01b67f84729220496379ebbdd6faade243570053d45ddb8e60450`
- `diagnostics.py` : `8cb7c4c537c44f3a88c95eeda6f730c6d495cb22c3e5c55ef2a878a1e37e7f08`
- `metrics.py` : `7c4f6e9e8230db8742a64d199f8f06183266ce41824fb46f2047f9e5c6e46eed`
- `schemas.py` : `b171308e228f49d48b30b5266d3179e38f8c5a49e10ada71f797b610b22385bc`
