# Recherche sur la régression S&P 500 — 14 novembre 2026

> État historique avant intégration. Après ce bilan, l’utilisateur a explicitement
> demandé l’implémentation de la variante défensive de phase 3. Elle est désormais
> disponible dans l’application ; voir [l’intégration et l’affinage](sp500-defensive-refinement.md).
> Les conclusions financières et les échecs ci-dessous restent inchangés.

## Résultat et décision

**31 752 configurations distinctes ont été évaluées. Aucune des configurations sélectionnées selon les procédures décrites ci-dessous ne satisfait tous les critères de rendement et de risque sur l’apprentissage, la validation et la vérification finale. La stratégie de l’application reste inchangée.** Cela ne signifie pas qu’aucune configuration de la grille n’aurait gagné rétrospectivement sur la période finale : cette période n’est volontairement pas utilisée pour rechercher son gagnant.

Deux résultats sont intéressants, mais insuffisants pour une adoption :

- Une régression longue réalise une surperformance très importante sur l’historique complet, sans reproduire cette surperformance dans les différentes sous-périodes. Elle ne repose que sur six transactions sur huit ans.
- Une méthode sélectionnée en conservant les positions entre périodes réduit fortement le risque et améliore le Sharpe sur les données ESE récentes, mais son rendement reste inférieur au témoin, particulièrement sur la vérification finale. Son comportement sur l’indice américain depuis 1993 est nettement moins favorable.

Les expériences ajoutent uniquement des scripts, tests et résultats de recherche. Aucun changement des seuils ni de l’interface de production.

## Données et comptabilité

Copie SQLite obtenue avec l’API de sauvegarde SQLite depuis une connexion en lecture seule ; aucune modification de la base utilisateur. Empreinte commune des trois recherches : `3828d8f2e06fa105c15379ab28b7959e2deb34f373d1a8dd82e75fd013da724a`.

ESE.PA, ETF S&P 500 PEA capitalisant en EUR : 3 361 observations du 16 septembre 2013 au 13 novembre 2026. Dans cet instantané, les cours ajustés et non ajustés sont identiques. Signal calculé sur le logarithme des cours ajustés ; régression en temps calendaire et dispersion résiduelle avec deux degrés de liberté consommés. Aucune observation future dans le signal. Les comparaisons commencent le 17 septembre 2018 pour laisser cinq années de préparation à toutes les fenêtres.

Capital initial de 10 000 €, titres entiers, frais de 0,5 % sur chaque montant acheté ou vendu. Exécution à la clôture suivante, jamais à la clôture du signal. Aucun levier, aucune vente à découvert ; liquidités non rémunérées. Le témoin achète le même ESE, sur le même calendrier et à la même première date d’exécution, avec les mêmes frais et arrondis. Aucune vente finale imposée aux deux méthodes. Les frais propres à l’ETF sont déjà reflétés dans les cours ; aucune seconde déduction.

La référence de cette recherche est **ESE conservé**, et non un indice S&P américain exprimé dans une autre devise. Le calendrier est celui d’ESE ; les chiffres peuvent différer d’une validation dont le calendrier commun exclut certaines séances européennes faute de cotation de la référence américaine.

Les pourcentages de volatilité sont annualisés sur 252 séances, le rendement annualisé utilise le temps calendaire, et le Sharpe utilise une référence de taux nulle, comme l’application. Les réductions d’exposition expliquent une partie de la réduction du risque ; une volatilité plus faible n’est pas, à elle seule, une preuve de meilleure sélection des entrées. Le Sharpe n’englobe pas tous les risques.

## Grille testée

| Dimension | Valeurs |
|---|---|
| Régression glissante | 3, 6, 12, 18, 24, 36, 60 mois calendaires |
| Seuil d’entrée | −2 ; −1,5 ; −1 ; −0,5 ; 0 ; +0,5 ; +1 ; +1,5 σ |
| Seuil de sortie / armement | +0,5 ; +1 ; +1,5 ; +2 ; +2,5 ; +3 σ ; strictement supérieur au seuil d’entrée |
| Entrée | Score strictement inférieur au seuil ; ou franchissement quotidien du seuil à la hausse après passage en dessous |
| Sortie | Dépassement strict du seuil ; ou repli de 0,5 / 1 σ depuis le maximum observé après armement |
| Filtre supplémentaire | Aucun ; cours au-dessus de sa moyenne mobile 200 séances ; pente de régression positive |
| Cadence des décisions | Toutes les 1, 5 ou 21 séances, depuis le début de l’expérience |
| Exposition défensive | Liquidités intégrales ; ou cible de 25 % sur ESE au passage à l’état défensif |

