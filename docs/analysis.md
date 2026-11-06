# Conventions du laboratoire quantitatif

## Données et périodes

Le HMM est réservé aux actions et cryptomonnaies. Matières premières et obligations restent consultables dans la vue marché ; leur analyse HMM est masquée dans l’interface et refusée par l’API, avant lecture des observations ou du cache.

Le calcul lit uniquement SQLite. L’utilisateur choisit deux fenêtres fermées, ordonnées et sans chevauchement. Une éventuelle zone entre entraînement et test sert seulement à mettre à jour le filtre, sans réentraîner le modèle ni ouvrir de position. Les premières observations de la fenêtre 1 initialisent le momentum glissant et sont exclues de l’ajustement. Minimum : 100 variations après initialisation pour entraîner, 20 variations pour tester ; maximum 40 000 observations au total.

Les dates réellement observées figurent dans le résultat. Une variation datée au début de la fenêtre 2 est calculée depuis la clôture précédente disponible : cette clôture est la base 100 commune du benchmark et de la stratégie. Les jours sans observation ne sont pas interpolés. Les séries très lacunaires peuvent rendre l’annualisation peu représentative.

Actions : clôtures ajustées Yahoo Finance, via `yfinance`, pour tenir compte des splits et distributions selon les ajustements du fournisseur. Crypto : clôtures quotidiennes en USD, sans rendement de staking. Commodities : prix de référence/indices mensuels Banque mondiale, consultables uniquement dans la vue marché. Les valeurs négatives ou nulles rendent le calcul logarithmique indisponible sur la période choisie.

