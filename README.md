# The Investor

Espace local de recherche de marché : matières premières, obligations par pays, sélection d’actions et principales cryptos. React Router 7, React 19, TypeScript, Tailwind CSS 4, TradingView Lightweight Charts 5. API Python FastAPI, environnement **uv**, données SQLite. Interface noir encre, cuivre et bleu glacier, navigation extensible par catégorie et laboratoire quantitatif pour les matières premières, actions et cryptos.

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

Ces trois commandes correspondent à **trois processus séparés**. Ouvrir http://localhost:5173. API : http://127.0.0.1:8000 ; documentation `/docs`. `make worker` doit rester actif pour traiter les ajouts d’actions et les actualisations. Il traite les imports demandés entre les tâches d’actualisation et rafraîchit les sources toutes les 24 heures. Une source en cours de téléchargement peut retarder le prochain import.

L’interface n’affiche pas de cotations en temps réel. Les dates et fréquences restent visibles ; les historiques mensuels et rendements sont des courbes, sans bougies OHLC artificielles.

## Ajouter des actions

Cliquer **Ajouter une action**, saisir le symbole de sa place de cotation (`AAPL`, `MC.PA`, `AIR.PA`, `7203.T`, etc.) et télécharger. Quelques suggestions facilitent la première utilisation, mais le champ accepte les symboles d’autres actions disponibles chez Yahoo. Les fonds, indices et contrats futures ne sont pas acceptés dans cette catégorie. Les noms des sociétés, devise et type d’instrument sont validés par les métadonnées du fournisseur.

Le serveur place la demande dans une file SQLite durable, sans requête au fournisseur. Le **worker indépendant** télécharge l’historique quotidien ajusté maximal disponible, archive les données et met à jour SQLite. La fenêtre peut être fermée pendant l’import ; le catalogue local se rafraîchit toutes les 15 secondes. En cas d’échec, le message du dialogue permet de réessayer. Le catalogue ne contient que les actions choisies. Apple a été ajoutée pour vérifier le parcours complet sur cette installation ; elle n’est pas imposée aux nouvelles installations.

Les demandes sont dédupliquées pendant le téléchargement ; les données ne sont pas effacées après un échec. Une demande sur un symbole déjà importé ouvre l’actif existant ; ses futures mises à jour sont assurées par le worker. Une seule instance du worker doit tourner : au redémarrage, elle reprend les demandes restées en cours.

