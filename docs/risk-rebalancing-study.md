# Parité de risque : rééquilibrage et suivi des contributions

## Protocole fixé avant calcul

Script : `PYTHONPATH=backend uv run python scripts/study_risk_rebalancing.py`.
Résultats : `data/backtests/risk-rebalancing.json`, empreinte SQLite incluse.
La base utilisateur est ouverte en lecture seule pour créer une copie temporaire.

96 simulations : 3 univers (journal_14, actions_11, crypto_4), 4 fenêtres historiques
(2016–2021, 2021–2024, 2024–2026, 2021–2026), frais de 0,5 % et 1 %, quatre variantes.
Titres entiers pour les actions/ETF, cryptos fractionnaires, capital 10 000 €.
Les contrôles achat-conservation, équipondération et référence restent calculés.

Variantes : contrôle sans tolérance, tolérance sur les poids de 3 points,
tolérance sur les contributions de variance de 3 points, combinaison des deux.
Chaque variante doit, dans chaque cas, limiter la perte de CAGR à 0,5 point,
la perte de Sharpe à 0,03, et la dégradation de drawdown à 1 point.
La somme descriptive des frais et des rotations doit baisser. Les fenêtres se
recouvrent : cette somme n'est pas un résultat de portefeuille indépendant.
Préférence fixée avant résultats : combinaison, puis risque seul, puis poids seuls.
Aucun ajustement après résultats. Ces historiques déjà examinés ne sont pas un
échantillon inédit et ces critères ne sont pas un test statistique.

## Règles retenues

Les trois variantes passent. L'interface applique la combinaison en parité de risque.
L'API conserve des tolérances nulles par défaut pour reproduire les anciens calculs ;
l'interface transmet explicitement `rebalance_tolerance=0.03` et
`risk_rebalance_tolerance=0.03`. Les autres méthodes ne changent pas.

Aux dates trimestrielles, conserver les quantités seulement si tous les écarts de
poids et de contributions restent dans les bandes. La part de cash doit aussi
rester à moins de 3 points de la cible. Une contribution indéfinie impose une
révision ; l'entrée initiale n'est jamais ignorée. Les contributions signées sont
`v_i (Σv)_i / (vᵀΣv)`, cash sans risque. Un nouvel actif admissible est donc aussi
pris en compte dans le contrôle de risque. Les décisions utilisent les valeurs
et la covariance connues au signal, jamais les cours du lendemain.

Le détail affiche cible, contributions des quantités après exécution (ou après
révision sans transaction), puis contributions en fin de période. La covariance
est figée à celle du signal pour isoler la dérive des positions. Ce ne sont pas
des contributions calculées à partir d'une covariance future, ni une nouvelle
estimation quotidienne des corrélations.

## Résultat sur journal_14, cinq ans, frais 0,5 %

| Mesure | Contrôle | Combinaison retenue |
|---|---:|---:|
| Rendement net | 172,16 % | 175,21 % |
| CAGR | 22,20 % | 22,47 % |
| Drawdown maximal | −15,22 % | −15,22 % |
| Sharpe | 1,450 | 1,464 |
| Frais | 259,30 € | 247,94 € |
| Rotation annuelle | 53,46 % | 50,58 % |
| Révisions ignorées | 0 | 2 |

La tolérance sur poids seule réduit davantage les frais sur cette fenêtre, mais
la combinaison respecte mieux l'objectif de contributions égales. Risque seul
et combinaison donnent ici les mêmes opérations. Les critères permettent de
petites dégradations : passer ne signifie pas gagner dans chaque cas ni garantir
une amélioration future. Aucun résultat ne justifie une promesse de rendement.
