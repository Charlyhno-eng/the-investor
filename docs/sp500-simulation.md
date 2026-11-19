# Simulation aléatoire de S&P 500 · Régression

La stratégie active est **`slow_defensive_sharpe_v6`**, dernière adoption du 15 novembre : **75 % du capital initial en poche lente, 25 % en défensive, sans poche passive**. Chaque poche cible 10 % en état défensif et 100 % sinon, uniquement à l'initialisation/changement d'état. Budgets indépendants sans transfert ni rééquilibrage ; poids dérivants. Seuils, états initiaux et cadences conservés. Voir [l’adoption Sharpe et sa vérification](sp500-sharpe-adoption.md). Les rapports v5 restent archivés.

Un onglet **Simulation aléatoire** apparaît uniquement dans l’entrée native S&P500 · Régression, à côté de **Validation historique**, sélectionnée par défaut. Aucune modification des onglets des stratégies personnelles ni de la simulation générale. Les deux vues gardent leurs réglages et résultats pendant les changements d’onglet.

## Utilisation

Choisir 1/3/5/10ans, capital initial, frais par achat/vente et titres entiers ou fractionnaires. En mode **Un parcours**, cliquer **Générer un nouveau parcours**. Les frais par achat/vente sont à **0,12 % par défaut**, comme dans la validation historique de cette stratégie. Ce paramètre est un coût de transaction simulé demandé par l’utilisateur ; les frais internes du fonds sont déjà reflétés dans ses cours, et ne sont pas soustraits une deuxième fois. Un nouveau tirage est effectué à chaque demande ; aucun filtrage selon les performances de la stratégie. Modifier un réglage invalide le résultat précédent. Les actualisations automatiques du catalogue et des cours PSP5 conservent les calculs en cours et les résultats affichés : chaque demande utilise l’historique lu au lancement. Une nouvelle simulation utilise les données alors disponibles.

Deux courbes nettes de frais en base100 :

- **S&P500 · Buy & Hold**, achat à la première clôture simulée, puis conservation.
- **S&P500 · Régression**, règles actuelles inchangées.

Le tableau réutilise le composant de validation historique : rendement net, CAGR, drawdown maximal, volatilité annualisée, rotation hors entrée, pire trimestre complet, Sharpe à taux de référence nul, frais, trimestres positifs, trimestres battant la référence et exposition moyenne. La ligne séparée des capitaux finaux a été retirée à la demande de l’utilisateur. Aucune équipondération ni contrôle d’actifs éligibles affiché.

## Plusieurs parcours et tableau en direct

Le mode **Plusieurs parcours** propose un nombre entier de1à10000, par défaut1000. Le serveur lit et prépare l’historique une fois. Le calcul groupé NumPy (`portfolio/sp500_batch.py`) réutilise les règles de transition, le calcul OLS et les métriques de production, sans préparer les journaux détaillés ni les témoins inutilisés du moteur de validation complet. Les fenêtres calendaires et l’état lent initial sont préparés une seule fois par demande. Un premier parcours isolé fournit rapidement un résultat, puis des groupes de 64 parcours sont calculés hors de la boucle des requêtes. Les graines et les livres de chaque parcours restent indépendants. Le serveur transmet toujours un état initial et chaque préfixe du tableau, dans l’ordre des graines. Les courbes temporaires sont limitées au groupe courant ; aucune courbe du lot n’est envoyée ni conservée après calcul.

Le tableau place **Buy & Hold avant Régression**. Pour chaque indicateur : moyenne de chaque méthode, pourcentage de victoires Buy & Hold, pourcentage de victoires Régression et égalités. La colonne « Paires valides » est masquée à la demande de l’utilisateur ; les dénominateurs restent conservés dans l’API et utilisés dans les calculs. Le pourcentage a pour dénominateur les paires valides de la ligne, pas les1000demandées avant leur calcul. Les moyennes portent sur le même ensemble de paires valides. Rendement/CAGR, Sharpe, Sortino, Calmar, drawdown signé, pire trimestre et trimestres positifs : plus élevé gagne. Volatilité, volatilité baissière, rotation et frais : plus faible gagne. Le drawdown−5 % bat−30 %. Égalité numérique : tolérance relative1e−9 et absolue1e−10. Les indicateurs indéfinis ne deviennent pas zéro. Exposition, alpha/bêta et trimestres battant le témoin ne sont pas classés : leur sens n’est pas symétrique entre les méthodes.

