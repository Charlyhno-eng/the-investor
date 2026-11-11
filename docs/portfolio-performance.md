# Performance, risque et optimisation du portfolio

L’onglet **Performance**, avant Corrélations, reprend les titres et sous-titres des
onglets du portfolio. Deux courbes comparent le portefeuille actuel et le S&P 500
sur la même période et dans la même devise (base 100 EUR). Le bouton
« Optimiser les poids » ajoute une courbe (cinq pour les bêtas cibles) et un tableau comparant les
poids et quantités actuels aux poids et quantités indicatives. Aucune position
ni quantité enregistrée n’est modifiée.

## Historiques et actifs récents

Les pondérations actuelles proviennent des valeurs réelles de l’onglet Positions.
Les séries utilisent les observations historiques, les prix ajustés pour les
actions (colonne Yahoo `Adj Close`, dividendes réinvestis et divisions
d’actions ajustées), le S&P 500 total return (`^SP500TR`) et le change connu à chaque date
(maximum sept jours d’ancienneté), via les mêmes fonctions que les frontières
d’efficience. Une position non valorisable bloque la comparaison complète avec
une raison explicite. Aucun sous-ensemble n’est silencieusement renormalisé.

Le réinvestissement s’applique à toutes les courbes de comparaison, dans le
Portfolio et les simulations de l’espace Stratégie, ainsi qu’aux cinq objectifs
d’optimisation. Les distributions figurant dans la table `dividends` ne sont
pas ajoutées aux rendements ajustés : elles y sont déjà prises en compte.
Les quantités et poids actuels restent valorisés aux cours non ajustés, et
ne sont pas augmentés par la simulation. La légende sous la courbe affiche
explicitement « Dividendes réinvestis ». Les allocations à poids constants sont avant frais et fiscalité. L’équipondération annuelle inclut les frais choisis, sans fiscalité.

Deux conventions sont disponibles :

- **Étendu · liquidités avant cotation** (par défaut dans l’interface) : la
  période peut remonter avant le premier prix d’un actif récent. La fraction
  affectée à cet actif reste en liquidités non rémunérées jusqu’à sa première
  observation. Le premier rendement d’actif commence entre ses deux premiers
  prix observés.
  Aucun prix ni rendement d’actif n’est inventé. Les données manquantes après
  l’apparition d’un actif sont exclues des dates, jamais remplacées par des
  rendements nuls. Les deux allocations suivent la même convention.
- **Dates communes uniquement** : l’actif le plus récent réduit la période.
  L’interface explique cette limitation si elle raccourcit la période demandée.

Les données se terminent à la dernière date exploitable par toutes les séries.
Les variations sont exclusivement quotidiennes : au moins 21 variations
observées par actif, annualisation de la volatilité et des ratios sur 252 séances.
Toutes les observations communes sont conservées pour les courbes, les métriques
et les cinq objectifs, y compris la dernière séance disponible et les variations
à l’intérieur d’un mois. Un actif mensuel bloque la comparaison complète avec
son nom et une demande d’historique journalier ; il n’entraîne plus de regroupement
mensuel du portefeuille. Aucun cours quotidien n’est interpolé depuis les sources
mensuelles. Les matières premières restent des séries de prix, sans rendement de futures inventé.

Pour une allocation constante `w`, chaque variation est `r_t @ w` ; la courbe
est `100 × produit(1 + r_t @ w)`. Les poids sont rééquilibrés à chaque observation.
Ce n’est pas l’historique réel du compte : les dates d’achat et les flux ne sont
pas connus. Seule l’équipondération annuelle inclut les frais de transaction. La convention étendue peut favoriser les actifs récents ayant passé
une partie de la période en liquidités ; le mode dates communes permet une
comparaison sur leur historique conjoint effectif.

## Indicateurs

Chaque courbe affiche rendement cumulé, volatilité annualisée, drawdown maximal
et ratio de Sharpe. Le drawdown est `min(capital / sommet_cumulé − 1)`, capital
initial inclus. Sharpe = moyenne des variations simples / écart-type empirique
(`ddof=1`) × racine de l’annualisation. Le taux de référence est fixé explicitement
à **0 %** ; ce n’est pas une série de taux sans risque observés. Avec une
volatilité quasi nulle, le ratio est indisponible (`null`, affiché « — »).

