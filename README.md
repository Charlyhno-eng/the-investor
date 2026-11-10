# The Investor

Espace local de recherche de marché : matières premières, obligations par pays, sélection d’actions et principales cryptos. React Router 7, React 19, TypeScript, Tailwind CSS 4, TradingView Lightweight Charts 5. API Python FastAPI, environnement **uv**, données SQLite. Interface noir encre, cuivre et bleu glacier, navigation extensible par catégorie et laboratoire quantitatif pour les actions et cryptos.

## Démarrer

Prérequis : uv, Python 3.12, Node.js >= 22 et npm. `.python-version` sélectionne Python 3.12 pour les bibliothèques numériques compilées.

```sh
make install
make import
```

Puis deux terminaux (et un worker facultatif) :

```sh
make api
make web
make worker  # facultatif : initialise le catalogue et ajoute un consommateur
```

Ouvrir http://localhost:5173. API : http://127.0.0.1:8000 ; documentation `/docs`. L’API traite automatiquement les ajouts et l’actualisation des actifs déjà présents en arrière-plan, même sans `make worker`. Le worker facultatif initialise aussi les catalogues et peut continuer les actualisations quand l’API est arrêtée. Les consommateurs partagent la même file SQLite et réclament les tâches atomiquement pour éviter les doubles imports.

Au démarrage puis toutes les 30 secondes, le consommateur recherche les vérifications échues : cours quotidiens, indices et changes toutes les heures, séries souveraines mensuelles toutes les six heures. Un échec conserve les données précédentes et autorise une nouvelle tentative après cinq minutes ; les téléchargements abandonnés sont récupérés après quinze minutes. La planification reste dédupliquée après redémarrage et avec plusieurs consommateurs. L’interface relit le catalogue toutes les 15 secondes et recharge les graphiques et calculs concernés après chaque import, y compris lors d’une correction historique ou d’une actualisation des références.

Les actualisations nécessitent une connexion et au moins l’API ou le worker en fonctionnement. Une donnée à la veille dépend de sa publication : les marchés fermés restent à leur dernière séance ; les séries OCDE/FRED sont mensuelles et peuvent être publiées avec retard. Les dates ne sont jamais prolongées artificiellement.

L’interface n’affiche pas de cotations en temps réel. Les dates et fréquences restent visibles ; les historiques mensuels et rendements sont des courbes, sans bougies OHLC artificielles.

## Ajouter des actions

Cliquer **Ajouter une action**, rechercher un nom d’entreprise ou un symbole, puis sélectionner la cotation souhaitée (nom, symbole et place boursière). La recherche Yahoo est temporisée et mise en cache cinq minutes ; les actions locales restent accessibles en cas d’indisponibilité du fournisseur. Les suggestions et une option explicite de symbole exact permettent aussi l’ajout direct. Les fonds, indices et contrats futures ne sont pas acceptés dans cette catégorie. Les noms des sociétés, devise et type d’instrument sont validés par les métadonnées du fournisseur.

Le serveur place la demande dans une file SQLite durable. Un consommateur de fond démarre avec l’API et télécharge l’historique quotidien ajusté maximal disponible, archive les données et met à jour SQLite. La fenêtre peut être fermée pendant l’import ; le catalogue local se rafraîchit toutes les 15 secondes. En cas d’échec, le message du dialogue permet de réessayer. Le catalogue ne contient que les actions choisies. Apple a été ajoutée pour vérifier le parcours complet sur cette installation ; elle n’est pas imposée aux nouvelles installations.

Les demandes sont dédupliquées pendant le téléchargement ; les données ne sont pas effacées après un échec. Une demande sur un symbole déjà importé ouvre l’actif existant ; ses futures mises à jour sont assurées par le consommateur de fond de l’API ou le worker. Une demande interrompue brutalement redevient disponible après un délai de quinze minutes ; un redémarrage du worker ne réinitialise pas les téléchargements encore actifs. L’arrêt normal de l’API attend la fin de son import en cours.

