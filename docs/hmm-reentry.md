# Stop par position, réentrée et décisions du modèle

> Étude historique : le stop est retiré à la demande de l’utilisateur. La politique actuelle est décrite dans [la revue directionnelle](hmm-directional.md).

Correction du 6 novembre 2026, après clarification explicite : **stop de 10 % par position, puis réentrée sur une nouvelle hausse**. Le verrou définitif et la revue hebdomadaire sont supprimés de la stratégie courante. Les résultats restent locaux sous `data/backtests/hmm-reentry/`, ignoré par Git. Aucun push.

## Décisions sans quota de transactions

Le GaussianHMM et ses trois initialisations d’entraînement restent inchangés. Le filtre causal donne les probabilités courantes `p`. Le rendement simple prédit est `p × matrice_transition × moyennes_entraînées`. Un régime calme n’est plus assimilé automatiquement à un signal d’achat : sa prévision peut être négative.

La bande de coûts est calculée avec le taux commun de frais `c`. La durée d’un état est estimée par `1 / (1 − persistance)` ; elle est bornée à une année d’observations pour éviter une durée infinie dans un état absorbant. La durée anticipée `h` est la moyenne de ces durées pondérée par les probabilités prédites. La bande vaut `exp(−2 × log(1−c) / h) − 1`.

Entrée si la prévision dépasse cette bande positive ; sortie si elle passe sous son opposé. Entre les deux, conservation de la position. Ce mécanisme amortit les coûts d’aller-retour sur la durée estimée et évite de changer pour une variation faible. C’est une heuristique économique, pas une preuve de rendement futur ni une résolution exacte d’un problème de contrôle optimal. Aucune cible, borne ou pénalité sur le nombre de transactions ; aucune recherche de seuil par actif. Seuls les frais restent réglables.

Les ordres du modèle s’exécutent à la clôture suivante. Après un stop, il faut une nouvelle prévision positive dépassant la bande, un rendement observé positif et une prévision stable ou croissante par rapport à la veille. Aucune réentrée le jour même du stop. Le nouveau signal s’exécute à la clôture suivante : un HMM inchangé favorable pendant une chute ne provoque pas un rachat instantané dans la même séance.

## Stop à 10 % et hypothèses d’exécution

Le sommet de chaque position est initialisé au capital précédant ses frais d’achat, puis mis à jour aux clôtures détenues. Le prix du stop est fixé avant chaque séance pour préserver 90 % de ce sommet **après frais de vente**. Le haut du jour ne modifie pas le stop avant le bas du même jour : les OHLC ne révèlent pas leur ordre exact.

Les archives locales Yahoo contiennent déjà les OHLC. Ils sont ajustés avec le ratio clôture ajustée/clôture brute et acceptés seulement si la clôture correspond à la série étudiée. Aucune nouvelle donnée téléchargée. La clé du cache inclut les OHLC, et la version de calcul est renouvelée.

- Ouverture sous le seuil : sortie à l’ouverture, avec dépassement réellement comptabilisé.
- Ouverture au-dessus et bas touchant le seuil : sortie au seuil dans le backtest, sous l’hypothèse de liquidité suffisante et de glissement nul.
- OHLC absents ou incohérents : sortie à la clôture observée si elle franchit le seuil ; aucune exécution intrajournalière n’est inventée.

La [SEC rappelle qu’un prix de stop ne garantit pas le prix d’exécution](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins-15). Les écarts d’ouverture et les replis sur clôture restent donc visibles, sans plafonner artificiellement les pertes. Le stop s’exécute indépendamment du signal HMM, sans attendre la clôture supplémentaire autrefois utilisée.

Chaque réentrée réarme une nouvelle position : plusieurs pertes successives peuvent donner un drawdown **global** supérieur à 10 %. Ce choix est distinct d’un plafond garanti sur tout le capital et correspond à la réponse explicite de l’utilisateur. L’interface distingue les stops, les réentrées et le drawdown global.

## Reproduction du cas de la capture

