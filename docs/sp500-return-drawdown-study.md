# S&P 500 : davantage de rendement sans aggraver le drawdown

## Résultat

Historique de la combinaison v2. La production utilise désormais sa variante
avec réentrée à 0 σ, explicitement demandée par l’utilisateur ; voir
`docs/sp500-next-iteration-study.md` et `docs/validation.md`.

Le relâchement de la contrainte de volatilité révèle une **piste de compromis
historique**, mais pas une stratégie parfaite ni validée pour l’avenir.
Après présentation des limites, l’utilisateur a explicitement demandé son
adoption : la combinaison ci-dessous est désormais intégrée. Les cinq ans par
défaut et les choix 1/3/5/10 ans sont conservés.

Deux campagnes supplémentaires : 22 680 règles, puis 309 combinaisons entre des
règles présélectionnées et la variante défensive actuelle. Une analyse exploratoire
identifie 12 combinaisons dont le rendement est légèrement supérieur sur cinq et
dix ans sans drawdown plus profond sur ces deux horizons. Leur découverte utilise
ces résultats ESE : **ce n’est pas une validation indépendante**.

La combinaison au meilleur gain minimum entre les deux horizons est :

- 75 % du capital initial dans une règle lente : régression logarithmique cinq ans,
  entrée sous −2 σ, sortie au-dessus de +1,5 σ, cible défensive de 25 %, décisions
  à la première séance du mois, exécution à la clôture suivante.
- 25 % du capital initial dans la variante défensive existante : régression
  18 mois, rebond −0,5 σ, sortie +1,5 σ, cible défensive 25 %, cadence existante
  toutes les cinq séances depuis le début de simulation.

Les deux poches détiennent **le même ESE et des liquidités**. Les pourcentages
75/25 répartissent le capital au départ ; ils ne sont pas rétablis ensuite. Les
poches évoluent indépendamment, sans transferts de cash. Il ne s’agit ni de deux
ETF ni d’une exposition fixe de 75 % au marché.

## Comparaison après frais

ESE en EUR, capital total 10 000 €, titres entiers, commissions de 0,5 % par montant
acheté/vendu, liquidités non rémunérées, sans levier. Chaque poche utilise son
capital réellement attribué pour acheter ses titres entiers. Tous les frais sont
comptés, même si les poches passent des ordres opposés : absence de compensation,
hypothèse conservatrice. Les statistiques sont calculées sur la somme quotidienne
des valeurs des deux poches, pas sur la moyenne des rendements ou des drawdowns.

Fin le 13/11/2026, début théorique le 13/11/2021 ou 13/11/2016, report à la première
cotation ESE suivante (15/11/2021 ou 14/11/2016). Simulations indépendantes depuis
le cash, aucune période spéciale imposée dans l’interface.

| Indicateur | Actuelle, cinq ans | Combinaison, cinq ans | Actuelle, dix ans | Combinaison, dix ans |
|---|---:|---:|---:|---:|
| Rendement annualisé | 9,76 % | **10,33 %** | 12,67 % | **13,07 %** |
| Volatilité | 7,25 % | 7,46 % | 9,98 % | **9,35 %** |
| Perte maximale | −7,13 % | **−6,99 %** | −15,05 % | **−8,85 %** |

L’amélioration de rendement est modeste : environ +0,56 point annualisé sur cinq
ans et +0,41 point sur dix ans. Le précédent objectif de 14 % n’est pas atteint.
Le gain de drawdown sur cinq ans est également modeste : environ 0,15 point.

## Recherche et critères, dans l’ordre réel

Les protocoles sont écrits dans les sorties avant chaque calcul. Copie privée
SQLite, connexion source en lecture seule, aucune modification de la base utilisateur.
Empreinte : `3828d8f2e06fa105c15379ab28b7959e2deb34f373d1a8dd82e75fd013da724a`.

### 1. Règles individuelles

