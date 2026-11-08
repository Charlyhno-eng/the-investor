# Bibliothèque et diagnostics de marché

La watchlist réutilise `/portfolio/regression`, comme le portfolio : écart du dernier prix à la tendance logarithmique sur cinq ans, en écarts types résiduels. La pente du graphique de régression dépend de la période sélectionnée. En logarithmique, son équivalent annuel vaut `exp(pente) - 1` ; en linéaire, la pente par année est divisée par le prix initial ajusté de la droite. Ce dernier pourcentage est une variation annuelle relative à cette base, pas un rendement composé.

Le badge dividende est automatique : moyenne des sommes annuelles des rendements par versement, sur les trois dernières années civiles complètes couvertes disponibles. Une année couverte sans versement compte pour zéro. Seuil strictement supérieur à 4 %. Chaque rendement utilise le dividende brut et la clôture précédant le détachement ; il ne représente pas le rendement net après fiscalité. Une donnée manquante n’est pas assimilée à un rendement nul. L’ancien indicateur manuel et son endpoint sont retirés.

Les catalogues sont centralisés dans `market_catalog.py` et `countries.py` : un ETF SPDR S&P 500 (SPY), vingt devises cotées en USD, douze matières premières à cours journaliers et vingt références souveraines. Les séries écartées restent archivées mais sont masquées de la bibliothèque. Les obligations sont classées par moyenne des taux observés sur douze mois. Ce sont des rendements de référence, pas des performances de titres détenus. Le Brésil utilise les données officielles Tesouro Direto : obligation nominale Prefixado disponible la plus proche de dix ans à chaque date ; la maturité varie selon les émissions disponibles. Les autres pays utilisent les références souveraines FRED/OECD à dix ans. Les risques et devises diffèrent.

Le worker actualise les nouveaux catalogues quotidiennement. Les secteurs des actions proviennent du profil fournisseur Yahoo ; une absence de données laisse le secteur vide. Les catalogues et métadonnées sont servis localement par l’API, sans appels fournisseur lors de la lecture de la bibliothèque.

Sources :
- https://www.bis.org/statistics/rpfx25_fx.pdf (contexte de sélection des grandes devises)
- https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3 (taux brésiliens)


Les matières premières utilisent désormais les clôtures journalières de futures Yahoo : Brent (`BZ=F`), gaz naturel US (`NG=F`), or (`GC=F`), argent (`SI=F`), platine (`PL=F`), aluminium (`ALI=F`), cuivre (`HG=F`), blé HRW (`KE=F`), maïs (`ZC=F`), soja (`ZS=F`), café arabica (`KC=F`) et cacao (`CC=F`). Les références sans équivalent journalier validé (charbon australien, minerai de fer, plomb, nickel, étain, zinc, riz thaï et coton) sont masquées. Aucun cours mensuel n’est interpolé en cours quotidien. Les imports quotidiens remplacent la série entière dans une transaction, sans mélanger prix physiques mensuels et futures ; les téléchargements bruts restent archivés.

Les identifiants des douze références restent stables afin de conserver les watchlists, quantités et stratégies du navigateur. Les prix sont convertis vers les anciennes unités : USD par once troy, baril, million de BTU, tonne métrique ou kilogramme. Pour les grains, le boisseau vaut 60 livres pour le blé et le soja, 56 pour le maïs ; une livre vaut 0,45359237 kg. Les cotations `USX` sont des cents USD. Le cuivre est coté en dollars par livre, le café en cents par livre, le cacao en dollars par tonne. Les unités de quantité restent physiques, pas des nombres de contrats ni des marges de futures.

Ces futures sont des références de prix, différentes des prix spot de la Banque mondiale. Les changements d’échéance peuvent créer des ruptures ; la courbe n’est pas le rendement d’une stratégie renouvelant des contrats (roulement, collatéral et frais absents). Les fiches signalent cette convention. `make import` et le worker actualisent les futures ; `--source world-bank` reste un import d’archive et ne remplace jamais une référence déjà migrée en quotidien.

Sources des nouvelles références : [Yahoo Brent](https://finance.yahoo.com/quote/BZ%3DF/history/), [Yahoo aluminium](https://ca.finance.yahoo.com/quote/ALI%3DF/), [Yahoo blé HRW](https://finance.yahoo.com/quote/KE%3DF/chart/), [spécifications des grains CME](https://www.cmegroup.com/trading/agricultural/files/AC-268_Grains_FC_FINAL_SR.pdf).
