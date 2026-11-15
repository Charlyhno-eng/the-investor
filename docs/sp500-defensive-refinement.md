# S&P 500 défensif : intégration et affinage

La variante défensive de l’[étude initiale](sp500-regression-study.md) est intégrée
à la demande explicite de l’utilisateur. Le plafond de risque et le rendement
historique de référence motivent ce choix, malgré les limites de généralisation
identifiées dans l’étude. L’ancienne règle S&P +1 / +2 σ est remplacée ; le retour
à la moyenne multi-actifs est inchangé.

Mise à jour ultérieure : la combinaison `slow_defensive_v2` a été adoptée
explicitement. La règle décrite ici représente désormais une poche de 25 % du
capital initial, aux côtés de la poche lente de 75 % ; voir
[le protocole actif](validation.md#sp-500--régression). Les chiffres ci-dessous
concernent la variante défensive seule, avant ce remplacement.

## Règles initialement intégrées

ESE.PA seul, régression glissante logarithmique sur 18 mois. Allocation cible de
25 % par défaut ; passage à 100 % après franchissement de −0,5 σ à la hausse
entre deux séances consécutives. Retour à 25 % lorsque le score dépasse
strictement +1,5 σ. Contrôle toutes les cinq séances depuis le début de simulation,
exécution à la clôture suivante. Entre deux changements d’état, les quantités
sont conservées et les poids dérivent. Liquidités non rémunérées, aucun levier.

Ces règles étaient identifiées par la version `defensive_v1` et sont conservées
pour la poche défensive dans `backend/investor/portfolio/etf_switch.py`. Le détail des états, frontières et conventions est
présent dans [la documentation du moteur](validation.md#sp-500--régression).

Mise à jour après retour de l’utilisateur : la période spéciale commençant en
2018 a été supprimée. L’interface reprend cinq ans par défaut et les seuls choix
1/3/5/10 ans. Les chiffres sur septembre 2018–2026 ci-dessous restent des résultats
de recherche ; ils ne décrivent pas la simulation courante par défaut.
La référence reste ESE en EUR et les comparateurs retirés restent masqués.
La [recherche élargie](sp500-adaptive-risk-study.md) n’a pas établi de remplacement
satisfaisant tous les objectifs ; les règles de cette variante demeurent
expérimentales.

## Affinage avant intégration

Le protocole a été enregistré avant le calcul de cette recherche locale :

| Paramètre | Valeurs |
|---|---|
| Fenêtre | 12, 15, 18, 21, 24 mois |
| Rebond d’entrée | −0,75 ; −0,5 ; −0,25 σ |
| Sortie | +1,25 ; +1,5 ; +1,75 σ |
| Cadence | 3, 5, 10 séances |
| Cible défensive | 25, 35, 50, 65 % |

**540 configurations**, toujours sans filtre de tendance supplémentaire ni levier.
Évaluation sur copie SQLite figée, frais de 0,5 % par achat/vente, 10 000 €,
titres entiers, calendrier ESE. Période complète 17/09/2018–13/11/2026 ;
sous-périodes 2018–2020 / 2021–2023 / 2024–2026 avec maintien effectif des positions,
de l’état et de l’ancrage des décisions entre les sous-périodes.

Pour remplacer la variante autorisée, une configuration devait atteindre au
moins 14 % annualisés, réduire la volatilité d’au moins 5 %, préserver le Sharpe
et la perte maximale sur la période complète. Sur chaque sous-période, perte de
CAGR limitée à un point, volatilité à 105 % et perte maximale à 110 % de la base.
Frais doublés et retard d’une séance supplémentaire recalculés sur toute la
trajectoire : plancher historique de 14 % et volatilité au plus égale à la base,
avec CAGR au moins égal à la base sous frais doublés. Classement éventuel par
volatilité croissante puis rendement décroissant. Aucun réajustement après les
résultats ; sinon conservation de la variante de départ autorisée.

**Aucune configuration ne satisfait les critères d’amélioration.** Même en
ignorant les critères de stabilité, aucune autre configuration de cette grille
n’atteint 14 % avec une volatilité inférieure à la base. À volatilité au plus égale
à la base, celle-ci offre aussi le meilleur rendement de la grille. Réduire
uniquement le seuil de sortie à +1,25 σ abaisse la volatilité à 9,31 %, mais le
rendement à 10,95 % : ce changement ne respecte pas la contrainte de l’utilisateur.
Aucun paramètre de cette recherche n’est donc adopté en supplément.

Ces données étaient toutes déjà connues lors de l’affinage : ce travail est
exploratoire rétrospectif, sans nouvelle période inconnue ni garantie de gain futur.
La demande d’implémentation autorise la variante initiale ; elle ne transforme pas
ses résultats en validation indépendante.

## Résultats de la version intégrée

Sur la période de référence du **17/09/2018 au 13/11/2026**, après frais :

| Mesure | Variante défensive | ESE conservé |
|---|---:|---:|
| Capital final, départ 10 000 € | 29 805,99 € | 30 373,68 € |
| Rendement annualisé | 14,3282 % | 14,5930 % |
| Sharpe, taux de référence nul | 1,3607 | 0,8846 |
| Volatilité annualisée | 10,0510 % | 16,7367 % |
| Perte maximale | −14,9973 % | −33,6020 % |
| Frais payés | 986,06 € | 49,72 € |

L’application reproduit les indicateurs du simulateur de recherche à moins de
10⁻⁹ et les frais à moins de 10⁻⁶ €. Les trajectoires synthétiques sont également
comparées point par point, en fractionnaire et en titres entiers.

Le seuil de **14 %** est vérifié uniquement sur cette période complète, avec ces
frais et ce capital. Il n’est ni une promesse future, ni un rendement minimum sur
toute durée sélectionnée. Exemples de simulations indépendantes démarrant en cash,
toujours arrêtées au 13/11/2026 :

| Début de simulation | Rendement annualisé | Volatilité |
|---|---:|---:|
| 17/09/2018, référence complète | 14,33 % | 10,05 % |
| 14/11/2016, environ dix ans | 12,67 % | 9,98 % |
| 15/11/2021, environ cinq ans | 9,76 % | 7,25 % |
| 13/11/2023, environ trois ans | 9,01 % | 7,12 % |
| 13/11/2025, un an | 6,60 % | 5,88 % |

Les débuts sont explicités car un décalage d’une séance change l’ancrage de la
cadence et les entrées d’une règle à hystérésis. Les options glissantes de
l’interface peuvent commencer une autre séance selon leur date exacte de fin.
Les performances en continu de l’étude précédente ne sont pas celles de nouveaux
placements démarrant en cash à ces dates.

Sur la période complète, **frais doublés : 13,63 %** annualisés et 10,09 % de
volatilité. Avec une séance de retard supplémentaire : 14,47 % annualisés et
10,02 % de volatilité. Le contrôle de risque reste un compromis ; les limites sur
l’indice américain depuis 1993, documentées dans l’étude initiale, demeurent.

## Reproduction

Depuis la racine :

```sh
PYTHONPATH=backend:scripts uv run python scripts/study_sp500_defensive_refinement.py
PYTHONPATH=backend uv run python scripts/verify_sp500_defensive.py
uv run pytest -q backend/tests/unit/test_etf_switch.py backend/tests/unit/test_sp500_study.py backend/tests/integration/test_validation_api.py
```

Résultats locaux ignorés par Git :
`data/backtests/sp500-defensive-refinement.json` (protocole et 540 résultats),
`data/backtests/sp500-defensive-production-verification.json` (vérification du
moteur de production sur copie privée). Empreinte des données :
`3828d8f2e06fa105c15379ab28b7959e2deb34f373d1a8dd82e75fd013da724a`.
Aucune écriture d’expérience dans la base utilisateur.