**Arrêter** annule la lecture réseau et garde le tableau partiel, explicitement indiqué comme arrêté. Le serveur cesse avant le groupe suivant et vérifie également la déconnexion avant chaque instantané ; le groupe déjà lancé, de 64 parcours au plus, peut terminer en arrière-plan. Une erreur arrête le lot et l’interface conserve les résultats déjà acquis : aucun échec n’est ignoré pour rendre le résultat favorable. Une coupure sans message final est signalée comme interruption. Modifier les paramètres annule le lot et efface le tableau précédent. Les mises à jour des données en arrière-plan ne l’interrompent pas et ne modifient pas son historique source. Quitter la vue de la stratégie annule toujours la demande en cours.

API : `POST /api/portfolio/sp500-simulation/batch`, mêmes paramètres que l’unitaire, plus `count`. Réponse progressive NDJSON (`application/x-ndjson`, cache désactivé). L’API accepte une graine de lot ; les parcours utilisent `(seed + i) modulo 2**32`. Le nombre et la graine affichée permettent de reproduire le lot et son préfixe. Aucun choix de graine favorable, aucune optimisation des règles sur les tirages. Les fréquences ne sont pas des probabilités prospectives ; tous les tirages partagent le même historique et le même état initial de stratégie.

## Construction du marché fictif

Source unique : observations ajustées **Amundi PEA S&P 500 UCITS ETF Acc (PSP5.PA, FR0011871128), en EUR** disponibles localement ; aucune substitution silencieuse par l’indice USD. Au moins60mois calendaires, le minimum d’observations de la poche lente et aucune interruption de plus de dix jours sont requis. Le dernier cours brut sert de prix unitaire initial pour les arrondis de titres. Historique insuffisant ou dernier cours brut absent : message explicite, pas de génération arbitraire ou d’import automatique.

Les rendements logarithmiques sont rééchantillonnés par séquences contiguës de longueur géométrique, de moyenne63séances. À la fin de l’historique, le bloc redémarre sur un indice tiré au hasard ; pas de raccord artificiel entre dernière et première séance. Cela conserve des séquences de volatilité et de baisse existantes, sans en imposer dans chaque scénario. Une petite perturbation normale indépendante, centrée, d’écart-type égal à5 % de l’écart-type historique quotidien, est ajoutée aux rendements. Les pertes extrêmes ne sont ni écrêtées ni forcées.

Deux flux pseudo-aléatoires indépendants pour les blocs et le bruit : à graine identique, prolonger l’horizon conserve exactement le préfixe des rendements simulés. L’API accepte une graine reproductible ; l’interface en demande une nouvelle au serveur et affiche le numéro du tirage. La graine est issue de32bits aléatoires, sans recherche du meilleur résultat.

Le parcours commence au dernier cours réel connu. Les dates suivantes sont des jours de semaine jusqu’à l’horizon choisi ; le calendrier ne retire pas les jours fériés boursiers. Elles désignent un scénario fictif, pas une prévision. Les conventions d’indicateurs restent celles du moteur : volatilité/Sharpe annualisés252séances et CAGR en durée calendaire.

Les deux poches achètent leurs cibles initiales à la première exécution admissible, avec leurs propres frais et arrondis. Tout l’historique réel antérieur est conservé pour calculer les régressions et reconstituer l’état lent ; la poche défensive démarre défensive. Aucun gain antérieur n'est ajouté. Les cours ajustés antérieurs sont multipliés par une constante pour raccorder le dernier prix unitaire brut : les scores de régression logarithmique restent inchangés. Les nouveaux cours synthétiques sont traités comme un support capitalisant ; aucun dividende supplémentaire n’est crédité.

## Comparaison équitable

En mode unitaire, le moteur **`validation_data` de production** évalue les deux portefeuilles sur la même série. En mode multiple, le calcul groupé conserve la même chronologie et les mêmes opérations financières ; ses douze métriques sont comparées au moteur complet par les tests et le script de mesure de performance. Même capital neuf, mêmes dates et frais, même convention de titres entiers, achat initial à la clôture suivante, aucun bénéfice antérieur ajouté. Les scores utilisent seulement le préfixe connu à chaque décision. Aucune modification de seuil, cadence, exposition ou poids de la stratégie pour améliorer les simulations. Liquidités non rémunérées, aucun levier, aucun transfert entre les deux poches, frais par poche même si leurs ordres s’opposent.

Endpoint : `POST /api/portfolio/sp500-simulation`.

```json
{"years":5,"initial_capital":10000,"fee_rate":0.0012,"whole_shares":true,"seed":42}
```