Obligations : les séries actuelles sont des **taux de référence**, parfois négatifs. L’analyse HMM est désactivée sur cette catégorie comme sur les matières premières. Le classement utilise la moyenne des taux annualisés disponibles sur les douze mois terminant à la dernière observation souveraine du catalogue. Ce n’est pas la performance totale réalisée sur un an. Le dernier taux apparaît au-dessus du graphique ; le coupon contractuel d’une émission précise n’est pas disponible dans ces séries. [Distinction entre prix, taux et rendement](https://www.treasurydirect.gov/marketable-securities/understanding-pricing/).

## Modèle

HMM gaussien à deux états, covariance diagonale, ajustement EM par `hmmlearn.hmm.GaussianHMM`. Deux variables : variation logarithmique du prix et momentum cumulé sur les dernières observations (10 quotidiennes, 3 mensuelles). Le momentum est `log(prix_t / prix_{t-fenêtre})` et utilise uniquement les clôtures disponibles à t. Sur les taux : différences de niveau et cumul glissant de ces différences. Les moyennes et écarts-types de normalisation sont appris uniquement sur la fenêtre 1.

Trois initialisations déterministes (17, 41, 83), au plus 150 itérations, sélection de la plus grande vraisemblance **sur l’entraînement**. La convergence est vérifiée et son absence signalée. Les états sont classés par variation moyenne entraînée, sans utiliser les résultats du test. Le modèle reste figé en période 2. Les régimes sont nommés « Neutre / baisse » et « Hausse », par ordre de variation moyenne entraînée. Ces noms décrivent un classement estimé : un HMM non supervisé ne garantit pas que le premier régime ait une moyenne négative, ni que le second prédise toute hausse.

Un filtre forward calcule `P(état_t | observations_1…t)`. Aucun Viterbi sur toute la fenêtre de test, aucun lissage forward-backward, aucune normalisation sur les données de test. La sélection du modèle utilise l’entraînement entier, y compris pour déterminer les états sur l’entraînement ; seuls les résultats de la période 2 sont évalués hors échantillon.

Référence : [documentation officielle hmmlearn](https://hmmlearn.readthedocs.io/en/latest/tutorial.html).

## Stratégie et exécution

Stratégie long/liquidités, capital initial 100, sans levier ni vente à découvert. Le régime de hausse est celui dont la variation logarithmique moyenne entraînée est la plus élevée. Pour être utilisable, elle doit dépasser le taux sans risque par période. Sinon, la stratégie reste en liquidités.

Entrée par défaut au-dessus de 80 % de probabilité porteuse ; sortie sous 50 %. Cet écart constitue l’hystérésis. Par défaut, les achats demandent cinq signaux consécutifs et les ventes trois. Ces deux paramètres sont ajustables indépendamment (`entry_confirmation` et `exit_confirmation`, de 1 à 30 observations). Une interruption du signal remet la confirmation en cours à zéro. Aucune détention minimale n’est imposée par défaut, et le momentum doit être strictement positif pour ouvrir une position. Un passage négatif isolé ne force plus la vente : la sortie dépend du seuil de probabilité et de sa confirmation. Un signal observé à la clôture t n’est exécuté qu’à la clôture t+1 ; le rendement entre t et t+1 reste celui de l’ancienne position. Aucune transaction n’utilise le signal du jour pour gagner le rendement de ce même jour. Au début du test, la stratégie est en liquidités et commence à construire ses confirmations avec les observations de test.

L’interface affiche les frais en pourcentage (0,1 % par défaut, soit 10 pb) et les convertit en points de base pour l’API. Le glissement est nul par défaut et n’est plus réglable dans l’interface. Dans l’API, les frais et le glissement, exprimés en points de base, s’ajoutent pour chaque transaction et réduisent le capital multiplicativement : `capital *= 1 − coût`. Un achat et une vente comptent chacun pour une transaction. Aucun plafond de transactions par défaut ; si un client API en demande un, une place est réservée pour clôturer une position ouverte. La dernière observation liquide toujours cette position, même si la détention minimale n’est pas atteinte. Le benchmark achète au début et vend à la fin, avec les mêmes frais d’entrée/sortie. Le taux sans risque rémunère les périodes en liquidités.

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

NumPy/SciPy pour les calculs vectorisés, bibliothèques numériques compilées pour EM ; momentum glissant calculé par sommes cumulées en O(N), filtre en O(N × 2²), exécuté par le noyau forward compilé de `hmmlearn` (sans lissage). Le calcul utilise `scaling`, avec repli logarithmique si les probabilités deviennent trop petites. Ce noyau interne est couvert par des tests de comparaison aux probabilités de préfixes calculées par l’API publique ; sa compatibilité doit être vérifiée lors d’une mise à jour de hmmlearn. Les pools BLAS sont limités à un thread par analyse pour éviter leur surallocation. Une seule analyse simultanée par processus API ; un second calcul reçoit HTTP 429 et peut être relancé. Pas de réentraînement lors du survol ou du zoom.

L’entraînement dispose aussi d’un cache mémoire LRU borné à huit modèles par processus, indexé par les seules variables d’entraînement. Changer les frais, les seuils ou les observations de test réutilise le modèle ; changer une variable d’entraînement provoque un nouvel ajustement. Les trois initialisations et les 150 itérations maximales sont conservées. Ce cache disparaît au redémarrage.

Avant le lancement, l’interface prévient du délai du premier calcul. Pendant la requête, elle affiche une attente indéterminée et le temps écoulé, puis un message adapté après 30 secondes. Les périodes et paramètres sont verrouillés jusqu’à la réponse ; aucune progression chiffrée fictive n’est affichée. Une erreur permet de relancer le calcul.

Le résultat expose aussi la position réellement détenue après chaque clôture (`positions`, 0 ou 1), distincte du régime le plus probable (`regimes`). La chronologie principale affiche « Achat » pour une position détenue et « Pas achat » pour les liquidités ; elle intègre les règles d’exécution et la liquidation finale. La matrice du HMM reste consultable dans les détails.

L’étude du dépôt de référence, les différences de calcul et une comparaison sur les données locales figurent dans [l’audit du modèle binaire](hmm-review.md).

Le résultat complet est conservé dans `analysis_runs`. Sa clé SHA-256 inclut les paramètres, la version de l’algorithme, les métadonnées de l’actif et les valeurs utilisées. Une correction d’historique ou un changement de paramètre invalide donc ce cache. Les seeds et paramètres sont conservés ; de petites différences restent possibles entre versions de bibliothèques ou architectures matérielles. La documentation décrit une API locale à un processus ; plusieurs processus multiplieraient la concurrence autorisée.

La simulation ne promet pas de battre le marché. Modifier les paramètres après avoir consulté la fenêtre 2 revient à sélectionner sur ce test : utiliser ensuite une nouvelle fenêtre intacte ou une validation walk-forward avant toute conclusion de robustesse.


Les paramètres visibles sont ouverts par défaut : frais par ordre en pourcentage et seuils d’entrée/sortie. Deux champs distincts permettent de régler les confirmations à l’achat (5 par défaut) et à la vente (3 par défaut). Détention minimale, plafond d’ordres et taux sans risque restent compatibles avec les clients API, mais ne sont plus proposés dans l’interface. Celle-ci fixe respectivement 1 observation, aucun plafond et 0 %. Une courbe interactive permet de sélectionner les périodes d’entraînement et de test ; les résultats HMM affichent les chiffres et une courbe comparative stratégie / achat-conservation, sur le même actif, en base 100 et frais inclus ; la vue marché affiche uniquement le graphique et ses contrôles.

La revue du nombre d’ordres et des frais est détaillée dans [le comparatif de rotation](hmm-turnover.md). Les champs numériques acceptent une saisie temporairement vide ; une valeur valide est enregistrée à la sortie du champ, sinon la précédente est conservée.

## Régression et retour à la tendance

L’onglet **Régression**, avant HMM pour les actions et cryptomonnaies, ajuste les prix locaux sur une période choisie (cinq dernières années par défaut, minimum 30 observations). Le calcul s’effectue dans le navigateur. Les moindres carrés ajustent une constante et une pente au temps calendaire, avec le même poids pour chaque observation. Le logarithme du prix est utilisé par défaut pour représenter une croissance composée ; le mode prix linéaire reste disponible.

Les prix sous la tendance sont des zones d’entrée potentielles, ceux au-dessus des zones de vente potentielles. Un seuil réglable de 0 à 2 écarts-types des résidus (2 par défaut) laisse éventuellement une zone neutre. La dispersion est calculée avec `sqrt(SSE / (n − 2))` dans l’échelle choisie ; le score normalisé et les seuils s’adaptent donc à chaque actif. Les bandes sont descriptives, sans probabilité de couverture annoncée. Une dispersion quasi nulle désactive la classification. Prix non positifs ou non finis et périodes trop courtes sont refusés.

Le diagnostic affiche le R², la pente annuelle, la valeur ajustée et l’écart du dernier cours. Une tendance non croissante, un R² inférieur à 0,5 ou un changement de signe des pentes ajustées séparément sur les deux moitiés de la période sont signalés. Ces repères ne constituent ni un test de stationnarité ni une validation de rentabilité. En mode linéaire, la pente annuelle en pourcentage est rapportée au premier prix ; en mode logarithmique, elle vaut `exp(pente annuelle) − 1`.

Toute la fenêtre est utilisée pour ajuster la droite : les zones historiques changent lorsque la fenêtre change. Cette vue n’est pas un backtest, ne simule ni ordres ni frais et ne démontre pas la réversion à la moyenne. Référence : [NIST, moindres carrés et erreur résiduelle](https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd431.htm).

Une infobulle près du curseur sur la courbe de régression affiche le prix, la tendance à la même date et leur écart en pourcentage : `100 × (prix / tendance − 1)`.


## Comparaison de marché au S&P 500

La comparaison de la vue marché utilise par défaut les prix hors dividendes et l’indice S&P 500 `^GSPC`. Le bouton « Dividendes réinvestis » sélectionne les prix ajustés des actions et l’indice de rendement total `^SP500TR`, incluant le réinvestissement des dividendes du S&P 500. Les clôtures hors dividendes sont conservées séparément dans `price_observations` lors des imports Yahoo ; une ancienne action sans ces données est réimportée par la queue. Le paramètre API `reinvest` sélectionne le mode (défaut API historique : `true`, l’interface envoie explicitement le choix). Les observations des actions sont déjà des clôtures ajustées pour les distributions et divisions : elles sont normalisées directement, sans ajouter à nouveau les dividendes enregistrés. La comparaison ne prélève ni frais ni impôt.

La durée choisie (1, 5, 10 ans ou tout) est bornée par les dates communes à l’actif, l’indice et, si nécessaire, au change. Les valeurs sont ramenées à 100 à la première date commune. Les jours sans donnée commune sont omis, sans interpolation, y compris les week-ends des cryptos. Les débuts et fins effectifs sont affichés. La référence Yahoo commence en 1988 ; le change peut limiter davantage l’historique. Les clôtures quotidiennes des différents marchés ne sont pas nécessairement simultanées.

Les comparaisons sont en USD. Une action en devise locale est convertie à chaque date via le cours `DEVUSD=X` (les prix en GBp sont d’abord divisés par 100). Les cryptos du catalogue sont en USD. Pour les matières premières Banque mondiale, on compare la variation de prix ou d’indice, sans rendement de roulement des futures ; les dates mensuelles absentes de l’indice ne sont pas interpolées. Une série de taux obligataires ne mesure pas une performance totale et est donc exclue. Les séries avec prix non positifs ou moins de deux dates communes sont refusées.

Le serveur lit les références dans SQLite. Si elles sont absentes ou datent de plus d’un jour, il place leur téléchargement dans la queue existante ; l’interface attend la fin de l’import puis lit la comparaison. Les échecs fournisseur sont affichés, avec un délai de cinq minutes avant une nouvelle tentative. Les références restent hors de la bibliothèque d’actifs.

Références : [S&P, méthodologie des indices de rendement total](https://www.spglobal.com/spdji/en/documents/methodologies/methodology-index-math.pdf), [Yahoo Finance, historique du S&P 500 Total Return](https://finance.yahoo.com/quote/%5ESP500TR/history/).


## Quantités, répartition et corrélations du Portfolio

Les quantités actuelles, positives ou nulles et éventuellement fractionnaires, sont stockées dans `investor-quantities` dans le navigateur. Elles sont indépendantes de l’étoile : une position déplacée en watchlist cesse d’être incluse, mais sa quantité est conservée si elle revient dans Portfolio. Une quantité nulle n’entre ni dans le total ni dans la matrice. Aucun prix d’achat, historique d’ordres ou gain personnel n’est déduit de ces quantités ; les divisions d’actions ne les modifient pas automatiquement.

Le serveur reçoit les positions par `POST /api/portfolio/analytics`, sans les enregistrer. La valeur est quantité × dernier prix coté disponible × taux de conversion en USD à la même date. Pour les actions, le dernier prix hors ajustement de dividendes est utilisé ; les prix en GBp sont convertis en GBP. Chaque position indique sa date de prix : le total peut donc agréger des cours de dates différentes. Une devise sans cours à la date du prix, un prix absent ou un indice sans valeur monétaire par unité est exclu de la valorisation avec une explication. Les indices de matières premières peuvent néanmoins participer aux corrélations. Les taux souverains sont exclus des deux calculs. Les matières premières sont des positions théoriques dans l’unité cotée, sans coûts de détention ou roulement ; les cours exprimés en cents sont convertis en dollars pour la valeur.

Les corrélations de Pearson sont calculées sur les différences des logarithmes des prix ajustés convertis en USD, après intersection des dates de tous les actifs inclus. Ce sont les rendements, et non les niveaux de prix, qui sont corrélés. Les quantités n’affectent pas les coefficients. Si une série est mensuelle, toutes les séries sont ramenées à la dernière observation disponible par mois terminé, puis alignées sur les mois communs ; aucune donnée n’est remplie. Il faut au moins 20 rendements sur dates communes, ou 6 rendements entre mois communs. Une dispersion nulle ou un échantillon insuffisant donne une cellule absente (`null`, affichée « — »). Les valeurs sont bornées à [-1, 1] pour absorber les arrondis numériques. Les durées proposées sont 1, 3, 5 et 10 ans à partir de la date courante.

Référence : [NumPy, coefficient de corrélation de Pearson](https://numpy.org/doc/2.2/reference/generated/numpy.corrcoef.html).