Fenêtres 6/12/18/24/36/60 mois ; huit seuils d’entrée de −2 à +1,5 σ ; six seuils
de sortie de +0,5 à +3 σ, entrée strictement inférieure à sortie ; sortie directe
ou après repli de 0,5/1 σ ; entrée sous le seuil ou après franchissement haussier ;
planchers défensifs 10/25/40/55/70 %. Décisions quotidiennes, le vendredi, ou à la
première séance du mois. Ces calendriers sont indépendants du zoom de graphique ;
la cadence de la référence actuelle conserve sa convention réelle.

Budget de volatilité relevé à 130 % de celui de l’actuelle (augmentation relative,
pas +30 points). Drawdown au plus égal à celui de l’actuelle et gain de rendement
annualisé d’au moins 0,5 point sur apprentissage 2018–2020 et sélection 2021–2023.
Les périodes démarrent chacune en cash. Les dates étaient déjà toutes connues :
recherche rétrospective, aucune nouvelle période future inconnue.

103 règles satisfont ces deux périodes. Le classement par le moins bon gain de
rendement des deux retient une règle cinq ans, entrée −1,5 σ, sortie +0,5 σ,
plancher 10 %, décisions le vendredi. Après choix figé :

- Cinq ans : 13,75 % annualisés, volatilité 9,56 %, drawdown −8,62 %.
- Dix ans : 12,41 % annualisés, volatilité 9,92 %, drawdown −10,99 %.

Le drawdown est plus profond sur cinq ans et le rendement inférieur sur dix ans :
rejet. Même dans toute la grille, aucune règle ne gagne sur les deux horizons avec
drawdown non aggravé et ce budget de volatilité, y compris en supprimant le seuil
arbitraire de gain de 0,5 point.

Une fenêtre cinq ans n’existe pas encore pour ESE en novembre 2016 (premières
cotations en septembre 2013). La composante lente reste à sa cible défensive tant
que son signal manque ; aucun historique n’est inventé. C’est une limite concrète
pour interpréter le test dix ans et pour comparer des dates de démarrage.

### 2. Combinaisons

Chacune des 103 règles qualifiées est combinée à l’actuelle avec 25/50/75 % du
capital initial : 309 simulations de politiques. Même critère de sélection sur
les deux premières périodes : 258 qualifiées. La combinaison initialement retenue
ne passe pas les critères sur cinq/dix ans. Aucune ne gagne au moins 0,5 point
sur les deux horizons sans aggraver le drawdown : pas d’adoption.

### 3. Audit des gains plus modestes

Un audit **ajouté après ces résultats**, explicitement exploratoire, supprime
uniquement le seuil de gain de 0,5 point et exige un gain strictement positif.
12 combinaisons améliorent alors rendement et drawdown sur cinq/dix ans. La piste
présentée en tête est choisie par le meilleur de leurs gains minimums. Cette
sélection regarde ces résultats : elle ne peut pas être appelée « hors échantillon ».
Les vérifications complémentaires restent des diagnostics, pas une preuve nouvelle.

## Robustesse de la piste présentée

| Hypothèse | CAGR cinq ans, mix / actuelle | Drawdown cinq ans, mix / actuelle | CAGR dix ans, mix / actuelle | Drawdown dix ans, mix / actuelle |
|---|---:|---:|---:|---:|
| Frais doublés à 1 % | 9,99 / 8,99 % | −7,01 / −7,13 % | 12,71 / 12,02 % | −8,84 / −15,36 % |
| Retard supplémentaire d’une séance | 10,18 / 9,49 % | −6,97 / −7,13 % | 12,85 / 12,75 % | −8,80 / −13,60 % |

Le compromis subsiste sous ces deux stress sur les horizons étudiés.

Sur quatorze fenêtres annuelles de trois/cinq ans, **dix** satisfont simultanément
rendement au moins égal, drawdown au plus égal et volatilité dans le budget.
Les quatre échecs sont conservés :

- Trois ans depuis novembre 2018 : rendement supérieur et drawdown moindre, mais
  hausse de volatilité supérieure au budget de 30 % relatif.