Un filtre non satisfait provoque aussi une sortie à une date de décision. Dans les variantes de rebond, le franchissement est mesuré entre la séance du signal et la précédente ; il faut qu’il soit constaté à une date de décision. Les variantes hebdomadaires n’exécutent donc pas rétrospectivement un franchissement survenu entre deux décisions. Pour les sorties après repli, armement et maximum sont mis à jour aux dates de décision.

Les poids de 25 % et 100 % sont visés seulement lorsque l’état change : **pas de rééquilibrage quotidien** pour rétablir un poids qui dérive ensuite avec les cours. Le solde reste en liquidités. Les actions entières et frais peuvent laisser une petite réserve après une entrée à 100 %.

Ces 31 752 configurations ne représentent pas toutes les stratégies possibles : ni options, ni levier, ni actifs supplémentaires, ni modèle appris complexe. Aucun paramètre n’est ajouté à l’application.

## Critères et séparation chronologique

Critères écrits dans le fichier de protocole avant chaque phase de calcul : par rapport au témoin, gain de rendement annualisé d’au moins 0,5 point, gain de Sharpe d’au moins 0,10, volatilité et perte maximale réduites d’au moins 10 %. Au moins trois achats sur l’apprentissage pour éviter de retenir uniquement une décision chanceuse. Adoption conditionnée au respect sur les trois périodes puis sous les stress de frais et délai.

| Rôle | Période |
|---|---|
| Apprentissage | 17/09/2018–31/12/2020 |
| Sélection / validation | 04/01/2021–29/12/2023 |
| Vérification finale | 02/01/2024–13/11/2026 |

Les critères sont exigeants : réussir sur tout l’historique mais échouer sur une sous-période ne suffit pas ici. Cela répond à la recherche de robustesse, sans constituer une condition nécessaire à toute stratégie financière utile.

Classement préétabli : gain de CAGR / 0,02 + gain de Sharpe / 0,2 + réduction relative de volatilité / 0,1 + réduction relative de perte maximale / 0,2. Priorité aux candidats satisfaisant les critères. Pas de classement à partir de la période finale.

**Ces périodes étaient historiquement disponibles, et certaines déjà examinées dans le projet. Elles ne deviennent pas inconnues parce qu’on les redécoupe.** La vérification est séparée dans chaque procédure de sélection, mais reste rétrospective ; les phases supplémentaires ne sont pas une validation indépendante des précédentes.

### Phase 1 : sélection des vingt premiers

Toutes les variantes sont testées sur l’apprentissage, puis seules les vingt premières sont comparées sur la validation. Chaque période démarre en liquidités avec 10 000 €.

1 633 variantes satisfont les critères d’apprentissage. Aucune des vingt premières ne satisfait ceux de validation. Elles sont majoritairement proches, avec une régression de cinq ans : ce classement concentre trop la sélection dans une même famille.

Le candidat diagnostique retenu avant calcul de la période finale : régression 60 mois, achat sous −2 σ, sortie au-dessus de +2,5 σ, décision toutes les cinq séances, cible défensive 25 %, sans filtre. Ses résultats ne justifient pas une adoption malgré un excellent historique agrégé.

### Phase 2 : diversification des familles

Cette phase est un **ajout exploratoire après l’échec de la validation de phase 1**, documenté séparément. Un représentant issu de l’apprentissage est conservé pour chacune des 252 familles `(fenêtre, sortie, filtre, exposition défensive, règle d’entrée)` ; seuils et cadence sont choisis sur l’apprentissage. La période finale n’entre pas dans ce choix.

Aucune famille représentée ne satisfait simultanément les critères d’apprentissage et de validation. Le meilleur diagnostic de validation — régression six mois, entrée après rebond au-dessus de +1 σ, sortie +1,5 σ, filtre moyenne mobile 200 séances, décisions toutes les cinq séances, liquidités défensives — déçoit fortement sur 2024–2026 : **−1,53 % annualisés contre +18,02 % pour ESE**. Cet échec est conservé dans les résultats.

### Phase 3 : continuité des positions

Les phases 1 et 2 mesurent la qualité d’une entrée depuis des liquidités au début de chaque sous-période. C’est utile, mais différent d’une stratégie qui fonctionne déjà : une entrée à −2 σ peut ne pas se produire pendant longtemps alors qu’une position ouverte auparavant aurait été conservée.

