# Conventions du laboratoire quantitatif

## Données et périodes

Le calcul lit uniquement SQLite. L’utilisateur choisit deux fenêtres fermées, ordonnées et sans chevauchement. Une éventuelle zone entre entraînement et test sert seulement à mettre à jour le filtre, sans réentraîner le modèle ni ouvrir de position. Les premières observations de la fenêtre 1 initialisent la volatilité glissante et sont exclues de l’ajustement. Minimum : 100 variations après initialisation pour entraîner, 20 variations pour tester ; maximum 40 000 observations au total.

Les dates réellement observées figurent dans le résultat. Une variation datée au début de la fenêtre 2 est calculée depuis la clôture précédente disponible : cette clôture est la base 100 commune du benchmark et de la stratégie. Les jours sans observation ne sont pas interpolés. Les séries très lacunaires peuvent rendre l’annualisation peu représentative.

Actions : clôtures ajustées Yahoo Finance, via `yfinance`, pour tenir compte des splits et distributions selon les ajustements du fournisseur. Crypto : clôtures quotidiennes en USD, sans rendement de staking. Commodities : prix de référence/indices mensuels Banque mondiale ; simulation illustrative, sans contrat exécutable, roulement de futures, stockage, spread variable ni contraintes de liquidité. Les valeurs négatives ou nulles rendent le calcul logarithmique indisponible sur la période choisie.

