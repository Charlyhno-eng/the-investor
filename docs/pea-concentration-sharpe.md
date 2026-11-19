# Maximisation du Sharpe sur PSP5 PEA

**Le meilleur candidat selon le Sharpe moyen simulé utilise 32 séances et vérifie le signal chaque soir.** La part des rendements logarithmiques négatifs au carré est rapportée à la somme de tous les carrés. Si elle dépasse strictement 80 %, la cible est 100 % liquidités. Sinon, elle est 100 % PSP5. L’exécution intervient à la clôture suivante, à l’initialisation puis aux changements de cible. Le seuil est celui de la règle actuelle, qui utilise 21 séances et décide toutes les cinq séances.

## Résultats au 19 novembre 2026

| Sharpe net | PSP5 passif | Règle actuelle | 32 séances, quotidien | Gagnant de l’apprentissage historique |
|---|---:|---:|---:|---:|
| Moyenne de 1 000 parcours réservés de 5 ans | 0,9442 | 0,9998 | **1,0129** | 0,9144 |
| Moyenne de 300 parcours réservés de 10 ans | 0,9098 | 0,9678 | **0,9763** | 0,8801 |
| Historique depuis janvier 2021 | 1,0383 | 0,9981 | 1,0033 | **1,0562** |
| Historique 1 an | 1,3164 | 1,1066 | 1,3164 | 1,2088 |
| Historique 3 ans | 1,2298 | **1,5019** | 1,1704 | 1,3079 |
| Historique 5 ans | 0,7398 | **0,8575** | 0,6895 | 0,7039 |
| Historique 10 ans | 0,8765 | 0,9479 | **0,9941** | 0,9028 |
| Depuis janvier 2021, frais doublés et exécution décalée d’une séance | **1,0196** | 0,9889 | 0,8352 | 0,9762 |

Le candidat quotidien gagne face à la règle actuelle sur 578/1 000 parcours à cinq ans et 174/300 à dix ans. Les gains moyens de Sharpe sont de +0,0131 et +0,0085. Les intervalles approximatifs à 95 % pour ces différences appariées sont respectivement [+0,0080 ; +0,0182] et [+0,0021 ; +0,0149]. Ils quantifient uniquement l’erreur Monte-Carlo du modèle. Les résultats historiques à trois et cinq ans et la sensibilité au prix d’exécution motivent le maintien de la stratégie active pendant l’évaluation du candidat.

La seconde sélection utilise uniquement le Sharpe historique d’apprentissage. Son gagnant calcule des rendements glissants sur deux séances et mesure la concentration sur 21 observations, avec un seuil de 75 % vérifié toutes les huit séances. Son Sharpe depuis 2021 atteint 1,0562, mais son Sharpe simulé est inférieur aux deux témoins aux deux horizons.

## Protocole

- 2 443 configurations distinctes, témoins inclus. Comparaison des familles de concentration des baisses, alertes de volatilité et de tendance, momentum, retour à la moyenne, canaux et autres signaux de la campagne PEA. Aucun critère de classement autre que le Sharpe. Le maximum concerne cette grille.
- Sharpe annualisé selon la convention de l’application, moyenne des rendements quotidiens simples nets divisée par leur écart-type échantillonnal, multipliée par la racine de 252. Taux sans risque et rendement du cash supposés nuls. Capital initial de 10 000 €, parts entières, frais de 0,12 % par ordre, PSP5 en euros et liquidités.
- Sélection principale sur le Sharpe moyen de 120 parcours de cinq ans, construits exclusivement avec les rendements disponibles avant janvier 2021. Sélection historique parallèle sur la moyenne des Sharpe de trois périodes de deux ans, de 2015 à 2020. Les deux gagnants sont figés avant les comparaisons réservées.
- Vérification sur 1 000 parcours de cinq ans et 300 de dix ans avec des graines distinctes et des marchés identiques pour chaque concurrent. Les parcours réservés rééchantillonnent l’historique complet PSP5 par blocs moyens de 63 séances, auquel s’ajoute le bruit du générateur de l’application. Les données depuis 2021 ont été examinées lors de campagnes antérieures. La fenêtre historique de dix ans chevauche l’apprentissage.
- Reproduction depuis la racine avec `PYTHONPATH=backend .venv/bin/python scripts/study_pea_downside_sharpe.py`. Le script vérifie les Sharpe des deux témoins contre leurs courbes quotidiennes et utilise une copie en mémoire de la base. [Code de recherche](../scripts/study_pea_downside_sharpe.py) · [Grille, classements et résultats](../data/backtests/pea-downside-sharpe.json).
