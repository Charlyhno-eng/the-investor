# S&P 500 — objectif unique de ratio de Sharpe

**Mise à jour après recherche :** le candidat historique a ensuite été adopté
à la demande de l'utilisateur comme [régression orientée Sharpe v6](sp500-sharpe-adoption.md).
Les protocoles, décisions initiales et résultats ci-dessous restent ceux de la
recherche avant adoption ; les rapports JSON et leurs échecs ne sont pas réécrits.

Le 15 novembre 2026, l'utilisateur remplace explicitement l'objectif précédent
de rendement et de drawdown par **maximiser le ratio de Sharpe uniquement**.
Les contraintes sans levier ni vente à découvert restent applicables. Il n'y a
plus de plancher de CAGR, de plafond de drawdown, ni de critère Sortino/Calmar.
Le rendement et les pertes sont publiés pour comprendre le résultat, sans
filtrer ou départager les candidats. La recherche ne remplace pas automatiquement
la politique de production v5.

**Bilan de cette campagne :** un mélange adaptatif de modèles passe le protocole
de gain de Sharpe moyen dans le simulateur (+0,03084/+0,03238 sur cinq/dix ans),
mais perd sur cinq/dix ans réels. La meilleure régression historique fait
l'inverse : Sharpe supérieur sur les fenêtres réelles, inférieur dans le modèle.
Deux sélections distinctes, **200 nouveaux parcours de sélection et 1 700
réservés**, rapports intégraux conservés. **Décision initiale avant la demande
d'adoption : v5 conservée.**

## Mesure et périmètre

La convention de l'application reste :

`Sharpe = sqrt(252) × moyenne(rendements quotidiens simples nets) / écart-type échantillonnal`.

Le taux sans risque et la rémunération des liquidités sont nuls. Ce résultat
n'est donc pas un Sharpe historique calculé avec une série de taux EUR.
Il ne faut pas le remplacer par CAGR/volatilité. Diluer une exposition constante
avec des liquidités ne change pas le Sharpe théorique sans frais à taux nul ;
les écarts de timing, frais et arrondis peuvent en revanche le changer.
Un portefeuille à variance nulle a un ratio indéfini, jamais un Sharpe infini.