GTT, entraînement du 24/12/2018 au 27/06/2024, test du 28/06/2024 au 06/11/2026, 604 observations, frais 0,1 % à chaque achat et vente. Même sélection initiale de 2 016 prix et découpage à 70 % que l’interface. Les anciens chiffres de la capture sont reproduits avant comparaison.

| Mesure | Ancien verrou | Stop avec réentrée | Conservation |
| --- | ---: | ---: | ---: |
| Rendement net | −0,77 % | +90,12 % | +61,48 % |
| Transactions | 2 | 24 | 2 |
| Drawdown global | 11,15 % | 20,62 % | voir détail local |

Huit stops intrajournaliers, chacun à 10 % net depuis le sommet de sa position, aucun gap sur ces huit exécutions, puis huit réentrées. Toutes les observations de ce test ont un OHLC concordant. Le nombre de 24 ordres résulte des signaux et des stops, sans avoir été imposé.

## Diagnostics sur tous les actifs locaux

Une seule nouvelle politique a été fixée avant l’évaluation, comparée à l’ancien verrou. Aucun ajustement après lecture des chiffres. Entraînement 2015–2021, test continu 2022–2025 ; 23 actifs ayant assez de données, Hyperliquid exclu faute d’entraînement. Deux politiques et trois taux de frais donnent 138 diagnostics ; les six cas supplémentaires reproduisent la capture, soit **144 simulations**.

À 0,1 % par ordre, médianes sur 23 simulations individuelles de quatre ans :

| Mesure | Ancien verrou | Nouvelle politique |
| --- | ---: | ---: |
| Rendement net | −11,26 % | +45,45 % |
| Drawdown global | 12,15 % | 43,98 % |
| Ordres | 2 | 56 |
| Actifs rentables | 3 / 23 | 16 / 23 |
| Surperformance sur conservation | 4 / 23 | 8 / 23 |

Ces médianes ne sont pas les performances d’un portefeuille diversifié. La protection par position autorise la reprise, mais laisse un risque cumulé important, surtout sur les cryptos. 801 stops sur ces simulations : 748 au seuil net de 10 %, 53 dépassés par un gap à l’ouverture. Aucun repli sur clôture n’a été nécessaire dans ce panel.

| Frais par ordre | Rendement médian net | Drawdown global médian | Ordres médians | Actifs rentables |
| --- | ---: | ---: | ---: | ---: |
| 0 % | +42,88 % | 43,75 % | 92 | 19 / 23 |
| 0,1 % | +45,45 % | 43,98 % | 56 | 16 / 23 |
| 0,5 % | +12,87 % | 50,14 % | 54 | 14 / 23 |

Les résultats ne sont pas monotones en frais parce que les bandes de décision et le déclenchement des stops changent avec les frais. Tous les scénarios sont conservés ; aucun taux n’a été choisi pour améliorer le rapport.

## Surapprentissage et vérifications

Ces périodes et actifs ont déjà été examinés pendant la recherche précédente : **ce sont des diagnostics de données connues, pas un nouveau test vierge**. Les décisions restent causales et le HMM n’est ajusté que sur l’entraînement. Cela ne prouve ni l’absence d’overfitting ni une surperformance future. Le bon résultat sur GTT n’efface pas le drawdown global élevé et les sous-performances du reste du panel. Les biais de survivance du catalogue et de données révisées restent présents.

`plan.json` contient les règles et les empreintes du modèle, du moteur, des OHLC, du service et des métriques. `results.json` conserve courbes, ordres, événements et empreintes des données ; `summary.csv` fournit les 144 cas compacts. Le script refuse d’écraser un résultat existant :

```sh
PYTHONPATH=backend .venv/bin/python scripts/backtest_reentry.py
```

Les tests couvrent signal prédit, bande de coûts, stop au seuil avant le prochain signal, frais dans le budget, gap réel sans troncature, absence d’OHLC, réentrée après hausse, absence de réentrée baissière, plusieurs stops réarmés, causalité, ajustement des OHLC, rejet d’archives obsolètes et invalidation après correction.

Vérifications terminées : 81 tests backend, 18 tests d’interface sur ordinateur et mobile, compilation de production du frontend et contrôles Ruff. Les simulations restent locales, sans push GitHub.
