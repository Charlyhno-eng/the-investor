# Validation chronologique des allocations

Dans **Portfolio**, ou **Stratégie → sélectionner une stratégie**, ouvrir directement **Volatilité minimale**, **Retour à la moyenne**, **Corrélation minimale** ou **Parité de risque**, choisir une durée de validation, un capital initial (10 000 € par défaut) et les frais, puis cliquer **Lancer la validation**. Ces onglets remplacent l’onglet « Validation historique » et sont séparés des analyses des positions par un trait avant « Volatilité minimale ». L’onglet « Comparaison & optimisation » a été retiré. Chaque méthode conserve indépendamment ses réglages et son résultat lors des changements d’onglet. Les actifs à quantité strictement positive définissent l’univers. Les quantités, favoris et cadenas ne sont jamais modifiés. Les quantités actuelles et les cadenas ne sont pas utilisés pour reconstituer des allocations anciennes.

## Protocole

Le moteur utilise les historiques quotidiens ajustés des actions, ETF et cryptos, convertis en EUR avec le change connu à chaque observation selon le chargeur partagé de performance. En mode fractionnaire, les dividendes sont déjà réinvestis dans les observations ajustées ; ils ne sont pas ajoutés une deuxième fois. En mode titres entiers, les actions et ETF sont valorisés avec les clôtures hors ajustement des dividendes et les distributions disponibles sont versées en liquidités ; l’apprentissage et les signaux restent calculés sur les cours ajustés. Le calendrier suit la référence, en exigeant une cotation des actifs quotidiens déjà introduits ; les actifs pas encore cotés n’écourtent pas le calendrier. Les variations crypto entre deux séances sont agrégées. Pour les lignes passives mensuelles, seule la dernière observation déjà connue est utilisée. Aucune observation ni cotation antérieure à l’introduction d’un actif n’est inventée.

Le début de validation suit la période demandée, après trois ans de données de référence. L’univers s’élargit au fil des cotations disponibles, sans prix ni quantité fictive avant l’introduction. Chaque actif doit disposer de ses propres trois années d’historique et de 500 variations réelles avant d’entrer dans une optimisation ou de déclencher un signal. Un actif trop récent reste en attente, sans bloquer les autres. Les dates de première cotation et les règles particulières sont affichées dans des messages nominatifs. Les messages nominatifs sur la date théorique des trois ans d’apprentissage ne sont plus affichés. Les trous internes de plus de dix jours sur une série quotidienne bloquent toujours le calcul pour éviter de masquer une panne de données.

La première décision est calculée à cette date. Les suivantes sont ancrées sur ses anniversaires à trois mois, reportés à la première observation commune disponible. Chaque allocation est exécutée à la **clôture commune suivante**, après le signal. Les observations d’exécution ne participent ni aux rendements d’apprentissage ni aux poids courants transmis à l’optimiseur. La convention est une exécution à poids cibles à cette clôture, sans glissement de prix.

Cinq méthodes sont disponibles (dont la régression S&P 500 décrite ci-dessous) :

