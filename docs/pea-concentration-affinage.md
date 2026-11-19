# PSP5 PEA · Affinage de la concentration des baisses

**Décision au 19 novembre 2026 — conserver la règle actuelle.** Parmi les sept variantes retenues en apprentissage, aucune ne gagne en rendement moyen face à la règle actuelle sur les parcours réservés, à cinq ou dix ans. Deux pistes réduisent sensiblement la volatilité. Leur coût en rendement dépend fortement de la période.

## Ce qui change dans les variantes

Le témoin actif détient PSP5 sauf lorsque la somme des carrés des rendements logarithmiques négatifs dépasse 80 % de la somme de tous les carrés sur 21 séances. Décision toutes les cinq séances depuis le début du test, ordre à la clôture suivante. Le témoin passif achète PSP5 à la même première clôture admissible.

La décomposition entre variations positives et négatives s’inspire de la semi-variance réalisée. Les auteurs de l’étude de référence examinent la prévision de volatilité avec des données à haute fréquence. Les règles quotidiennes d’achat et de vente ci-dessous sont des adaptations expérimentales. [Barndorff-Nielsen, Kinnebrock et Shephard](https://www.nuff.ox.ac.uk/economics/papers/2008/w2/downside.pdf)

504 paramétrages ont été comparés sur trois périodes distinctes de PSP5 en euros, 2015–2016, 2017–2018 et 2019–2020. Chaque famille combine trois fenêtres (15, 21, 32 séances), quatre seuils (70, 75, 80, 85 %), trois cadences (3, 5, 8 séances) et deux expositions défensives (0 ou 35 %). Un représentant par famille est figé avant la comparaison suivante. Le classement additionne le plus faible gain moyen parmi les trois indicateurs et le gain moyen de la moins bonne période, en points, face à la règle actuelle. Une diminution de volatilité ou de perte compte comme un gain.

| Variante | Modification du signal | Fenêtre / seuil / cadence / exposition défensive retenus |
|---|---|---|
| Chocs plafonnés | Limiter chaque rendement à deux fois la racine de la moyenne des carrés sur les 63 séances précédentes | 15 / 80 % / 8 / 0 % |
| Amplitude absolue | Remplacer les carrés par les valeurs absolues | 15 / 75 % / 5 / 0 % |
| Pondération exponentielle | Accorder plus de poids aux variations récentes, coefficient 2/(fenêtre+1) | 32 / 75 % / 8 / 0 % |
| Rendements sur deux séances | Calculer la part des baisses avec les variations glissantes de deux séances | 21 / 75 % / 8 / 0 % |
| Majorité de baisses | Exiger aussi que plus de la moitié des séances soient négatives | 15 / 85 % / 5 / 0 % |
| Alerte de volatilité | Sortir aussi si la variation sur 21 séances est négative et si la volatilité quadratique sur 10 séances dépasse 1,6 fois celle sur 126 | 21 / 80 % / 3 / 0 % |
| Alerte de tendance | Réduire aussi l’exposition sous la moyenne mobile 150 séances si la variation sur 42 séances est négative | 32 / 85 % / 8 / 35 % |

## Comparaison sur marchés simulés

Chaque colonne de performance est une moyenne sur les mêmes marchés pour toutes les règles. DD désigne la pire baisse entre un sommet et un creux sur chaque parcours. La dernière colonne compte les parcours où la règle bat strictement le passif **à la fois** en rendement et en drawdown. Rendements et volatilités sont annualisés.

| Stratégie | Rendement 5 ans | DD 5 ans | Vol. 5 ans | Rendement 10 ans | DD 10 ans | Vol. 10 ans | Double victoire 5 ans / 10 ans |
|---|---:|---:|---:|---:|---:|---:|---:|
| PSP5 passif | 15,17 % | −25,28 % | 16,56 % | 14,77 % | −30,17 % | 16,63 % | — |
| Règle actuelle | 15,53 % | −21,00 % | 15,60 % | 15,06 % | −24,46 % | 15,66 % | 432/1 000 · 152/300 |
| Chocs plafonnés | 14,68 % | −23,96 % | 16,06 % | 14,26 % | −28,37 % | 16,13 % | 208/1 000 · 74/300 |
| Amplitude absolue | 15,32 % | −22,05 % | 15,81 % | 14,85 % | −25,41 % | 15,86 % | 329/1 000 · 131/300 |
| Pondération exponentielle | 15,22 % | −21,27 % | 15,50 % | 14,77 % | −24,49 % | 15,54 % | 373/1 000 · 132/300 |
| Rendements sur deux séances | 13,27 % | −20,60 % | 14,68 % | 12,77 % | −24,37 % | 14,70 % | 242/1 000 · 49/300 |
| Majorité de baisses | 15,16 % | −21,85 % | 15,72 % | 14,71 % | −25,39 % | 15,78 % | 351/1 000 · 122/300 |
| Alerte de volatilité | 12,94 % | −21,06 % | 14,73 % | 12,65 % | −24,60 % | 14,80 % | 203/1 000 · 43/300 |
| Alerte de tendance | 12,12 % | −20,54 % | 14,00 % | 11,69 % | −24,62 % | 14,06 % | 61/1 000 · 7/300 |

La règle actuelle remplit le double objectif dans 432 parcours sur 1 000 à cinq ans, puis 152 sur 300 à dix ans. Même les variantes donnant une volatilité plus faible peuvent subir des pertes sévères. À cinq ans, le seuil délimitant les 5 % de drawdowns les plus profonds atteint −30,4 % pour la règle actuelle et −30,7 % pour la variante deux séances.

## Contre-épreuve historique et coûts

| Stratégie | Depuis janvier 2021 · rendement / DD / volatilité | Dix dernières années · rendement / DD / volatilité |
|---|---|---|
| PSP5 passif | 15,61 % / −23,19 % / 14,78 % | 13,94 % / −33,67 % / 16,15 % |
| Règle actuelle | 14,68 % / −22,51 % / 14,54 % | 14,08 % / −26,65 % / 14,84 % |
| Rendements sur deux séances | 13,58 % / −19,27 % / 12,60 % | 12,39 % / −19,43 % / 13,79 % |
| Alerte de volatilité | 11,59 % / −23,82 % / 13,93 % | 14,02 % / −18,81 % / 14,07 % |

**La piste la plus défensive mérite un prix explicite.** Depuis janvier 2021, les rendements sur deux séances économisent 3,24 points de drawdown et 1,94 point de volatilité pour un coût de 1,10 point de rendement annualisé face à la règle actuelle. En moyenne synthétique à cinq ans, le coût augmente à 2,26 points de rendement pour seulement 0,40 point de drawdown économisé. Sur huit dates de départ consécutives début 2021, elle améliore les trois mesures ensemble sur deux départs.

**L’alerte de volatilité est sensible à la période choisie.** Sur dix ans historiques elle économise 7,84 points de drawdown pour 0,06 point de rendement annuel sacrifié. Depuis janvier 2021, elle perd 3,09 points de rendement annuel et subit un drawdown plus profond de 1,31 point. Avec frais doublés et exécution à la deuxième clôture sur cette dernière période, elle atteint 13,07 % de rendement et −23,86 % de drawdown, contre 14,51 % et −22,47 % pour la règle actuelle.

## Hypothèses et reproduction

- Copie SQLite en mémoire, 3 201 clôtures PSP5 du 20 mai 2014 au 19 novembre 2026. Capital neuf de 10 000 €, cash à 0 %, titres entiers, frais de 0,12 % à chaque achat et vente, aucun levier. Le coût de marché effectif peut différer. Les cibles sont exécutées seulement à l’initialisation et aux changements de signal.
- 1 000 parcours de cinq ans, graines à partir de 381905100, puis 300 de dix ans à partir de 381907100. Générateur de l’application, blocs historiques de longueur moyenne 63 séances et bruit de 5 % de la volatilité quotidienne. Le lot utilise de nouvelles graines, avec la même source économique. Les fréquences dépendent de ce modèle.
- La sélection de cette campagne s’arrête en 2020. La période depuis 2021 a déjà été examinée dans les recherches précédentes. La fenêtre historique de dix ans chevauche l’apprentissage. Seules des observations futures apporteront une épreuve prospective.
- Le script vérifie les trois indicateurs des deux témoins contre le moteur indépendant de la stratégie sur les horizons historiques 1, 3, 5 et 10 ans ainsi que depuis 2021. Le JSON contient tous les résultats d’apprentissage, les paramètres figés, frais, nombres d’ordres, mesures de risque, décalages de départ et test de frais et de retard.

Reproduire depuis la racine avec `PYTHONPATH=backend .venv/bin/python scripts/study_pea_downside_refinements.py`. [Script de recherche](../scripts/study_pea_downside_refinements.py) · [Résultats chiffrés](../data/backtests/pea-downside-refinements.json).
