# S&P 500 : retard sur trois ans et initialisation de l’état

Étude du 14 novembre 2026. **Après présentation des résultats et limites,
l’utilisateur demande explicitement l’implémentation : v4 désormais active.**
La décision initiale de recherche était de conserver v3. L’utilisateur demande
d’approcher le rendement du S&P 500 sur trois ans sans trop augmenter les risques,
en préservant le compromis cinq/dix ans. Une piste réduit fortement le retard,
mais aucun des 99 ajustements ne satisfait tous les critères fixés avant calcul.

## Cause identifiée

Sur le test 13 novembre 2023–13 novembre 2026, la stratégie rapporte 8,97 %
annualisés contre 18,79 % pour ESE.PA. Son exposition moyenne reste voisine de
46 % ; sa volatilité et son drawdown sont bien moindres. La poche lente ne monte
sa cible qu’en mars 2026 ; la poche défensive, en juillet 2025.

Le moteur redémarre les deux états en mode défensif à chaque nouveau test,
sans reconstituer les décisions précédentes. Dans le test cinq ans, la poche
lente entre pourtant le 3 janvier 2023 après un signal à −2,08 σ et ne ressort
que le 3 décembre 2024. Le nouveau test trois ans ignore cet état historique et
commence avec une cible de 25 % au lieu de 100 % pour cette poche. Le franchissement
de zéro est aussi facile à manquer : il doit tomber sur la première séance du
mois en comparant deux séances consécutives.

La partie trois ans extraite du fonctionnement continu dix ans affiche +61,85 %
cumulés, contre +29,42 % pour un nouveau compte défensif trois ans. Ce sont deux
expériences différentes : conserver les positions acquises n’est pas démarrer
avec 10 000 € entièrement en liquidités.

## Hypothèses et sélection

100 configurations, dont le témoin actuel, soit 99 ajustements :

- Initialisation froide actuelle ou reconstitution de l’état lent avec les
  décisions mensuelles antérieures au départ.
- Entrée lente au franchissement quotidien actuel, entre décisions mensuelles,
  dans une zone positive 0–1 σ confirmée par tendance, ou au-dessus de moyenne
  mobile 100/200 séances avec momentum 63 séances positif.
- Sortie à +1,5/+2/+2,5 σ, ou sous moyenne mobile 50/100 après armement à +1,5 σ.
- Décision lente mensuelle ou vendredi fixe. Poche défensive inchangée.

La persistance des tendances motive les essais de suivi de tendance, sans valider
ces règles particulières : [Moskowitz, Ooi et Pedersen, Time Series Momentum](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum).
L’allocation longue ESE/liquidités ne réplique pas leur stratégie multi-marchés.

Sélection sur 2018-09-17–2020-12-31 et 2021-01-04–2023-12-29 seulement.
Par période : rendement au moins égal à l’actuelle moins 0,2 point annualisé,
drawdown aggravé d’au plus 0,5 point, volatilité au plus 120 % de l’actuelle,
Sharpe au moins égal à l’actuelle moins 0,05. Gain moyen d’au moins 0,5 point
annualisé ; classement par le moins bon gain, puis gain moyen.

Deux candidats admissibles, identiques sur ces deux périodes. Le premier dans
l’ordre de la grille est figé avant les résultats cibles : **initialiser l’état
lent avec les décisions passées, sans changer les seuils ni la cadence.**
Aucun candidat de remplacement n’est choisi après examen des résultats ultérieurs.

Adoption : rendement trois ans à moins de deux points annualisés de la référence ;
rendement cinq/dix ans conservé à 0,2 point près ; limites de drawdown, volatilité
et Sharpe ci-dessus sur les trois horizons ; au moins 12/14 fenêtres novembre
acceptables ; résistance aux frais doublés, délai supplémentaire et diagnostics USD.
Le protocole JSON est écrit avant les calculs. Les données historiques sont déjà
examinées ; aucune période n’est une nouvelle preuve prospective.

## Résultats de la piste figée

La reconstitution utilise uniquement les scores connus avant le départ. Elle
n’ajoute ni positions gratuites, ni gains passés, ni points de courbe avant le
départ : les 10 000 € sont investis à la clôture suivante, avec frais et titres
entiers. Seul l’état lent est reconstitué. La poche défensive conserve son état
initial et sa cadence ancrée au début du test.

| Indicateur sur trois ans | Actuelle | État lent reconstitué | Référence ESE |
|---|---:|---:|---:|
| Rendement annualisé | 8,97 % | **15,68 %** | 18,79 % |
| Rendement cumulé | 29,42 % | **54,81 %** | 67,63 % |
| Capital final | 12 941,82 € | **15 480,68 €** | 16 762,81 € |
| Volatilité annualisée | 6,52 % | 8,37 % | 14,15 % |
| Drawdown maximal | −7,51 % | **−7,02 %** | −23,28 % |
| Sharpe, taux sans risque nul | 1,335 | **1,760** | 1,272 |
| Frais cumulés | 61,55 € | 139,74 € | 49,73 € |

