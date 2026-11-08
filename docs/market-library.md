# Bibliothèque et diagnostics de marché

La watchlist réutilise `/portfolio/regression`, comme le portfolio : écart du dernier prix à la tendance logarithmique sur cinq ans, en écarts types résiduels. La pente du graphique de régression dépend de la période sélectionnée. En logarithmique, son équivalent annuel vaut `exp(pente) - 1` ; en linéaire, la pente par année est divisée par le prix initial ajusté de la droite. Ce dernier pourcentage est une variation annuelle relative à cette base, pas un rendement composé.

Le badge dividende est automatique : moyenne des sommes annuelles des rendements par versement, sur les trois dernières années civiles complètes couvertes disponibles. Une année couverte sans versement compte pour zéro. Seuil strictement supérieur à 4 %. Chaque rendement utilise le dividende brut et la clôture précédant le détachement ; il ne représente pas le rendement net après fiscalité. Une donnée manquante n’est pas assimilée à un rendement nul. L’ancien indicateur manuel et son endpoint sont retirés.

Les catalogues sont centralisés dans `market_catalog.py` et `countries.py` : un ETF SPDR S&P 500 (SPY), vingt devises cotées en USD, vingt matières premières et vingt références souveraines. Les séries écartées restent archivées mais sont masquées de la bibliothèque. Les obligations sont classées par moyenne des taux observés sur douze mois. Ce sont des rendements de référence, pas des performances de titres détenus. Le Brésil utilise les données officielles Tesouro Direto : obligation nominale Prefixado disponible la plus proche de dix ans à chaque date ; la maturité varie selon les émissions disponibles. Les autres pays utilisent les références souveraines FRED/OECD à dix ans. Les risques et devises diffèrent.

Le worker actualise les nouveaux catalogues quotidiennement. Les secteurs des actions proviennent du profil fournisseur Yahoo ; une absence de données laisse le secteur vide. Les catalogues et métadonnées sont servis localement par l’API, sans appels fournisseur lors de la lecture de la bibliothèque.

Sources :
- https://www.bis.org/statistics/rpfx25_fx.pdf (contexte de sélection des grandes devises)
- https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3 (taux brésiliens)
