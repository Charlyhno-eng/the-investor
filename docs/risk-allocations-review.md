# Révision des allocations de risque — 14 novembre 2026

## Décisions appliquées

- **Corrélation minimale** : garder l’objectif `wᵀ Corr w`, mais résoudre le
  problème convexe sur tous les actifs éligibles. Supprimer le plancher de 3 %
  et la contrainte de conserver la moitié des lignes. Poids positifs ou nuls,
  somme 1, plafond 35 % dès trois actifs, 50/50 à deux, 100 % à un.
  Les frais, titres entiers et bande de révision de 3 points restent appliqués.
- **Volatilité minimale** : conserver l’estimation empirique sur trois ans et
  les contraintes actuelles. Aucune variante ne satisfait les critères préfixés.
  Ne pas promettre une forte baisse du risque réalisé.
- **Correction commune** : transmettre réellement la covariance alternative à
  chaque résolution interne, y compris la résolution relâchée des grands
  univers. Auparavant, elle servait à évaluer les candidats, tandis que leurs
  poids étaient calculés avec la covariance empirique. Ce correctif rend les
  expériences OAS cohérentes ; il n’active pas OAS par défaut dans l’interface.

## Protocole fixé avant les résultats

288 validations : 3 univers (`journal_14`, `actions_11`, `crypto_4`) × 4 périodes
× 2 niveaux de frais × 12 combinaisons méthode/variante (5 volatilité,
7 corrélation). Toutes terminent avec le statut `ready` ; aucun échec n’est
écarté. Les fenêtres se recoupent : ce ne sont pas 24 observations indépendantes.

| Période | Début | Fin |
|---|---|---|
| Ancienne | 14/11/2016 | 12/11/2021 |
| Intermédiaire | 15/11/2021 | 14/11/2024 |
| Récente | 15/11/2024 | 13/11/2026 |
| Cinq ans | 15/11/2021 | 13/11/2026 |

10 000 € initiaux ; 0,5 % puis 1 % par achat et vente ; actions/ETF entiers,
cryptos fractionnaires ; apprentissage propre de trois ans, au moins 500
variations ; révision trimestrielle ; bande automatique de 3 points. Signaux
sur informations connues et exécution à la clôture suivante. Même calendrier,
univers et conventions pour toutes les variantes d’un cas.

Critères fixés dans `PROTOCOL`, avant exécution :

- Volatilité : ratio médian de volatilité réalisée ≤ 0,95 face à l’existant.
- Corrélation : ratio médian de l’objectif de corrélation ≤ 1,01, et poids agrégé
  strictement positif pour la paire corrélée du test synthétique.
- Les deux : volatilité ne dépassant pas 105 % de l’existant dans au moins
  75 % des cas ; perte médiane de CAGR ≤ 0,5 point/an et de Sharpe ≤ 0,03 ;
  frais cumulés ≤ 110 % de ceux du contrôle. Tous les 24 cas doivent être prêts.
- Aucun choix selon le meilleur rendement ; aucun ajustement après résultats.

Pour la corrélation, les cibles de chaque variante sont évaluées sur **la même
matrice empirique des trois années connues** que le contrôle. Le ratio est
calculé à chaque signal, puis médiane par cas et médiane des 24 cas. Les huit
signaux intégralement en liquidités, communs à chaque variante, n’ont pas
d’objectif normalisable et sont signalés séparément ; les 24 cas restent tous
inclus dans les mesures de performance et de frais.

## Variantes et résultats

Les écarts de volatilité sont relatifs à l’existant, en médiane sur les 24 cas.
Les frais comparent les sommes des euros effectivement payés sur ces mêmes cas.
« Conforme » signifie conforme au protocole rétrospectif, pas preuve prospective.

| Méthode | Variante | Δ volatilité | Δ frais | Conforme |
|---|---|---:|---:|---|
| Volatilité | Tous les poids continus | ≈ 0 % | +0,1 % | Non |
| Volatilité | Fenêtre 252 séances | −0,5 % | +38,3 % | Non |
| Volatilité | Pondération exponentielle, demi-vie 63 séances | −0,5 % | +55,7 % | Non |
| Volatilité | OAS corrigé, contraintes conservées | ≈ 0 % | +0,5 % | Non |
| Corrélation | Tous les poids continus | ≈ 0 % | −1,8 % | Oui, retenue |
| Corrélation | Fenêtre 252 séances | −1,7 % | +37,1 % | Non |
| Corrélation | Pondération exponentielle, demi-vie 63 séances | −2,3 % | +53,1 % | Non |
| Corrélation | OAS corrigé et poids continus | −0,4 % | −2,5 % | Oui, non retenue |
| Corrélation | Un représentant par groupe ≥ 0,80 | ≈ 0 % | −1,0 % | Oui, non retenue |
| Corrélation | Matrice des corrélations au carré | −2,5 % | −13,9 % | Non |