Connecteur : [yfinance, historique ajusté](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html). Accès non garanti, dépendant des disponibilités, corrections et limites du fournisseur. La bibliothèque n’est pas affiliée à Yahoo ; voir [ses conditions et avertissements](https://github.com/ranaroussi/yfinance) avant tout usage commercial ou redistribution des données. Les réglages/cache fournisseur restent dans `data/provider-cache/`.

## Couverture

- **71 séries Banque mondiale**, incluant benchmarks, variantes et indices : énergie, métaux, agriculture, engrais, etc. Historiques mensuels disponibles depuis 1960 selon la série. Ce n’est pas l’intégralité des matières premières, places ou contrats futures.
- **34 références souveraines**, une entrée par pays : États-Unis, Canada, Mexique, Chili, France, Allemagne, Royaume-Uni, Italie, Espagne, Pays-Bas, Belgique, Autriche, Portugal, Irlande, Grèce, Finlande, Danemark, Suède, Norvège, Suisse, Pologne, Tchéquie, Hongrie, Slovaquie, Slovénie, Islande, Lituanie, Lettonie, Japon, Corée du Sud, Australie, Nouvelle-Zélande, Inde et Afrique du Sud. Rendement mensuel OCDE à 10 ans distribué par FRED. Ce sont des taux de référence, pas des prix d’obligations ni un agrégat de toutes les durées. Chine et Brésil restent à intégrer ; l’Islande s’arrête en août 2022 dans cette source. Les 11 anciennes séries US par maturité sont conservées dans SQLite et accessibles par l’API, mais masquées du catalogue et non actualisées.
- **6 cryptos en USD** : Bitcoin, Ethereum, Solana, BNB, XRP et Cardano. Historiques quotidiens maximaux disponibles chez Yahoo, téléchargés par `make import` ou par le worker. Pas de série synthétique en cas d’indisponibilité.
- **Actions à la demande** : historique quotidien ajusté maximal selon le symbole et la place ; pas de chargement du catalogue mondial.

La couverture et les dernières dates varient selon l’actif. Il n’y a ni interpolation des jours manquants, ni données simulées dans le catalogue. Un cours quotidien téléchargé pendant une séance peut encore être révisé par le fournisseur.

Sources : [Banque mondiale, Commodity Markets](https://www.worldbank.org/en/research/commodity-markets), [classeur historique](https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx), [OCDE, taux longs](https://www.oecd.org/en/data/indicators/long-term-interest-rates.html), [OCDE via FRED, France](https://fred.stlouisfed.org/series/IRLTLT01FRM156N), [Yahoo Finance](https://finance.yahoo.com/). Attribution OCDE (2026), Main Economic Indicators, via FRED, Federal Reserve Bank of St. Louis, consultation le 6 novembre 2026.

## Dividendes des actions

Le worker télécharge aussi les événements `Dividends` de l’historique quotidien Yahoo (`actions=True`) et les conserve dans les tables `dividends` et `dividend_imports`. Les consultations `GET /api/assets/{id}/dividends` restent locales. Une actualisation réussie remplace les événements de la fenêtre téléchargée pour prendre en compte corrections et suppressions ; une erreur conserve les données précédentes. Les actions déjà présentes sont complétées à leur prochaine actualisation.

Sous le graphique : dernier dividende connu et date de détachement, somme brute par action des douze derniers mois disponibles, puis dates personnalisables inclusives avec cumul et détail des événements. L’interface distingue les données en attente d’import d’une période connue sans dividende. La couverture est explicitement affichée. Il s’agit des montants historiques du fournisseur, corrigés des divisions d’actions, hors fiscalité et conversion de devise ; pas d’une prévision. Les prix ajustés du graphique incluent déjà l’ajustement des dividendes, donc les backtests ne les ajoutent pas une seconde fois. [Documentation du fournisseur](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html).

## Analyse quantitative

L’onglet **Analyse quantitative**, présent sur les matières premières, actions et cryptos, propose un HMM à trois régimes. Sélectionner la carte entraînement ou test, puis faire glisser sur la miniature historique ; les champs de dates permettent aussi une sélection précise au clavier. Les fenêtres doivent être ordonnées et disjointes. Les paramètres permettent de régler frais, glissement, confirmation, détention minimale, plafond de transactions, seuils d’entrée/sortie et taux sans risque.

La simulation long/liquidités compare le capital net à l’achat-conservation du même actif, affiche les régimes, la matrice de transition et les transactions. Sharpe, Sortino, Calmar, volatilité annualisée, drawdown maximal, VaR 95 %, alpha et bêta disposent d’une infobulle au survol **et au focus clavier**, avec définition et repères. Le modèle n’a accès qu’à l’entraînement pour son ajustement ; les probabilités en période 2 sont filtrées causalement, avec exécution retardée.

Les obligations ne proposent pas d’analyse HMM, et l’API refuse ces analyses. Elles sont classées par moyenne décroissante des taux annualisés sur les douze mois précédant la dernière observation souveraine du catalogue. Les observations absentes ne sont pas interpolées ; les pays sans données dans cette fenêtre sont placés en fin de liste. Le dernier taux disponible apparaît au-dessus du graphique. Ces séries n’identifient pas une émission et ne permettent donc pas d’afficher son coupon contractuel, ni de mesurer un rendement total réalisé sur un an. Pour les commodities mensuelles, la simulation reste un proxy de prix/indice et n’inclut pas le roulement de futures. Les limites sont rappelées dans le résultat. [Conventions, formules, exécution et limites détaillées](docs/analysis.md).

## Organisation

```text
backend/investor/
  api.py                   lecture du catalogue/historiques et route d’analyse
  db.py                    stockage, migration et écritures transactionnelles
  ingest.py, countries.py  connecteurs Banque mondiale et OCDE/FRED
  market_catalog.py        sélection crypto initiale
  market_schemas.py        validation des demandes d’import
  market_api.py            file d’import persistante, sans réseau fournisseur
  market.py                téléchargement et archives Yahoo
  worker.py                orchestration indépendante des imports
  analysis/
    schemas.py             validation des périodes et paramètres
    model.py               variables, ajustement HMM, filtre causal
    strategy.py            règles, exécution et coûts
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

`data/raw/` conserve les téléchargements par SHA-256 et leur provenance ; les archives Yahoo sont des exports du tableau ajusté retourné par yfinance, pas les réponses HTTP brutes de Yahoo. `data/investor.sqlite3` conserve actifs, observations, imports, file des demandes et cache des analyses. Les écritures sont transactionnelles et idempotentes par actif/date ; réimporter corrige les valeurs sans dupliquer les points. Les historiques complets sont retéléchargés pour intégrer les révisions. La consultation des données et les analyses ne contactent aucun fournisseur.

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

Tests : parsing des fournisseurs, migrations, erreurs HTTP, queue persistante/dédupliquée, conservation après erreur, archives Yahoo et type d’instrument, séparation temporelle, causalité des variables et régimes, exécution retardée, coûts, limites de transactions/détention, formules connues, cas dégénérés, refus HMM des obligations, classement souverain sur douze mois, dividendes et corrections, cache invalidé après correction. Le build vérifie TypeScript puis produit `frontend/dist`.

Le proxy Vite sert `/api` en développement. Un déploiement devra router `/api` vers FastAPI et les routes d’interface vers `index.html`. Cette application est prévue pour un usage local : avant exposition publique, ajouter contrôle d’accès, quotas et supervision des imports/calculs.

TradingView Lightweight Charts™ — Copyright © 2025 TradingView, Inc., Apache-2.0. [Projet et attribution](https://github.com/tradingview/lightweight-charts). Aucun compte TradingView requis.