Cette troisième phase conserve donc réellement titres, cash, état investi/défensif, maximum du score, armement et ancrage de cadence entre apprentissage, validation et période finale. Toutes les 31 752 variantes sont comparées en validation, puis un seul candidat est retenu avant son calcul final. Les 73 variantes satisfaisant apprentissage et validation sont classées selon le score prévu ; le gagnant est une régression de 18 mois, entrée après rebond au-dessus de −0,5 σ, sortie au-dessus de +1,5 σ, décisions toutes les cinq séances, cible défensive 25 %, aucun filtre de tendance.

Les performances des sous-périodes sont normalisées par leur capital au début de la sous-période ; aucune remise arbitraire à 10 000 € ni liquidation au changement de période. Les tableaux de cette phase commencent à la clôture précédant le premier jour demandé pour inclure son rendement.

## Résultats après frais

Historique complet ESE : **17/09/2018–13/11/2026**, 10 000 € initiaux. « Longue » désigne le candidat de phase 1, « défensive » celui de phase 3. Le calcul complet est un diagnostic après sélection, pas son critère de classement.

| Méthode | Valeur finale | Rendement annualisé | Sharpe | Volatilité | Perte maximale |
|---|---:|---:|---:|---:|---:|
| ESE conservé | 30 373,68 € | 14,59 % | 0,88 | 16,74 % | −33,60 % |
| Stratégie actuelle, régression 36 mois, +1 / +2 σ | 29 770,99 € | 14,31 % | 0,90 | 16,11 % | −25,81 % |
| Longue, phase 1 | 46 654,94 € | 20,78 % | 1,39 | 14,05 % | −23,28 % |
| Défensive, phase 3 | 29 805,99 € | 14,33 % | 1,36 | 10,05 % | −15,00 % |

La longue n’effectue que six transactions, paie 340,48 € de commissions et a une exposition moyenne observée de 86,34 %. La défensive effectue quatorze transactions, paie 986,06 € et a une exposition moyenne de 62,84 %. Le témoin paie 49,72 € à l’entrée. Les expositions sont des moyennes par séance, pas pondérées en jours calendaires.

Le rendement de la longue paraît excellent, mais dépend fortement de l’état et de la date de départ. Sur la validation recommencée en liquidités, il tombe à **8,45 % contre 13,96 %** pour ESE. Sur la vérification finale indépendante : **15,19 % contre 18,02 %**. Depuis novembre 2021, elle gagne davantage, mais sa perte maximale n’est pas améliorée : −23,28 % contre −23,25 %. Une sortie sur surévaluation n’est pas un stop de crise : un prix peut s’effondrer en restant sous le seuil haut.

Décomposition de la défensive en fonctionnement continu :

| Période | CAGR méthode / ESE | Sharpe méthode / ESE | Volatilité méthode / ESE | Perte maximale méthode / ESE |
|---|---:|---:|---:|---:|
| Apprentissage 2018–2020 | 14,35 / 11,02 % | 1,03 / 0,60 | 13,69 / 20,95 % | −15,00 / −33,60 % |
| Validation 2021–2023 | 14,81 / 13,88 % | 1,71 / 0,92 | 8,08 / 15,16 % | −4,36 / −17,18 % |
| Vérification 2024–2026 | 13,81 / 18,29 % | 1,57 / 1,23 | 8,36 / 14,38 % | −7,14 / −23,28 % |

L’avantage de risque récent est réel dans ces calculs, mais ne remplit pas l’objectif combiné de surperformance et de risque réduit.

## Frais, délai, stabilité et périodes longues