Connecteur : [yfinance, historique ajusté](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html). Accès non garanti, dépendant des disponibilités, corrections et limites du fournisseur. La bibliothèque n’est pas affiliée à Yahoo ; voir [ses conditions et avertissements](https://github.com/ranaroussi/yfinance) avant tout usage commercial ou redistribution des données. Les réglages/cache fournisseur restent dans `data/provider-cache/`.

## Couverture

- **12 matières premières en quotidien** : Brent, gaz naturel US, or, argent, platine, aluminium, cuivre, blé HRW, maïs, soja, café arabica et cacao. Clôtures de futures Yahoo, converties dans les unités physiques affichées ; elles remplacent les références Banque mondiale mensuelles. Les autres matières premières sont masquées. Les changements d’échéance peuvent créer des ruptures de prix ; il ne s’agit pas d’un rendement intégrant le roulement des contrats. Voir [la méthode et les conversions](docs/market-library.md).
- **34 références souveraines**, une entrée par pays : États-Unis, Canada, Mexique, Chili, France, Allemagne, Royaume-Uni, Italie, Espagne, Pays-Bas, Belgique, Autriche, Portugal, Irlande, Grèce, Finlande, Danemark, Suède, Norvège, Suisse, Pologne, Tchéquie, Hongrie, Slovaquie, Slovénie, Islande, Lituanie, Lettonie, Japon, Corée du Sud, Australie, Nouvelle-Zélande, Inde et Afrique du Sud. Rendement mensuel OCDE à 10 ans distribué par FRED. Ce sont des taux de référence, pas des prix d’obligations ni un agrégat de toutes les durées. Chine et Brésil restent à intégrer ; l’Islande s’arrête en août 2022 dans cette source. Les 11 anciennes séries US par maturité sont conservées dans SQLite et accessibles par l’API, mais masquées du catalogue et non actualisées.
- **6 cryptos en USD** : Bitcoin, Ethereum, Solana, BNB, Monero et Hyperliquid. Historiques quotidiens maximaux disponibles chez Yahoo, téléchargés par `make import` ou par le worker. Cardano et XRP sont retirés du catalogue ; leurs archives restent conservées. Pas de série synthétique en cas d’indisponibilité.
- **Actions à la demande** : historique quotidien ajusté maximal selon le symbole et la place ; pas de chargement du catalogue mondial.

La couverture et les dernières dates varient selon l’actif. Il n’y a ni interpolation des jours manquants, ni données simulées dans le catalogue. Un cours quotidien téléchargé pendant une séance peut encore être révisé par le fournisseur.

Sources : [Banque mondiale, Commodity Markets](https://www.worldbank.org/en/research/commodity-markets), [classeur historique](https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx), [OCDE, taux longs](https://www.oecd.org/en/data/indicators/long-term-interest-rates.html), [OCDE via FRED, France](https://fred.stlouisfed.org/series/IRLTLT01FRM156N), [Yahoo Finance](https://finance.yahoo.com/). Attribution OCDE (2026), Main Economic Indicators, via FRED, Federal Reserve Bank of St. Louis, consultation le 6 novembre 2026.

## Dividendes des actions

Le filtre **Dividendes uniquement** sélectionne les actions dont le rendement annuel moyen des dividendes dépasse 4 %, sur les trois années civiles terminées précédant la dernière date de couverture. Seules les années entièrement couvertes et aux pourcentages connus entrent dans la moyenne ; les années sans versement comptent pour zéro. La classification est calculée à partir de l’historique importé, indépendamment des favoris. Les actions retirées peuvent être réajoutées sans dupliquer leur historique.

Le worker télécharge aussi les événements `Dividends` de l’historique quotidien Yahoo (`actions=True`) et les conserve dans les tables `dividends` et `dividend_imports`. Les consultations `GET /api/assets/{id}/dividends` restent locales. Une actualisation réussie remplace les événements de la fenêtre téléchargée pour prendre en compte corrections et suppressions ; une erreur conserve les données précédentes. Les actions déjà présentes sont complétées à leur prochaine actualisation.

Les repères menthe « D » sont intégrés au graphique, sans panneau supplémentaire. Au survol ou au toucher : date de détachement et pourcentage du versement brut rapporté à la clôture de la séance précédente, hors ajustement des dividendes (pourcentage ponctuel, non annualisé). Le fournisseur renvoie `Close` et `Adj Close` avec `auto_adjust=False` : les observations utilisent `Adj Close`, tandis que les pourcentages utilisent `Close` ; les deux valeurs du ratio sont corrigées des divisions selon Yahoo. La première séance sans clôture précédente donne un pourcentage absent. Les anciennes données attendent une actualisation pour leur pourcentage, sans approximation à partir du prix ajusté. La légende distingue chargement, attente, erreur et historique sans dividende. Il s’agit des montants historiques du fournisseur, corrigés des divisions d’actions, hors fiscalité et conversion de devise ; pas d’une prévision. Le graphique de marché réinvestit automatiquement les dividendes via `Adj Close`, qui intègre déjà les distributions : aucun versement n’est ajouté à cette série et aucun bouton d’activation n’est nécessaire. Le pourcentage affiché utilise la même série que la courbe. La comparaison au S&P 500 utilise aussi les cours ajustés et son indice de rendement total `^SP500TR`. Les analyses et backtests utilisent les observations ajustées sans ajouter de dividendes. L’API conserve un mode explicite `reinvest=false` pour consulter les cours hors dividendes. [Documentation du fournisseur](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html).

## Analyse quantitative

L’onglet **Régression**, sur les actions, cryptos, ETF et devises, ajuste une tendance linéaire ou logarithmique sur une période choisie. Il colore les zones sous et au-dessus de la tendance, avec un seuil réglable selon la dispersion de l’actif (2 écarts-types par défaut), et affiche la qualité de l’ajustement. Cette lecture descriptive ne simule pas une stratégie de trading. [Méthode et limites](docs/analysis.md#régression-et-retour-à-la-tendance).

Les obligations présentent des taux de référence souverains. Elles sont classées par moyenne décroissante des taux annualisés sur les douze mois précédant la dernière observation souveraine du catalogue. Les observations absentes ne sont pas interpolées ; les pays sans données dans cette fenêtre sont placés en fin de liste. Le dernier taux disponible apparaît au-dessus du graphique. Ces séries n’identifient pas une émission et ne permettent donc pas d’afficher son coupon contractuel, ni de mesurer un rendement total réalisé sur un an. Pour les commodities mensuelles, la simulation reste un proxy de prix/indice et n’inclut pas le roulement de futures. Les limites sont rappelées dans le résultat. [Conventions, formules, exécution et limites détaillées](docs/analysis.md).

## Organisation

```text
backend/investor/
  api.py                   assemblage FastAPI et cycle de vie du worker
  assets/                  routes du catalogue, métadonnées et comparaison
  portfolio/               routes, valorisation, performance, régression, volatilité
  imports/                 routes, validation, recherche, catalogue et file d’import
  db.py                    stockage SQLite et migrations
  ingest.py, countries.py  connecteurs Banque mondiale et OCDE/FRED
  worker.py                orchestration indépendante des imports
backend/tests/
  unit/                    calculs numériques, métadonnées et parseurs
  integration/             API, stockage, imports et traitements asynchrones
  conftest.py, support.py  données et fixtures partagées
frontend/src/
  components/              graphiques, infobulles et saisies partagées
  features/assets/         catalogue et vue marché
  features/reversion/      régression et bandes
  features/portfolio/      composants, hooks, types et stockage des simulations
  features/volatility/     frontières d’efficience
frontend/tests/
  unit/                    calculs purs exécutés par Vitest dans Node
  e2e/                     parcours navigateur Playwright, desktop et mobile
scripts/
  check_structure.py       vérification des fichiers et dossiers sources
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
PYTHONPATH=backend uv run python -m investor.imports.service --seed
```

Les imports indépendants continuent après l’échec d’une source ; les données précédentes sont conservées. Un import ponctuel incomplet retourne un code non nul. Les archives et la base sont ignorées par Git : exécuter `make import` sur une nouvelle installation. `INVESTOR_DATA_DIR` choisit un autre répertoire. Prévoir un volume persistant et sauvegarder SQLite avec son API de sauvegarde.

## Vérification

```sh
make check       # lint, format, code inutilisé, structure, tests backend/unitaires et build
make check-all   # ajoute les parcours navigateur desktop et mobile
make format      # corrige les règles automatiques et formate Python/TypeScript/CSS
make test-unit   # uniquement les tests unitaires backend et frontend
```

Le proxy Vite sert `/api` en développement. Un déploiement devra router `/api` vers FastAPI et les routes d’interface vers `index.html`. Cette application est prévue pour un usage local : avant exposition publique, ajouter contrôle d’accès, quotas et supervision des imports/calculs.

TradingView Lightweight Charts™ — Copyright © 2025 TradingView, Inc., Apache-2.0. [Projet et attribution](https://github.com/tradingview/lightweight-charts). Aucun compte TradingView requis.

### Organisation et tests

Les tests unitaires sont séparés des tests d’intégration et des parcours navigateur. Les fixtures partagées du backend vivent dans `backend/tests/support.py`, sans importer un module de tests depuis un autre. La régression des prix est calculée dans le navigateur.

Ruff contrôle les imports, les erreurs Python et le formatage. ESLint vérifie TypeScript, les règles des hooks et les exports compatibles avec React Refresh. Prettier fixe le style du frontend. Knip détecte les fichiers, exports et dépendances inutilisés. `scripts/check_structure.py` refuse les fichiers et dossiers sources vides et les tests placés dans le code applicatif. Les dépendances installées, caches, rapports de tests et données locales sont exclus du contrôle de structure.

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

Dans la **Vue du marché**, le bouton **Comparer au S&P 500** affiche les performances en base 100 sur la durée sélectionnée. Les dividendes sont automatiquement réinvestis via les cours ajustés des actions et l’indice de rendement total `^SP500TR`, sans double comptage ni bouton supplémentaire. Les actions dans une autre devise sont converties en USD aux taux historiques. Les dates communes effectivement observées sont affichées. Les taux obligataires sont exclus ; les matières premières restent des proxys de prix ou d’indice. Les références et taux de change sont mis en cache localement et importés par la queue persistante, sans nouveau service ni clé API.

Le **Portfolio** propose les vues **Positions**, **Répartition**, **Comparaison & optimisation**, **Corrélations** et **Frontières d’efficience**. Saisissez vos quantités, y compris fractionnaires, depuis Positions. Elles sont enregistrées dans le navigateur. Les montants utilisent les derniers prix monétaires disponibles, convertis uniquement en euros. La valeur totale et le nombre d’actifs figurent à droite du titre du Portfolio ; les dates de valorisation et les exclusions sont affichées. La matrice représente la corrélation des rendements des positions dont la quantité est positive, sur les dates communes de la durée choisie. Changer d’actif conserve le défilement de la bibliothèque. Monero (`XMR-USD`) fait partie des cryptos importées.

L’espace **Stratégie** permet de créer plusieurs portefeuilles simulés indépendants. La comparaison propose cinq objectifs : équilibre (Sharpe), volatilité minimale, performance maximale, drawdown minimal et diversification maximale. L’alpha annualisé est affiché en décimal ; le bêta mesure la sensibilité au facteur S&P 500 choisi pour cette comparaison. [Calculs et conventions](docs/portfolio-performance.md).

Les actions proposent aussi l’onglet **Momentum** : score pondéré sur 36, 12 et 6 mois (40/35/25 par défaut), dernier mois exclu, régression logarithmique, résidus et force relative au S&P 500 (par défaut), au CAC 40 ou à un ETF. Toutes les actions de la bibliothèque sont classées ensemble, indépendamment de leur pays ou devise, sur leurs variations en devise de cotation sans effet de change. Les poids et la référence sont partagés avec les scores affichés dans Portfolio et Watchlist ; les horizons manquants sont exclus et les poids disponibles sont recalculés, avec une mention « historique partiel ». L’ETF Amundi CAC 40 fait partie du catalogue. La variation récente et la correction depuis le sommet permettent de repérer une baisse malgré une forte hausse ancienne. [Formule et conventions](docs/momentum.md).

Le Portfolio propose **Recommandation action**, limité aux actions détenues (étoile or) et à celles de la watchlist (étoile argent). Les règles combinent le Momentum partagé et l’écart normalisé à la régression logarithmique sur cinq ans pour proposer acheter, renforcer, conserver, alléger, vendre ou attendre. La formule et ses seuils expérimentaux sont expliqués dans l’interface et dans [la comparaison des calculs](docs/recommendations.md). Les répartitions du Portfolio et des stratégies utilisent des couleurs générées sans doublons ; les matrices de corrélation conservent une taille fixe et permettent d’inspecter les cellules, même avec 500 actifs.

Les cryptomonnaies proposent également **Momentum**, avec classement entre cryptos, Bitcoin comme référence par défaut et réglages indépendants des actions. Leurs scores sont disponibles dans Portfolio et Watchlist. Le catalogue ETF inclut aussi LQQ (Nasdaq-100 x2 quotidien), EXA1 (iShares EURO STOXX Banks 30-15, capitalisation) et SPMO (Invesco S&P 500 Momentum, fonds américain). [Références des ETF](docs/etfs.md).