La solution continue est retenue pour supprimer une contrainte arbitraire et
la recherche approximative de sous-ensembles, en conservant l’objectif initial.
La médiane de l’objectif normalisé diminue d’environ 0,004 %. L’effet financier
reste modeste : pas de gain médian de CAGR ou de Sharpe. OAS ne justifie pas
l’ajout d’un estimateur par défaut pour un bénéfice aussi faible. La sélection
de représentants ajoute un seuil et peut couper une diversification utile.
Les corrélations au carré améliorent certains risques et les frais, mais
dégradent de 2,75 % l’objectif initial médian ; elles changent la façon de traiter
les corrélations négatives. Elles ne remplacent donc pas silencieusement la méthode.

### Airbus et Safran

Le moteur précédent ne supprimait pas explicitement les deux membres d’une
paire corrélée. Il optimisait déjà leur contribution à l’ensemble du portefeuille,
mais le plancher de 3 % pouvait éliminer une petite exposition utile.

Dans `journal_14`, cinq ans, frais 0,5 %, les deux cibles étaient nulles à
13 signaux trimestriels sur 20 ; elles le sont à 9 sur 20 avec la solution
continue. **Ce sont des poids cibles**, pas une garantie de détention réelle :
les titres entiers et la bande de 3 points peuvent empêcher une petite transaction.
Les deux positions restent absentes du portefeuille final dans cet exemple.

Test synthétique : corrélation de 0,98 entre les deux titres, 0,05 avec les
12 autres, ces derniers corrélés à 0,45 entre eux. La solution continue attribue
32,17 % à la paire (16,09 % chacun). L’ancienne méthode la conservait aussi :
une forte corrélation interne n’entraîne donc pas à elle seule leur exclusion.
Aucune règle ne force Airbus ou Safran si d’autres actifs diversifient mieux.

### Volatilité : pourquoi l’effet n’est pas spectaculaire

Sur `journal_14`, cinq ans, frais 0,5 %, la volatilité réalisée de l’existant
est de 13,71 %/an, contre 14,89 % pour le contrôle équipondéré de mêmes actifs
éligibles. Les expositions et arrondis de ces portefeuilles diffèrent ; ce
chiffre est descriptif, sans preuve d’un avantage de sélection isolé.

Passer à 252 séances donne 13,61 %, mais les frais passent de 234,73 € à
391,90 € et le CAGR de 20,18 % à 18,53 %. L’exponentiel donne 13,65 % et
498,83 € de frais. OAS donne 13,73 %. Aucun ne justifie un remplacement.

La stratégie minimise une variance **historique estimée**, sous des contraintes
et parmi les actifs proposés ; elle ne cible pas une volatilité absolue future.
Un univers dominé par les actions, un plafond par ligne et un capital investi
limitent la réduction possible. Introduire du cash ou d’autres actifs modifierait
la stratégie et demanderait un protocole distinct.

Pour la corrélation continue, les frais diminuent au total des 24 cas, mais
augmentent sur ce cas précis : 312,05 € → 326,17 €. Sa volatilité passe de
17,10 % à 17,12 %, son CAGR de 21,92 % à 21,89 %. Ne pas présenter le correctif
comme une amélioration financière dans chaque portefeuille.

## Reproduction et limites

```sh
PYTHONPATH=backend:scripts uv run python scripts/study_risk_allocations_review.py
PYTHONPATH=backend:scripts uv run python scripts/summarize_risk_allocations_review.py
```

Les scripts travaillent sur une copie SQLite temporaire ; aucune écriture dans
la base utilisateur pour les expériences. Le résumé vérifie l’empreinte de
l’instantané avant d’évaluer les cibles. Le script principal retire explicitement
le nouveau réglage continu pour reproduire le contrôle historique.

Résultats complets locaux : `data/backtests/risk-allocations-review.json`.
Empreinte SHA-256 :
`372408ce7f4e91e38c781c98a4f35e3cfed94835dcfe8c2541254211e87f91e0`.
La version intégrée est également comparée aux 24 simulations de la variante
continue : poids par signal et métriques concordent à 10⁻⁶ près.

Biais de sélection/survivance, fenêtres déjà examinées et recoupements temporels :
ces résultats ne constituent pas une validation prospective. Le cas synthétique
vérifie une propriété du calcul, pas un rendement de marché.

Références techniques : [MOSEK, optimisation de Markowitz](https://docs.mosek.com/portfolio-cookbook/markowitz.html),
[SciPy, résolution SLSQP](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-slsqp.html).
La référence commune des frontières est documentée dans [volatility.md](volatility.md).
