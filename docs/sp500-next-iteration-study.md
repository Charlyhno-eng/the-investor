# S&P 500 : sorties, réentrées et coûts de risque

Historique de la v3, ensuite remplacée par la v4 à état initial lent reconstitué :
voir `docs/sp500-three-year-study.md`. Les comparaisons ci-dessous restent figées.

## Décision

Recherche supplémentaire du 14 novembre 2026 après adoption de
`slow_defensive_v2`. La décision initiale était de conserver la production.
**Après présentation des limites, l’utilisateur a explicitement demandé
l’implémentation : la réentrée à 0 σ est désormais active sous
`slow_defensive_reentry_v3`.**
L’interface est simplifiée séparément : titre unique, texte qui revient à la ligne,
plus de badge « Incluse dans l’application », encadré de couleur dans la liste.

792 configurations de la combinaison existante sont examinées. Aucune ne remplit
les critères de sélection définis avant calcul sur les deux premières périodes.
Une piste améliore les cinq et dix ans, mais n’est identifiée qu’en regardant ces
résultats après l’échec initial. Elle reste documentée comme diagnostic exploratoire,
sans remplacement silencieux du candidat ni assouplissement des critères d’adoption.
Son adoption ultérieure relève de l’instruction explicite de l’utilisateur ; elle
ne signifie pas que les critères initiaux ont été satisfaits.

## Hypothèses et protocole

Capital initial 10 000 €, ESE.PA en EUR, titres entiers, frais 0,5 % à chaque achat
et vente, exécution à la clôture suivante, liquidités non rémunérées. Deux budgets
indépendants, sans transferts, levier ni compensation d’ordres opposés. Historique
source ouvert en lecture seule et sauvegardé dans une copie SQLite privée.

La nouvelle simulation de recherche reproduit les indicateurs de **15 cas du moteur
actuel**, aux tolérances de 1e−9 pour CAGR/volatilité/Sharpe/drawdown et 1e−6 € pour
les frais. L’empreinte de la base complète a changé depuis l’étude précédente ;
la comparaison est donc refaite avec le moteur de production sur la copie courante,
sans supposer que les anciennes données sont encore strictement identiques.

Familles examinées :

- Sortie au seuil actuel, après repli de score 0,5/1 σ, ou après rupture de moyenne
  mobile 50/100/200 séances une fois le seuil +1,5 σ dépassé. Modification de la
  poche lente seule ou des deux poches.
- Réentrée lente supplémentaire au franchissement haussier de 0 σ, ou lors d’une
  reprise au-dessus de moyenne mobile 100/200 séances avec momentum 63 séances
  positif et score inférieur à +0,5 σ. L’entrée originale sous −2 σ est conservée.
- Cible défensive de 25/35/45 %, budget initial lent de 50/75/90 %.
- Cadence défensive historique ou vendredi fixe. Le calendrier mensuel lent reste
  inchangé. Les règles de recherche ne modifient pas les règles de l’application.

Sélection : 2018-09-17–2020-12-31 et 2021-01-04–2023-12-29. Gain annualisé d’au
moins 0,5 point dans chacune, aucun drawdown plus profond, volatilité au plus
115 % de l’actuelle, Sharpe au moins égal à l’actuelle moins 0,03 ; classement par
le moins bon gain des deux périodes, puis Sharpe. **Aucun candidat admissible.**

Garde-fous d’adoption définis avant les résultats : gain d’au moins 0,3 point,
drawdown non aggravé et mêmes contraintes volatilité/Sharpe sur 2024+, cinq et dix
ans ; au moins 12/14 fenêtres glissantes respectant les tolérances inscrites dans
le script ; maintien du compromis sous frais 1 % et deux séances de décalage ;
absence de forte dégradation des drawdowns sur les diagnostics USD longs.
Les périodes historiques ont déjà été examinées : aucune n’est une nouvelle preuve
prospective. Les fenêtres glissantes se chevauchent.

## Piste exploratoire : réentrée lente au franchissement de 0 σ

Même combinaison 75/25 et mêmes paramètres ; une seule règle supplémentaire :
lors d’une décision mensuelle, la poche lente peut également entrer si le score
était strictement négatif à la séance précédente et atteint 0 σ ou plus.
Ce n’est ni un franchissement entre deux décisions mensuelles ni une entrée
permanente dès que le score devient positif.

| Indicateur | Actuelle 5 ans | Piste 5 ans | Actuelle 10 ans | Piste 10 ans |
|---|---:|---:|---:|---:|
| CAGR | 10,33 % | 12,25 % | 13,07 % | 14,06 % |
| Volatilité | 7,46 % | 8,33 % | 9,35 % | 9,71 % |
| Drawdown | −6,99 % | −6,99 % | −8,85 % | −8,85 % |
| Sharpe | 1,333 | 1,406 | 1,340 | 1,382 |
| Capital final | 16 334,61 € | 17 808,54 € | 34 151,27 € | 37 248,01 € |