- **Parité de risque** (`risk_parity`, expérimentale) : contributions égales au risque total sur la covariance empirique des rendements en EUR des trois années connues, révision trimestrielle. Tous les actifs éligibles sont inclus ; poids strictement positifs de somme 1, sans levier. Les bornes de 3 % / 35 % et la sélection de supports de la volatilité minimale ne s’appliquent pas : elles peuvent empêcher la parité exacte. Résolution convexe de `xᵀΣx/2 − Σᵢ log(xᵢ)`, puis normalisation des poids. Contrôle de convergence et des contributions relatives `wᵢ(Σw)ᵢ / (wᵀΣw)` à `1/N` (tolérance absolue 10⁻⁶). Volatilité nulle ou absence de solution vérifiable : interruption explicite, sans allocation de remplacement. Les contributions estimées à la cible sont affichées par trimestre ; les arrondis en titres entiers et la dérive entre révisions peuvent rompre leur égalité. Aucun rendement supérieur ni niveau absolu de risque n’est garanti. [Maillard, Roncalli et Teiletche](https://www.thierry-roncalli.com/download/erc.pdf).

- **Volatilité minimale** : minimise la variance totale des rendements d’apprentissage, avec révision trimestrielle.
- **Corrélation minimale** : minimise `wᵀ Corr w`, variance du portefeuille de rendements standardisés, avec révision trimestrielle. Optimisation continue sur tout l’univers éligible, sans plancher ni cardinalité minimale ; plafond de 35 % dès trois actifs, 50/50 à deux, 100 % à un. Une allocation ne change pas les corrélations des actifs et ne garantit pas leur indépendance.
- **Retour à la moyenne** (`mean_reversion`) : actions et cryptomonnaies. Chaque séance commune, une régression du logarithme des cours ajustés en devise native est recalculée sur les trois années précédentes jusqu’à la clôture connue. Le z-score est le résidu final divisé par l’écart type résiduel (N−2 degrés de liberté). Dans l’interface, par défaut, achat si z ≤ −2 ; activation de la sortie après repli dès z ≥ +2, puis vente après un recul de 1 σ depuis le maximum observé pendant la détention. Les seuils d’achat et de vente sont réglables séparément. Exécution à la clôture commune suivante. Une tendance sans dispersion résiduelle ne produit aucun signal. Le seuil est testé à la clôture, et non en continu : l’écart peut passer directement d’une valeur sous le seuil à une valeur nettement supérieure. L’écart-type affiché est celui du signal, pas de l’exécution du lendemain.

Le formulaire du retour à la moyenne ne présente que les deux seuils d’achat et d’activation de la vente, tous deux à **2** par défaut, en plus du capital, de la période, des frais et du mode titres entiers. Les préréglages et les contrôles avancés sont retirés. Les paramètres fixes transmis au moteur sont `reversion_exit_mode="trailing_z"`, `reversion_trailing_gap=1` et `reversion_funding_min_z=0.3`. La référence S&P 500, dividendes réinvestis, est fixe pour les cinq méthodes, sans liste de choix.

Le suivi mémorise le plus haut écart-type connu pendant la détention. Une fois le seuil positif d’activation atteint, il vend après un repli d’au moins 1 σ depuis ce maximum, avec exécution à la clôture commune suivante. Exemple : activation à +2, maximum +2,7 : vente déclenchée à +1,7 ou moins. Il suit le z-score, pas le prix ; ce n’est pas un stop de prix. Le maximum est effacé après liquidation et conservé après une vente partielle de financement. Les ventes de financement restent possibles avant cette sortie, uniquement à partir de +0,3 σ dans l’interface. Le journal indique « Repli de l’écart-type ». Modifier un réglage invalide le résultat de cette méthode et nécessite une nouvelle validation.

L’[étude comparative des seuils](reversion-threshold-study.md) détaille les 47 simulations, la sélection chronologique et les limites des résultats. Le script reproductible est `scripts/study_reversion_thresholds.py`.


Pour les optimisations de volatilité et corrélation minimales, seuls les actifs disposant des trois ans requis à la date du signal sont alloués ; les nouveaux actifs éligibles rejoignent l’univers à la révision trimestrielle suivante. Le solveur existant et ses contraintes sont conservés : au moins la moitié des actifs, plancher de 3 % et plafond de 35 % dès trois actifs, sans emprunt ni vente à découvert. La sélection est approchée au-delà de huit actifs. Un échec interrompt la validation complète ; aucun trimestre difficile n’est ignoré. Les parts restent constantes entre deux opérations.

Pour le retour à la moyenne, les liquidités sont communes et chaque nouvelle entrée est plafonnée à 25 % de la valeur totale du portefeuille au moment de l’ordre, frais d’achat compris. Le capital est la valeur courante, pas quatre enveloppes fixes du capital initial : une hausse des cours augmente la cible mais pas les liquidités. Ce plafond ne force pas la vente d’une position qui le dépasse ensuite par appréciation. À chaque nouvelle entrée, la taille cible est une part égale du capital actif, selon le nombre de positions actives déjà ouvertes et de nouveaux signaux simultanés. Les achats utilisent d’abord les liquidités disponibles. Une entrée doit atteindre un plancher de `min(10 %, 1/N)` de la valeur totale, frais d’achat compris, où N compte les actions et cryptomonnaies de l’univers actif négociables à cette séance (hors lignes passives et avant filtrage des signaux). Cela donne environ 7,14 % pour 14 actifs, et 5 % pour 20. En titres entiers, le minimum est arrondi au nombre de titres supérieur ; le plafond de 25 % reste impératif. Lorsque les liquidités couvrent ce minimum pour les entrées retenues, le budget peut être réduit aux liquidités sans vente de financement. Pour financer le complément, la position active dont l’écart-type connu est le plus élevé au signal parmi les valeurs atteignant le seuil de financement (+0,3 dans l’interface) est réduite du strict nécessaire pour atteindre seulement le plancher utile, frais de vente et d’achat compris, sans financer systématiquement la cible maximale. Une seule ligne peut financer les achats d’une séance : si ses fonds ne suffisent pas, les achats sont réduits plutôt que de vendre une deuxième ligne. En titres entiers, la vente est arrondie à l’unité supérieure nécessaire. Les positions dont l’écart-type est négatif ou incalculable ne financent pas d’entrée : cela évite notamment de liquider une ligne sous le seuil d’achat pour la racheter dès la séance suivante. Une entrée qui ne peut pas atteindre le plancher est ignorée ; aucun reliquat de 80 ou 100 euros ne peut ouvrir une petite position, et aucune liquidité n’est créée. Les entrées simultanées sont prioritaires par écart-type croissant (le plus négatif d’abord), puis par prix unitaire en cas d’égalité. Les positions déjà détenues ne sont pas renforcées. La cible est limitée par le plafond de 25 %, y compris pour la toute première entrée. Le solde reste en liquidités pour les prochains signaux. Une réduction peut donc avoir lieu sans atteindre le seuil de vente ; le journal l’indique par « Financement d’un achat », avec le gain ou la perte réalisé. Les sorties au seuil ou après repli liquident toujours la position. Aucune vente trimestrielle n’est imposée. En titres entiers, l’achat doit respecter à la fois le plancher utile arrondi vers le haut et le plafond de 25 %, avec les fonds disponibles (liquidités et unique ligne de financement) ; si tous les signaux simultanés ne sont pas abordables, les écarts négatifs les plus forts ont priorité, puis les titres les moins chers. Une entrée physiquement impossible ne déclenche pas de vente inutile. Les ETF, matières premières et autres actifs à prix exploitables sont achetés une fois avec 1/N du capital initial (frais compris), à la clôture suivant leur première cotation connue, puis conservés en quantité constante. Ce budget est réservé jusqu’à leur disponibilité et ne finance pas les signaux des autres lignes. Une ligne sans prix exploitable (par exemple un taux souverain, qui n’est pas un prix obligataire) garde son budget en liquidités ; l’application ne traite jamais un taux comme un cours. Les messages indiquent ces règles par actif. Les liquidités ne sont pas rémunérées. Les périodes trimestrielles servent seulement au compte rendu de régularité. Le signal est en devise native, la valorisation du portefeuille est en euros.

## Comparateurs et frais

Les quatre courbes commencent à 100 €, en liquidités non rémunérées jusqu’à la première exécution :

- Méthode testée : décisions trimestrielles ou quotidiennes selon la méthode, avec les seules observations passées.
- Équipondération trimestrielle : mêmes actifs, mêmes dates et frais, poids ramenés à 1/N pour chaque actif déjà coté à chaque exécution ; la part des actifs non cotés reste en liquidités.
- Achat-conservation : budget initial de 1/N réservé par actif, investi à sa première disponibilité puis conservé sans rééquilibrage.
- Référence : S&P 500 total return fixe dans l’interface. L’API conserve la possibilité d’utiliser un ETF quotidien importé pour les études. La référence est convertie en EUR et conservée après son achat initial. Elle sert également de facteur pour le bêta réalisé dans les données API ; cet indicateur n’est pas affiché dans le tableau. Aucun bêta cible n’est imposé. Le Sharpe utilise un taux de référence nul.

Les frais proportionnels (0,5 % par achat et vente par défaut, réglables de 0 à 10 %) portent sur chaque montant acheté ou vendu, entrée initiale incluse. Le capital réinvesti est résolu par l’identité `capital_net + frais × somme(abs(capital_net × poids_cible − valeurs_avant_ordre)) = capital_avant_ordre`. Les coûts sont financés par le portefeuille, sans apport implicite ni double comptage. Aucun frais de sortie fictif n’est prélevé à la fin. Le coût d’entrée de la référence indicielle est une convention théorique : les frais de réplication d’un fonds ne sont pas modélisés.

## Résultats

Le graphique et les indicateurs portent uniquement sur la validation : rendement net, CAGR, drawdown maximal (capital initial inclus), volatilité, Sharpe avec taux de référence fixé à 0 %, frais réellement payés pour le capital initial saisi et rotation annuelle. La rotation est le montant acheté **plus** le montant vendu, divisé par le capital avant opération. L’annualisation divise la somme des rotations de rééquilibrage par la durée calendaire de validation, en excluant l’achat initial. La volatilité et le Sharpe sont annualisés sur 252 observations.

La légende des courbes et les tableaux affichent la référence de marché en premier (S&P 500 par défaut), puis l’achat-conservation, l’équipondération trimestrielle et la méthode testée. Les traits colorés comparent chaque valeur à la référence ; pour les deux méthodes, un second trait compare à l’achat-conservation. Vert : meilleur, rouge : moins bon, gris : égal ou indisponible. Des libellés accessibles précisent chaque comparaison. La volatilité, les frais et la rotation sont favorables lorsqu’ils diminuent ; les rendements, ratios et fréquences de réussite lorsqu’ils augmentent. Un drawdown signé moins négatif est préférable. L’exposition au marché figure en dernière ligne, sans classement meilleur/moins bon. Elle est la moyenne de la part de capital investie (`valeur des positions / (positions + liquidités)`), pondérée par la durée calendaire entre deux clôtures, week-ends compris. Le calcul commence à la première exécution commune, en excluant l’attente initiale après le signal ; les périodes suivantes entièrement en liquidités comptent pour zéro. Retenir seulement une partie des actifs ne réduit pas l’exposition si tout le capital est investi : l’exposition vaut alors 100 %. Une opération à la dernière clôture n’ajoute pas de durée d’exposition. La meilleure valeur disponible des autres lignes est signalée, ex æquo inclus ; aucune distinction n’est ajoutée si toutes les valeurs sont égales. Ces repères comparent les indicateurs, sans désigner une meilleure stratégie dans l’ensemble.

La régularité est décrite par le nombre de trimestres positifs, le nombre de trimestres battant la référence et le pire trimestre. Chaque trimestre commence avant ses frais d’exécution et finit avant les frais de l’exécution suivante : les coûts de début lui sont attribués. Le dernier trimestre partiel reste dans la courbe et les indicateurs globaux, mais est exclu de ces trois statistiques. Moins de quatre trimestres complets déclenche une mention de recul limité. Le détail affiche chaque période d’apprentissage, le nombre de variations, les dates de signal et d’exécution, les rendements et les poids retenus.

Le portefeuille final affiche tous les actifs sélectionnés, y compris ceux à quantité nulle, leur valeur, leur poids et les liquidités à la dernière date commune. Le journal affiche chaque achat et vente, la date du signal, celle d’exécution, le montant hors frais, les frais et l’écart-type au signal pour toutes les stratégies (régression sur les trois années connues, ou 60/18 mois selon la poche S&P 500, en devise native ; indisponible si la dispersion résiduelle est nulle). En mode fractionnaire, le capital initial règle l’échelle en euros sans changer les décisions ni les courbes en base 100. En mode titres entiers, ce capital influence les quantités abordables et les performances. En mode fractionnaire, les quantités sont des **parts ajustées de simulation**, incluant les effets des dividendes réinvestis et opérations sur titres : ce ne sont pas des quantités brutes à transmettre à un courtier. Chaque vente indique `profit_return`, le rendement réalisé sur le coût moyen des titres cédés (frais d’achat et de vente inclus, plus les dividendes encaissés attribués aux titres cédés). Les ventes partielles retirent une fraction proportionnelle du coût moyen et des dividendes ; en mode fractionnaire, les dividendes sont déjà intégrés aux cours ajustés. Ce pourcentage est vert si positif, rouge si négatif et neutre si nul. Les opérations sont présentées des plus récentes aux plus anciennes, par pages de 50.

## Titres entiers et stabilité de l’interface

La case **Titres entiers uniquement (actions et ETF)** active `whole_shares` (désactivé par défaut, sauf pour S&P 500 · Régression). Chaque achat et vente sur ces catégories utilise une quantité entière. Les quantités cibles sont arrondies à l’entier inférieur après calcul des frais ; les frais sont ensuite recalculés sur les montants réellement échangés et le reliquat demeure en liquidités. Pour les stratégies de volatilité et corrélation minimales et de parité de risque, le reliquat est investi dans des titres entiers abordables parmi les poids cibles strictement positifs, à chaque révision trimestrielle. Les budgets suivent ces poids, puis la ligne la plus en dessous de sa cible est privilégiée pour une unité supplémentaire. Les frais sont inclus dans le budget ; aucun crédit n’est utilisé. L’arrondi peut modifier les poids optimaux. Les comparateurs conservent leurs règles d’arrondi sans redistribution. Les cryptos restent fractionnables. Pour le retour à la moyenne, l’arrondi s’effectue sur le budget de chaque entrée ; une action trop chère n’est pas achetée. Les dividendes sont versés en liquidités sans création de fractions. La référence S&P 500 reste théorique et fractionnable ; un ETF local choisi comme référence suit le même arrondi.

Les cours d’exécution sont les `price_observations` convertis avec le même change historique que les séries ajustées. Des cours bruts manquants interrompent ce mode avec un message explicite. Le fournisseur ajuste toujours ces cours des divisions de titres : le nombre nominal de titres avant chaque division n’est pas reconstitué. Ce mode ne vérifie pas l’éligibilité fiscale au PEA.

L’actualisation périodique du catalogue ne réinitialise plus le formulaire et n’annule pas le calcul en cours. Un résultat reste affiché après changement des données ; une mention invite à relancer explicitement pour prendre ces données en compte. Changer l’univers ou un paramètre invalide le résultat. Les appels d’actualisation des analyses générales du Portfolio sont suspendus pendant la consultation de la validation. Le bandeau de dates et le message de démarrage après l’apprentissage ne sont plus affichés.

## Limites

L’univers est choisi aujourd’hui : **biais de survivance et de sélection**, sans reconstitution des anciennes compositions ni des sociétés disparues. Les observations ajustées et les changes sont les versions actuelles du fournisseur, susceptibles de révision ; il ne s’agit pas d’une base de données archivée telle qu’elle était connue à chaque date. Fiscalité, spread, impact de marché et rémunération des liquidités sont absents. Les résultats ne sont pas ceux des transactions réelles du compte. Le bêta réalisé décrit la sensibilité passée sur la validation et ne prédit pas le bêta futur.

Comparer de nombreuses variantes puis retenir la meilleure peut surajuster la validation elle-même. Cette vue n’effectue pas de recherche automatique de paramètres et ne constitue pas une garantie de performance. Le retour à la moyenne teste la politique de seuils décrite ci-dessus ; il ne reproduit pas les recommandations individuelles Momentum + Régression.

## API et contrôles

`POST /api/portfolio/validation` reçoit `asset_ids` (1 à 20 identifiants uniques), `mode`, `years` (1, 3, 5 ou 10 ans), `fee_rate`, `initial_capital`, `whole_shares` (booléen facultatif, défaut `false`) et `benchmark_asset_id` facultatif. Statuts : `pending`, `insufficient`, `ready`. Une réponse prête contient les paramètres, les conventions, les courbes, les métriques, toutes les fenêtres, `final_portfolio` et `transactions`. Chaque opération expose `cash_before`, `cash_after` (liquidités avant/après cette opération, frais compris) et `portfolio_before` (valeur totale avant les opérations de la séance). Le journal affiche les liquidités après chaque opération. Les métriques incluent `cost_eur` (somme des frais pour le capital initial) et `market_exposure` (fraction entre 0 et 1). Les modes sont `volatility`, `mean_reversion` et `correlation`.

Les tests du moteur modifient les prix après le signal, y compris le prix d’exécution, pour vérifier l’invariance des décisions antérieures. Un registre indépendant de parts et liquidités reproduit les quatre courbes et les frais. Les tests API couvrent les changes, une référence locale, les historiques insuffisants, les univers mixtes avec cryptos et les imports en attente. Les tests navigateur vérifient le parcours Portfolio et Stratégie, l’invalidation des résultats, les erreurs et le rendu ordinateur/mobile.

Le bandeau « Composer la stratégie » est repliable avec une flèche. Son état est mémorisé dans le navigateur et conservé entre onglets, stratégies et rechargements.

Pour préserver la reproductibilité des études existantes, les valeurs implicites de l’API restent distinctes des réglages envoyés explicitement par l’interface. Les paramètres facultatifs du retour à la moyenne sont `reversion_entry_z` (défaut 1,4 ; 0,5 à 4), `reversion_exit_z` (défaut 1,4 ; 0 à 4), `reversion_exit_mode` (`threshold` par défaut, ou `trailing_z`), `reversion_trailing_gap` (défaut 0,5 ; 0,1 à 2), et `reversion_funding_min_z` (défaut 0 ; 0 à 2). Ils sont renvoyés dans les paramètres et conventions. La raison d’une transaction peut être `trailing_z`. Pour les études reproductibles, `start_date` et `end_date` peuvent borner la période en ISO `YYYY-MM-DD` ; le début doit précéder la fin. Le début conserve les trois années d’historique antérieures nécessaires et la fin est limitée aux observations disponibles. Les prix postérieurs à la borne de fin ne participent pas au résultat.

## Parité de risque : révisions avec tolérance

L'interface applique désormais deux tolérances de 3 points : écart des poids et
écart des contributions au risque, avec contrôle de la part de liquidités. Une
révision trimestrielle peut conserver les quantités si les deux conditions sont
satisfaites. L'API accepte `risk_rebalance_tolerance` et `rebalance_tolerance`
(défauts nuls pour reproduire le contrôle). Les contributions calculées sur les
quantités effectives après exécution et en fin de trimestre sont affichées avec
la covariance connue au signal. [Protocole et résultats](risk-rebalancing-study.md).

## Diagnostics et comparaisons (14 novembre 2026)

Le contrôle `eligible_equal` rééquilibre trimestriellement les seuls actifs
ayant le même historique admissible que les allocations. Les références
antérieures restent présentes.

Le retour à la moyenne expose AR(1), demi-vie indicative, déplacement récent
absolu des résidus et différence des pentes logarithmiques annualisées entre
les deux moitiés de la fenêtre. Ces diagnostics ne bloquent aucun ordre et
ne constituent pas un test de stationnarité. Les prix ajustés natifs et scores
au signal pendant les détentions sont consultables dans un détail repliable.

À la demande de l’utilisateur, les champs d’exécution et de spread, le journal
prospectif, le contrôle rétrospectif d’exposition et la stratégie CVaR ont été
retirés de l’interface. La CVaR et le contrôle d’exposition ont également été
retirés du moteur. Les anciens journaux locaux ne sont plus lus ni modifiés.
Les paramètres techniques `execution_delay` et `spread_bps` restent disponibles
pour les scripts de recherche des autres méthodes ; l’interface utilise la
clôture suivante et aucun spread ajouté. Pour le retour à la moyenne, le retard
supplémentaire reste une sensibilité approximative, avec dimensionnement selon
les fonds disponibles à l’exécution.

L’interface applique désormais systématiquement la bande de tolérance de
3 points, sans sélecteur, pour les allocations optimisées (poids et risque
pour la parité). Les paramètres API restent disponibles pour la recherche. Aucun
filtre de vente ou seuil du retour à la moyenne n’est modifié pour économiser
des frais sans étude préalable. Les frais et rotations seuls ne suffisent pas
à conclure : vérifier aussi CAGR, drawdown et Sharpe.

## S&P 500 · Régression

Méthode expérimentale distincte du retour à la moyenne existant. Univers fixe :
`yf-psp5.pa` (Amundi PEA S&P 500 UCITS ETF Acc, PSP5.PA) uniquement, indépendamment
des positions personnelles. Le moteur refuse tout autre univers ; aucune
référence CAC ou position inverse n’est chargée pour cette méthode.

**Politique active depuis la dernière adoption du 15 novembre 2026 : `slow_defensive_sharpe_v6`**, 75 % du capital initial en poche lente et 25 % en défensive, sans poche passive. Chacune cible 10 % PSP5 en état défensif, 100 % sinon, uniquement à l'initialisation ou au changement d'état. Budgets indépendants, sans transfert ni rééquilibrage ; mêmes seuils, calendriers et reconstitution de l'état lent. Référence PSP5 EUR, frais par défaut 0,12 %. [Règles complètes, limites et vérification](sp500-sharpe-adoption.md). La v5 65 % régression / 35 % passif est désormais [archivée](sp500-core35-adoption.md).

**Archive ESE/v4 :** les règles et résultats ci-dessous décrivent la version antérieure avant remplacement de l’instrument puis ajout de la poche passive. La combinaison historique `slow_defensive_warm_state_v4` conserve les signaux de la
v3 et reconstitue l’état initial de sa poche lente avec les décisions historiques,
à la demande explicite de l’utilisateur après présentation de
`docs/sp500-three-year-study.md`. La sélection reste rétrospective ; l’adoption
ne change pas les limites de l’étude ni son échec aux critères initiaux.
Elle répartit **le capital initial** en
**75 % pour une poche lente et 25 % pour une poche défensive**. Chaque poche a ses
propres titres, liquidités et état logique. Aucun transfert ni rééquilibrage de
la répartition 75/25 : les poids entre poches dérivent avec leurs performances.

Les deux scores utilisent le cours ajusté natif d’ESE et une régression
logarithmique glissante, avec dispersion résiduelle N−2. La durée de simulation
choisie ne modifie pas leurs fenêtres :

| Poche | Fenêtre | Entrée vers cible 100 % ESE | Sortie vers cible 25 % ESE | Décisions |
|---|---|---|---|---|
| Lente (75 % initialement) | 60 mois, au moins 501 observations et fenêtre complète | Score strictement inférieur à −2 σ **ou** franchissement haussier de 0 σ depuis la séance précédente | Score strictement supérieur à +1,5 σ | Première séance observée du mois |
| Défensive (25 % initialement) | 18 mois, au moins 251 observations et fenêtre complète | Franchissement haussier de −0,5 σ : séance précédente strictement en dessous, courante supérieure ou égale | Score strictement supérieur à +1,5 σ | Toutes les cinq séances depuis le premier signal de simulation |

La réentrée lente compare deux séances consécutives : score précédent
strictement négatif, score courant supérieur ou égal à zéro. Elle n’est évaluée
qu’à la première séance observée du mois, pas au franchissement en milieu de mois
ni entre deux scores mensuels. Un score déjà positif ne déclenche pas de réentrée.
L’entrée initiale sous −2 σ reste possible sans score précédent. En position, la
sortie au-dessus de +1,5 σ garde la priorité ; le rebond ne change pas cette règle.

La cible s’applique à la valeur propre de chaque poche, frais inclus. Avant le
début du test, le moteur rejoue les décisions mensuelles lentes disponibles,
depuis un état défensif, avec les seuls scores connus à chaque date. La dernière
décision retenue précède strictement la première séance du test. Cela reconstitue
un état logique, sans positions, gains, frais ni points de courbe antérieurs.
La poche défensive conserve son état initial défensif.

À la première exécution admissible, chaque poche investit son capital initial
selon sa cible : 100 % si son état est investi, 25 % sinon. Cette initialisation
reste possible hors première séance du mois. Ensuite, les changements d’état
nécessitent une décision programmée et sa condition habituelle. Un score manquant
conserve l’état ; sans cinq ans d’historique ni signal lent antérieur, la poche
lente reste passive à sa cible de 25 %. Le démarrage du test ne
requiert que les 18 mois nécessaires à la poche défensive. Les autres méthodes
conservent leurs trois années et 501 observations.

Exécution à la clôture suivante. Les ordres ne sont passés qu’à l’initialisation
et aux changements de cible : aucun rééquilibrage quotidien ou trimestriel pour
rétablir un poids qui a dérivé. Les titres entiers et reliquats sont calculés
**dans chaque poche**. Les frais de chaque achat/vente restent comptabilisés,
même lorsque les poches passent des ordres opposés le même jour ; aucune
compensation artificielle ne réduit les frais du test. Le journal distingue la
poche, son signal et sa raison ; le portefeuille final agrège les titres et
liquidités. L’API expose aussi les soldes finaux propres à chaque poche.

La référence imposée est **le même ESE.PA en EUR**, avec les mêmes frais et
arrondis, sur son propre calendrier : aucun indice américain ni change ne sont
chargés pour cette méthode. L’API accepte une référence absente ou ESE puis
normalise `benchmark_asset_id` à ESE ; une autre référence est refusée.

Dans l’interface, la durée initiale reste **cinq ans**, avec les choix 1, 3, 5 et
10 ans. Aucune date spéciale n’est injectée. Titres entiers cochés initialement,
frais à 0,5 %. Chaque horizon démarre depuis des liquidités et reconstitue
uniquement l’état logique lent, puis achète effectivement à la clôture suivante.
Les résultats restent des diagnostics historiques.

Vérification sur copie privée de la base arrêtée au 13/11/2026, 10 000 € initiaux,
frais 0,5 %, titres entiers :

| Période observée | CAGR v4 / v3 | Volatilité v4 / v3 | Drawdown v4 / v3 |
|---|---:|---:|---:|
| 13/11/2023–13/11/2026 | 15,68 / 8,97 % | 8,37 / 6,52 % | −7,02 / −7,51 % |
| 15/11/2021–13/11/2026 | 12,25 / 12,25 % | 8,33 / 8,33 % | −6,99 / −6,99 % |
| 14/11/2016–13/11/2026 | 14,06 / 14,06 % | 9,71 / 9,71 % | −8,85 / −8,85 % |

Le moteur reproduit les **20 cas** de recherche figés : cinq périodes principales,
quatorze fenêtres de trois/cinq ans et un test un an. Tolérances de 10⁻⁹ pour les indicateurs et
10⁻⁶ € pour les frais et le capital final. Reproduction :
`PYTHONPATH=backend uv run python scripts/verify_sp500_warm_state.py`.
Les anciens vérificateurs `verify_sp500_reentry.py` et `verify_sp500_compromise.py`
concernent uniquement les politiques historiques v3 et v2.

La piste est adoptée après examen des données : aucune validation indépendante.
Elle améliore les nouveaux départs, sans modifier les décisions d’un compte déjà
en fonctionnement. Le trois ans reste sous ESE (18,79 % annualisés) et sa
volatilité augmente de 28,42 %, au-delà des 20 % permis par le protocole initial.
Sur 166 fenêtres chevauchantes, 59 rendements augmentent et 107 restent identiques ;
16 drawdowns sont légèrement plus profonds, au maximum de 0,138 point.
Les drawdowns observés ne garantissent aucun plafond de perte future et le
rendement dix ans ne garantit pas un rendement annuel de 14 %.

Le protocole expose les deux poches, leur capital initial relatif, leurs
fenêtres, seuils et cadences, l’absence de transferts et de compensation d’ordres.
`training_years` vaut 1,5 (éligibilité minimale de la simulation) et
`signal_frequency` vaut `monthly_and_every_5_sessions`.

Cette stratégie affiche uniquement sa courbe et sa référence de marché :
les deux comparateurs d’allocation habituels ne figurent ni dans les tableaux,
ni dans les marqueurs, ni dans l’aide. `eligible_equal` reste calculé pour la
recherche et masqué dans toutes les stratégies. Les autres méthodes conservent
leurs comparateurs habituels. Aucune supériorité financière n’est établie.

Dans Simulation, les seules sources sont le portefeuille principal et chaque
portefeuille de stratégie enregistré, avec ses quantités propres. La
composition sur mesure dans cet onglet a été supprimée.

La parité de risque affine désormais la solution L-BFGS-B par minimisations
coordonnées exactes du même objectif convexe lorsque les contributions ne
sont pas encore assez proches de leurs budgets. La solution finale reste
strictement positive, investie à 100 % et vérifiée à 10⁻⁶ sur les contributions.
Un statut de recherche linéaire défavorable n’entraîne plus un rejet si les
budgets sont réellement satisfaits. Aucun portefeuille arbitraire de secours
ni modification de covariance ne remplace une solution non calculable.

## Révision des optimiseurs de risque, 14 novembre 2026

La stratégie de corrélation minimale résout désormais le problème convexe sur
tous les actifs éligibles, poids entre zéro et 35 % dès trois actifs, somme 1.
À deux actifs, poids 50/50 ; à un actif, 100 %. Aucun plancher de 3 % ni nombre
minimal de lignes. La relation avec l’ensemble du portefeuille détermine les
poids : deux actifs fortement corrélés entre eux peuvent tous deux diversifier
les autres. Une allocation nulle reste possible. Les quantités entières et la
bande de révision de 3 points peuvent empêcher l’exécution d’une petite cible.
La volatilité minimale conserve sa sélection et ses bornes historiques.

Une covariance alternative était utilisée pour comparer les sélections mais
pas pour calculer leurs poids : elle est désormais transmise à chaque résolution
interne, y compris la résolution relâchée des grands univers. La covariance
empirique reste le défaut ; OAS reste un outil de recherche, sans activation
implicite dans l’interface. Voir [l’étude comparative](risk-allocations-review.md).

### Accès à la stratégie native S&P 500

« S&P 500 · Régression » figure directement dans la liste des stratégies, avec
un encadré de couleur distincte, sans badge ni mention « Incluse dans l’application ».
Son écran utilise un seul titre, avec description et formulaire alignés. Elle est toujours
disponible, même sans stratégie personnelle, et ne peut être supprimée ni
modifiée via le composeur. Elle utilise exclusivement ESE.PA depuis la bibliothèque,
indépendamment de la watchlist et des univers des stratégies personnelles.
Les autres stratégies conservent leurs quatre onglets de validation, avec des
icônes distinctes ; aucun onglet S&P 500 n’y est ajouté. Ce déplacement ne change
ni la politique active ni les paramètres et périodes de simulation.

## Scénarios fictifs de la stratégie native S&P 500

L’entrée S&P500 · Régression possède aussi un onglet **Simulation aléatoire**,
exclusif à cette stratégie. La validation historique et les paramètres v4 restent
inchangés. L’onglet compare le Buy & Hold et la stratégie sur un même parcours
synthétique issu des rendements ESE EUR rééchantillonnés par blocs, avec un léger
bruit indépendant. Les régressions sont initialisées avec l’historique réel,
le moteur `validation_data` applique ses règles usuelles aux deux portefeuilles.
Le tableau d’indicateurs est partagé avec la validation historique.
Voir [le protocole et ses limites](sp500-simulation.md).


## Référence Amundi et frais S&P — mise à jour du 14 novembre 2026

La référence ETF applicative est désormais **Amundi PEA S&P 500 UCITS ETF Acc**, ISIN **FR0011871128**, symbole **PSP5.PA**, identifiant `yf-psp5.pa`. Catalogue, rafraîchissements, référence de la carte risque/frontière, stratégie native et simulations utilisent cet instrument et ses propres cours EUR. ESE et SPY restent archivés en base mais sont masqués de la bibliothèque et des rafraîchissements. Aucun historique BNP n’est renommé ou raccordé à celui d’Amundi. Source d’identification : [fiche officielle Amundi](https://www.amundietf.fr/pdfDocuments/monthly-factsheet/FR0011871128/FRA/FRA/RETAIL/ETF).

Les frais de transaction par défaut de la seule stratégie S&P et de ses simulations sont **0,12 % par achat/vente** (API0,0012), remplaçant0,5 %. Un paramètre explicite continue d’être respecté, y compris zéro. Les autres stratégies restent à0,5 % par défaut. Ce coût de transaction est distinct des frais internes du fonds, déjà incorporés dans les prix. La politique v6 orientée Sharpe utilise désormais tout le capital dans les deux budgets régressifs 75/25, avec plancher10% et sans poche passive ; la combinaison v5 est archivée.

Les références enregistrées dans le navigateur (portefeuille, stratégies, favoris, verrous) sont migrées une seule fois de l’identifiant BNP à l’identifiant Amundi, avec sauvegarde préalable sous les clés suffixées `-before-amundi-sp500`. **Le nombre d’unités saisi est conservé** ; il ne s’agit pas d’une conversion à valeur constante ni d’une transaction de courtage. Si les deux lignes existent, leurs quantités sont additionnées. L’ancien lien d’actif ouvre le nouvel ETF. Un ancien retrait local de PSP5 est levé lors de cette migration uniquement.

Les tableaux historiques plus haut et les anciennes études restent les résultats **BNP ESE avec frais0,5 %**. Ils ne représentent pas la nouvelle combinaison instrument/frais. PSP5 a un historique propre débutant en2014 : aucune donnée antérieure n’est inventée pour les régressions longues.
