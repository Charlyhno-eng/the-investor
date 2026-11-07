# Conventions du laboratoire quantitatif

## Données et périodes

Le HMM est réservé aux actions et cryptomonnaies. Matières premières et obligations restent consultables dans la vue marché ; leur analyse HMM est masquée dans l’interface et refusée par l’API, avant lecture des observations ou du cache.

Le calcul lit uniquement SQLite. L’utilisateur choisit deux fenêtres fermées, ordonnées et sans chevauchement. Une éventuelle zone entre entraînement et test sert seulement à mettre à jour le filtre, sans réentraîner le modèle ni ouvrir de position. Aucun contexte glissant ni remplissage des observations manquantes. Minimum : 100 variations pour entraîner, 20 variations pour tester ; maximum 40 000 observations au total.

Les dates réellement observées figurent dans le résultat. Une variation datée au début de la fenêtre 2 est calculée depuis la clôture précédente disponible : cette clôture est la base 100 commune du benchmark et de la stratégie. Les jours sans observation ne sont pas interpolés. Les séries très lacunaires peuvent rendre l’annualisation peu représentative.

Actions : clôtures ajustées Yahoo Finance, via `yfinance`, pour tenir compte des splits et distributions selon les ajustements du fournisseur. Crypto : clôtures quotidiennes en USD, sans rendement de staking. Commodities : prix de référence/indices mensuels Banque mondiale, consultables uniquement dans la vue marché. Les valeurs négatives ou nulles rendent le calcul logarithmique indisponible sur la période choisie.

Obligations : les séries actuelles sont des **taux de référence**, parfois négatifs. L’analyse HMM est désactivée sur cette catégorie comme sur les matières premières. Le classement utilise la moyenne des taux annualisés disponibles sur les douze mois terminant à la dernière observation souveraine du catalogue. Ce n’est pas la performance totale réalisée sur un an. Le dernier taux apparaît au-dessus du graphique ; le coupon contractuel d’une émission précise n’est pas disponible dans ces séries. [Distinction entre prix, taux et rendement](https://www.treasurydirect.gov/marketable-securities/understanding-pricing/).

## Modèle et exécution

Le [moteur actif](hmm-live.md) utilise exactement deux états sur les rendements logarithmiques seuls. L’état dont la moyenne entraînée est supérieure est appelé « haussier », l’autre « autre ». Leurs moyennes peuvent être toutes deux positives ou négatives. Trois initialisations sont comparées par vraisemblance d’entraînement ; aucun choix de modèle ne dépend des résultats du test. L’ancienne validation de un à trois états et le seuil de prévision sur cinq observations sont conservés comme archives de recherche.

Paramètres figés sur le test, filtrage causal en espace logarithmique, sans lissage. Les ordres sont exécutés à la clôture suivant le signal ; le signal précédant le test peut être exécuté à sa première clôture. Investi lorsque l’état haussier est dominant, en liquidités sinon. Les moyennes apprises décrivent des distributions, sans imposer un rendement positif ou négatif à chaque état.

Long/liquidités, capital initial 100, sans levier. Les frais sont déduits des ordres, sans bloquer les changements de régime. Même taux à chaque achat et vente, liquidation finale comprise ; benchmark avec une entrée et une sortie. Défauts : crypto 1 pb, action 50 pb, valeur explicite zéro respectée. Liquidités non rémunérées, hors fiscalité, glissement, impact et arrondis. Les autres paramètres sont refusés par l’API. Aucun stop, quota de transactions ou durée minimale de détention.

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

Le modèle utilise NumPy/SciPy et hmmlearn pour l’ajustement, une récursion forward logarithmique indépendante des noyaux privés pour le filtrage. Trois initialisations, au plus 500 itérations par ajustement, BLAS limité à un thread. Une analyse simultanée par processus ; un second calcul reçoit HTTP 429. Cache mémoire borné à huit entraînements, indexé par les seules données d’entraînement. Frais et données de test ne réajustent pas le modèle.

Le cache SQLite des résultats inclut la version du moteur, les données, les métadonnées de l’actif et les paramètres. La correction change la version et invalide les anciennes simulations sans supprimer les cours. Les empreintes du moteur et des données sont conservées avec [l’audit actif](hmm-live.md).

L’interface distingue régime dominant et position après clôture, applicable au rendement suivant. Les diagnostics exposent l’excès net face à la conservation, les expositions presque permanentes et le nombre de signaux d’entrée et de sortie. Ils n’imposent aucun ordre. Pendant un calcul, la courbe précédente reste affichée ; les changements valides sont exécutés successivement.

Les simulations ne garantissent pas la surperformance. Ajuster le modèle après consultation du test crée un biais de sélection ; toute nouvelle validation économique demande une fenêtre intacte ou une évaluation chronologique supplémentaire.

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
