# Adoption de la régression orientée Sharpe — v6

Le 15 novembre 2026, après présentation des deux candidats et de leurs limites,
l'utilisateur demande la mise en place du candidat recommandé : **régression
sans poche passive, budgets 75/25, plancher d'exposition 10 %**.
La politique active devient **`slow_defensive_sharpe_v6`**, en remplacement de
`core35_slow_defensive_v5`. La priorité de recherche reste le seul ratio de
Sharpe, avec la convention actuelle de taux sans risque nul.

## Règles adoptées

PSP5.PA, Amundi PEA S&P 500 UCITS ETF Acc, historique propre en EUR. Deux
budgets indépendants au départ : **75 % lente, 25 % défensive**, chacun avec
ses titres, liquidités, arrondis et frais. Aucune poche passive, aucun transfert
ni rééquilibrage entre les deux budgets ; leurs poids dérivent ensuite.

Chaque poche vise **10 % d'ETF en état défensif et 100 % en état investi**.
La cible n'est appliquée qu'à l'initialisation ou lors d'un changement d'état,
sans rééquilibrage pour corriger une dérive ultérieure. Ce plancher est une
cible d'exposition, pas une limite de perte.

- Lente : régression logarithmique native 60 mois, au moins 501 observations et
  fenêtre complète. Entrée strictement sous −2σ ou au franchissement haussier
  de 0σ entre deux séances consécutives, constaté à la première séance du mois.
  Sortie strictement au-dessus de +1,5σ, même calendrier mensuel.
- Défensive : régression native 18 mois, au moins 251 observations et fenêtre
  complète. Entrée au franchissement haussier de −0,5σ ; sortie strictement
  au-dessus de +1,5σ. Décisions toutes les cinq séances depuis le début du test.
- Avant le début, reconstituer seulement l'état lent avec les décisions
  mensuelles strictement antérieures. Aucun gain, position ou frais antérieur
  ajouté. La poche défensive démarre défensive. En l'absence de score lent
  exploitable, sa cible initiale reste 10 % ; validation admissible dès 18 mois.

Même moteur pour validation, simulation unitaire et simulation multiple.
Exécution à la clôture suivante, frais par défaut 0,12 % par achat/vente,
paramètres explicites conservés, frais séparés même pour des ordres opposés,
titres entiers par poche. Aucun changement de générateur, graine, instrument,
calcul des indicateurs ou choix de périodes 1/3/5/10 ans, cinq ans par défaut.
Aucune modification de la base utilisateur ni de ses quantités.

## Résultats et limites conservées

La [recherche Sharpe](sp500-sharpe-study.md) classe ce candidat par moyenne des
Sharpe historiques 3/5/10 ans : 1,576 contre 1,288 pour v5. Le portefeuille
global exécuté est mesuré, pas une moyenne des ratios des poches.

| Historique au 13/11/2026 | Sharpe v5 | Sharpe v6 | CAGR v6 | DD v6 |
|---|---:|---:|---:|---:|
| 3 ans | 1,6121 | 1,8875 | 15,52 % | −6,77 % |
| 5 ans | 1,1407 | 1,4873 | 12,51 % | −6,78 % |
| 10 ans | 1,1111 | 1,3520 | 11,72 % | −7,99 % |

24/24 fenêtres réelles cinq ans ont un Sharpe supérieur, avantage conservé
avec frais doublés et retard supplémentaire en recherche. Ces données ont
servi à la sélection et se chevauchent : elles ne sont pas prospectives.

**Le désaccord synthétique demeure :** sur les 300 parcours réservés cinq ans,
Sharpe 0,853 contre 0,919 v5 ; sur les 100 dix ans, 0,803 contre 0,903.
Respectivement 98 et 14 victoires, IC95 % des gains entièrement négatifs.
Le nouveau critère ne transforme pas cet échec de Sharpe dans le modèle en
succès. L'adoption répond à la décision utilisateur après présentation de cette
limite ; elle ne démontre pas un meilleur Sharpe futur. Les anciens rapports
JSON restent inchangés, y compris leur décision de non-adoption à leur date.

## Vérification de l'implémentation

`PYTHONPATH=backend:scripts .venv/bin/python scripts/verify_sp500_sharpe.py`

Sur copie SQLite privée : **18 cas** — historique 1/3/5/10 ans avec frais
0/0,12/0,24 %, puis six parcours synthétiques figés cinq/dix ans. Comparaison
au moteur indépendant et aux résultats archivés du candidat avant adoption,
métriques à 1e−9, frais à 1e−6 €. Contrôle des deux livres sans cash négatif,
sans poche passive et sans position/gain avant le début. Rapport distinct
`data/backtests/sp500-sharpe-production-verification.json`.

Le stress de retard de l'étude reste une expérience du moteur de recherche ;
l'API de production conserve obligatoirement la clôture suivante.

Le vérificateur générique de simulations utilise aussi v6 et écrit désormais
`data/backtests/sp500-sharpe-simulation-verification.json` : neuf scénarios
unitaires et, lors de cette adoption, un lot logiciel de 25 parcours cinq ans.
Son défaut reste 1 000 parcours, sans filtrage. Ce petit lot vérifie les calculs
et l'agrégation ; les 400 parcours de recherche réservés restent la référence
pour le diagnostic financier défavorable déjà publié.

Les tests conservent les contrôles de causalité, titres entiers/fractionnaires,
rejeu lent, absence de transfert, dividendes séparés et ordres opposés facturés.
Les contrôles logiciels réussis ne constituent pas une validation financière.
Le vérificateur `verify_sp500_core35.py` est désormais une archive v5 protégée
contre une réécriture sous v6. Les témoins v5 des campagnes Sharpe restent
historiques ; leurs contrôles embarqués contre la production v5 ne vérifient
plus la politique courante.

Vérifications de cette adoption : **462 tests backend réussis**, Ruff,
**40 tests unitaires frontend**, lint/format/code inutilisé et build réussis.
Parcours navigateur ordinateur/mobile : 29/30 réussis au lot, avec un délai
expiré dans le test annexe des quantités verrouillées ; ce dernier a réussi
isolément. Tous les parcours S&P, dont les cibles affichées à10%, ont réussi.