- Trois ans depuis novembre 2021 : drawdown **−6,99 % contre −4,34 %**, malgré
  un meilleur rendement. C’est un contre-exemple direct à « jamais plus de drawdown ».
- Trois ans depuis novembre 2022 : rendement supérieur et drawdown moindre, mais
  volatilité supérieure au budget.
- Trois ans depuis novembre 2023 : rendement inférieur (6,28 % contre 9,01 %).

Ces fenêtres se chevauchent ; dix sur quatorze n’est pas une probabilité de succès.
Le seuil de 75 % prévu avant vérification n’est pas atteint (71,4 %).

Sur l’indice total-return américain **en USD**, utilisé uniquement pour un contrôle
long et non comme historique de l’ETF PEA :

| Période | CAGR mix / actuelle | Drawdown mix / actuelle |
|---|---:|---:|
| 2000–2003 | −4,99 / −5,02 % | **−43,11 / −35,67 %** |
| 2007–2009 | −6,79 / −10,41 % | −51,52 / −51,67 % |
| 1993–2026 | 7,07 / 5,54 % | **−57,18 / −55,25 %** |

Le contrôle long apporte deux autres contre-exemples de pertes maximales plus
profondes. Le mix ne satisfait donc pas la contrainte de protection générale,
même si son compromis est plus favorable sur les deux horizons ESE récents.

## Décision initiale de recherche

À l’issue de l’étude, piste conservée pour recherche, sans installation automatique.
Le progrès historique existe, mais le gain est modeste, la sélection exploite des
données déjà examinées et les drawdowns sont plus élevés dans plusieurs autres
fenêtres. Aucun plafond de pertes futures ni rendement de 14 % n’est garanti.

Il serait trompeur d’appeler cette combinaison le compromis parfait ou de cacher
les fenêtres qui échouent.

### Adoption explicite ultérieure

Après présentation de ces résultats et limites, l’utilisateur a demandé
l’implémentation. La combinaison 75 % lente / 25 % défensive remplace donc
l’ancienne méthode dans l’application sous la version `slow_defensive_v2`.
Les paramètres restent ceux de l’audit, sans nouvelle optimisation ni date
spéciale. Cinq ans restent sélectionnés par défaut ; choix 1/3/5/10 ans conservés.
Les budgets sont indépendants, arrondis et frais calculés par poche, sans transfert.
Les contre-exemples et conclusions de robustesse ci-dessus restent valables.
Voir `docs/validation.md` pour le protocole actif.

## Reproduction et contrôles

```sh
PYTHONPATH=backend:scripts uv run python scripts/study_sp500_return_drawdown.py
PYTHONPATH=backend:scripts uv run python scripts/study_sp500_compromise_blends.py
PYTHONPATH=backend:scripts uv run python scripts/audit_sp500_compromise.py
PYTHONPATH=backend uv run python scripts/verify_sp500_compromise.py
uv run pytest -q backend/tests/unit/test_sp500_study.py backend/tests/unit/test_sp500_adaptive_risk.py
```

Résultats locaux ignorés par Git : `data/backtests/sp500-return-drawdown.json`,
`data/backtests/sp500-compromise-blends.json`, `data/backtests/sp500-compromise-audit.json`.
Tous les paramètres, échecs, métriques et stress sont conservés. Les changements
au simulateur de recherche sont optionnels (calendrier et capital initial) ; ses
conventions précédentes sont préservées. Le moteur de production reproduit
maintenant la combinaison adoptée ; les 15 cas de l’audit figé concordent à 10⁻⁹
pour les indicateurs et à 10⁻⁶ € pour les frais et le capital final.

Les tests vérifient notamment l’équivalence des deux poches de recherche au moteur
de production en titres entiers et fractionnaires, y compris avant maturité de
la fenêtre lente et hors première séance du mois, l’absence de données futures, le capital réellement alloué à une poche
et le drawdown calculé sur les valeurs quotidiennes combinées plutôt que sur une
moyenne erronée de drawdowns individuels. 
