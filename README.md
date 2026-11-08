# The Investor

Espace local de recherche de marché : matières premières, obligations par pays, sélection d’actions et principales cryptos. React Router 7, React 19, TypeScript, Tailwind CSS 4, TradingView Lightweight Charts 5. API Python FastAPI, environnement **uv**, données SQLite. Interface noir encre, cuivre et bleu glacier, navigation extensible par catégorie et laboratoire quantitatif pour les actions et cryptos.

## Démarrer

Prérequis : uv, Python 3.12, Node.js >= 22 et npm. `.python-version` sélectionne Python 3.12 pour les bibliothèques numériques compilées.

```sh
make install
make import
```

Puis trois terminaux :

```sh
make api
make web
make worker
```

Ces trois commandes correspondent à **trois processus séparés**. Ouvrir http://localhost:5173. API : http://127.0.0.1:8000 ; documentation `/docs`. L’API traite automatiquement les ajouts d’actions en arrière-plan, même sans `make worker`. Le worker indépendant assure les actualisations de toutes les sources toutes les 24 heures. Les deux consommateurs réclament les tâches atomiquement pour éviter les doubles imports.

L’interface n’affiche pas de cotations en temps réel. Les dates et fréquences restent visibles ; les historiques mensuels et rendements sont des courbes, sans bougies OHLC artificielles.

## Ajouter des actions

Cliquer **Ajouter une action**, rechercher un nom d’entreprise ou un symbole, puis sélectionner la cotation souhaitée (nom, symbole et place boursière). La recherche Yahoo est temporisée et mise en cache cinq minutes ; les actions locales restent accessibles en cas d’indisponibilité du fournisseur. Les suggestions et une option explicite de symbole exact permettent aussi l’ajout direct. Les fonds, indices et contrats futures ne sont pas acceptés dans cette catégorie. Les noms des sociétés, devise et type d’instrument sont validés par les métadonnées du fournisseur.

Le serveur place la demande dans une file SQLite durable. Un consommateur de fond démarre avec l’API et télécharge l’historique quotidien ajusté maximal disponible, archive les données et met à jour SQLite. La fenêtre peut être fermée pendant l’import ; le catalogue local se rafraîchit toutes les 15 secondes. En cas d’échec, le message du dialogue permet de réessayer. Le catalogue ne contient que les actions choisies. Apple a été ajoutée pour vérifier le parcours complet sur cette installation ; elle n’est pas imposée aux nouvelles installations.

Les demandes sont dédupliquées pendant le téléchargement ; les données ne sont pas effacées après un échec. Une demande sur un symbole déjà importé ouvre l’actif existant ; ses futures mises à jour sont assurées par le worker. Une demande interrompue brutalement redevient disponible après un délai de quinze minutes ; un redémarrage du worker ne réinitialise pas les téléchargements encore actifs. L’arrêt normal de l’API attend la fin de son import en cours.