`seed` est facultatif. La réponse comporte `comparison` (résultats du moteur avec uniquement les deux séries demandées dans métriques/courbes) et `simulation` (graine, source, méthode, calendrier et paramètres du générateur). Le calcul est synchrone dans le worker FastAPI ; sur le snapshot local audité, les scénarios testés prennent moins d’une seconde côté moteur. Aucune série fictive n’est enregistrée dans la base et les paramètres de la stratégie restent inchangés.

## Vérifications reproductibles

```sh
uv run pytest -q backend/tests/unit/test_sp500_simulation.py backend/tests/integration/test_sp500_simulation_api.py
PYTHONPATH=backend uv run python scripts/verify_sp500_simulation.py
cd frontend
npm run test -- tests/e2e/sp500-simulation.spec.ts tests/e2e/validation.spec.ts tests/e2e/strategies.spec.ts
```

Le vérificateur travaille sur une sauvegarde SQLite privée en lecture seule. Rapport actuel ignoré par Git : `data/backtests/sp500-sharpe-simulation-verification.json`. Le vérificateur ajoute par défaut1000comparaisons complètes à cinq ans (`--batch-count` permet de changer ce nombre). Lors de l'adoption v6 : neuf scénarios et un lot de25parcours contrôlés. Les anciens rapports BNP/Amundi/v4/v5 restent des archives, sans réécriture.

**Archive du générateur sur l’ancien ETF BNP ESE, avant remplacement par Amundi :** avec l’historique local du16/09/2013 au13/11/2026 (3361cours), tirages0à199, fréquence de drawdown du marché brut d’au moins30 % :

| Horizon | Tirages concernés /200 |
|---|---:|
| 1an | 9 |
| 3ans | 40 |
| 5ans | 60 |
| 10ans | 113 |

Ces comptes vérifient que de fortes baisses sont possibles sans survenir dans tous les tirages. Ce sont des propriétés de ce générateur sur cet historique, **pas des probabilités futures estimées**. Neuf scénarios supplémentaires exécutent le vrai moteur (graines0/1/42, horizons1/5/10ans) : version de politique exacte, capital initial100, ordres postérieurs au début, décalage signal/exécution, cash non négatif et métriques finies.

Les tests vérifient également la reproduction d’une graine, la stabilité du préfixe selon l’horizon, la différence entre tirages, les extrêmes non tronqués, les frais d’entrée, les titres entiers/fractionnaires, le rejet de données insuffisantes et la conservation des observations en base. Parcours navigateur : onglet réservé à la stratégie native, deux courbes/tableau, régénération, paramètres indépendants, conservation entre onglets, erreurs et relance, ordinateur/mobile.

## Accélération des lots — 15 novembre 2026

Le calcul multiple prépare une seule fois les contrôles de source, les dates,
les fenêtres centrées des régressions et l’état lent historique. Les opérations
NumPy évaluent ensuite 64 livres indépendants à la fois, avec les mêmes flux
aléatoires que les appels unitaires. Le calcul OLS et les transitions d’état
sont partagés avec la production ; près d’un seuil de décision, une réduction
scalaire évite qu’un arrondi de calcul matriciel change le signal. Le
rééquilibrage garde les 60 itérations de dichotomie de production, les frais,
les arrondis en titres entiers et l’ordre ventes puis achats par poche. Les
trimestres sont clôturés avant les transactions du jour, comme dans le moteur
complet. Aucun réglage de stratégie ou du générateur n’est modifié.

Les tests confrontent les douze métriques au moteur complet sur 48 cas
déterministes : quatre horizons, frais nuls/usuels/10 %, titres entiers ou
fractionnaires, capital de 1 € à 1 million et dates initiales mensuelles
différentes. Ils vérifient également l’indépendance selon le regroupement,
les historiques insuffisants, le bouclage des graines, les préfixes et l’arrêt
sur erreur ou déconnexion. Tolérance des métriques : relative 1e−10,
absolue 1e−9 ; nombres de victoires, égalités et paires valides identiques.

Mesure reproductible sur copie SQLite privée, PSP5 du 20/05/2014 au
13/11/2026 (3 197 observations), horizon de cinq ans, 10 000 € initiaux,
frais 0,12 %, titres entiers :

| Mesure | Résultat local |
|---|---:|
| Ancien calcul complet, 64 parcours | 15,490 s |
| Flux groupé, mêmes 64 graines | 0,537 s |
| Accélération sur ce même lot | ×28,84 |
| Flux groupé complet, 10 000 parcours | 58,842 s |
| Écart absolu maximal des moyennes sur les 64 paires | 3,33 × 10⁻¹⁶ |

