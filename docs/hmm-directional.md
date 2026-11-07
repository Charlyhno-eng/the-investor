# HMM directionnel, frais et benchmarks locaux

> Archive : ce document concerne les versions ou recherches antérieures à la reconstruction du 6 novembre 2026. Le [moteur actif est décrit ici](hmm-rebuilt.md).

**Revue ultérieure :** l’[audit de passivité et la recherche de variantes](hmm-literature.md) montrent que 11 modèles sur 22 ne peuvent pas déclencher de sortie par leur politique actuelle. Cette version ne satisfait pas la surperformance demandée ; les variantes lissées et les filtres de volatilité ont été testés séparément, sans remplacement du moteur actif.

Mise à jour du 6 novembre 2026. À la demande de l’utilisateur : retrait du stop de drawdown à 10 %, des règles de réentrée associées et des messages de protection. Le HMM décide seul des changements long/liquidités, avec prise en compte des frais. Aucun objectif de nombre d’ordres.

Défauts communs à l’interface et à l’API : **crypto 0,01 % par ordre, action 0,5 % par ordre**. Un taux explicite, y compris zéro, est conservé. Le bouton se trouve à droite du paramètre sur ordinateur ; les contrôles se replient sur petit écran. Cardano et XRP sont retirés du catalogue et des actualisations automatiques ; leurs archives ne sont pas effacées.

## Ce qui change dans le modèle

L’ancienne modélisation à deux états séparait surtout les volatilités. « Calme » ne voulait pas dire « haussier ». La nouvelle version classe les états par rendement logarithmique moyen estimé sur l’entraînement, sans utiliser les performances du test pour leur attribuer un sens.

Quatre structures candidates, sans grille de seuils de trading : deux ou trois états, avec le rendement logarithmique seul ou avec sa moyenne et sa log-volatilité sur les 20 dernières observations. Le contexte est une observation du HMM, pas une règle d’entrée/sortie séparée. Les 19 premières variations sont indisponibles, sans remplissage futur. Le minimum d’entraînement est 100 variations valides après cette mise en place.

La période d’entraînement est divisée en 80 % d’ajustement et 20 % de validation chronologique. Trois initialisations par structure (17, 41, 83) sont départagées par vraisemblance d’ajustement. La structure est ensuite choisie par la **log-densité prédictive du prochain rendement quotidien** sur la validation. Les quatre structures prédisent ainsi exactement la même variable ; comparer les vraisemblances conjointes d’une et trois observations aurait été incorrect. Le filtre de validation continue depuis le passé et n’utilise pas de lissage futur. Aucun gain de stratégie, frais ou nombre d’ordres n’entre dans le score de sélection.

Le modèle retenu est réajusté sur toute la période d’entraînement. Normalisation, moyennes, covariances et transitions restent figées pendant le test. Les covariances sont régularisées ; un état occupé par moins de cinq observations ou de 1 % de l’ajustement est rejeté. Une absence de convergence est signalée. Le résultat expose les scores de validation et les colonnes retenues dans `model_selection`.

