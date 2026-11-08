# Performance, risque et optimisation du portfolio

L’onglet **Performance**, avant Corrélations, reprend les titres et sous-titres des
onglets du portfolio. Deux courbes comparent le portefeuille actuel et le S&P 500
sur la même période et dans la même devise (base 100 EUR). Le bouton
« Optimiser les poids » ajoute une troisième courbe et un tableau comparant les
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
explicitement « Dividendes réinvestis ». Il s’agit d’un rendement avant frais
et fiscalité, sans retenue à la source propre à l’investisseur.

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
Les variations sont quotidiennes (annualisation 252, au moins 21 variations
observées par actif). Si un actif est mensuel : derniers prix observés des mois
terminés, annualisation 12, au moins 12 variations observées par actif. Les
matières premières restent des séries de prix, sans rendement de futures inventé.

Pour une allocation constante `w`, chaque variation est `r_t @ w` ; la courbe
est `100 × produit(1 + r_t @ w)`. Les poids sont rééquilibrés à chaque observation.
Ce n’est pas l’historique réel du compte : les dates d’achat et les flux ne sont
pas connus. Frais, fiscalité et coûts de rééquilibrage ne sont pas inclus dans
cet onglet. La convention étendue peut favoriser les actifs récents ayant passé
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
Sharpe, Sortino et Calmar. L’alpha et le bêta restent calculés dans la réponse
technique mais ne sont plus affichés dans l’interface.

## Portefeuilles simulés

L’espace Stratégie permet de créer plusieurs simulations vides, de leur ajouter des actifs de la watchlist et du portfolio (actions, puis cryptomonnaies, puis autres actifs, avec accès à l’import), de définir leurs quantités et de retirer des actifs ou de supprimer une simulation. Les mêmes vues et calculs que Portfolio sont utilisés. Les simulations sont enregistrées dans le navigateur sous `investor-strategies`, indépendamment des favoris et des quantités du Portfolio.

## Cinq objectifs

Les modes conservent le même univers d’actifs et un budget de 100 %, sans levier
ni vente à découvert. Dès trois actifs détenus, chaque poids est plafonné à
35 % ; cela impose au moins trois poids non nuls dans chacun des cinq modes.
Avec un ou deux actifs, le plafond est de 100 % pour conserver un problème
réalisable. La contrainte s’applique pendant les résolutions, y compris sous la
forme `y_i ≤ 0,35 × somme(y)` pour le Sharpe, et non après coup par simple
troncature. Des positions actuelles plus concentrées restent le comparateur ;
elles ne sont pas modifiées. Un poids nul est possible. Le S&P 500
reste un comparatif. Aucun compromis ne maximise simultanément tous les critères.

1. **Équilibre** : maximiser le Sharpe historique. Si une moyenne positive est
   disponible, transformation convexe `min yᵀΣy` sous `μᵀy = 1`, `y ≥ 0`, puis
   `w = y / somme(y)`. Les moyennes sont mises à l’échelle pour le calcul.
   Pour des moyennes toutes non positives, le meilleur ratio défini se situe
   à un sommet du simplexe ; on compare aussi les poids initiaux et la solution
   de variance minimale, notamment pour le cas de variance nulle et moyenne nulle.
2. **Volatilité minimale** : minimiser `wᵀΣw` sans contrainte de rendement.
3. **Performance maximale** : maximiser la moyenne de `log(1 + r_t @ w)`, donc
   la performance composée de la période. Le rendement n’est pas remplacé par
   une moyenne arithmétique et aucune limite artificielle de volatilité n’est ajoutée.
4. **Drawdown minimal** : minimiser le drawdown composé exact. Le maximum des
   pertes logarithmiques entre tous les couples sommet/creux est convexe en `w`.
   Une épigraphe et des contraintes successives ajoutent l’intervalle réellement
   le plus défavorable jusqu’à ce que le drawdown calculé et sa borne inférieure
   coïncident à `1e-8` près. Ce n’est pas une optimisation de variance présentée
   comme une optimisation du drawdown, ni un proxy de rendements non composés.

5. **Diversification maximale** : maximiser `(w @ volatilités individuelles) / sqrt(wᵀΣw)`. La transformation homogène `y = w / (w @ volatilités)` permet une minimisation quadratique convexe sous contrainte `volatilités @ y = 1`, avec le plafond de poids appliqué avant normalisation. Ce mode utilise les volatilités et corrélations historiques et ne dépend pas des moyennes de rendement. Si toutes les volatilités sont nulles, le ratio est indéfini et l’allocation initiale admissible est conservée.

SLSQP utilise des gradients analytiques, une tolérance `1e-12`, au plus 1 500
itérations par résolution. Le mode drawdown ajoute au plus 150 contraintes
successives. Convergence, valeurs finies et somme des poids sont vérifiées ;
un échec affiche une erreur réessayable. Les résultats utilisent **le même
historique pour optimiser et évaluer** : simulation rétrospective, sans validation
hors échantillon ni prévision. Ce point est expliqué dans l’infobulle de méthode. Changer le mode, la période ou les quantités invalide
le résultat précédent.

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
- [TOBAM — ratio de diversification](https://www.tobam.fr/maximum-diversification/).
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
Sharpe gardent l’annualisation 252 séances ou 12 mois et un taux sans risque de
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