Fin au 13 novembre 2026 ; débuts théoriques novembre 2021/2016 reportés à la
première cotation observée. Aucune nouvelle période favorable dans l’interface.

Le gain résiste aux frais doublés : CAGR 11,86/13,67 % contre 9,99/12,71 % pour
l’actuelle. Avec une séance supplémentaire : 11,99/13,76 % contre 10,18/12,85 %.
Les drawdowns restent égaux à ceux de l’actuelle sur ces deux stress.

Mais les limites sont déterminantes :

- Résultats **strictement identiques** à l’actuelle sur les deux périodes de
  sélection ; aucun gain justifiant la sélection avant de regarder la suite.
- Sur 2024+, volatilité 6,01 % contre 4,16 %, soit environ +44 % relatif :
  dépassement du budget relatif préfixé, même si l’écart absolu reste de 1,85 point.
- 13/14 fenêtres respectent le compromis toléré ; les résultats de 12 fenêtres
  sont identiques à l’actuelle. Le compteur ne représente donc pas treize gains
  indépendants. La fenêtre trois ans depuis novembre 2023 échoue sur la volatilité
  (6,52 % contre 4,82 %, environ +35 % relatif).
- Contrôle américain total-return USD 1993–2026 : CAGR 6,87 % contre 7,07 % ;
  drawdowns très proches autour de −57,18 %. Les crises 2000–2003 et 2007–2009
  restent identiques. L’indice USD est un diagnostic, pas l’historique de l’ETF PEA.
- Sur dix ans la piste reste sous le témoin ESE (14,52 % annualisés dans l’audit
  précédent) ; aucun dépassement général du S&P 500 n’est démontré.

Un diagnostic supplémentaire de sensibilité, explicitement décidé après le premier
résultat, examine aussi les franchissements −0,5/−0,25/0/+0,25/+0,5 σ sans modifier
les autres paramètres. Toutes les sorties sont conservées sous `sensitivity` ;
ces essais ne servent pas à remplacer rétrospectivement la sélection initiale.

| Seuil de réentrée supplémentaire | CAGR 5 ans | Drawdown 5 ans | CAGR 10 ans | Drawdown 10 ans |
|---|---:|---:|---:|---:|
| −0,5 σ | 10,33 % | −6,99 % | 11,29 % | **−21,84 %** |
| −0,25 σ | 10,33 % | −6,99 % | 13,07 % | −8,85 % |
| 0 σ | 12,25 % | −6,99 % | 14,06 % | −8,85 % |
| +0,25 σ | 12,56 % | −7,13 % | 14,22 % | −8,85 % |
| +0,5 σ | 10,33 % | −6,99 % | 13,07 % | −8,85 % |

Le gain disparaît de part et d’autre de la zone 0/+0,25 σ sur les deux horizons ;
le seuil −0,5 σ augmente fortement les pertes dix ans. La trajectoire d’une règle
à hystérésis dépend aussi de l’état acquis dans chaque simulation, d’où des effets
qui ne sont pas monotones avec le seuil. Cette sensibilité renforce la décision
initiale de conserver v2 ; elle reste valable comme limite de la v3 ensuite
explicitement adoptée par l’utilisateur.

## Reproduction

```sh
PYTHONPATH=backend:scripts uv run python scripts/study_sp500_next_iteration.py
uv run pytest -q backend/tests/unit/test_sp500_next_iteration.py backend/tests/unit/test_sp500_study.py backend/tests/unit/test_etf_switch.py
```

Sortie locale ignorée par Git : `data/backtests/sp500-next-iteration.json`.
Le protocole et la sélection sont écrits avant les calculs suivants. Tous les
paramètres, métriques, stress, contre-exemples et diagnostics additionnels sont
conservés. Les tests logiciels vérifient la comptabilité et l’ordre temporel ;
ils ne valident pas la rentabilité future d’une stratégie.

## Adoption explicite ultérieure

L’utilisateur demande l’implémentation après présentation des résultats et limites.
La version `slow_defensive_reentry_v3` ajoute exactement le franchissement haussier
de 0 σ à l’entrée lente sous −2 σ ; autres paramètres, budgets, frais, cadence et
périodes inchangés. Le moteur compare la séance précédant le signal mensuel au
signal lui-même. Il ne mémorise pas les franchissements en milieu de mois et ne
rentre pas simplement parce que le score est positif. La poche défensive reste
identique. Les critères de recherche et leurs échecs ci-dessus sont conservés.

`PYTHONPATH=backend uv run python scripts/verify_sp500_reentry.py` vérifie les
19 cas figés contre le moteur, sur copie privée de la base. Sortie locale :
`data/backtests/sp500-reentry-production-verification.json`. Le moteur reproduit
CAGR/volatilité/Sharpe/drawdown à 1e−9 et frais/capital final à 1e−6 €.