Le tableau pliable affiche CAGR, volatilité annualisée, drawdown maximal,
Sharpe, Sortino, Calmar et bêta. Le bêta du S&P 500 est fixé à 1 ; les autres sont mesurés par régression sur les rendements du S&P 500 en EUR. Le bêta reste neutre dans les couleurs de comparaison : plus élevé ne signifie pas meilleur. Chaque indicateur possède un petit « ? » accessible au survol, au clavier et au toucher, avec une définition simple sans formule. L’alpha reste disponible dans l’API.

## Portefeuilles simulés

L’espace Stratégie permet de créer plusieurs simulations vides, de leur ajouter des actifs de la watchlist et du portfolio (actions, puis cryptomonnaies, puis autres actifs, avec accès à l’import), de définir leurs quantités et de retirer des actifs ou de supprimer une simulation. Les mêmes vues et calculs que Portfolio sont utilisés. Les simulations sont enregistrées dans le navigateur sous `investor-strategies`, indépendamment des favoris et des quantités du Portfolio.

## Cinq objectifs

Les modes partent des actifs détenus et valorisés du portefeuille ou de la
simulation. Une position à quantité nulle n’est pas ajoutée à cet univers.
Les objectifs de ratios imposent (l’équipondération conserve tous les actifs sans seuil de 3 % / 35 %) :

- budget de 100 %, sans levier ni vente à découvert ;
- au moins `ceil(n / 2)` positions parmi les `n` actifs disponibles ;
- poids de chaque position soit nul, soit **au moins 3 %** ;
- poids plafonné à **35 %** dès trois actifs disponibles (100 % pour un ou deux).

Le plafond peut imposer davantage de positions que la moitié. Les positions de
l’allocation actuelle restent le comparateur, même si elles ne respectent pas
ces limites ; aucune quantité enregistrée n’est modifiée. Le minimum de 3 %
limite à 33 positions retenues : à partir de 67 actifs disponibles, la règle de
la moitié devient impossible et une erreur explicite est retournée.

1. **Équipondération annuelle** (`equal`, défaut) : tous les actifs ont le même poids initial. Les poids dérivent entre deux rééquilibrages, au premier jour observé à partir de chaque anniversaire du début de simulation. Les frais par achat et vente sont réglables de 0 à 10 %, avec **0,5 %** par défaut. Ils portent sur chaque montant effectivement acheté ou vendu, achat initial inclus. Le capital net réinvesti tient compte des deux côtés des transactions, sans vente finale fictive. Les liquidités réservées avant cotation ne supportent les frais d’achat qu’à l’entrée effective de l’actif. Des quantités verrouillées incompatibles empêchent l’équipondération.
2. **Sortino maximal** (`sortino`) : rendement moyen rapporté au risque de baisse sous 0 %, sans pénaliser la volatilité à la hausse.
3. **Volatilité à la baisse minimale** (`downside`) : minimiser la moyenne des carrés des rendements négatifs du portefeuille, sous une cible de 0 %. Les rendements positifs contribuent zéro et ne sont pas pénalisés. Cet objectif minimise le risque de baisse seul, tandis que Sortino maximise un ratio rendement / risque de baisse. Le tableau affiche aussi cette volatilité à la baisse, annualisée sur 252 séances.
4. **Drawdown minimal** (`drawdown`) : minimiser la plus forte baisse composée entre un sommet et un creux, capital initial inclus.
5. **Sharpe à bêta cible** (`beta_sharpe`) : cinq optimisations indépendantes pour des bêtas de **0,3, 0,4, 0,5, 0,6 et 0,7**. Chaque cible est une contrainte d’égalité, vérifiée à 1e-7. Les cinq courbes, colonnes d’indicateurs et répartitions sont affichées simultanément. Chaque cible non obtenue a son propre message ; les autres résultats et les comparateurs restent disponibles. Aucun levier ni actif supplémentaire n’est ajouté pour atteindre une cible.

