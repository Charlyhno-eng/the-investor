# Affinage de S&P 500 · Régression v4

Étude du 14 novembre 2026, après adoption explicite de `slow_defensive_warm_state_v4`. La production conserve cette version. La seule modification de l’application est la présentation du résumé : texte condensé, pleine largeur, deux lignes au format ordinateur testé, retour à la ligne naturel sur mobile.

## Protocole et reproduction

```sh
PYTHONPATH=backend:scripts uv run python scripts/study_sp500_v4_refinements.py
```

Le script écrit son plan, ses seuils et sa grille avant de lire les prix ou de calculer les résultats. Le rapport complet, ignoré par Git, est `data/backtests/sp500-v4-refinements.json`. Il contient toutes les configurations, tous les indicateurs et toutes les fenêtres, pas seulement les meilleurs résultats.

Référence : politique **actuellement active**, initialisation lente reconstituée comprise. Reproduction préalable des 20 cas de production archivés : indicateurs à 1e−9, frais et valeur finale à 1e−6 €. Empreinte du snapshot SQLite privé : `67cba9cbb59db6ed9ce518b29c8bf2861dd9348bc5fa55ded0df51cead49ce9f`. Source utilisateur ouverte en lecture seule et copiée ; aucune écriture dans la base utilisateur.

72 paramétrages supplémentaires, dont quatre redondances avec des changements isolés (68 variantes distinctes) :

- Poids initial lent : 50/60/65/70/80/85/90 %, sans transfert ultérieur.
- Plancher défensif par poche : 10/15/20/30/35 %.
- Entrée défensive par franchissement : −1/−0,75/−0,25/0 σ.
- Sortie de la seule poche défensive : +1/+1,25/+1,75/+2 σ.
- Décisions défensives toutes les une ou dix séances au lieu de cinq.
- 24 filtres de baisse : cours ajusté sous moyenne mobile 100/200 séances ET momentum 63 séances sous 0/−5 %, exposition plafonnée à 10/25/50 %, poche lente seule ou deux poches. Signaux évalués à la clôture, réduction et réentrée à une clôture ultérieure avec frais ; état logique de régression conservé.
- 26 combinaisons poids lent 65/75/85 %, plancher 15/25/35 %, sortie défensive +1,25/+1,5/+1,75 σ, hors référence.

Les défauts du moteur de recherche historique sont inchangés : les anciens rapports restent reproductibles. Les nouveaux paramètres sont facultatifs et n’entrent pas dans le moteur de l’application.

Hypothèses identiques : ESE.PA en EUR, 10 000 €, deux livres indépendants, titres entiers, frais 0,5 % à chaque achat/vente, clôture suivante, liquidités non rémunérées, aucun levier/netting/transfert. Scores, moyennes et momentum calculés avec les seules observations connues à la date du signal. Les nouveaux filtres de baisse modifient seulement la cible négociée, pas l’état logique ni les profits antérieurs.

Sélection avant lecture des résultats récents : sur 17/09/2018–31/12/2020 **et** 04/01/2021–29/12/2023, gain annualisé ≥0,25 point sur chaque période, aucun drawdown plus profond, volatilité ≤115 % du témoin, Sharpe ≥témoin−0,03. Classer par pire gain de rendement puis gain moyen. Une seule sélection figée, aucun remplacement après les audits.

Audit : mêmes exigences sur 3/5/10 ans ; au moins 90 % des 166 départs mensuels complets sur 3/5 ans conservent le rendement à 0,2 point près, le drawdown à 0,5 point près et la volatilité à +15 % relatif ; frais doublés et retard supplémentaire d’une séance sur 3/5/10 ans ; baisse maximale non aggravée sur les diagnostics USD 2000–2003, 2007–2009 et 1993–2026. Tout est testé pour tous les paramétrages, sans nouvelle sélection. Les 14 départs de novembre sont également archivés pour comparaison aux recherches antérieures.

## Résultat de la sélection fixée

Trois candidats passent les deux périodes de sélection. Celui figé avant l’audit : **85 % lent / 15 % défensif, plancher 15 %, sortie défensive +1,75 σ** (index 66).

| Horizon, fin 13/11/2026 | CAGR actuel → candidat | Drawdown actuel → candidat | Volatilité actuelle → candidat |
|---|---:|---:|---:|
| 3 ans, début 13/11/2023 | 15,68 → 16,50 % | −7,02 → −7,43 % | 8,37 → 8,63 % |
| 5 ans, début effectif 15/11/2021 | 12,25 → 12,83 % | −6,99 → −7,41 % | 8,33 → 8,32 % |
| 10 ans, début effectif 14/11/2016 | 14,06 → 14,27 % | −8,85 → −8,04 % | 9,71 → 9,47 % |