Les comptes sont identiques sur les douze indicateurs. L’estimation de
40,3 minutes pour 10 000 parcours avec l’ancien calcul est une extrapolation
des 64 parcours, pas une mesure complète. Les temps comprennent la préparation,
le calcul, l’agrégation et la sérialisation/lecture NDJSON du flux en mémoire ;
ils excluent le réseau et le rendu navigateur et dépendent de la machine, de sa
charge et de l’horizon. Le rapport est distinct des archives financières :
`data/backtests/sp500-batch-performance.json`.

```sh
PYTHONPATH=backend .venv/bin/python scripts/benchmark_sp500_batch.py \
  --count 10000 --reference-count 64 \
  --output data/backtests/sp500-batch-performance.json
```

Vérifications logicielles : 483 tests backend, Ruff et six parcours navigateur
S&P ordinateur/mobile réussis. Il s’agit d’un audit d’équivalence et de temps
de calcul, pas d’une nouvelle validation financière de la stratégie.

## Limites

Le rééchantillonnage exploite uniquement les régimes présents dans l’historique PSP5 disponible : notamment, il ne recrée pas fidèlement une crise absente de cette période. Les raccords entre blocs interrompent les dépendances longues. La longueur63séances et le bruit5 % sont des hypothèses de simulation, pas des paramètres optimisés pour favoriser la stratégie. Même des blocs tirés d’un épisode réel ne reproduisent pas toute sa dynamique économique. Un scénario favorable, une faible volatilité ou de nombreux scénarios gagnants ne constituent pas une preuve prospective de surperformance.

## Archive : vérification Amundi/v4 du 14 novembre 2026

Cours PSP5 locaux : 20/05/2014–13/11/2026,3197observations. Neuf scénarios unitaires vérifiés (graines0/1/42 ×1/5/10ans), puis **1000parcours complets de cinq ans**, graines0à999,10000 € initiaux, frais0,12 %, titres entiers. Aucune erreur ni sélection de tirage.

| Indicateur | Buy & Hold moyen | Régression moyenne | Buy & Hold gagne | Régression gagne |
|---|---:|---:|---:|---:|
| CAGR | 15.15 % | 10.92 % | 85.5 % | 14.5 % |
| Drawdown maximal | -25.23 % | -19.17 % | 1.6 % | 98.4 % |
| Volatilité | 16.59 % | 12.29 % | 0.0 % | 100.0 % |
| Sharpe | 0.92 | 0.93 | 49.4 % | 50.6 % |
| Frais (€) | 11.95 | 44.42 | 100.0 % | 0.0 % |

1000paires valides pour ces lignes, aucune égalité. Le modèle montre ici surtout une réduction du risque : il ne démontre pas une supériorité générale de rendement. Les règles ne sont pas retouchées pour améliorer ces fréquences.

Le lot a pris environ267secondes sur cette machine, avec un instantané après chaque parcours. Un contrôle HTTP réel, sur copie privée avec serveur sans import, a reçu les états0/1/2 en0,006/0,273/0,534seconde ; une requête API parallèle a répondu en0,024seconde. Ces timings locaux ne sont pas des engagements de latence.

Diagnostic séparé du marché brut sur200tirages par horizon : DD≥30 % pour15/42/69/107parcours sur1/3/5/10ans respectivement. Pas de baisse imposée à chaque tirage, pas de probabilité future estimée.

## Allègement visuel demandé après les lots Amundi

L’interface n’affiche plus les paragraphes explicatifs sous le formulaire et les
résultats, le récapitulatif historique/parcours du tirage unitaire, la légende
textuelle des couleurs du tableau unitaire, ni la ligne « Capital final ».
Les deux courbes, leurs noms, les métriques, les paramètres et la graine des lots
restent disponibles. Le générateur, les règles, les graines transmises par l’API
et les calculs ne changent pas. Les conventions et limites restent documentées ici.

### Filtre de baisses + cinq modèles

La stratégie dispose aussi des deux onglets historique et simulation. Dans sa simulation, le mode multiple ouvre un lot de 1 000 parcours sur cinq ans. Chaque paire partage les mêmes clôtures synthétiques. La stratégie réchauffe ses cinq modèles sur tout le préhistorique PSP5 disponible, puis combine leur exposition avec le filtre de baisses sur 32 séances. Elle évalue sa cible à chaque clôture et exécute à la suivante, à l’initialisation puis dès que l’exposition s’écarte de la cible d’au moins cinq points. Le lot indique aussi le nombre de parcours où rendement annualisé et drawdown surpassent tous deux PSP5 passif. Les routes de simulation unitaire et multiple acceptent le champ `strategy: "downside"`.