Pour un rendement moyen positif réalisable, Sortino et Sharpe à bêta cible utilisent une transformation homogène : minimiser le risque au carré sous un rendement normalisé fixé à 1. Ce problème convexe, résolu avec des gradients analytiques, évite les divisions par un risque quasi nul et conserve les bornes, les verrous et le bêta cible. Les égalités redondantes après verrouillage sont supprimées ; une allocation entièrement déterminée par les contraintes est retournée directement. Pour les rendements non positifs et pour Calmar, SLSQP utilise plusieurs points de départ, sans garantie d’optimum global. Le Sharpe positif libre conserve aussi sa transformation homogène. Les anciens modes (`balanced`, `sharpe`, `calmar`, `volatility`, `performance`, `correlation`) restent acceptés par l’API pour compatibilité, mais ne sont plus proposés dans l’interface.

Les contraintes de cardinalité et de plancher rendent le choix des positions
discret ([formulation avec variables de sélection](https://docs.mosek.com/MOSEKPortfolioCookbook/transaction.html)).
Pour huit actifs ou moins, tous les sous-ensembles réalisables sont examinés.
Au-delà, la sélection est **approchée et déterministe** : solutions sur des
sous-ensembles classés selon la solution relâchée et les poids actuels, puis
échanges bornés de positions autour de la meilleure solution. Il n’y a pas de
garantie d’optimum global pour cette sélection. Chaque sous-ensemble impose le
plancher de 3 % et le plafond dans le solveur, jamais par ajout de petites lignes
après calcul. Les sous-ensembles qui échouent à converger sont ignorés ; s’il
n’en reste aucun, une erreur est retournée. Somme, finitude, nombre de positions,
plancher et plafond sont vérifiés avant de retourner une allocation.

Les résultats utilisent **le même historique pour optimiser et évaluer** :
simulation rétrospective, sans prévision. Changer le mode, la période ou les
quantités invalide le résultat précédent.

Les quantités indicatives sont `valeur_totale_actuelle × poids / dernier_prix_EUR`.
La date du cours figure dans la cellule et dans Positions ; les fractions sont
permises pour ce calcul indicatif.

## Régression dans Positions

`POST /api/portfolio/regression` calcule en lot le dernier résidu normalisé d’une
régression logarithmique sur les cinq dernières années disponibles, ancrées sur
la dernière observation de chaque actif. C’est le même ajustement que l’onglet
Régression par défaut : temps calendaire, OLS, écart-type résiduel avec `n − 2`
degrés de liberté, au moins 30 prix positifs finis. L’historique réellement utilisé
figure au survol. Données insuffisantes ou dispersion quasi nulle : « — ».

La teinte passe continûment du vert (écart négatif) au jaune (zéro), puis au rouge
(écart positif), avec saturation à ± 1,5 σ. Il s’agit d’un repère descriptif,
indépendant de la quantité détenue et de la période de corrélation choisie.

## Frais et exposition dans Régression

La simulation des bandes propose un seul réglage de frais, identique à l’achat
et à la vente, à **0,10 %** par défaut. Discret à droite du résumé, derrière une
séparation verticale, il est ajustable par pas de 0,01 point de pourcentage ou par saisie
avec deux décimales (virgule ou point ; 0,00 accepté). Ils sont appliqués au montant
exécuté : achat `unités = liquidités / (prix × (1 + frais_achat))`, vente
`liquidités = unités × prix × (1 − frais_vente)`. L’achat-conservation subit le même
frais d’achat initial. Les positions ouvertes sont valorisées au dernier prix,
sans frais de vente fictifs à la fin. Les liquidités ne rapportent rien.

La quatrième case affiche la durée d’exposition : somme des durées calendaires
entre observations pendant lesquelles la stratégie reste investie, divisée par
la durée totale. L’état après le signal s’applique à l’intervalle suivant ; un
achat à la dernière observation ne crée aucune durée d’exposition passée. Le
long paragraphe sous le graphique a été retiré ; la méthode reste dans
« Comprendre l’ajustement ».

## Références et vérification

- [MOSEK — Markowitz et ratio rendement/risque](https://docs.mosek.com/portfolio-cookbook/markowitz.html).
- [Norges Bank — régressions et alpha de Jensen](https://www.nbim.no/contentassets/fdd69abfff8445cc967c30322b2d3968/factor-and-risk-adjusted-return_2024.pdf).
- [MOSEK — cardinalité et planchers de position](https://docs.mosek.com/MOSEKPortfolioCookbook/transaction.html).
- [SciPy — SLSQP](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-slsqp.html).

`backend/tests/test_performance.py` confronte les cinq objectifs à une recherche
dense indépendante à deux actifs, puis vérifie les courbes, les quantités, les
indicateurs, les historiques courts, les dates manquantes et la réservation en
liquidités. `backend/tests/test_portfolio_regression.py` confronte l’écart normalisé
à un ajustement indépendant sur les log-prix. Les tests Playwright couvrent les
modes, le changement d’historique, les teintes, les frais, l’exposition, les
survols et le toucher sur ordinateur et mobile, sans modifier les quantités.

Les cartes de comparaison n’affichent plus le capital final. Le seuil propose
0 ; 0,5 ; 1 ; 1,2 ; 1,4 ; 1,6 ; 1,8 ; 2 σ, avec 1,5 σ conservé comme défaut
antérieur. L’infobulle de la colonne de régression dans Positions utilise un
portail vers le document et une position fixe bornée à l’écran : le conteneur
défilant du tableau ne peut plus la découper ni la placer sous le contenu voisin.

Le tableau sous les rendements cumulés compare le S&P 500, l’allocation actuelle
et celle du mode optimisé sélectionné. CAGR, Sharpe, Sortino et Calmar sont
favorables lorsqu’ils sont supérieurs au benchmark ; volatilité et amplitude
positive du drawdown lorsqu’elles sont inférieures. Traits verts : meilleur,
rouges : moins bon, gris : égalité ou comparaison indisponible. Les statuts sont
aussi disponibles aux lecteurs d’écran. L’allocation optimisée reste vide avant
calcul et lors d’un changement de mode.

Le CAGR utilise la durée calendaire réelle (jours / 365,25). La volatilité et le
Sharpe gardent l’annualisation 252 séances et un taux sans risque de
0 %. Le Sortino utilise une cible de 0 % et la racine de la moyenne des carrés
des rendements négatifs, les rendements positifs contribuant zéro sur l’ensemble
des observations ([convention de downside deviation décrite par le CFA Institute](https://rpc.cfainstitute.org/-/media/documents/code/gips/the-sortino-ratio.pdf)).
Calmar = CAGR / amplitude du drawdown maximal. Les ratios dont le dénominateur
est nul sont indéfinis et affichés « — ».

Un test de régression vérifie deux détachements avec réinvestissement en parts
supplémentaires, calculé indépendamment dans un registre de parts. Il confronte
les courbes actuelle et optimisée à ce registre pour les cinq objectifs et les
deux conventions d’historique, avec baisse des cours bruts aux détachements et
absence de double comptage des distributions.

Dans les indicateurs, la stratégie de base porte un trait comparé au S&P 500.
L’allocation optimisée porte deux traits indépendants : le premier comparé au
S&P 500, le second à la stratégie de base. Chaque trait est vert si meilleur,
rouge si moins bon, gris si égal ou indisponible. Les métriques de risque
inversent le sens de comparaison ; le drawdown est comparé en amplitude.
Le survol et les libellés accessibles précisent chaque référence.

Le bandeau de composition d’une stratégie et les pastilles de retrait d’actifs
s’affichent uniquement dans Positions. Les autres onglets conservent l’en-tête
et les vues partagées avec le Portfolio, sans les contrôles de composition.

Dans une stratégie, le cadenas de chaque ligne de Positions conserve exactement sa quantité dans les cinq objectifs d’optimisation. Il désactive la saisie et le retrait jusqu’au déverrouillage. Les cadenas sont enregistrés avec la stratégie dans le navigateur ; les stratégies existantes sont lues sans cadenas par défaut. L’API reçoit `locked_asset_ids` et fixe le poids courant correspondant, à budget et prix de valorisation constants ; la quantité indicative retournée est exactement la quantité initiale. Les bornes de 3 % / 35 % s’appliquent aux positions libres, les positions verrouillées sont prioritaires. La cardinalité minimale reste applicable. Des contraintes incompatibles produisent une erreur explicite, sans modifier un verrou. Lorsque toutes les positions sont verrouillées, l’allocation reste identique.

Les frontières d’efficience utilisent aussi les poids fixes : chaque allocation admissible conserve les positions verrouillées, et seul le budget restant est réparti. Tous les actifs verrouillés réduisent la frontière au point du portefeuille. Les courbes des objectifs de ratios conservent leur convention de pondérations constantes rééquilibrées ; le cadenas fixe les quantités recommandées aux cours de valorisation, pas un historique de transactions. L’équipondération annuelle exige de déverrouiller toute quantité incompatible avec des poids égaux.

Les nouveaux calculs sont couverts par `backend/tests/unit/test_new_allocations.py` : recherche dense indépendante pour les trois ratios, frais d’achat et vente, dérive et rééquilibrage annuel, bêtas exacts et objectifs inaccessibles. Chaque poids recommandé des cinq bêtas porte les mêmes flèches de renforcement, allègement, sortie ou conservation que les autres répartitions, avec la même légende. Les tests navigateur `frontend/tests/e2e/performance.spec.ts` couvrent aussi les cinq courbes, les colonnes, les définitions et le réglage des frais sur ordinateur et mobile.

## Chargement de Positions et comparaison individuelle

L’interface demande `include_correlation=false` à l’ouverture : seuls les derniers
prix non ajustés et les changes nécessaires à leur valorisation sont lus. Le
S&P 500, les historiques ajustés et la matrice de corrélation ne sont demandés
qu’à l’ouverture de Corrélations. L’API conserve `include_correlation=true` par
défaut pour ses clients existants ; en mode valorisation seule, `correlation`
vaut `null`. Les calculs de performance, de frontières et de prédiction utilisent
aussi cette valorisation légère avant de charger leurs propres historiques.
Les historiques de corrélation sont filtrés dans SQLite sur la période choisie,
et chaque historique de change n’est chargé qu’une fois par requête.

Un change déjà archivé reste utilisable pendant son actualisation en arrière-plan,
y compris après un échec du fournisseur. La file conserve sa déduplication et son
délai de cinq minutes après échec. La règle de fraîcheur du taux appliqué au prix
reste inchangée : date exacte pour convertir le prix en USD, dernier taux EUR
connu dans les sept jours précédents pour afficher sa valeur en euros. Une
référence absente attend toujours son import. Le délai initial de 450 ms côté
interface est supprimé.

Mesure indicative sur une copie de la base locale (53 actions, ETF et cryptos,
quantité unitaire, références déjà présentes, médiane de quatre appels directs) :
427 ms avant contre 1,5 ms en valorisation seule. Cela ne mesure ni le réseau ni
le rendu du navigateur ; les premiers imports restent dépendants du fournisseur.

Dans chaque fiche action, crypto, ETF ou matière première, « Comparer au S&P 500 »
affiche les huit mêmes indicateurs que Portfolio, avec uniquement les colonnes
S&P 500 et nom de l’actif. Les métriques sont calculées sur les dates communes
exactes de la courbe sélectionnée, dans la même devise USD. Les dividendes sont
réinvestis pour les actions et ETF. Le CAGR utilise les jours calendaires ;
les autres mesures sont annualisées sur 252 séances (12 pour une série mensuelle).
Les cryptos utilisent ici les dates communes avec le marché, pas les 365 jours
cryptos. Les ratios indéfinis sont affichés « — » ; une seule variation ne permet
pas d’estimer la volatilité empirique, le Sharpe ou le bêta de l’actif.
Les matières premières restent des comparaisons de prix, sans rendement de
roulement inventé. Calculs et infobulles sont partagés avec le tableau Portfolio.
