# S&P 500 · Momentum SPMO

**Archive.** L’entrée et ses routes ont été retirées le 19 novembre 2026 à la demande de l’utilisateur, qui exige une stratégie utilisable en PEA. Les paragraphes suivants décrivent le fonctionnement avant retrait. La première séance commune du mois fixe la cible en SPMO selon la clôture de PSP5 en euros. La règle principale vise 100 % au-dessus de sa moyenne sur 200 séances, 75 % sinon. La variante MM 150/200 vise 70 %, 85 % ou 100 % selon le nombre de moyennes dépassées. Au démarrage d’une simulation, le signal initial est calculé à la date de départ. Ensuite, seule une modification de cible entraîne un ordre, à la clôture commune suivante. Les poids dérivent entre les ordres.

L’optimiseur évalue 24 réglages à une moyenne et 30 à deux moyennes. Il maximise le rendement annuel moyen parmi ceux qui dépassent PSP5 en rendement et en drawdown moyens sur 250 parcours. Les deux règles de référence et le gagnant éventuel sont ensuite évalués sur 1 000 nouveaux parcours communs. La sélection d’un lot est un résultat de recherche. Elle ne change pas le signal mensuel de la stratégie principale. Les témoins sont PSP5 passif et SPMO passif. La graine affichée est réutilisable via POST /api/portfolio/spmo/optimize (years, count, seed). GET /api/portfolio/spmo/signal fournit la cible mensuelle.

## Deux campagnes au 19 novembre 2026

Première sélection sur 250 parcours de cinq ans, graine 191101. Parmi les 24 règles, MM 200/plancher 85 % maximise le rendement avec les deux moyennes supérieures à PSP5. Audit sur 1 000 parcours par horizon, graines 191205/191210, règles figées. Valeurs en pourcentage, sous forme rendement annualisé moyen / drawdown maximal moyen / doubles victoires.

| Règle | 5 ans | 10 ans |
|---|---|---|
| MM 200, 75 % | 16,67 / −25,36 / 390 | 16,94 / −28,85 / 548 |
| MM 200, 85 % | 17,25 / −25,95 / 377 | 17,53 / −29,50 / 534 |
| PSP5 passif | 15,09 / −25,58 | 15,04 / −30,64 |
| SPMO passif | 17,82 / −26,65 / 339 | 17,88 / −30,03 / 512 |

La règle initiale passe le critère moyen. À cinq ans l’intervalle bootstrap apparié à 95 % sur son gain moyen de drawdown va de −0,08 à +0,53 point. La variante à 85 % échoue sur cette moyenne à cinq ans.

Deuxième sélection exploratoire, après la première campagne. Trente règles à deux moyennes et le témoin à 75 %, 400 nouveaux parcours de sélection à cinq ans (194000). Maximisation du rendement parmi les candidats dont la borne basse normale à 95 % du gain moyen est positive pour les deux critères. Audit séparé sur 1 000 parcours par horizon (194105/194110).

| Règle | 5 ans | 10 ans |
|---|---|---|
| MM 200, 75 % | 17,23 / −25,09 / 410 | 17,41 / −29,01 / 499 |
| MM 150/200, 70 % | 16,86 / −24,70 / 417 | 17,06 / −28,55 / 498 |
| PSP5 passif | 15,22 / −25,29 | 15,44 / −30,20 |

La variante défensive est affichée comme comparaison permanente. La règle 200/75 conserve la priorité pour l’objectif de rendement. Une exécution indépendante de l’API sur copie privée avec years=5, count=1000, seed=191119 a sélectionné MM 50/250, plancher 80 %. Ce réglage a donné 17,37 %/an et −25,21 % contre 15,24 %/an et −25,30 % pour PSP5, 419 doubles victoires. Observation d’un seul lot.

## Conventions et reproduction

PSP5, SPMO et EUR/USD sur leurs dates communes, cours bruts corrigés des divisions, signaux ajustés, distributions implicites créditées en cash, 10 000 € initiaux, ordres en titres entiers et frais de 0,12 %. Aucun spread, commission de change distincte ou impôt. Blocs conjoints circulaires de longueur moyenne 63 séances tirés dans les rendements en euros des deux instruments. Le calendrier futur suit les jours ouvrés de semaine ; les années sont calendaires. Les simulations héritent de la performance relative de SPMO depuis octobre 2015. Les graines réservées ne corrigent pas le biais de sélection de cette période.

Reproduction depuis la racine sur copie privée en mémoire avec `PYTHONPATH=backend .venv/bin/python scripts/study_spmo_optimizer.py`. Sortie locale dans `data/backtests/spmo-optimizer.json`. Sur les historiques 3/5/10 ans les chiffres du moteur pour la règle initiale reproduisent ceux de [l’étude avant intégration](sp500-objectif-indice.md), dont le stress combiné annule le bénéfice de drawdown récent.
