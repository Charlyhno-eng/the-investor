# Conventions du laboratoire quantitatif

## Données et périodes

Le HMM est réservé aux actions et cryptomonnaies. Matières premières et obligations restent consultables dans la vue marché ; leur analyse HMM est masquée dans l’interface et refusée par l’API, avant lecture des observations ou du cache.

Le calcul lit uniquement SQLite. L’utilisateur choisit deux fenêtres fermées, ordonnées et sans chevauchement. Une éventuelle zone entre entraînement et test sert seulement à mettre à jour le filtre, sans réentraîner le modèle ni ouvrir de position. Les 20 premières variations établissent le contexte, sans remplissage des observations manquantes. Minimum : 100 variations valides après cette mise en place pour entraîner, 20 variations pour tester ; maximum 40 000 observations au total.

Les dates réellement observées figurent dans le résultat. Une variation datée au début de la fenêtre 2 est calculée depuis la clôture précédente disponible : cette clôture est la base 100 commune du benchmark et de la stratégie. Les jours sans observation ne sont pas interpolés. Les séries très lacunaires peuvent rendre l’annualisation peu représentative.

Actions : clôtures ajustées Yahoo Finance, via `yfinance`, pour tenir compte des splits et distributions selon les ajustements du fournisseur. Crypto : clôtures quotidiennes en USD, sans rendement de staking. Commodities : prix de référence/indices mensuels Banque mondiale, consultables uniquement dans la vue marché. Les valeurs négatives ou nulles rendent le calcul logarithmique indisponible sur la période choisie.