Dans les fenêtres par défaut du panel, le modèle sans contexte est retenu pour 20 actifs sur 22, celui avec contexte pour deux. Le contexte n’est donc pas imposé parce qu’il semble plus sophistiqué. Références méthodologiques : [API officielle hmmlearn](https://hmmlearn.readthedocs.io/en/stable/api.html), [Dynamax, validation et sélection de modèles gaussiens](https://probml.github.io/dynamax/notebooks/hmm/gaussian_hmm.html).

## Décisions et exécution

Soient `P` la matrice de transition, `μ` les rendements logarithmiques moyens par état et `c = −log(1 − frais)` le coût d’un ordre. Le signal de clôture t est exécuté à la clôture t+1 et commence à percevoir les rendements à t+2. Son premier rendement prévu est donc `r = P² μ`.

La différence des valeurs de continuation entre détenir et rester en liquidités satisfait l’approximation de Bellman `d = clip(r + P d, −c, c)`. Une itération moyennée évite les oscillations pour une matrice de transition périodique. Avec les probabilités filtrées courantes `p`, l’avantage est `p × (r + P d)` : achat au-delà de `c`, vente sous `−c`, maintien autrement. Le modèle tient ainsi compte de la persistance des états et des coûts de changements futurs, sans durée de détention, calendrier d’ordres ou quota imposés.

Cette politique utilise une approximation des états cachés par leurs probabilités : ce n’est pas une résolution exacte du problème de contrôle avec information partielle. Le chevauchement des observations glissantes s’écarte aussi de l’hypothèse d’indépendance conditionnelle du HMM. Ni ses probabilités ni ses espérances de rendement ne sont garanties calibrées.

Le moteur paie le même coût à chaque achat/vente, sans percevoir le rendement précédant une entrée. Il liquide à la fin du test. Le benchmark supporte aussi une entrée et une sortie. Liquidités non rémunérées, hors fiscalité et glissement. **Aucun stop, plafond de drawdown, verrou de réentrée ni OHLC dans le moteur actif.** Une position peut rester ouverte longtemps si le modèle demeure favorable, ou être conservée pendant une forte perte.

## Protocole local

22 actifs du catalogue actuel : 16 actions et six cryptos. Cardano et XRP exclus conformément à la demande. Comparaisons aux mêmes frais entre l’ancienne version avec stop/réentrée, sa politique de prévision sans stop et le nouveau HMM.

- Test continu 2022–2025, entraînement 2015–2021.
- Cinq tests annuels 2022 à 2026, chaque fois entraînés sur les cinq années précédentes ; 2026 est arrêté à la dernière observation disponible. Ce sont des fenêtres indépendantes, pas une courbe de portefeuille recollée.
- Fenêtre par défaut de l’interface pour chaque actif : jusqu’à 2 016 prix, découpage 70/30.
- Frais par catégorie demandés, puis scénario de sensibilité à deux fois ces frais.

Hyperliquid manque d’entraînement pour le test continu et les années 2022–2025 : ces cinq fenêtres sont explicitement exclues. **149 fenêtres admissibles × trois politiques × deux scénarios de frais = 894 diagnostics**, sans échec du modèle.

Les 894 cas finaux sont conservés dans `data/backtests/hmm-directional-final/`, ignoré par Git. Le plan et les empreintes des sources sont écrits avant le calcul ; résultats, ordres, capitaux, sélections internes et empreintes des données restent disponibles. Le script refuse d’écraser une expérience :

```sh
PYTHONPATH=backend .venv/bin/python scripts/backtest_regimes.py
```

Deux conceptions ont été examinées, et sont conservées : `hmm-regimes/` imposait les trois observations et choisissait seulement le nombre d’états par vraisemblance jointe ; `hmm-regimes-selected/` ajoute le retour possible aux rendements seuls et compare la même cible prédictive. La première réduisait les transactions mais n’améliorait pas régulièrement les gains par rapport au simple retrait du stop. La seconde a été réexécutée à règles financières identiques dans le dossier final après changement de version du cache. Ces étapes font partie de la recherche exploratoire et ne sont pas présentées comme des confirmations indépendantes.

## Résultats aux frais demandés

Médianes des 22 simulations sur les fenêtres par défaut. Les durées diffèrent selon l’actif et ces médianes ne décrivent pas un portefeuille diversifié.

| Mesure | Ancienne version avec stop | Ancienne version sans stop | HMM retenu |
| --- | ---: | ---: | ---: |
| Rendement net médian | +10,24 % | +33,40 % | +27,33 % |
| Drawdown maximal médian | 42,56 % | 35,69 % | 35,69 % |
| Nombre médian d’ordres | 28 | 2 | 2 |
| Actifs rentables | 13 / 22 | 17 / 22 | 16 / 22 |
| Actifs battant la conservation | 4 / 22 | 11 / 22 | 7 / 22 |

Le retrait du stop explique une grande part de l’amélioration. **Le nouveau HMM ne domine pas la simple suppression du stop**, notamment sur le rendement médian. La complexité supplémentaire ne démontre donc pas un avantage financier général.

Deux ordres signifient souvent une position conservée pendant presque tout le test, contrairement à l’ancien verrou qui pouvait immobiliser le capital en liquidités après une sortie. Aucun nombre d’ordres n’est forcé. Le problème des transactions reste présent sur certains actifs : Ethereum compte 104 ordres sur sa fenêtre par défaut, BNB 44, Monero 40, avec 0,01 % de frais par ordre. Ils ne sont ni plafonnés ni masqués. Ethereum rapporte +3,50 % contre +17,10 % en conservation : l’algorithme ne résout pas tous les cas de sous-performance.

GTT, sur la fenêtre correspondant à la capture et aux nouveaux frais de 0,5 % : **+72,73 %**, quatre ordres, drawdown 20,22 %, contre **+60,19 %** en conservation. L’ancienne version avec stop donne +44,11 %, 22 ordres. Ces chiffres diffèrent de la revue précédente, qui utilisait 0,1 % par ordre.

| Fenêtre | Actifs | Rendement médian HMM | Drawdown médian | Ordres médians | Surperformance sur conservation |
| --- | ---: | ---: | ---: | ---: | ---: |
| Continu 2022–2025 | 21 | +35,43 % | 40,61 % | 6 | 4 / 21 |
| Année 2022 | 21 | −25,39 % | 36,18 % | 4 | 4 / 21 |
| Année 2023 | 21 | +28,36 % | 20,06 % | 6 | 3 / 21 |
| Année 2024 | 21 | +24,90 % | 26,18 % | 2 | 12 / 21 |
| Année 2025 | 21 | +8,48 % | 29,77 % | 2 | 5 / 21 |
| Année 2026 disponible | 22 | +1,71 % | 30,25 % | 2 | 11 / 22 |

En doublant les frais, le rendement net médian des fenêtres par défaut passe à +26,84 %. Les régimes et choix de modèle restent identiques ; les ordres peuvent changer parce que les coûts entrent dans la décision.

## Portée et vérifications

Ces actifs et périodes ont déjà servi à la recherche. Les fenêtres se chevauchent, le catalogue présente un biais de survivance et les historiques peuvent être révisés. La séparation interne réduit les choix de modèles fondés sur les résultats de test, mais **ne prouve pas l’absence de surapprentissage** après cette recherche exploratoire. Le HMM ne bat pas la conservation dans la majorité des cas. Une validation prospective sur des données nouvelles est nécessaire pour conclure à un avantage reproductible.

92 tests backend réussis, dont causalité des observations/états/ordres, densité prédictive validée depuis chaque préfixe passé, réutilisation du modèle après changement des frais ou du futur, reconnaissance de dérives opposées à bruit identique, coûts symétriques et exécution retardée, maintien malgré une perte de 50 % sans stop, réentrée sur changement du modèle et convergence du contrôle de coûts. 20 tests d’interface passent sur ordinateur et mobile, notamment frais par catégorie et alignement du bouton. Compilation TypeScript et build de production réussis. Cardano/XRP sont absents de la bibliothèque et de l’import, sans suppression de leurs historiques. Aucun push GitHub.