Obligations : les séries actuelles sont des **taux de référence**, parfois négatifs. L’analyse HMM est retirée de cette catégorie ; son accès API est refusé avant tout calcul ou lecture du cache. Le classement utilise la moyenne des taux annualisés disponibles sur les douze mois terminant à la dernière observation souveraine du catalogue. Ce n’est pas la performance totale réalisée sur un an. Le dernier taux apparaît au-dessus du graphique ; le coupon contractuel d’une émission précise n’est pas disponible dans ces séries. [Distinction entre prix, taux et rendement](https://www.treasurydirect.gov/marketable-securities/understanding-pricing/).

## Modèle

HMM gaussien à trois états, covariance diagonale, ajustement EM par `hmmlearn`. Deux variables : variation logarithmique du prix et volatilité glissante des variations (10 observations quotidiennes, 3 mensuelles). Sur les taux : différences de niveau et volatilité de ces différences. Les moyennes et écarts-types de normalisation sont appris uniquement sur la fenêtre 1.

Trois initialisations déterministes (17, 41, 83), au plus 150 itérations, sélection de la plus grande vraisemblance **sur l’entraînement**. La convergence est vérifiée et son absence signalée. Les états sont classés par variation moyenne entraînée, sans utiliser les résultats du test. Le modèle reste figé en période 2.

Un filtre forward calcule `P(état_t | observations_1…t)`. Aucun Viterbi sur toute la fenêtre de test, aucun lissage forward-backward, aucune normalisation sur les données de test. La sélection du modèle utilise l’entraînement entier, y compris pour déterminer les états sur l’entraînement ; seuls les résultats de la période 2 sont évalués hors échantillon.

Référence : [documentation officielle hmmlearn](https://hmmlearn.readthedocs.io/en/latest/tutorial.html).

## Stratégie et exécution

Stratégie long/liquidités, capital initial 100, sans levier ni vente à découvert. Le régime porteur est celui dont la variation logarithmique moyenne entraînée est la plus élevée. Pour être utilisable, elle doit dépasser le taux sans risque par période plus le coût estimé d’un aller-retour réparti sur la détention minimale. Sinon, la stratégie reste en liquidités.

Entrée par défaut au-dessus de 65 % de probabilité porteuse ; sortie sous 35 %. Cet écart constitue l’hystérésis. Le signal doit être confirmé sur plusieurs observations. Une position est conservée au moins le nombre d’observations demandé. Un signal observé à la clôture t n’est exécuté qu’à la clôture t+1 ; le rendement entre t et t+1 reste celui de l’ancienne position. Aucune transaction n’utilise le signal du jour pour gagner le rendement de ce même jour. Au début du test, la stratégie est en liquidités et commence à construire ses confirmations avec les observations de test.

Les frais et le glissement, exprimés en points de base, s’ajoutent pour chaque transaction et réduisent le capital multiplicativement : `capital *= 1 − coût`. Un achat et une vente comptent chacun pour une transaction. Le plafond de transactions réserve une place pour clôturer une position ouverte. La dernière observation liquide toujours cette position, même si la détention minimale n’est pas atteinte. Le benchmark achète au début et vend à la fin, avec les mêmes frais d’entrée/sortie. Le taux sans risque rémunère les périodes en liquidités.

Les frais sont un modèle proportionnel constant ; fiscalité, impact de marché, frais fixes, arrondis de quantité et profondeur ne sont pas simulés.

## Indicateurs

Les indicateurs portent sur les rendements simples **nets** et sur la même fenêtre 2 pour la stratégie et le benchmark. `A` = 252 observations annuelles pour les actions, 365 pour les cryptos, 12 pour les séries mensuelles ; `rf = (1 + taux annuel)^(1/A) − 1` ; `e = rendement − rf`.

| Indicateur | Convention |
| --- | --- |
| Rendement total | Capital final / initial − 1 |
| Rendement annualisé | `(capital final / initial)^(A / N) − 1` |
| Sharpe | `moyenne(e) / écart-type(rendements, ddof=1) × √A` |
| Sortino | `moyenne(e) / √moyenne(min(e, 0)²) × √A` |
| Calmar | Rendement annualisé / drawdown maximal de toute la fenêtre de test |
| Volatilité annualisée | `écart-type(rendements, ddof=1) × √A` |
| Drawdown maximal | Plus forte baisse relative à un sommet précédent, capital initial compris ; affiché en perte positive |
| VaR 95 % historique | `max(0, −quantile_5%(rendements))` ; horizon **une observation**, jour ou mois selon la série |
| Bêta | `covariance(e_stratégie, e_marché) / variance(e_marché)` |
| Alpha annualisé | `A × moyenne(e_stratégie − bêta × e_marché)` ; annualisation arithmétique de l’intercept |

Le benchmark pour alpha/bêta est **le même actif en achat-conservation**, pas le S&P 500. Les valeurs à dénominateur nul et les valeurs non finies sont `null`, affichées « — ». Les seuils indiqués dans les infobulles sont des repères usuels, sans garantie ni test de significativité ; les métriques dépendantes de l’actif n’ont pas de seuil universel.

Les conventions s’appuient sur les définitions publiques du [projet Quantopian empyrical](https://github.com/quantopian/empyrical/blob/master/empyrical/stats.py). L’alpha et la VaR suivent les conventions explicites ci-dessus, et peuvent différer de bibliothèques utilisant une autre annualisation ou un autre signe.

## Performance et reproductibilité

NumPy/SciPy pour les calculs vectorisés, bibliothèques numériques compilées pour EM ; volatilité glissante calculée par sommes cumulées en O(N), filtre en O(N × 3²). Les pools BLAS sont limités à un thread par analyse pour éviter leur surallocation. Une seule analyse simultanée par processus API ; un second calcul reçoit HTTP 429 et peut être relancé. Pas de réentraînement lors du survol ou du zoom.

Le résultat complet est conservé dans `analysis_runs`. Sa clé SHA-256 inclut les paramètres, la version de l’algorithme, les métadonnées de l’actif et les valeurs utilisées. Une correction d’historique ou un changement de paramètre invalide donc ce cache. Les seeds et paramètres sont conservés ; de petites différences restent possibles entre versions de bibliothèques ou architectures matérielles. La documentation décrit une API locale à un processus ; plusieurs processus multiplieraient la concurrence autorisée.

La simulation ne promet pas de battre le marché. Modifier les paramètres après avoir consulté la fenêtre 2 revient à sélectionner sur ce test : utiliser ensuite une nouvelle fenêtre intacte ou une validation walk-forward avant toute conclusion de robustesse.