Cinq/dix ans : résultats strictement identiques à la production, soit
12,25/14,06 % annualisés, volatilité 8,33/9,71 %, drawdown −6,99/−8,85 %.
Un an : résultat inchangé, 14,33 % annualisés.

Frais 1 % : rendement trois ans 15,24 % contre 8,79 % pour l’actuelle.
Deux séances de délai : 15,39 % contre 8,67 %. Drawdowns légèrement meilleurs.
Sur cinq/dix ans, résultats inchangés sous les mêmes stress.

Sur l’indice USD, pas d’aggravation des drawdowns examinés : ceux-ci restent
cependant très élevés, autour de −51,52 % sur 2007–2009 et −57,18 % sur l’historique
long. Ce n’est pas un historique négociable de l’ETF PEA en EUR.

## Audit supplémentaire des départs

Après les premiers résultats, un protocole supplémentaire est écrit puis exécuté
pour la seule piste figée, sans nouvelle sélection : tous les départs mensuels
complets depuis janvier 2016, fenêtres de trois/cinq ans au 13 du mois.

166 fenêtres, fortement chevauchantes :

- 59 rendements annualisés améliorés, 107 identiques, aucun inférieur au témoin.
- 147/166 passent les limites combinées de rendement, volatilité, drawdown et Sharpe.
- 16 drawdowns légèrement plus profonds ; aggravation maximale de **0,138 point**
  sur cinq ans depuis juin 2020 (−7,13 % → −7,26 %). Aucun n’est aggravé de plus
  de 0,5 point. Ne pas annoncer des drawdowns toujours inférieurs.
- Volatilité augmentée jusqu’à environ +94 % relatif sur trois ans depuis février
  2023. Les 19 échecs aux limites combinées restent dans le rapport.
- Les 14 fenêtres novembre passent dans 13 cas ; l’échec est le trois ans récent.

## Décision et limites

**Décision initiale : aucune adoption automatique.** La piste figée échoue à deux critères du trois
ans cible : écart de rendement de 3,11 points annualisés à la référence, contre
deux autorisés ; volatilité augmentée de 28,42 %, contre 20 % autorisés.
Aucune autre configuration ne satisfait conjointement les critères des trois
horizons, même lors d’un examen descriptif après les résultats.

Cette piste réduit beaucoup le retard avec les mêmes seuils. Elle rapproche un
nouveau départ des décisions historiques d’une stratégie déjà en fonctionnement.
Elle expose davantage immédiatement si l’état hérité est investi ; cet héritage
peut être défavorable dans une autre histoire de prix. Ce n’est pas une amélioration
du fonctionnement continu d’un compte déjà investi.

Aucune promesse de surperformance ni validation prospective. Les paramètres et
l’univers ont déjà été largement examinés. Les fenêtres chevauchantes ne sont
pas 166 observations indépendantes.

## Reproduction et vérifications

```sh
PYTHONPATH=backend:scripts uv run python scripts/study_sp500_three_years.py
PYTHONPATH=backend:scripts uv run python scripts/audit_sp500_three_years.py
uv run pytest -q backend/tests/unit/test_sp500_three_years.py backend/tests/unit/test_sp500_next_iteration.py backend/tests/unit/test_sp500_study.py backend/tests/unit/test_etf_switch.py
uv run ruff check backend scripts
```

Base utilisateur ouverte en lecture seule et sauvegardée dans des copies SQLite
privées. Même empreinte que la vérification v3 archivée. Le témoin reproduit
les **19 cas de production** : CAGR, volatilité, Sharpe et drawdown à 1e−9 ;
frais à 1e−6 €. Capital 10 000 €, frais 0,5 % par côté, titres entiers,
exécution à la clôture suivante, budgets 75/25 indépendants, aucune compensation
d’ordres ni transfert, liquidités non rémunérées. Dates de l’application inchangées.
**63 tests ciblés réussis** : comptabilité et chronologie, pas rentabilité future.

Résultats complets ignorés par Git :
`data/backtests/sp500-three-years.json` et
`data/backtests/sp500-three-years-audit.json`.

## Adoption explicite ultérieure

L’utilisateur demande la mise en place après présentation des résultats et des
limites. La version `slow_defensive_warm_state_v4` reconstitue l’état initial
lent en rejouant ses décisions mensuelles strictement antérieures au début du
test. Les prix et scores de chaque signal utilisent uniquement son passé.
Les deux comptes démarrent avec leur capital neuf ; aucun titre, gain ou coût
antérieur n’est ajouté. La première allocation réelle suit les règles normales
d’exécution et de frais. État défensif initial de l’autre poche, seuils, cadences,
budgets indépendants, univers et périodes restent identiques.

L’adoption explicite ne transforme pas les critères initiaux en succès. Les
scripts de recherche conservent leur témoin v3 et leurs résultats négatifs.

`PYTHONPATH=backend uv run python scripts/verify_sp500_warm_state.py` vérifie
**20 cas figés** : cinq périodes principales, quatorze fenêtres novembre et un an.
Même base privée, indicateurs à 1e−9, frais et capital à 1e−6 €. La première valeur
reste 10 000 € et aucune transaction n’est antidatée. Sortie locale :
`data/backtests/sp500-warm-state-production-verification.json`.