La [définition de William Sharpe (1994)](https://web.stanford.edu/~wfsharpe/art/sr/SR.htm)
porte sur les rendements différentiels par rapport à une référence. Ici la
référence supposée vaut zéro, conformément à l'application ; la rémunération
effective du sans-risque EUR n'est pas mesurée. Un autre taux peut changer le
classement, et l'annualisation usuelle ne corrige pas les autocorrélations.

PSP5.PA, cours propres ajustés en EUR, capital initial 10 000 €, titres entiers,
frais 0,12 % par ordre, liquidités non rémunérées. Informations connues à la
clôture et exécution à la clôture suivante ; budgets réellement indépendants
lorsque la règle conserve une poche v4. Aucune liquidation finale artificielle,
ni modification du générateur ou de la base utilisateur : copie SQLite privée.

La gestion de l'exposition par volatilité est inspirée de
[Moreira–Muir, Volatility Managed Portfolios](https://www.nber.org/papers/w22208).
L'adaptation ici est plafonnée à 100 % et conserve PSP5/liquidités ; elle ne
reproduit pas les résultats du papier. Les adaptations antérieures rejetées
pour d'autres objectifs ne sont pas considérées comme adoptées ou validées.

## Protocole déclaré avant les nouveaux résultats

Script : `scripts/study_sp500_sharpe.py` ; résultat distinct :
`data/backtests/sp500-sharpe.json`. Le JSON écrit le protocole et la grille
complète avant les premiers nouveaux parcours, puis fige le gagnant avant les
parcours réservés. Empreintes des trois rapports réutilisés conservées.

1. Relire les seuls résultats de sélection des trois branches approfondies :
   2 409 configurations déclarées, 2 391 distinctes. Conserver le meilleur Sharpe
   moyen de chaque famille et source, soit 11 candidats. C'est une réutilisation
   après examen, pas 2 409 nouveaux essais ni une sélection prospective.
2. Ajouter 162 règles de taille d'exposition : fenêtres 21/63/126 séances,
   cibles annualisées 8/12/16 %, planchers 0/25/50 %, puissances 1/2,
   poche indépendante v4 0/35/65 %. Exposition
   `clip((cible/volatilité)^puissance, plancher, 1)`, décisions toutes les cinq
   séances, bande de cinq points. Priorité fixe de volatilité 16 % avant
   disponibilité de la fenêtre ; aucun remplissage par le futur.
3. Comparer les 173 candidats sur **les mêmes 200 parcours cinq ans**, graines
   1710000–1710199. Choisir uniquement le plus grand Sharpe moyen ; ratios définis
   sur tous les parcours requis pour qu'un score soit comparable. En cas
   d'égalité, premier indice. Aucun filtre de rendement, drawdown ou historique.
4. Figer **un seul gagnant**. Contrôler sur 1 000 nouveaux parcours cinq ans
   1720000–1720999 et 300 dix ans 1730000–1730299. Publier la différence de
   Sharpe appariée avec v5, moyenne, médiane, victoires/égalités/défaites et IC95 %
   par 2 000 rééchantillonnages. Conclusion de gain de Sharpe dans le modèle
   seulement si tous les ratios sont définis et la borne inférieure est positive
   sur les deux horizons. Aucun remplacement par un second candidat après audit.
5. Publier les historiques 1/3/5/10 ans, 24 départs trimestriels cinq ans,
   frais doublés et exécution retardée d'une séance supplémentaire. Ce sont des
   diagnostics de stabilité, sans critères supplémentaires d'admissibilité.

Chaque premier parcours d'un lot compare exactement les témoins passif/v5 au
moteur de production à 1e−9. Ces contrôles et les tests de causalité sont des
vérifications logicielles, pas une validation financière.

## Limites

L'historique PSP5 depuis 2014 a déjà été largement examiné. De nouvelles graines
produisent des tirages du même modèle, pas des observations économiques inédites.
Le réemploi des configurations et leur sélection introduisent un biais ; les
intervalles synthétiques ne corrigent pas le risque de modèle, les recherches
multiples ou l'absence de crises 2000/2008 dans cet ETF. Les fenêtres réelles se
chevauchent. Aucun optimum global ni Sharpe futur supérieur n'est démontré.

## Résultats

La sélection commune retient l'indice 10, combinaison adaptative d'experts :
fenêtre 252 séances, sensibilité 2, pénalité de variance 3, aucune pénalité de
drawdown, plancher 10 %, aucune poche v4 indépendante, décisions toutes les
cinq séances. Elle est différente de la combinaison retenue dans l'ancienne
campagne visant le rendement et le drawdown.

Ses cinq modèles conseillers sont deux expositions inspirées des états
régressifs, deux CUSUM (seuils 5/8, rebond 6 %) et un modèle Markov. Ces modèles
produisent des cibles théoriques, avec rendements conseillers retardés de deux
clôtures et frais de rotation approximatifs 0,12 % ; le portefeuille final
paie ses propres vrais frais et utilise des titres entiers. La cible inspirée
de v5 n'est pas la reproduction exacte des poids dérivants de v5. Les scores
glissants combinent rendement logarithmique et variance ; leur mélange utilise
des poids exponentiels et un a priori 50/12,5/12,5/12,5/12,5 %. La sélection
des paramètres repose uniquement sur le Sharpe du vrai portefeuille exécuté.

| Sélection commune, 200 parcours cinq ans | v5 | Candidat figé |
|---|---:|---:|
| Sharpe moyen | 0,94956 | 0,97050 |
| CAGR moyen | 12,505 % | 12,245 % |
| Volatilité moyenne | 13,543 % | 12,773 % |
| Drawdown moyen | −21,136 % | −18,767 % |
| Frais moyens | 33,05 € | 99,81 € |

Le deuxième candidat, CUSUM avec 35 % de budget v4, obtient 0,97043 :
l'écart entre les deux meilleurs n'est que 0,000076. Il ne faut donc pas
interpréter la première place comme une supériorité stable entre familles.
Le meilleur nouveau réglage par variance obtient 0,96790. Aucun de ces deux
challengers ne remplace le gagnant après lecture des parcours réservés.

Le Sharpe historique du gagnant synthétique est 1,562/1,681/1,010/1,104 sur
1/3/5/10 ans, contre 1,608/1,612/1,141/1,111 pour v5. Son avantage de sélection
synthétique ne se retrouve donc pas sur chacun des horizons réels. Aucun filtre
historique n'est ajouté après constat : son audit initial est conservé.

Sur les 1 000 parcours réservés cinq ans, Sharpe moyen **0,99622 contre
0,96538 v5**, différence moyenne **+0,03084**, médiane +0,02582,
IC95 % [+0,02636 ; +0,03561]. **648 victoires, 352 défaites**, aucune égalité,
tous ratios définis. C'est un avantage moyen dans le modèle, pas un gain sur
chaque parcours. Le CAGR moyen est 12,596 % contre 12,785 %, le DD moyen
−18,360 % contre −20,857 % : ces deux mesures n'interviennent pas dans la
conclusion sur le Sharpe.

Sur les **300 parcours réservés dix ans**, Sharpe moyen **0,95073 contre
0,91835 v5**, gain moyen **+0,03238**, médiane +0,03046,
IC95 % [+0,02625 ; +0,03851]. **218 victoires, 82 défaites**, aucune égalité,
tous ratios définis. CAGR moyen 12,205 % contre 12,544 %, DD moyen −22,603 %
contre −25,882 % ; ces diagnostics ne changent pas le classement.

**Le candidat passe le protocole de gain de Sharpe moyen dans le modèle sur
les deux horizons.** Ce n'est pas un succès de l'ancien objectif de rendement
ou de drawdown, ni une validation prospective. Les deux lots ne sont que de
nouveaux tirages du même historique économique déjà examiné. Le recul du
Sharpe réel cinq ans reste publié et empêche d'annoncer une domination uniforme.
Il n'est pas transformé après coup en nouveau filtre d'échec du protocole.

Les 24 fenêtres trimestrielles cinq ans donnent **17 Sharpe supérieurs et
7 inférieurs** au témoin, écarts −0,13105 à +0,10855. Frais doublés, Sharpe
3/5/10 ans : 1,666/0,995/1,092 contre 1,604/1,133/1,107 pour v5. Retard
supplémentaire : 1,625/1,021/1,102 contre 1,588/1,126/1,103. L'avantage
synthétique n'efface donc pas les contre-exemples réels, même sur le seul Sharpe.

## Deuxième sélection : Sharpe historique seul

Après le gel du premier candidat et l'examen de ses seuls chiffres historiques,
avant de consulter les classements historiques complets ou les résultats des
audits réservés, une seconde branche a été déclarée :
`scripts/study_sp500_sharpe_history.py`,
`data/backtests/sp500-sharpe-history.json`. Ce protocole n'est pas une correction
du classement synthétique initial et ne remplace pas son candidat après audit.

Elle classe les 2 409 anciennes configurations et les 162 règles de volatilité
par **moyenne des trois Sharpe historiques 3/5/10 ans**, sans filtre de rendement
ou de drawdown. Les fenêtres imbriquées donnent un poids répété aux dernières
années ; c'est une convention de classement explicite, pas trois validations
indépendantes. V5 est conservée si aucun score n'est supérieur au sien.

Un gagnant est figé, puis évalué sur 300 nouveaux parcours cinq ans
1820000–1820299 et 100 dix ans 1830000–1830099. Même conclusion statistique
limitée au modèle : borne inférieure de l'IC95 % du gain moyen de Sharpe
strictement positive sur les deux horizons, tous ratios définis. Aucun filtre
sur les autres métriques, aucun candidat de remplacement après audit.

Le gagnant historique est la combinaison régressive sans poche passive,
75 % de budget lent et 25 % défensif, plancher de chaque poche 10 % au lieu
de 25 %. Entrée lente et sortie +1,5σ, cadence mensuelle et réchauffement de
l'état lent conservés ; entrée/sortie défensives inchangées, cinq séances,
état initial défensif. Budgets indépendants, aucun transfert. C'est une variante
de règles antérieures sous un nouvel objectif, pas une invention ni une adoption.

| Historique réel jusqu'au 13/11/2026 | Sharpe v5 | Sharpe candidat historique | CAGR v5 | CAGR candidat | DD v5 | DD candidat |
|---|---:|---:|---:|---:|---:|---:|
| 1 an | 1,608 | 1,617 | 15,80 % | 14,07 % | −5,33 % | −4,79 % |
| 3 ans | 1,612 | 1,888 | 17,14 % | 15,52 % | −12,38 % | −6,77 % |
| 5 ans | 1,141 | 1,487 | 12,06 % | 12,51 % | −11,73 % | −6,79 % |
| 10 ans | 1,111 | 1,352 | 13,04 % | 11,72 % | −20,45 % | −7,99 % |

Score moyen 3/5/10 : 1,576 contre 1,288. Tous ces chiffres sont des données
de sélection déjà examinées, **pas une validation hors échantillon**. Les
anciens rapports et leurs critères rendement/risque restent inchangés.

L'audit de ce candidat historique est défavorable dans le modèle :

| Parcours réservés | Sharpe moyen v5 | Sharpe moyen candidat | Gain moyen | IC95 % du gain | Victoires |
|---|---:|---:|---:|---:|---:|
| 300 cinq ans | 0,91878 | 0,85303 | −0,06575 | [−0,08193 ; −0,04966] | 98/300 |
| 100 dix ans | 0,90309 | 0,80332 | −0,09977 | [−0,11809 ; −0,08108] | 14/100 |

Tous les ratios sont définis. Aucun autre candidat n'est sélectionné après cet
échec. Le rendement synthétique moyen cinq ans passe de 12,159 % à 9,498 % ;
ce chiffre est un diagnostic, **pas la raison de l'échec** : c'est le Sharpe
lui-même qui est inférieur.

Sur les 24 fenêtres réelles trimestrielles cinq ans, **24 Sharpe supérieurs**,
écarts de +0,02250 à +0,38245. Frais doublés sur 3/5/10 ans : Sharpe candidat
1,873/1,475/1,342 contre 1,604/1,133/1,107. Retard supplémentaire :
1,849/1,458/1,337 contre 1,588/1,126/1,103. Ces fenêtres réelles se chevauchent
et proviennent du même historique déjà examiné. La stabilité historique n'est
pas une preuve prospective ; le désaccord avec le modèle n'est pas non plus
la preuve que le modèle décrit correctement l'avenir.

## Reproduction

```sh
PYTHONPATH=backend:scripts .venv/bin/python scripts/study_sp500_sharpe.py
PYTHONPATH=backend:scripts .venv/bin/python scripts/study_sp500_sharpe_history.py
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/unit/test_sp500_sharpe.py backend/tests/unit/test_sp500_deep_search.py -q
.venv/bin/ruff check backend scripts
```

Vérifications : **14 tests ciblés réussis**, Ruff backend/scripts et contrôle
du diff. Ils couvrent les filtres causaux, la sélection indépendante des anciens
critères, la définition du ratio et les témoins. Aucun changement du moteur de
production, de l'interface ou de la base utilisateur pendant cette recherche ;
v5 était restée active à cette étape. L'adoption ultérieure de v6 est documentée
séparément, avec son propre vérificateur de production.
