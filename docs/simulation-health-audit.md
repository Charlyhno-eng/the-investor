# Audit des simulations Covid et santé — 11 novembre 2026

## Question et méthode

Pourquoi les actions de santé ne sont-elles pas systématiquement favorisées dans les scénarios Covid et vaccins/réouverture ?

Échantillon exploratoire : Pfizer (PFE), Moderna (MRNA), BioNTech (BNTX), Johnson & Johnson (JNJ), UnitedHealth (UNH), Sanofi (SAN.PA), ainsi que deux proxys sectoriels XLV et XBI. Cours ajustés téléchargés via yfinance, observations de fin de mois et conversion en EUR. Fenêtres identiques au moteur : janvier 2020 → janvier 2021 et octobre 2020 → octobre 2021. Calibration récente de 61 mois, octobre 2021 → octobre 2026.

Ces mesures historiques utilisent le change de fin de mois ; le moteur utilise un change antérieur ou égal au jour de l’observation, avec sept jours maximum de décalage. De légers écarts sont possibles. Les données ajustées peuvent être révisées par le fournisseur.

**Il ne s’agit pas d’un backtest prédictif** : les sensibilités récentes sont appliquées à des chocs anciens, conformément à la simulation demandée. Les activités, attentes et valorisations de ces sociétés ont pu changer. Les performances observées ne sont pas des rendements à imposer à une nouvelle pandémie.

## Comparaison du moteur actuel et des observations

Rendements en EUR, dividendes réinvestis selon les clôtures ajustées ; arrondis au dixième de point.

| Actif | Covid observé | Covid simulé | Réouverture observée | Réouverture simulée |
| --- | ---: | ---: | ---: | ---: |
| Pfizer | −3,7 % | −13,2 % | +35,2 % | +10,9 % |
| Moderna | +668,3 % | +10,9 % | +411,4 % | +36,8 % |
| BioNTech | +264,3 % | +59,0 % | +226,4 % | +8,1 % |
| Johnson & Johnson | +2,4 % | −19,4 % | +21,8 % | +11,7 % |
| UnitedHealth | +13,3 % | −9,8 % | +53,0 % | +19,7 % |
| Sanofi | −8,0 % | −18,0 % | +16,0 % | +11,8 % |
| XLV · santé large | +7,4 % | −8,0 % | +33,6 % | +15,7 % |
| XBI · biotechnologies | +56,4 % | +15,9 % | +10,8 % | +6,4 % |

Le modèle macro manque bien une partie de la réaction sectorielle, mais « santé » ne signifie pas « vaccin gagnant ». Sanofi et Pfizer finissent négatifs sur la première fenêtre. Les trajectoires des développeurs de vaccins sont sans commune mesure avec celles du secteur large.

Les huit facteurs actuels représentent actions, Nasdaq-100, actions internationales, obligations longues, crédit, or, pétrole et change. Ils n’expliquent pas directement l’approbation d’un vaccin, les contrats, les revenus d’un produit ou l’évolution des attentes. Le scénario de réouverture capture aussi la rotation de marché et la reprise économique, pas uniquement la commercialisation des vaccins.

## Expérience : ajouter XLV et XBI

Deux facteurs additionnels ont été testés en régression ridge avec la même pénalité. Ils **ne sont pas activés dans le moteur**. L’amélioration mécanique obtenue sur XLV et XBI eux-mêmes n’est pas une preuve de généralisation : leur propre série est alors utilisée comme facteur.

Sur les six actions, RMSE logarithmique mensuelle de validation sur les douze derniers mois (coefficients réestimés uniquement sur les mois précédents) :

| Actif | Modèle actuel | Avec santé + biotech | Lecture |
| --- | ---: | ---: | --- |
| Pfizer | 6,87 % | 8,34 % | dégradation |
| Moderna | 34,13 % | 31,78 % | amélioration, erreur encore élevée |
| BioNTech | 13,08 % | 13,72 % | dégradation |
| Johnson & Johnson | 6,18 % | 4,59 % | amélioration |
| UnitedHealth | 13,35 % | 15,27 % | dégradation |
| Sanofi | 4,42 % | 3,82 % | amélioration |

Les deux facteurs rapprochent par exemple la simulation de réouverture de JNJ de l’observation (+23,1 % simulé contre +21,8 % observé). Ils ne reconstituent pas les gains spécifiques de Moderna ou BioNTech. Trois erreurs de validation s’améliorent et trois se dégradent. L’échantillon restreint et une seule fenêtre de validation ne permettent pas de conclure à un meilleur moteur global.

## Conclusion technique

L’observation de l’utilisateur met en évidence une limite réelle des facteurs macro. Une règle « santé = hausse en pandémie » déformerait les données. Avant de déployer des facteurs sectoriels, il faut comparer plusieurs validations chronologiques, davantage d’actifs, les régions et les sous-secteurs, puis mesurer les effets sur les autres crises. Les réactions spécifiques aux vaccins nécessitent des hypothèses distinctes sur les produits et entreprises ; elles ne peuvent pas être déduites des seuls prix récents.

Le moteur reste inchangé à l’issue de cet audit. La suppression du graphique détaillé et du tableau de contributions de la watchlist concerne uniquement l’interface ; le tableau comparatif reste disponible.

## Reproduction et sources

Commande : `PYTHONPATH=backend .venv/bin/python scripts/audit_health_simulation.py`. Télécharge les séries publiques et affiche les résultats. Il faut les facteurs actuels en cache local. Les résultats peuvent varier après une actualisation des historiques et de la fenêtre récente.

- [Historique Pfizer — Yahoo Finance](https://finance.yahoo.com/quote/PFE/history/), mêmes URLs pour les autres symboles.
- [Rapport annuel Pfizer 2021](https://www.pfizer.com/sites/default/files/investors/financial_reports/annual_reports/2021/letter-from-ceo/) : développement et déploiement du vaccin avec BioNTech ; le succès commercial est propre à des produits et entreprises.
- [Prospectus officiel XLV](https://www.sectorspdrs.com/api/documents/by-fullname/Sector%20Documents/XLV%20-%20Health%20Care%20Documents/Summary%20Prospectus) : fonds sectoriel large, distinct d’un fabricant de vaccin.