Obligations : les séries actuelles sont des **taux de référence**, parfois négatifs. L’analyse HMM est désactivée sur cette catégorie comme sur les matières premières. Le classement utilise la moyenne des taux annualisés disponibles sur les douze mois terminant à la dernière observation souveraine du catalogue. Ce n’est pas la performance totale réalisée sur un an. Le dernier taux apparaît au-dessus du graphique ; le coupon contractuel d’une émission précise n’est pas disponible dans ces séries. [Distinction entre prix, taux et rendement](https://www.treasurydirect.gov/marketable-securities/understanding-pricing/).

## Modèle

La [revue de recherche et les comparaisons nettes](hmm-literature.md) confirment que le moteur actif reste presque toujours investi sur de nombreux actifs et ne satisfait pas l’objectif de surperformance. Les cinq variantes étudiées séparément restent expérimentales ; aucune n’a été activée dans l’application.

L’[étude suivante sur la passivité](hmm-passivity.md) ajoute 298 backtests d’un HMM à trois états sur tendance normalisée, avec recalibration causale. Cette variante est également rejetée financièrement et reste hors API. Les diagnostics et la chronologie de l’interface ont changé, sans modification des décisions du moteur actif.

HMM gaussien directionnel à deux ou trois états, covariance complète, ajustement EM par `hmmlearn.hmm.GaussianHMM`. Les observations candidates sont le rendement logarithmique seul, ou le rendement avec sa moyenne et le logarithme de sa volatilité sur les 20 dernières variations. Ces variables sont strictement causales ; les 19 premières lignes n’ont pas de contexte et sont exclues. Aucun indicateur MACD ni règle technique externe.

La période 1 est divisée chronologiquement en 80 % d’ajustement et 20 % de validation. Pour chaque famille d’observations et nombre d’états, trois initialisations déterministes (17, 41, 83), au plus 1 000 itérations et tolérance 0,01 ; la graine est choisie par vraisemblance d’ajustement. Des covariances régularisées et un minimum d’occupation des états évitent les composantes dégénérées. Le score de validation est la log-densité prédictive du **prochain rendement**, même cible pour les deux familles ; les vraisemblances conjointes de dimensions différentes ne sont pas comparées. Ni gains de stratégie ni nombre de transactions ne participent à ce choix.

La structure retenue est réajustée sur toute la période 1 et reste figée en période 2. Moyenne et écart-type de normalisation sont appris uniquement sur les données d’ajustement correspondantes. La convergence est vérifiée et son absence signalée. Les états sont classés par rendement moyen entraîné, non par volatilité ; leur numéro brut et leur rentabilité en test ne déterminent pas leur sens. `model_selection` expose observations retenues, scores internes et nombre d’états.

Un filtre forward calcule `P(état_t | observations_1…t)`. Aucun Viterbi sur toute la fenêtre de test ni lissage forward-backward. Les probabilités dépendent des hypothèses gaussiennes et markoviennes ; le chevauchement du contexte glissant limite leur interprétation comme probabilités calibrées.

Références : [documentation officielle hmmlearn](https://hmmlearn.readthedocs.io/en/stable/api.html), [Dynamax : sélection par vraisemblance de validation](https://probml.github.io/dynamax/notebooks/hmm/gaussian_hmm.html).

## Stratégie et exécution

Stratégie long/liquidités, capital initial 100, sans levier ni vente à découvert. Le modèle évalue la valeur de continuation de chaque position à partir de ses rendements moyens, de sa matrice de transition et des frais. Les probabilités filtrées pondèrent cet avantage : achat si le gain prévu dépasse le coût du changement, vente si l’avantage de sortir dépasse ce coût, maintien autrement. Cette approximation fournit une zone d’inaction liée aux frais, sans quota d’ordres ni durée minimale de détention. [Formule et limites](hmm-directional.md).

Un signal du modèle à la clôture t s’exécute à la clôture t+1, après son rendement. L’entrée commence donc à percevoir les rendements à t+2 ; le calcul du premier rendement prévu tient compte de ces deux transitions. La dernière observation liquide toute position et ne permet aucun nouvel achat.

**Le stop de 10 % est retiré.** Aucune sortie ne dépend du drawdown, d’un prix de stop, d’une confirmation de hausse externe ou d’un verrou de réentrée. Un modèle encore favorable peut conserver une position pendant une perte importante. L’application ne lit plus les OHLC pour cette simulation et ne renvoie plus `risk_control` ; les moteurs historiques restent disponibles uniquement pour reproduire les comparaisons locales explicites.

Le seul réglage reste `fee_bps`, commun aux achats et ventes. Défauts par catégorie : crypto **1 pb = 0,01 %**, action **50 pb = 0,5 %**. Une valeur explicite, y compris zéro, est conservée ; l’API applique ces mêmes défauts si le champ est omis ou nul. Chaque ordre applique `capital *= 1 − fee_bps / 10000`. L’achat-conservation supporte aussi ses frais d’entrée et de sortie. Changer les frais peut changer les décisions, sans réentraîner ni modifier les régimes.

Les liquidités ne sont pas rémunérées. Les anciens réglages de seuils/glissement/confirmations sont refusés (422). Fiscalité, glissement, impact de marché, frais fixes, arrondis de quantité et profondeur ne sont pas simulés.

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

NumPy/SciPy pour les calculs vectorisés, bibliothèques numériques compilées pour EM ; rendements calculés en O(N), filtre en O(N × 2²), exécuté par le noyau forward compilé de `hmmlearn` (sans lissage). Le calcul utilise `scaling`, avec repli logarithmique si les probabilités deviennent trop petites. Ce noyau interne est couvert par des tests de comparaison aux probabilités de préfixes calculées par l’API publique ; sa compatibilité doit être vérifiée lors d’une mise à jour de hmmlearn. Les pools BLAS sont limités à un thread par analyse pour éviter leur surallocation. Une seule analyse simultanée par processus API ; un second calcul reçoit HTTP 429 et peut être relancé. Pas de réentraînement lors du survol ou du zoom.

L’entraînement dispose aussi d’un cache mémoire LRU borné à huit modèles par processus, indexé par les seules variables d’entraînement. Changer les frais ou les observations de test réutilise le modèle ; changer une variable d’entraînement provoque un nouvel ajustement. Les trois initialisations et les 1 000 itérations maximales sont conservées. Ce cache disparaît au redémarrage.

Avant le lancement, l’interface prévient du délai du premier calcul. Pendant la requête, elle affiche une attente indéterminée et le temps écoulé, puis un message adapté après 30 secondes. Les modifications valides sont mises en attente et les calculs sont exécutés successivement ; aucune progression chiffrée fictive n’est affichée. Une erreur permet de relancer le calcul.

Le résultat expose aussi la position réellement détenue après chaque clôture (`positions`, 0 ou 1), distincte du régime le plus probable (`regimes`). Sous les courbes de capital, deux bandes séparent le régime dominant et la position après clôture (« Investi » / « Liquidités »). La couleur des régimes distingue le signe du rendement moyen appris, sans assimiler une moyenne négative à une prévision certaine de baisse. Les segments donnent leurs dates au survol. La position après clôture s’applique au rendement suivant ; elle intègre le délai d’exécution et la liquidation finale. La matrice du HMM reste consultable dans les détails.

`diagnostics` indique notamment si une vente de régime est mathématiquement accessible : la règle est linéaire dans les probabilités, donc si aucun avantage d’état pur ne passe sous le seuil `−cost`, aucune combinaison de probabilités ne peut vendre. Le nombre d’observations en état négatif dominant et celles détenues sans signal de sortie distinguent classification et politique d’exécution. Ces observations ne sont pas des prévisions de pertes. Une exposition ≥95 % est signalée comme proche de la conservation ; ce seuil ne modifie aucun ordre. L’interface montre aussi la différence des rendements nets en **points**, et précise si la liquidation finale est la seule vente possible. Une nouvelle version de clé de cache ajoute ces diagnostics aux simulations recalculées, sans changer les capitaux ni les transactions.

L’étude du dépôt de référence, les différences de calcul et une comparaison sur les données locales figurent dans [l’audit du modèle binaire](hmm-review.md).

Le résultat complet est conservé dans `analysis_runs`. Sa clé SHA-256 inclut les paramètres, la version de l’algorithme, les métadonnées de l’actif et les valeurs utilisées. Une correction d’historique ou un changement de paramètre invalide donc ce cache. Les seeds et paramètres sont conservés ; de petites différences restent possibles entre versions de bibliothèques ou architectures matérielles. La documentation décrit une API locale à un processus ; plusieurs processus multiplieraient la concurrence autorisée.

La simulation ne promet pas de battre le marché. Modifier les paramètres après avoir consulté la fenêtre 2 revient à sélectionner sur ce test : utiliser ensuite une nouvelle fenêtre intacte ou une validation walk-forward avant toute conclusion de robustesse.


Le champ de frais est ouvert par défaut. La sélection des périodes reste disponible et la courbe comparative stratégie / achat-conservation conserve la base 100 et les frais. Les champs numériques acceptent une saisie temporairement vide ; une valeur valide actualise automatiquement le résultat après un premier lancement.

La [revue directionnelle](hmm-directional.md) décrit la politique actuelle. La [revue de réentrée](hmm-reentry.md), la [revue de risque](hmm-risk-review.md) et la [revue vidéo](hmm-video.md) concernent les versions précédentes. Les études de [rotation](hmm-turnover.md) et de [modèle directionnel](hmm-review.md) concernent les versions précédentes.

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

La valorisation du Portfolio est uniquement en euros, sans paramètre de devise ni préférence dans le navigateur. L’API utilise EUR par défaut et refuse une autre devise de valorisation. `total`, `positions[].price` et `positions[].value` sont exprimés en euros ; les anciens champs `total_usd`, `price_usd` et `value_usd` restent des valeurs intermédiaires en dollars. La conversion depuis USD divise par `EURUSD=X` à la date du cours ou au dernier jour connu antérieur, avec une ancienneté maximale de 7 jours pour couvrir les fermetures du marché des changes. Aucune valeur future n’est utilisée ; un change manquant exclut la valorisation. `fx_date` indique le jour du change. Le total, les valeurs de position et le camembert utilisent les valeurs converties. Les cours des fiches d’actifs gardent leur devise de cotation ; la matrice de corrélation conserve la base USD indiquée dans son infobulle de méthode.

Les corrélations de Pearson sont calculées sur les différences des logarithmes des prix ajustés convertis en USD, après intersection des dates de tous les actifs inclus. Ce sont les rendements, et non les niveaux de prix, qui sont corrélés. Les quantités n’affectent pas les coefficients. Si une série est mensuelle, toutes les séries sont ramenées à la dernière observation disponible par mois terminé, puis alignées sur les mois communs ; aucune donnée n’est remplie. Il faut au moins 20 rendements sur dates communes, ou 6 rendements entre mois communs. Une dispersion nulle ou un échantillon insuffisant donne une cellule absente (`null`, affichée « — »). Les valeurs sont bornées à [-1, 1] pour absorber les arrondis numériques. Les durées proposées sont 1, 3, 5 et 10 ans à partir de la date courante.

Référence : [NumPy, coefficient de corrélation de Pearson](https://numpy.org/doc/2.2/reference/generated/numpy.corrcoef.html).