Connecteur : [yfinance, historique ajusté](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html). Accès non garanti, dépendant des disponibilités, corrections et limites du fournisseur. La bibliothèque n’est pas affiliée à Yahoo ; voir [ses conditions et avertissements](https://github.com/ranaroussi/yfinance) avant tout usage commercial ou redistribution des données. Les réglages/cache fournisseur restent dans `data/provider-cache/`.

## Couverture

- **71 séries Banque mondiale**, incluant benchmarks, variantes et indices : énergie, métaux, agriculture, engrais, etc. Historiques mensuels disponibles depuis 1960 selon la série. Ce n’est pas l’intégralité des matières premières, places ou contrats futures.
- **34 références souveraines**, une entrée par pays : États-Unis, Canada, Mexique, Chili, France, Allemagne, Royaume-Uni, Italie, Espagne, Pays-Bas, Belgique, Autriche, Portugal, Irlande, Grèce, Finlande, Danemark, Suède, Norvège, Suisse, Pologne, Tchéquie, Hongrie, Slovaquie, Slovénie, Islande, Lituanie, Lettonie, Japon, Corée du Sud, Australie, Nouvelle-Zélande, Inde et Afrique du Sud. Rendement mensuel OCDE à 10 ans distribué par FRED. Ce sont des taux de référence, pas des prix d’obligations ni un agrégat de toutes les durées. Chine et Brésil restent à intégrer ; l’Islande s’arrête en août 2022 dans cette source. Les 11 anciennes séries US par maturité sont conservées dans SQLite et accessibles par l’API, mais masquées du catalogue et non actualisées.
- **6 cryptos en USD** : Bitcoin, Ethereum, Solana, BNB, Monero et Hyperliquid. Historiques quotidiens maximaux disponibles chez Yahoo, téléchargés par `make import` ou par le worker. Cardano et XRP sont retirés du catalogue ; leurs archives restent conservées. Pas de série synthétique en cas d’indisponibilité.
- **Actions à la demande** : historique quotidien ajusté maximal selon le symbole et la place ; pas de chargement du catalogue mondial.

La couverture et les dernières dates varient selon l’actif. Il n’y a ni interpolation des jours manquants, ni données simulées dans le catalogue. Un cours quotidien téléchargé pendant une séance peut encore être révisé par le fournisseur.

Sources : [Banque mondiale, Commodity Markets](https://www.worldbank.org/en/research/commodity-markets), [classeur historique](https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx), [OCDE, taux longs](https://www.oecd.org/en/data/indicators/long-term-interest-rates.html), [OCDE via FRED, France](https://fred.stlouisfed.org/series/IRLTLT01FRM156N), [Yahoo Finance](https://finance.yahoo.com/). Attribution OCDE (2026), Main Economic Indicators, via FRED, Federal Reserve Bank of St. Louis, consultation le 6 novembre 2026.

## Dividendes des actions

Le bouton **Dividende** en haut à droite d’une fiche action active une classification manuelle, indépendante des étoiles du Portfolio et de la Watchlist. Elle est enregistrée dans SQLite (`assets.is_dividend`) via `PATCH /api/assets/{id}/dividend-status` et reste présente après actualisation des cours. Le filtre **Dividendes uniquement** sélectionne les actions marquées encore présentes dans la liste affichée ; un retrait les exclut, un réajout restaure leur classification. Il ne prédit aucun versement et ne modifie pas l’historique des dividendes. Les actions retirées de la bibliothèque peuvent être réajoutées par le dialogue d’ajout sans télécharger une deuxième copie de leur historique.

Le worker télécharge aussi les événements `Dividends` de l’historique quotidien Yahoo (`actions=True`) et les conserve dans les tables `dividends` et `dividend_imports`. Les consultations `GET /api/assets/{id}/dividends` restent locales. Une actualisation réussie remplace les événements de la fenêtre téléchargée pour prendre en compte corrections et suppressions ; une erreur conserve les données précédentes. Les actions déjà présentes sont complétées à leur prochaine actualisation.

Les repères menthe « D » sont intégrés au graphique, sans panneau supplémentaire. Au survol ou au toucher : date de détachement et pourcentage du versement brut rapporté à la clôture de la séance précédente, hors ajustement des dividendes (pourcentage ponctuel, non annualisé). Le fournisseur renvoie `Close` et `Adj Close` avec `auto_adjust=False` : les observations utilisent `Adj Close`, tandis que les pourcentages utilisent `Close` ; les deux valeurs du ratio sont corrigées des divisions selon Yahoo. La première séance sans clôture précédente donne un pourcentage absent. Les anciennes données attendent une actualisation pour leur pourcentage, sans approximation à partir du prix ajusté. La légende distingue chargement, attente, erreur et historique sans dividende. Il s’agit des montants historiques du fournisseur, corrigés des divisions d’actions, hors fiscalité et conversion de devise ; pas d’une prévision. Les prix ajustés du graphique incluent déjà l’ajustement des dividendes, donc les backtests ne les ajoutent pas une seconde fois. [Documentation du fournisseur](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html).

## Analyse quantitative

L’onglet **MAD 21/200**, après HMM sur les actions et cryptos, compare une adaptation de suivi de tendance à l’achat-conservation. Cible : investi si la moyenne simple des 21 dernières clôtures dépasse celle des 200 dernières, liquidités sinon ; signal à la clôture et exécution à la clôture observée suivante. Les 200 observations d’amorçage précèdent la période comparée. Les dates sont réglables ; le graphique du prix et des deux moyennes précède les rendements cumulés et les capitaux base 100 sur les mêmes observations. Les frais par opération sont réglables (0,5 % actions, 0,01 % cryptos par défaut), appliqués aux deux méthodes : achat à `capital / (prix × (1 + frais))`, vente à `quantité × prix × (1 − frais)`. Positions finales valorisées sans liquidation forcée, liquidités non rémunérées, hors fiscalité, spread et glissement. Les clôtures ajustées ne reçoivent aucun ajout de dividendes. Le calcul utilise l’historique local déjà chargé, sans appel fournisseur ni modification de la base.

Cette variante sur un actif **ne reproduit pas le classement transversal d’actions** de l’étude [Avramov, Kaplanski et Subrahmanyam, *Moving average distance as a predictor of equity returns* (2021)](https://onlinelibrary.wiley.com/doi/10.1002/rfe.1118). La publication ne valide pas directement la règle de timing proposée ici ni son extension aux cryptos. Le panneau détaille la méthode et cette distinction. Les tests `frontend/tests/mad.spec.ts` vérifient calcul des moyennes, causalité, exécution retardée, frais, capital, exposition, amorçage, périodes et parcours ordinateur/mobile.

L’onglet **HMM**, réservé aux actions et cryptos, utilise désormais **exactement deux états**, haussier et autre, sur les rendements logarithmiques seuls. Investi lorsque l’état à moyenne entraînée supérieure domine, en liquidités sinon. Paramètres figés sur le test, probabilités filtrées causalement, signal à la clôture et exécution à la suivante. Les frais sont déduits des ordres sans les bloquer : **0,01 % pour les cryptos, 0,5 % pour les actions par défaut**, à chaque achat et vente. L’ancien seuil de prévision qui bloquait le moteur en liquidités est retiré du parcours actif et les caches de résultats sont invalidés par la version. [Correction et audit du moteur réellement utilisé](docs/hmm-live.md).

**Fonctionnement corrigé, surperformance non validée** : les 24 actions du catalogue actuel sont calculées sans erreur et passent toutes des ordres (1 108 transactions au total). Sur GTT : 34 ordres, +40,32 % net contre +60,19 % pour la conservation. Seulement 1/24 actions bat la conservation aux frais par défaut. `make audit-hmm` conserve le critère financier de majorité stricte et échoue tant qu’il n’est pas atteint ; `make test-all` inclut ce contrôle distinct des tests techniques. [Ancien audit du moteur à seuil, conservé pour comparaison](docs/hmm-stock-audit.md).

La [première évaluation du HMM minimal « haussier / autre »](docs/hmm-basic.md) portait sur 19 actions : 4/19 surperformances sans frais et 1/19 à 0,5 % par ordre. Cette règle alimente maintenant l’API ; ces chiffres restent ceux du catalogue historique.

La [recherche sur les régimes persistants](docs/hmm-persistent.md) compare 30 variantes et deux témoins sur toutes les actions. Une variante exploratoire atteint 6/19 à 0,5 % par ordre, avec 6 ordres médians contre 36 pour le HMM minimal. La majorité reste non validée. Le rapport contrôle aussi l’égalité des dates d’entrée : certains résultats apparents de 10/19 proviennent surtout d’un décalage d’une séance du benchmark.

Les anciennes variantes et études HMM sont conservées pour la recherche, hors du moteur actif. Les résultats financiers et les expositions presque permanentes sont affichés explicitement.

L’onglet **Régression**, avant HMM sur les actions et cryptos, ajuste une tendance linéaire ou logarithmique sur une période choisie. Il colore les zones sous et au-dessus de la tendance, avec un seuil réglable selon la dispersion de l’actif (2 écarts-types par défaut), et affiche la qualité de l’ajustement. Cette lecture descriptive ne simule pas une stratégie de trading. [Méthode et limites](docs/analysis.md#régression-et-retour-à-la-tendance).

Les matières premières et les obligations ne proposent pas d’analyse HMM ; l’API refuse ces analyses avant toute lecture du cache de résultats. Elles sont classées par moyenne décroissante des taux annualisés sur les douze mois précédant la dernière observation souveraine du catalogue. Les observations absentes ne sont pas interpolées ; les pays sans données dans cette fenêtre sont placés en fin de liste. Le dernier taux disponible apparaît au-dessus du graphique. Ces séries n’identifient pas une émission et ne permettent donc pas d’afficher son coupon contractuel, ni de mesurer un rendement total réalisé sur un an. Pour les commodities mensuelles, la simulation reste un proxy de prix/indice et n’inclut pas le roulement de futures. Les limites sont rappelées dans le résultat. [Conventions, formules, exécution et limites détaillées](docs/analysis.md).

## Organisation

```text
backend/investor/
  api.py                   lecture du catalogue/historiques et route d’analyse
  db.py                    stockage, migration et écritures transactionnelles
  ingest.py, countries.py  connecteurs Banque mondiale et OCDE/FRED
  market_catalog.py        sélection crypto initiale
  market_schemas.py        validation des demandes d’import
  market_api.py            file d’import et recherche par nom ou symbole
  stock_search.py          découverte Yahoo, cache borné, repli local
  import_runner.py         traitement automatique de la file avec l’API
  market.py                téléchargement et archives Yahoo
  worker.py                orchestration indépendante des imports
  analysis/
    schemas.py             validation des périodes et paramètres
    regimes.py             rendements seuls, validation croissante de 1 à 3 états
    switching.py           prévision sur 5 observations, frais et exécution retardée
    model.py               filtre causal et modèle historique
    legacy.py, strategy.py politiques historiques pour comparaisons explicites
    metrics.py             mesure de risque/performance vectorisée
    service.py             orchestration, concurrence et cache versionné
frontend/src/
  App.tsx                  navigation et catalogue
  components/              graphique partagé, icônes, infobulles
  features/assets/         bibliothèque, détail, dialogue d’import
  features/analysis/       périodes, laboratoire, résultats, indicateurs
  lib/                     types, accès API et formatage
```

Les calculs s’appuient sur NumPy/SciPy et hmmlearn avec code numérique compilé, sans nouveau service dans un autre langage. Une analyse simultanée par processus évite la surallocation ; les résultats sont mis en cache avec une empreinte des données et paramètres.

## Stockage et pipeline

```text
Banque mondiale / FRED / Yahoo → worker → archives + SQLite → API → React
```

`data/raw/` conserve les téléchargements par SHA-256 et leur provenance ; les archives Yahoo sont des exports du tableau retourné par yfinance, avec les clôtures ajustées et non ajustées, pas les réponses HTTP brutes de Yahoo. `data/investor.sqlite3` conserve actifs, observations, imports, file des demandes et cache des analyses. Les écritures sont transactionnelles et idempotentes par actif/date ; réimporter corrige les valeurs sans dupliquer les points. Les historiques complets sont retéléchargés pour intégrer les révisions. La consultation des données et les analyses ne contactent aucun fournisseur.

```sh
# Imports ponctuels ; ne nécessitent pas l’API
PYTHONPATH=backend uv run python -m investor.ingest --source world-bank
PYTHONPATH=backend uv run python -m investor.ingest --source fred
PYTHONPATH=backend uv run python -m investor.market --seed
```

Les imports indépendants continuent après l’échec d’une source ; les données précédentes sont conservées. Un import ponctuel incomplet retourne un code non nul. Les archives et la base sont ignorées par Git : exécuter `make import` sur une nouvelle installation. `INVESTOR_DATA_DIR` choisit un autre répertoire. Prévoir un volume persistant et sauvegarder SQLite avec son API de sauvegarde.

## Vérification

```sh
make test
make build
# Formatage et contrôles statiques :
uv run ruff check backend
uv run ruff format --check backend
cd frontend
npm run format:check
```

Tests : parsing des fournisseurs, migrations, erreurs HTTP, queue persistante/dédupliquée, conservation après erreur, archives Yahoo et type d’instrument, séparation temporelle, causalité des variables et régimes, exécution retardée, coûts, limites de transactions/détention, formules connues, cas dégénérés, refus HMM des obligations, classement souverain sur douze mois, dividendes et corrections, pourcentages sans double ajustement, recherche et repli local, imports automatiques sans worker, cache invalidé après correction. Le build vérifie TypeScript puis produit `frontend/dist`.

Le proxy Vite sert `/api` en développement. Un déploiement devra router `/api` vers FastAPI et les routes d’interface vers `index.html`. Cette application est prévue pour un usage local : avant exposition publique, ajouter contrôle d’accès, quotas et supervision des imports/calculs.

TradingView Lightweight Charts™ — Copyright © 2025 TradingView, Inc., Apache-2.0. [Projet et attribution](https://github.com/tradingview/lightweight-charts). Aucun compte TradingView requis.

### Organisation et tests

Le backend métier est dans `backend/investor/` et ses tests dans `backend/tests/`. L’analyse est séparée entre préparation et ajustement (`model.py`), simulation (`strategy.py`), métriques (`metrics.py`), validation des paramètres (`schemas.py`) et orchestration/cache (`service.py`).

Le frontend répartit les fonctionnalités dans `src/features/`, les composants partagés dans `src/components/` et les types et appels API dans `src/lib/`. Le graphique de performance HMM est assemblé dans `PerformanceChart.tsx` à partir du composant partagé `HistoryChart` et des capitaux nets renvoyés par l’API. Les tests navigateur et leurs données synthétiques sont exclusivement dans `frontend/tests/`, hors du code de production.

```sh
make test                           # tests Python
cd frontend
npx playwright install chromium    # une fois, pour les tests navigateur
npm test                           # tests sur ordinateur et mobile
npm run build                      # TypeScript, imports/variables inutilisés, build
```

`make test-all` lance les deux suites après installation des dépendances et du navigateur. Pour utiliser un Chrome déjà installé, définir `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` avec son chemin. Les tests navigateur utilisent un serveur Vite dédié et des réponses API simulées : ils ne modifient pas la base locale et n’importent pas de données externes.

L’accueil `/` ne sélectionne aucun actif. Choisir une catégorie affiche sa bibliothèque ; ouvrir un actif reste une action explicite. Après une simulation HMM, les chiffres sont complétés par la courbe du capital de la stratégie et celle de l’achat-conservation du même actif, base 100 et frais inclus.

Les étoiles suivent un cycle dans toutes les classes d’actifs : or (actif détenu), argent (watchlist), puis aucun favori. Les favoris existants deviennent des étoiles or. Les onglets **Portfolio** (étoiles or) et **Watchlist** (étoiles argent), placés avant les catégories, reprennent la même bibliothèque et permettent de retrouver séparément les actifs détenus et ceux suivis. Les actifs détenus apparaissent avant la watchlist, puis les autres actifs, dans leur catégorie ; le classement habituel est conservé entre actifs de même statut. La sélection est enregistrée dans le stockage local du navigateur.

Après un premier lancement HMM, les paramètres valides déclenchent une actualisation automatique après une courte pause de saisie. La courbe précédente reste visible pendant le calcul ; les calculs sont exécutés successivement. Le bouton de lancement fait défiler vers le graphique. Dans la régression, l’écart prix/tendance apparaît dans une infobulle près du curseur.

Dans la **Vue du marché**, le bouton **Comparer au S&P 500** affiche les performances en base 100 sur la durée sélectionnée. La comparaison affiche d’abord les prix hors dividendes (indice S&P 500 `^GSPC`). Le bouton **Dividendes réinvestis** bascule vers les prix ajustés des actions et l’indice de rendement total `^SP500TR`, pour mesurer la différence. Les actions dans une autre devise sont converties en USD aux taux historiques. Les dates communes effectivement observées sont affichées. Les taux obligataires sont exclus ; les matières premières restent des proxys de prix ou d’indice. Les références et taux de change sont mis en cache localement et importés par la queue persistante, sans nouveau service ni clé API.

Le **Portfolio** propose les vues **Positions**, **Répartition par actif** et **Corrélations**. Saisissez vos quantités, y compris fractionnaires, depuis Positions. Elles sont enregistrées dans le navigateur. Les montants utilisent les derniers prix monétaires disponibles, convertis uniquement en euros. La valeur totale et le nombre d’actifs figurent à droite du titre du Portfolio ; les dates de valorisation et les exclusions sont affichées. La matrice représente la corrélation des rendements des positions dont la quantité est positive, sur les dates communes de la durée choisie. Changer d’actif conserve le défilement de la bibliothèque. Monero (`XMR-USD`) fait partie des cryptos importées.