Échec : drawdowns plus profonds sur trois/cinq ans, gain dix ans sous le seuil de 0,25 point. Sur 166 fenêtres mensuelles : 152 gains annualisés, 14 pertes de rendement, 65 drawdowns plus profonds, aggravation maximale 0,89 point ; seulement 143/166 fenêtres passent les tolérances combinées. Même problème de drawdown récent avec frais doublés ou retard supplémentaire. Sur l’indice USD long : CAGR 6,87 → 6,67 %, drawdown −57,18 → −59,41 %. Aucun candidat ne passe tous les critères d’audit.

## Deux pistes plus modestes, exploratoires

La condition de gain minimal n’est pas nécessaire pour observer des améliorations modestes. Les deux pistes ci-dessous améliorent le rendement et préservent ou réduisent le drawdown sur les trois horizons récents. Elles sont relevées **après** examen des résultats, ne passent pas la sélection initiale et ne remplacent pas le candidat figé.

A : seule la sortie défensive passe de +1,5 à **+1,75 σ** (index 19 ; index 60 équivalent).

B : même sortie défensive à +1,75 σ **et plancher des deux poches de 25 à 15 %** (index 58), budgets toujours 75/25.

| Horizon | Actuelle : CAGR / DD | A : CAGR / DD | B : CAGR / DD |
|---|---:|---:|---:|
| 3 ans | 15,68 / −7,02 % | 16,13 / −7,02 % | 15,77 / −6,84 % |
| 5 ans | 12,25 / −6,99 % | 12,45 / −6,98 % | 12,57 / −6,80 % |
| 10 ans | 14,06 / −8,85 % | 14,22 / −8,80 % | 14,14 / −8,04 % |

Pour A, volatilités 3/5/10 ans 8,74/8,47/9,76 %, contre 8,37/8,33/9,71 % actuellement. Gain annualisé sur 143/166 fenêtres, quatre pertes et 19 égalités, mais drawdown aggravé dans **43/166**. Contre-exemple : départ janvier 2017 sur cinq ans, drawdown **−8,84 → −15,21 %**, malgré un CAGR amélioré 14,23 → 15,30 %. Le cas récent favorable ne suffit donc pas. Les gains sur 3/5/10 ans persistent à frais doublés et avec une séance de retard. Diagnostic USD long meilleur (CAGR 6,87 → 7,26 %, DD −57,18 → −57,09 %), sans annuler les contre-exemples ESE.

Pour B, volatilités 3/5/10 ans réduites à **8,34/8,02/9,30 %**. Cependant 86 gains et 80 pertes de rendement sur les fenêtres mensuelles, drawdown aggravé dans 15/166 ; départ octobre 2016 sur cinq ans : **−8,84 → −12,60 %**. Rendement annuel d’une fenêtre trois ans depuis février 2016 : **6,69 → 5,69 %**. Sur USD long : CAGR 6,87 → 6,69 %, DD −57,18 → −58,37 %. Les frais doublés et le retard ne détruisent pas les gains récents, mais ne corrigent pas cette fragilité.

## Autres essais

- Plancher seul réduit à 20 % : DD 3/5/10 ans −6,93/−6,90/−8,05 %, mais CAGR 15,49/12,30/14,02 %. Trois drawdowns mensuels très légèrement aggravés, rendement inférieur dans 100/166 fenêtres. Risque récent plus bas, gain de rendement non général.
- Décision défensive quotidienne : DD trois ans passe à −9,68 %, CAGR cinq/dix ans diminue ; plus de réactivité ne garantit pas de protection.
- Décision toutes les dix séances : CAGR trois ans 16,12 %, mais cinq/dix ans seulement 11,85/13,18 %.
- Exemple filtre MA200 et momentum <−5 %, plafond 25 % pour les deux poches : CAGR dix ans **12,24 %** contre 14,06 %, 158 pertes de rendement sur 166 fenêtres, 85 drawdowns aggravés. Il réduit fortement le drawdown du diagnostic USD 2007–2009 (−51,52 → −33,52 %), mais les faux signaux/réentrées et les frais dégradent d’autres épisodes. Ne pas sélectionner une seule crise favorable.

## Décision et limites

**Conserver la politique active v4.** Les petites pistes A/B méritent d’être documentées, pas présentées comme des améliorations robustes ni intégrées automatiquement. Aucune des variantes testées n’atteint tous les critères annoncés. L’absence de succès dans cette grille ne démontre pas qu’aucune amélioration n’existe.

Les fenêtres se chevauchent et les historiques ont déjà servi à de nombreuses recherches. Ce sont des diagnostics rétrospectifs, pas une validation future. L’indice total-return USD est un test distinct, pas l’historique négociable de l’ETF PEA en EUR. Les tests logiciels vérifient la comptabilité et l’absence d’anticipation dans les scénarios contrôlés ; ils ne prouvent pas la performance financière.

Vérifications : 20 équivalences historiques avec la production, 24 tests unitaires ciblés sur les livres/signaux/reconstitution/frais/délais et nouveaux filtres, Ruff backend/scripts, contrôle complet frontend (37 tests unitaires et build), 24 parcours navigateur ordinateur/mobile. Le parcours S&P vérifie la pleine largeur du résumé et au plus deux lignes sur le format ordinateur testé, sans tronquer le texte sur mobile.