- **Frais doublés à 1 % par achat ou vente**, avec toute la trajectoire continue recalculée : sur la période finale, défensive à 12,92 % annualisés, contre 18,30 % pour ESE. Le risque reste moindre, le manque à gagner augmente.
- **Une séance supplémentaire avant exécution** : défensive à 13,38 % contre 18,30 %. Le candidat reste figé ; aucune recherche de nouveaux paramètres sous stress.
- **Coût additionnel de 0,2 % par montant échangé** : défensive à 13,45 % contre 18,29 %. Diagnostic de recherche uniquement, aucun champ ajouté dans l’application.
- **Titres fractionnaires** également vérifiés dans les phases 1 et 2 : les arrondis n’expliquent pas leur échec.
- **Voisinage de la défensive** : 27 combinaisons autour des seuils et des fenêtres 12/18/24 mois, autres règles inchangées. Aucune ne satisfait l’ensemble des critères sur la période finale. Pas de nouveau classement pour choisir a posteriori celle qui y gagne.
- **Réoptimisation annuelle** : choisir sur toutes les données antérieures, puis tester l’année suivante, sur six années 2021–2026. Le rendement ne dépasse celui d’ESE que deux années sur six. Les années sont des expériences indépendantes avec redémarrage en cash ; aucun rendement cumulé de cette procédure n’est présenté.
- **Rééchantillonnage par blocs appariés** : 5 000 tirages de blocs de 21 séances, puis 5 000 de 63, sur les rendements finaux de la défensive et du témoin. L’intervalle descriptif à 95 % de l’écart de CAGR est environ [−17,2 ; +7,1] points pour 21 séances ; celui du gain de Sharpe [−0,44 ; +1,06]. Ces intervalles sont conditionnels aux choix effectués, ne corrigent pas les multiples recherches et ne donnent pas une probabilité de succès futur.

Pour tester d’autres crises sans inventer un historique d’ETF, utilisation secondaire de l’indice S&P 500 total-return local en **USD**, dividendes inclus, titres fractionnaires et mêmes frais. Ce n’est ni ESE, ni un investissement PEA en EUR ; cette vérification ne sert pas à la sélection :

| Période indice USD | CAGR défensive / indice | Perte maximale défensive / indice |
|---|---:|---:|
| 2000–2003 | −5,02 / −4,31 % | −35,67 / −47,41 % |
| 2007–2009 | −10,41 / −5,80 % | −51,67 / −55,25 % |
| 1993–2026 | 5,54 / 10,86 % | −55,25 / −55,25 % |

Sur l’horizon long, l’amélioration de perte maximale disparaît et le Sharpe devient inférieur (0,46 contre 0,66). **La piste défensive récente n’est donc pas universellement défensive ni démontrée supérieure.** La longue de phase 1 sous-performe également l’indice USD sur 1993–2026 : 9,42 % annualisés contre 10,86 %, Sharpe 0,60 contre 0,66.

## Portée de la conclusion

On peut obtenir une très belle courbe ESE en ajustant ces règles. Ce travail ne démontre pas qu’elle survivrait à une période future, et il fournit plusieurs contre-exemples à une supériorité générale. Les travaux de [Bailey et coauteurs sur le surajustement des backtests](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) expliquent pourquoi multiplier les variantes rend nécessaire cette distinction. Aucun ratio de Sharpe « déflaté » ni test formel de probabilité de surajustement n’a été calculé ici ; les 31 752 variantes sont très dépendantes entre elles.

La piste concrète est une règle moins active, avec une exposition partielle plutôt qu’une sortie toujours intégrale ; elle mérite d’être comprise comme un compromis de risque. L’historique disponible ne permet pas de la présenter comme la stratégie supérieure sur tous les objectifs demandés. **Aucune substitution automatique dans l’application.**

## Reproduction et artefacts

Depuis la racine du projet, dans cet ordre :

```sh
PYTHONPATH=backend uv run python scripts/study_sp500_regression.py
PYTHONPATH=backend:scripts uv run python scripts/extend_sp500_regression_study.py
PYTHONPATH=backend:scripts uv run python scripts/study_sp500_continuation.py
PYTHONPATH=backend:scripts uv run python scripts/summarize_sp500_regression.py
uv run pytest -q backend/tests/unit/test_sp500_study.py
```

Sorties locales (ignorées par Git) :

- `data/backtests/sp500-regression-study.json` : protocole initial, 31 752 résultats d’apprentissage, sélection, stress et réoptimisations annuelles.
- `data/backtests/sp500-regression-diversified.json` : 252 représentants, échecs, stress et références longues.
- `data/backtests/sp500-regression-continuation.json` : sélection des 73 candidats qualifiés, choix figé, continuité, stress, voisinage, rééchantillonnage et références longues.

Les phases 2 et 3 vérifient l’empreinte de la copie de données contre celle de la première phase ; les diagnostics complémentaires vérifient celle de la troisième. Des données mises à jour nécessitent de relancer toute la chaîne et produiront potentiellement d’autres résultats.

Les tests logiciels vérifient la causalité des signaux, l’équivalence de l’OLS trois ans avec le moteur existant, l’identité de toutes les valeurs et frais de la règle actuelle avec le moteur de production sur historique synthétique, les titres entiers et la continuité exacte entre sous-périodes. Ces tests ne valident pas la performance financière.
