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

- **12 matières premières en quotidien** : Brent, gaz naturel US, or, argent, platine, aluminium, cuivre, blé HRW, maïs, soja, café arabica et cacao. Clôtures de futures Yahoo, converties dans les unités physiques affichées ; elles remplacent les références Banque mondiale mensuelles. Les autres matières premières sont masquées. Les changements d’échéance peuvent créer des ruptures de prix ; il ne s’agit pas d’un rendement intégrant le roulement des contrats. Voir [la méthode et les conversions](docs/market-library.md).
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

L’onglet **Régression**, sur les actions, cryptos, ETF et devises, ajuste une tendance linéaire ou logarithmique sur une période choisie. Il colore les zones sous et au-dessus de la tendance, avec un seuil réglable selon la dispersion de l’actif (2 écarts-types par défaut), et affiche la qualité de l’ajustement. Cette lecture descriptive ne simule pas une stratégie de trading. [Méthode et limites](docs/analysis.md#régression-et-retour-à-la-tendance).

Les obligations présentent des taux de référence souverains. Elles sont classées par moyenne décroissante des taux annualisés sur les douze mois précédant la dernière observation souveraine du catalogue. Les observations absentes ne sont pas interpolées ; les pays sans données dans cette fenêtre sont placés en fin de liste. Le dernier taux disponible apparaît au-dessus du graphique. Ces séries n’identifient pas une émission et ne permettent donc pas d’afficher son coupon contractuel, ni de mesurer un rendement total réalisé sur un an. Pour les commodities mensuelles, la simulation reste un proxy de prix/indice et n’inclut pas le roulement de futures. Les limites sont rappelées dans le résultat. [Conventions, formules, exécution et limites détaillées](docs/analysis.md).

## Organisation

```text
backend/investor/
  api.py                   catalogue, historiques et routes de portefeuille
  db.py                    stockage, migration et écritures transactionnelles
  ingest.py, countries.py  connecteurs Banque mondiale et OCDE/FRED
  market_catalog.py        sélection crypto initiale
  market_schemas.py        validation des demandes d’import
  market_api.py            file d’import et recherche par nom ou symbole
  stock_search.py          découverte Yahoo, cache borné, repli local
  import_runner.py         traitement automatique de la file avec l’API
  market.py                téléchargement et archives Yahoo
  worker.py                orchestration indépendante des imports
frontend/src/
  components/              graphiques, infobulles et saisies partagées
  features/assets/         catalogue et vue marché
  features/reversion/      régression et bandes
  features/portfolio/      portefeuille, simulations et optimisation
  features/volatility/     frontières d’efficience
```

## Stockage et pipeline

```text
Banque mondiale / FRED / Yahoo → worker → archives + SQLite → API → React
```

`data/raw/` conserve les téléchargements par SHA-256 et leur provenance ; les archives Yahoo sont des exports du tableau retourné par yfinance, avec les clôtures ajustées et non ajustées, pas les réponses HTTP brutes de Yahoo. `data/investor.sqlite3` conserve actifs, observations, imports, file des demandes et références de marché. Les écritures sont transactionnelles et idempotentes par actif/date ; réimporter corrige les valeurs sans dupliquer les points. Les historiques complets sont retéléchargés pour intégrer les révisions. La consultation des données et les analyses ne contactent aucun fournisseur.

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

Le proxy Vite sert `/api` en développement. Un déploiement devra router `/api` vers FastAPI et les routes d’interface vers `index.html`. Cette application est prévue pour un usage local : avant exposition publique, ajouter contrôle d’accès, quotas et supervision des imports/calculs.

TradingView Lightweight Charts™ — Copyright © 2025 TradingView, Inc., Apache-2.0. [Projet et attribution](https://github.com/tradingview/lightweight-charts). Aucun compte TradingView requis.

### Organisation et tests

Le backend métier est dans `backend/investor/` et ses tests dans `backend/tests/`. Les calculs du portefeuille sont dans `portfolio.py`, `performance.py` et `volatility.py`. La régression des prix est calculée dans le navigateur.

```sh
make test                           # tests Python
cd frontend
npx playwright install chromium    # une fois, pour les tests navigateur
npm test                           # tests sur ordinateur et mobile
npm run build                      # TypeScript, imports/variables inutilisés, build
```

`make test-all` lance les deux suites après installation des dépendances et du navigateur. Pour utiliser un Chrome déjà installé, définir `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` avec son chemin. Les tests navigateur utilisent un serveur Vite dédié et des réponses API simulées : ils ne modifient pas la base locale et n’importent pas de données externes.

L’accueil `/` ne sélectionne aucun actif. Choisir une catégorie affiche sa bibliothèque ; ouvrir un actif reste une action explicite.

Les étoiles suivent un cycle dans toutes les classes d’actifs : or (actif détenu), argent (watchlist), puis aucun favori. Les favoris existants deviennent des étoiles or. Les onglets **Portfolio** (étoiles or) et **Watchlist** (étoiles argent), placés avant les catégories, reprennent la même bibliothèque et permettent de retrouver séparément les actifs détenus et ceux suivis. Les actifs détenus apparaissent avant la watchlist, puis les autres actifs, dans leur catégorie ; le classement habituel est conservé entre actifs de même statut. La sélection est enregistrée dans le stockage local du navigateur.

Dans la **Vue du marché**, le bouton **Comparer au S&P 500** affiche les performances en base 100 sur la durée sélectionnée. La comparaison affiche d’abord les prix hors dividendes (indice S&P 500 `^GSPC`). Le bouton **Dividendes réinvestis** bascule vers les prix ajustés des actions et l’indice de rendement total `^SP500TR`, pour mesurer la différence. Les actions dans une autre devise sont converties en USD aux taux historiques. Les dates communes effectivement observées sont affichées. Les taux obligataires sont exclus ; les matières premières restent des proxys de prix ou d’indice. Les références et taux de change sont mis en cache localement et importés par la queue persistante, sans nouveau service ni clé API.

Le **Portfolio** propose les vues **Positions**, **Répartition**, **Comparaison & optimisation**, **Corrélations** et **Frontières d’efficience**. Saisissez vos quantités, y compris fractionnaires, depuis Positions. Elles sont enregistrées dans le navigateur. Les montants utilisent les derniers prix monétaires disponibles, convertis uniquement en euros. La valeur totale et le nombre d’actifs figurent à droite du titre du Portfolio ; les dates de valorisation et les exclusions sont affichées. La matrice représente la corrélation des rendements des positions dont la quantité est positive, sur les dates communes de la durée choisie. Changer d’actif conserve le défilement de la bibliothèque. Monero (`XMR-USD`) fait partie des cryptos importées.

L’espace **Stratégie** permet de créer plusieurs portefeuilles simulés indépendants. La comparaison propose cinq objectifs : équilibre (Sharpe), volatilité minimale, performance maximale, drawdown minimal et diversification maximale. L’alpha annualisé est affiché en décimal ; le bêta mesure la sensibilité au facteur S&P 500 choisi pour cette comparaison. [Calculs et conventions](docs/portfolio-performance.md).
