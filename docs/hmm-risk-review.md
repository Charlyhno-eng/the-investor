# HMM : rotation, protection et audit de rentabilité

> Archive : ce document concerne les versions ou recherches antérieures à la reconstruction du 6 novembre 2026. Le [moteur actif est décrit ici](hmm-rebuilt.md).

> Version historique : le verrou définitif est remplacé par [un stop par position avec réentrée](hmm-reentry.md), selon la clarification de l’utilisateur.

Étude locale du 6 novembre 2026. Aucun commit, push, publication ou envoi de données. Les résultats volumineux sont dans `data/backtests/hmm-risk/`, ignoré par Git.

**Conclusion : la correction réduit fortement les transactions et implémente le seuil de protection demandé, mais la rentabilité n’est pas validée. Le contrôle réservé échoue. Il serait incorrect de présenter cette stratégie comme rentable ou sans surapprentissage.**

## Références et choix techniques

[QuantStart / QSTrader](https://www.quantstart.com/articles/market-regime-detection-using-hidden-markov-models-in-qstrader/) utilise le HMM comme gestionnaire de risque d’une stratégie de tendance. Un état peu volatil ne constitue pas, seul, une prévision de rendement positif. Nous avons donc comparé une variante HMM avec tendance SMA200, sans la retenir automatiquement.

[Fox et al., ICML 2008](https://icml.cc/Conferences/2008/papers/305.pdf) étudient la persistance des états et le problème des commutations excessives. Ce papier ne justifie pas une rentabilité financière. Notre correction utilise une hystérésis de décision et une revue hebdomadaire ; elle n’implémente pas leur modèle bayésien sticky HDP-HMM et ne force pas artificiellement la matrice de transition.

[Moskowitz, Ooi et Pedersen](https://www.aqr.com/insights/research/journal-article/time-series-momentum) documentent le momentum temporel sur des contrats futures diversifiés. Cela motive un contrôle de tendance mais ne prouve pas l’efficacité de notre filtre SMA200 sur actions individuelles et cryptos.

[Bailey et al.](https://www.davidhbailey.com/dhbpapers/overfitting.pdf) expliquent pourquoi la multiplication des essais favorise le surapprentissage. Le protocole limite donc les variantes, conserve les échecs et interdit les modifications entre sélection et audit.

## Correction implémentée

- HMM inchangé : rendements journaliers, deux états, trois initialisations choisies sur vraisemblance d’entraînement. Aucun nouveau réglage de modèle sur les résultats de trading.
- Premier cours disponible de chaque semaine ISO : entrée si probabilité calme > 80 %, sortie si probabilité calme ≤ 20 %, conservation entre ces seuils.
- Signal de clôture exécuté à la clôture suivante ; aucune information future.
- Seul champ réglable : frais proportionnels identiques par achat et vente.
- Drawdown quotidien sur le capital net depuis son sommet, capital initial compris. Détection à 10 %, vente à la clôture suivante, sans attendre la revue hebdomadaire.
- Après déclenchement, achats bloqués jusqu’à la fin du test ; pas de remise à zéro annuelle, pas de redémarrage opportuniste après une perte.
- Le journal distingue signal, protection et liquidation finale. L’interface affiche le déclenchement et la suspension des achats.

**Le seuil de 10 % n’est pas un plafond garanti.** Des clôtures journalières ne permettent pas de connaître le premier prix négociable lors du franchissement intrajournalier. Les pertes peuvent déjà dépasser 10 % lors de la détection, puis s’aggraver avant l’exécution et ses frais. Les courbes et métriques conservent ces dépassements réels ; aucune perte n’est plafonnée dans les calculs. Un arrêt définitif réduit également les chances de participer au rebond.

## Protocole fixé avant l’évaluation

Le [plan](../scripts/hmm_research_plan.json) définit cinq politiques : quotidienne originale ; quotidienne avec protection ; hebdomadaire HMM avec protection ; hebdomadaire tendance + HMM avec protection ; contrôle tendance seule avec protection. Seules les deux variantes hebdomadaires HMM sont candidates à la sélection. Aucun balayage de paramètres ou choix par actif.

Validation : entraînement 2015–2017, test continu 2018–2021 sur les huit actifs de développement de l’étude précédente. ETH et SOL exclus faute de 101 prix d’entraînement : **six actifs**, cinq politiques, trois taux de frais = **90 évaluations**. Les dates et actifs déjà examinés auparavant restent des données de développement, pas un test vierge.

Critère fixé : Sharpe net médian à 10 pb ; en cas d’égalité, variante HMM seule. Les deux candidates obtiennent le même score médian (−0,107) ; sélection de `weekly_hmm`. Ce score négatif n’est pas un succès. Le choix a été figé dans `selection.json` avant l’ouverture de l’audit.

Audit : entraînement 2015–2021, test continu 2022–2025. Douze nouveaux actifs : ASML, BESI, GTT, Hermès, Safran, Schneider, TotalEnergies, Tesla, ADA, BNB, XRP, XMR. Variante sélectionnée et trois contrôles définis au préalable, trois taux de frais = **144 évaluations**. Aucun ajustement après consultation de ces résultats. Les épisodes d’arrêt ne sont pas réinitialisés entre années.

Les empreintes SHA-256 du plan, du moteur de simulation/modèle et des historiques sont enregistrées. L’audit refuse un changement du plan ou du noyau après validation. Les scripts refusent d’écraser leurs fichiers de résultats.

## Résultats de l’audit, frais de 0,1 % par ordre

Médianes sur douze simulations individuelles continues de quatre ans ; ce ne sont pas les performances d’un portefeuille agrégé.

| Politique | Rendement net médian | Sharpe médian | Drawdown médian | Ordres médians | Actifs rentables | Bat la conservation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Quotidienne originale | +11,87 % | 0,318 | 46,74 % | 70 | 8 / 12 | 2 / 12 |
| Quotidienne + protection | −10,42 % | −0,464 | 12,09 % | 4 | 2 / 12 | 1 / 12 |
| **Hebdomadaire HMM + protection retenue** | **−11,52 %** | **−0,728** | **12,24 %** | **2** | **2 / 12** | **1 / 12** |
| Contrôle tendance seule + protection | −9,42 % | −0,598 | 11,05 % | 2 | 1 / 12 | 1 / 12 |

Le faible nombre d’ordres résulte aussi du verrou de protection, pas seulement de l’hystérésis. Comparer la version protégée à la version originale ne permet pas d’attribuer toute la réduction à la fréquence hebdomadaire.

Les douze simulations retenues déclenchent la protection et dépassent chacune 10 % de drawdown. Ce résultat confirme la limite d’un seuil détecté et exécuté sur clôtures, sans inventer un prix de vente au seuil. La variante retenue ne généralise pas mieux que le contrôle quotidien protégé.

Sensibilité de la variante retenue :

| Frais par ordre | Rendement net médian | Drawdown médian | Actifs rentables |
| --- | ---: | ---: | ---: |
| 0 % | −11,34 % | 11,99 % | 2 / 12 |
| 0,1 % | −11,52 % | 12,24 % | 2 / 12 |
| 0,5 % | −10,89 % | 13,14 % | 2 / 12 |

La sensibilité n’est pas strictement monotone : les frais peuvent avancer le déclenchement du stop, donc modifier les dates des ordres et les rendements capturés. Tous les scénarios sont conservés, sans sélectionner le plus favorable.

## Portée des conclusions

La causalité des calculs et la séparation sélection/audit sont vérifiées ; elles ne prouvent pas une absence de surapprentissage. Les actifs sont corrélés, sélectionnés dans le catalogue actuel et exposés à un biais de survivance. Les années d’audit recoupent des années déjà vues sur d’autres actifs. Cet audit apporte une indépendance partielle par actifs et chronologie, pas une certification statistique.

Pas de test de significativité positif, pas de preuve d’alpha, pas de garantie de rentabilité. L’audit réservé est désormais consommé ; une prochaine recherche doit le traiter comme développement et réserver de nouvelles données. Aucun changement n’a été effectué dans les règles après l’échec pour faire disparaître ce résultat.

## Reproduction locale et tests

```sh
PYTHONPATH=backend .venv/bin/python scripts/research_hmm.py validation
PYTHONPATH=backend .venv/bin/python scripts/research_hmm.py audit
```

Les artefacts déjà présents ne sont pas écrasés : conserver leur répertoire avant une nouvelle reproduction. Fichiers : `validation.json`, `selection.json`, `audit.json` sous `data/backtests/hmm-risk/`. Ils contiennent les courbes nettes, ordres, coûts, métriques, dates et événements du stop, ainsi que les empreintes de données.

Un export compact des 234 cas est disponible dans `data/backtests/hmm-risk/summary.csv`. Validation fonctionnelle : 66 tests backend, 18 tests navigateur (ordinateur/mobile), Ruff et build TypeScript/Vite réussis.

Les tests couvrent seuil exact, sommet après gain, frais, gap avec dépassement non tronqué, délai d’exécution, sortie d’urgence hors revue hebdomadaire, absence de réentrée après changement d’année, hysteresis, jours manquants, causalité des variables et des régimes, cache et affichage de l’arrêt sur ordinateur/mobile.
