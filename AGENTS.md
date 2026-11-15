# The Investor — repères pour les prochaines sessions

## Dernière adoption — régression Sharpe v6, 15 novembre 2026

- Après recommandation du candidat historique, l'utilisateur demande sa mise
  en place. **Politique active : `slow_defensive_sharpe_v6`**, remplaçant v5.
  Deux budgets initiaux indépendants75%lent/25%défensif, **aucune poche passive**.
  Chaque poche cible10%PSP5 en état défensif,100%sinon, uniquement à
  l'initialisation/changement d'état ; poids dérivants, aucun transfert/netting.
- Seuils, fenêtres60/18mois, calendriers mensuel/cinq séances, état lent rejoué
  strictement avant début et défensive initialement défensive inchangés.
  PSP5 EUR/frais0,12%, clôture suivante, titres entiers par poche, choix1/3/5/10ans
  et générateur inchangés. Aucun changement de base ou de quantités utilisateur.
- L'objectif reste **Sharpe seul**. Réel3/5/10ans1,8875/1,4873/1,3520 contre
  1,6121/1,1407/1,1111 v5,24/24fenêtres5ans supérieurs ; mais réservé
  synthétique5/10ans0,853/0,803 contre0,919/0,903. Adoption après présentation
  de ce désaccord, pas validation prospective ni réécriture des anciens échecs.
- `docs/sp500-sharpe-adoption.md`, `scripts/verify_sp500_sharpe.py` :18cas
  historiques/synthétiques contre candidat figé et moteur indépendant, copie
  SQLite privée, métriques1e-9/frais1e-6€. Sortie distincte
  `data/backtests/sp500-sharpe-production-verification.json`.
- Vérificateur générique courant `verify_sp500_simulation.py` : sortie distincte
  `sp500-sharpe-simulation-verification.json`,9scénarios et lot logiciel25pour
  cette adoption (défaut1000 inchangé). Ancien vérificateur core35 protégé par
  version ; tous rapports v4/v5/recherche archivés inchangés. Les contrôles de
  production v5 incorporés aux anciennes études ne vérifient pas v6.
- 462tests backend,40tests unitaires frontend et vérifications/build réussis.
  E2E30cas :29réussis au lot, cas annexe de verrouillage expiré puis réussi
  isolément ; parcours S&P ordinateur/mobile réussis. Vérifications logicielles,
  pas validation financière.

## Nouvel objectif explicite — recherche avant adoption v6, 15 novembre 2026

- L'utilisateur remplace les anciens objectifs rendement/drawdown : désormais
  **maximiser le ratio de Sharpe seul**, sans plancher de CAGR ni plafond de DD.
  Garder sans levier/shorts, PSP5 EUR/cash, frais et exécution causale. Rendement,
  DD, Sortino/Calmar restent des diagnostics, pas des filtres de sélection.
- Convention actuelle : moyenne quotidienne simple nette / écart-type
  échantillonnal ×sqrt(252), taux sans risque0 et cash0 ; hypothèse explicite,
  pas CAGR/volatilité ni Sharpe excédentaire historique EUR. Cash pur indéfini.
- Campagne distincte `scripts/study_sp500_sharpe.py`, rapport
  `docs/sp500-sharpe-study.md`, JSON `data/backtests/sp500-sharpe.json` :
  réemploi explicite des sélections antérieures pour11 pistes par famille/source,
  plus162 règles volatilité/variance, puis173 candidats sur200 parcours communs.
  Un gagnant figé,1000 cinq ans/300 dix ans réservés ; aucun changement de
  production automatique. Ce nouvel objectif autorise la recherche de pistes
  autrefois écartées pour faible rendement, sans effacer les anciens échecs.
- Gagnant synthétique : mélange causal5experts, fenêtre252,eta2,aversion3,
  aucune pénalité DD,plancher10%,aucune poche v4,step5. Sharpe réservé5/10ans
  **0,9962/0,9507 contre0,9654/0,9183 v5**, gains+0,03084/+0,03238,
  IC95[0,02636;0,03561]/[0,02625;0,03851],648/1000 et218/300victoires.
  **Passe le protocole de Sharpe dans le modèle**, pas les anciens objectifs.
  Réel5/10ans1,010/1,104 contre1,141/1,111 : aucune domination uniforme ni
  preuve prospective. Ne pas transformer le gain synthétique en adoption.
- Branche distincte `study_sp500_sharpe_history.py`/`sp500-sharpe-history.json` :
  classement2571 configurations déclarées par moyenne des seuls Sharpe3/5/10
  réels, objectif d'optimisation historique explicite, pas validation inconnue.
  Un gagnant figé avant300cinq ans/100dix ans réservés ; cette branche ne modifie
  pas la sélection synthétique ni son audit.
- Gagnant historique : sans passif, budgets75/25 lent/défensif, plancher10%,
  autres règles inchangées. Sharpe réel3/5/10ans1,888/1,487/1,352 contre
  1,612/1,141/1,111 v5 ;24/24fenêtres5ans meilleurs, frais/retard conservés.
  Mais Sharpe synthétique réservé5/10ans0,853/0,803 contre0,919/0,903 ;
  98/300 et14/100victoires, IC95 des gains négatifs. Pas de validation ni
  adoption ; conserver le désaccord historique/modèle, sans ajouter un filtre DD.

## Recherche approfondie et petits gains — 15 novembre 2026

- Nouvelle demande : creuser internet pour battre v5 avec DD proche. Rapport
  `docs/sp500-deep-search-study.md`, scripts `study_sp500_deep_search.py`,
  `study_sp500_deep_continuation.py`, `study_sp500_online_ensemble.py` :
  **2409 configurations déclarées,2391 distinctes** après18 recouvrements,
  600marchés de sélection. Canaux,Markov,MACD,Kalman,CUSUM,OLMAR,noyau,
  retournement conditionnel,régression conjointe,continuation et experts causaux.
  Aucune sélection initiale admissible ; aucun succès de l'objectif+0,5point.
- Quatre audits distincts totalisent **5200 marchés réservés** (4×1000cinq ans,
  4×300dix ans), mêmes PSP5/générateur/frais0,12%, copies privées. Le quatrième
  `study_sp500_modest_edge.py` est explicitement post-sélection, quatre réglages
  figés et objectif moindre ; il ne réécrit pas les échecs initiaux.
- Seule variante1250 passe ce protocole secondaire : v5 avec sortie défensive
  +1,75σ au lieu de+1,5. Réel5/10ans CAGR12,06→12,15% /13,04→13,14%,
  DD−11,73→−11,71% /−20,45→−20,37%. Gain synthétique moyen+0,1074/+0,0934pt,
  mais DD moyen aggravé0,1694/0,2522pt ; cas jusqu'à5,11points plus profond.
  24/24fenêtres dans les tolérances, pas24surperformances. Ancienne piste v4,
  nouvelle comparaison contre v5, pas découverte de ce seuil ni adoption.
- Audit mensuel supplémentaire `audit_sp500_modest_edge.py` : **168fenêtres**
  (96trois ans,72cinq ans),125CAGR meilleurs,40identiques,3inférieurs ;
  **23DD dégradés**, jusqu'à4,09points. Exemple5ans septembre2018–2023 :
  CAGR11,41→12,44%,DD−19,19→−23,28%. Pas de période spéciale en application.
  Ce contre-exemple empêche de conclure à une amélioration stable du DD.
- **v5 reste active, aucune piste adoptée.** CUSUM améliore la protection mais
  perd0,14/0,18point de CAGR moyen réservé5/10ans. Quatre JSON d'audit plus
  `sp500-modest-edge-monthly.json`, échecs et graines conservés. Aucun changement
  production/UI/base. Option de recherche `keep_trace=False`, défaut inchangé ;
  456tests backend puis11tests ciblés, Ruff réussis. Contrôles logiciels et
  nouvelles graines du même historique ne constituent pas une validation financière.

## Recherche internet de stratégies publiées — 15 novembre 2026

- `docs/sp500-published-rules-study.md`, `scripts/study_sp500_published_rules.py` :
  Faber MM10 et momentum absolu12 adaptés ETF/cash, quatre adaptations déclarées,
  **18 configurations fixes**,300parcours5ans/100dix ans pour tous,24fenêtres,
  frais doublés/retard. PAA multi-actifs et GEM ne sont pas revendiqués reproduits.
- Aucun admissible ; **v5 reste active**. Diagnostic65%v4/35%MM10 ET momentum12 :
  réel5ans CAGR12,06→10,44%,DD−11,73→−8,83% ;10ans13,04→11,44%.
  Simulé5ans12,55→10,64%,DD−20,50→−18,13%,baisses>30%33→16/300 ;
 10ans12,44→10,41%,DD−25,38→−22,32%. Au mieux1/24fenêtres conforme.
  Protection supplémentaire avec coût de rendement, aucun diagnostic adopté.
- Rapport distinct `data/backtests/sp500-published-rules.json`, copie privée,
  mêmes PSP5/générateur/frais.57tests ciblés, Ruff backend/scripts réussis.
  Aucun changement de production/UI/base. Pas de crises2000/2008 dans PSP5 ;
  les témoins déjà explorés ne constituent pas de nouvelles découvertes.

## Dernière recherche écart-type et momentum — 15 novembre 2026

- Demande utilisateur : croiser z de régression et momentum de l'application.
  `docs/sp500-sigma-momentum-study.md`, `scripts/study_sp500_sigma_momentum.py` :
  **288 configurations**,150marchés de sélection,1000cinq ans/300dix ans réservés.
  Confirmation, achat de repli, sortie différée et interaction continue ; aucun
  ancien score fixe multi-actifs70/30 réintroduit. Momentum natif6/12/36 mois,
  mois récent exclu, référence PSP5 lui-même donc composante relative nulle.
- Aucun admissible ; **v5 reste active**. Diagnostic65%v4/35%interaction
  z18/momentum12/seuil55/plancher50 : CAGR cinq ans12,48→11,59 %, DD−20,84→−19,80 %,
  trois ratios sous v5. Dix ans12,26→11,21 %, DD−25,61→−24,06 %.
  Réel cinq/dix ans12,06→11,36 % /13,04→11,94 %,1/24fenêtres acceptable.
  Protection accrue ne signifie pas rendement maintenu ; aucune domination
  moyenne rendement/DD dès la sélection. Ne pas adopter ces diagnostics.
- Rapport distinct `data/backtests/sp500-sigma-momentum.json`, mêmes PSP5,
  générateur/frais et copie privée.443tests backend,18cas v5 exacts.
  `drawdown_frontier.tactical` accepte `target_weights` optionnel pour recherche,
  défaut inchangé. Aucun changement de moteur de production, UI ou base.

## Dernière recherche drawdown après v5 — 15 novembre 2026

- Autorisation utilisateur : explorer d'autres familles et implémenter seulement
  si elles améliorent le compromis sans sacrifier la performance. Trois campagnes
  terminées, **852 configurations (396+432+24)**,450 marchés de sélection,
  **3900 réservés** (3×1000 cinq ans,3×300 dix ans), mêmes PSP5/générateur/frais.
- Aucune configuration ne passe les sélections complètes ; **v5 reste active**.
  Piste65%v4/35%stop : CAGR cinq ans12,53→12,15%,DD−20,85→−19,30%,
  seuil des5%pires−33,67→−31,11%,baisses>30%145→68/1000 ; rendement
  inférieur dans737cas,262gains,1égalité. Réel cinq ans12,06→11,28%.
  Gain de protection et ratios ne signifient pas rendement conservé.
- Retour sur repli et protection des trois poches avec exposition accrue :
  non retenus, ratios/rendement ou drawdowns historiques dégradés. Aucun de
  ces diagnostics n'est adopté. Pas de changement de base utilisateur.
- Rapport `docs/sp500-drawdown-frontier-study.md` ; scripts `study_sp500_drawdown_`
  `frontier.py`, `reversal.py`, `overlay.py` et rapports JSON distincts correspondants.
  Critères, graines et échecs conservés ; aucune promesse de plafond de pertes.
- Moteur de recherche trois ans : `exposure_caps` optionnel, défaut inchangé,
  replay limité aux dates où un calendrier peut décider ;18cas v5 exacts,
  438tests backend réussis. Ce sont des contrôles logiciels, pas une validation.

## Adoption précédente — v5, 15 novembre 2026

- L’utilisateur a demandé d’implémenter la combinaison présentée65%v4/35%passif.
  **Production alors active : `core35_slow_defensive_v5`**, remplaçant les mentions v4
  seule comme politique active ci-dessous. PSP5 EUR uniquement, frais0,12%.
- Trois budgets initiaux indépendants : lente48,75%, défensive16,25%, passive35%.
  Le budget actif65% garde exactement v4 (75/25 interne, mêmes seuils, cadence,
  replay lent et état défensif initial). Passive achetée une seule fois à la
  première clôture admissible après début ; quantité constante ensuite.
  Aucun transfert/rééquilibrage entre poches, ordres/frais/titres entiers séparés.
- Même moteur pour validation et simulations unitaire/multiple, mêmes graines,
  générateur et choix1/3/5/10ans. Aucun50/50, levier ou changement de base utilisateur.
- Adoption explicite malgré limites : retard synthétique cinq ans3,0111points
  contre3maximum, Calmar dix ans légèrement sousBH, réel cinq ans moins rentable
  et protection réduite face à v4. Ne pas transformer l’adoption en validation.
- Documentation `docs/sp500-core35-adoption.md` ; vérificateur actif
  `scripts/verify_sp500_core35.py`,18cas contre recherche indépendante sur copie.
  Vérificateur de simulation courant : sortie distincte
  `data/backtests/sp500-core35-simulation-verification.json` ; rapports v4/BNP
  archivés inchangés, anciens contrôles de production v4 non valables pour v5.


Application locale d’analyse financière : bibliothèque multi-actifs, portefeuille et stratégies personnelles, momentum, régression, corrélations, optimisation et validation historique. Backend Python/FastAPI/SQLite dans `backend/`, frontend React/TypeScript/Vite dans `frontend/`. Documentation dans `docs/`, expériences isolées dans `scripts/`.

Point d’entrée des recherches : `docs/journal-des-essais.md`. Y conserver le bilan
des campagnes, les échecs et contre-exemples, les décisions de recherche et les
adoptions explicites séparément ; lier chaque nouvelle étude détaillée et ne pas
présenter une vérification logicielle comme une validation financière.

## Stratégies et décisions à conserver

Bilan au 14 novembre 2026. « Retenue » signifie conservée dans l’application, pas rentabilité future démontrée.

| Stratégie | Bilan et décision |
|---|---|
| Retour à la moyenne | Retenue ; meilleur résultat des essais récents sur l’univers utilisateur. Achat à −2 σ, activation de sortie à +2 σ, vente après repli de 1 σ depuis le maximum ; financement à partir de +0,3 σ. Sur 2021–2026 : 10 000 € → 43 080,84 €, baisse maximale −16,22 %. Résultats moins bons sur d’autres périodes/univers : aucun succès universel démontré. |
| Volatilité minimale | Retenue, allocation révisée trimestriellement. Objectif de réduction de variance ; aucune supériorité générale établie dans les expériences documentées. |
| Corrélation minimale | Retenue, allocation révisée trimestriellement. Minimise `wᵀ Corr w` ; ne rend pas les actifs indépendants. Aucune supériorité générale établie. |
| Gestion par variance (adaptation Moreira–Muir) | Non retenue : plus défensive, mais échoue aux critères rendement/risque et frais fixés avant les essais. Sur cinq ans : 21 746,88 €, contre 25 321,50 € pour le contrôle équipondéré mensuel. Code de recherche seulement. |
| Momentum temporel avec contrôle du risque (adaptation Moskowitz–Ooi–Pedersen) | Non retenu : critères non satisfaits, rendement et Sharpe insuffisants. Sur cinq ans : 21 059,51 €. Code de recherche seulement. |
| Momentum + Régression (score 70/30) | Échec pour l’objectif recherché ; onglet et implémentation de simulation supprimés à la demande de l’utilisateur. Sur cinq ans : 24 567,83 €, contre 26 486,20 € pour l’équipondération trimestrielle et 43 080,84 € pour le retour à la moyenne. Les indicateurs et recommandations préexistants restent disponibles. |

Ces montants concernent les 14 actifs du journal utilisateur, du 15/11/2021 au 13/11/2026, avec 10 000 € initiaux, 0,5 % de frais par achat/vente, actions entières et cryptos fractionnaires. Biais de sélection/survivance et paramètres déjà examinés : ne pas présenter ces résultats comme une validation prospective.

Ne pas réintroduire les stratégies rejetées à l’identique. Une nouvelle tentative doit expliciter ce qui change, fixer ses critères avant les résultats, comparer aux mêmes références et vérifier plusieurs périodes et les frais. Détails reproductibles des deux adaptations académiques : `docs/quantitative-strategies-study.md` et `scripts/study_quantitative_strategies.py`. Le résultat Momentum + Régression ci-dessus est une mémoire de session ; ses fichiers spécifiques ont été supprimés.

## Conventions à préserver

- Onglets de validation des stratégies personnelles : volatilité minimale, retour à la moyenne, corrélation minimale et parité de risque. S&P 500 · Régression est une entrée native distincte dans la liste des stratégies, distinguée uniquement par un encadré de couleur (pas de badge « Incluse dans l’application »), non modifiable et non supprimable ; ne pas la réintroduire comme onglet des stratégies personnelles. Documentation du moteur : `docs/validation.md`.
- Signaux calculés avec les seules informations disponibles, exécution ultérieure, frais explicites, historique propre de chaque actif. Ne pas modifier la base utilisateur pour les expériences : utiliser une copie.
- Retour à la moyenne : actions et cryptos ; autres actifs conservés passivement. Entrée plafonnée à 25 % du portefeuille, minimum utile pour éviter les achats de reliquats ; financement par une seule ligne au plus, choisie selon l’écart-type le plus élevé admissible. Respecter les règles exactes du moteur, les frais et les titres entiers pour actions/ETF uniquement.
- Ne pas remplacer les réglages actuels par les anciens seuils 1,4/1,5 ou plafonds 20/30/33 % évoqués dans l’historique de conversation.

## Vérifications utiles

Backend : `uv run pytest -q` et `uv run ruff check backend scripts`.
Frontend, depuis `frontend/` : `npm run check` ; parcours navigateur : `npm run test -- tests/e2e/validation.spec.ts tests/e2e/strategies.spec.ts`.
Adapter les vérifications aux changements. Ne pas confondre tests logiciels réussis et stratégie financière concluante.

## Ajustement demandé le 14 novembre 2026

- CVaR retirée à la demande de l’utilisateur ; ne pas la réintroduire.
- Interface stratégies : pas de champs spread/exécution, de journal prospectif
  ni de contrôle rétrospectif d’exposition moyenne.
- Simulation : portefeuille principal et portefeuilles des stratégies enregistrées
  uniquement ; pas de composition sur mesure dans cet onglet.
- Méthode « S&P 500 · Régression » (`etf_switch` pour compatibilité), combinaison
  `slow_defensive_warm_state_v4` explicitement adoptée par l’utilisateur : ESE.PA uniquement,
  référence identique en EUR. Deux budgets indépendants, 75 % du capital initial
  pour la règle lente, 25 % pour la défensive ; pas de transfert ni rééquilibrage
  des poids entre poches. Chacune cible 25 % ESE en état défensif, 100 % sinon,
  uniquement à l’initialisation/changement d’état ; les poids dérivent ensuite.
  Lente : régression logarithmique native 60 mois, entrée strictement sous −2 σ
  OU franchissement haussier de 0 σ depuis la séance immédiatement précédente,
  sortie strictement au-dessus de +1,5 σ, décisions première séance observée du
  mois. Défensive : 18 mois/251 observations, entrée au franchissement haussier
  de −0,5 σ entre deux séances consécutives, sortie strictement au-dessus de
  +1,5 σ, décisions toutes les cinq séances depuis le début du test. Sans signal
  lent disponible, rester passif à 25 % ; simulation admissible dès 18 mois.
  Avant le début du test, reconstituer uniquement l’état lent avec les décisions
  mensuelles strictement antérieures ; aucun gain, position ni frais antérieurs.
  La poche défensive démarre toujours en état défensif. Acheter les cibles
  héritées à la première exécution admissible, même hors début de mois.
  Exécution clôture suivante, titres entiers et frais par poche, même pour les
  ordres opposés. Aucun CAC ni levier. Autres méthodes inchangées.
- Pour cette variante, cinq ans par défaut, choix 1/3/5/10 ans uniquement.
  L’utilisateur a rejeté la période spéciale de 2018 : ne pas la réintroduire.
  CAGR 12,25/14,06 % sur cinq/dix ans jusqu’au 13/11/2026, DD −6,99/−8,85 %,
  et 15,68 % sur trois ans (volatilité 8,37 %, DD −7,02 %),
  avec 10 000 €, frais 0,5 % et titres entiers. Sélection après examen des données,
  plusieurs contre-exemples : aucun plancher garanti ni plafond de pertes.
- Masquer `eligible_equal` partout ; sur S&P 500 · Régression, uniquement
  méthode et référence S&P 500, y compris tableaux, marqueurs et aide.
  Aucun affichage Achat-conservation / Équipondération trimestrielle.
- Corrélation minimale : optimisation convexe de `wᵀ Corr w` sur tout
  l’univers éligible, sans plancher 3 % ni cardinalité minimale ; plafond
  35 % dès trois actifs (50/50 à deux). Pas de suppression par paire ou
  par secteur ; conserver deux actifs corrélés reste possible. Étude de
  288 simulations : `docs/risk-allocations-review.md`. Variantes réactives
  et corrélations au carré non retenues. Volatilité minimale : conserver
  la méthode empirique actuelle ; aucune variante n’atteint les critères.
- Frontières d’efficience : référence commune ESE.PA (S&P 500 PEA) en EUR,
  jamais remplacement silencieux par un indice. La frontière du portefeuille
  conserve son univers réel, donc sa forme dépend des actifs détenus.
- Pas de sélecteur « Tolérance de révision » : bande 3 points automatique
  pour les allocations optimisées, poids et risque pour la parité.
- Prédictions : préparation en arrière-plan, worker et cache mémoire invalidé
  par quantités/révision des données ; conserver les 4 096 trajectoires.

## Recherche S&P 500 supplémentaire du 14 novembre 2026

- Recherche de 31 752 configurations ESE : `docs/sp500-regression-study.md`,
  scripts `study_sp500_regression.py`, `extend_sp500_regression_study.py`,
  `study_sp500_continuation.py`, `summarize_sp500_regression.py`.
- Bilan initial avant autorisation de la variante défensive : aucune procédure de sélection ne satisfait
  tous les critères de rendement/risque sur apprentissage, validation, période
  finale et stress. Les 20,78 % annualisés de la variante 60 mois sont un résultat
  agrégé fragile, pas une stratégie validée. La variante 18 mois améliore le risque
  ESE récent mais sous-performe en rendement et échoue sur l’indice USD long.
- Conserver état et positions entre fenêtres pour étudier le fonctionnement continu
  d’une règle à hystérésis ; les simulations démarrant en cash mesurent autre chose.
  Aucun historique déjà disponible ne devient une preuve prospective.

## Intégration défensive et affinage

- Historique : variante 18 mois initialement intégrée à la demande de l’utilisateur.
  Elle est désormais la poche de 25 % de la combinaison explicitement adoptée
  ci-dessous ; ne pas remplacer cette combinaison par la règle lente seule.
- 540 variantes locales supplémentaires : aucune n’améliore la volatilité en
  conservant au moins 14 % annualisés sur la période complète à frais 0,5 %.
  Conservation des paramètres de la variante autorisée, pas de sélection opportuniste.
- Rapport : `docs/sp500-defensive-refinement.md`. Reproduction :
  `scripts/study_sp500_defensive_refinement.py` puis
  `scripts/verify_sp500_defensive.py`, sur copies privées de la base.

## Recherche élargie après rejet de la période spéciale

- Voir `docs/sp500-adaptive-risk-study.md`. Campagnes de 588 puis 648
  configurations (en grande partie communes), au-delà de la régression : tendance,
  momentum multi-horizon, cassures, hystérésis, budgets de baisse, volatilité,
  downside, sélection adaptative de signaux et expositions constantes.
- Sélection sur indice total-return USD 1993–2012 seulement, vérification sur
  ESE EUR 5/10 ans et 14 fenêtres de 3/5 ans. Aucune méthode sélectionnée ne
  satisfait les critères de robustesse et rendement. Ne pas promouvoir les
  candidats perdants ni annoncer des signaux futurs fiables.
- Les règles calendaires stables sont testées en recherche, pas appliquées à
  l’ancienne poche défensive : elle garde son ancrage toutes les cinq séances.
  Seule la nouvelle poche lente adopte le calendrier mensuel audité ci-dessous.

## Compromis rendement/drawdown, volatilité assouplie

- `docs/sp500-return-drawdown-study.md` : 22 680 règles et 309 combinaisons.
  Volatilité permise jusqu’à +30 % relatif à l’actuelle, sans drawdown plus profond.
- Aucun candidat sélectionné selon les critères initiaux ne satisfait tout. Audit
  exploratoire de gains plus modestes : 12 combinaisons dominent l’actuelle sur
  cinq/dix ans, mais sélection après examen de ces résultats, pas validation inconnue.
- Piste 75 % de capital en régression60 mois (entrée−2/sortie+1,5/plancher25%,
  cadence premier jour du mois),25 % en défensive actuelle : CAGR10,33/13,07 %,
  DD−6,99/−8,85 % sur5/10 ans. Seulement10/14 fenêtres satisfont le compromis ;
  DD plus profond sur2000–2003 et1993–2026 USD. Ne pas la présenter comme parfaite
  ou comme plafond de pertes.
- Après présentation de ces limites, l’utilisateur a explicitement demandé
  l’implémentation : combinaison v2 initialement active, ensuite remplacée par
  la v3 avec réentrée à 0 σ ci-dessous, sans changement de période.
  Ancien `scripts/verify_sp500_compromise.py` : 15 cas figés v2 sur copie privée
  de la base (indicateurs à 1e−9, frais/capital à 1e−6 €). L’ancien vérificateur
  `verify_sp500_defensive.py` concerne uniquement l’ancienne politique et ne
  doit plus servir à vérifier la production actuelle.

## Nouvelle exploration de la combinaison adoptée

- `docs/sp500-next-iteration-study.md`, `scripts/study_sp500_next_iteration.py` :
  792 variantes (sorties conditionnelles, réentrées, cibles défensives, budgets,
  calendriers). Aucun candidat ne satisfait les critères de sélection définis
  avant calcul ; décision initiale : production `slow_defensive_v2` inchangée.
  L’utilisateur a ensuite explicitement demandé d’adopter la piste de réentrée :
  `slow_defensive_reentry_v3` adoptée, puis remplacée par v4 ci-dessous,
  malgré les limites de recherche conservées.
- Piste post-hoc de réentrée lente au franchissement mensuel de 0 σ : CAGR
  12,25/14,06 % sur 5/10 ans, mêmes drawdowns, volatilité 8,33/9,71 %. Gain récent,
  aucun changement sur les deux premières périodes, volatilité relative trop
  élevée sur 2024+ et une fenêtre 3 ans, rendement USD long un peu inférieur.
  Ne pas la présenter comme validée : adoption explicite, pas succès aux critères.
- Interface native S&P : un seul titre, description sur plusieurs lignes,
  indication de statut uniquement par couleur dans la liste ; aucun badge
  « Incluse dans l’application » dans la liste ou l’écran.
- Sensibilité complémentaire : les gains 5/10 ans disparaissent aux seuils de
  réentrée −0,25/+0,5 σ ; à −0,5 σ le drawdown dix ans passe à −21,84 %.
  Ne pas assimiler les 13/14 fenêtres acceptables de la piste à treize gains :
  douze fenêtres restent identiques à l’actuelle.

## Adoption de la réentrée lente à 0 σ

- Instruction utilisateur explicite après présentation des limites : v3 adoptée,
  puis remplacée par la v4 à état initial reconstitué ci-dessous.
  Ajouter à l’entrée sous −2 σ un franchissement haussier de 0 σ entre deux séances
  consécutives, constaté lors du signal mensuel. Aucun franchissement mémorisé
  depuis la décision précédente, aucun achat simplement parce que z est positif.
- Tous les autres réglages v2 restent identiques ; cinq ans par défaut, choix
  1/3/5/10 ans, aucun début spécial, ESE/cash seulement, mêmes frais et budgets.
- Vérification historique v3 : `scripts/verify_sp500_reentry.py`, 19 cas figés, copie
  privée ; les anciens vérificateurs défensif et compromis concernent v1/v2.
- Étude `study_sp500_next_iteration.py` : sa référence reste v2, vérifiée contre
  les résultats de production archivés, même après l’activation de v3.

## Recherche du retard trois ans

- `docs/sp500-three-year-study.md`, `scripts/study_sp500_three_years.py` et
  `scripts/audit_sp500_three_years.py` : 99 ajustements plus témoin, puis 166
  départs mensuels pour le seul candidat figé. Décision initiale : production v3
  conservée, aucun candidat ne satisfait tous les critères fixés avant calcul.
- Cause importante : chaque test redémarre en état défensif. Reconstituer l’état
  lent depuis les décisions antérieures donne 15,68 % annualisés sur trois ans
  contre 8,97 % pour v3 et 18,79 % pour ESE ; volatilité 8,37/6,52/14,15 %,
  DD −7,02/−7,51/−23,28 %. Cinq/dix ans strictement inchangés. Changement
  d’initialisation ensuite explicitement adopté, sans améliorer un compte déjà
  en fonctionnement.
- La piste échoue aux critères trois ans : écart au témoin supérieur à 2 points
  annualisés et hausse de volatilité de 28,42 %, au-delà des 20 % permis.
  Sur 166 fenêtres chevauchantes : 59 gains, 107 identiques, aucun rendement
  inférieur ; 16 DD légèrement plus profonds (maximum +0,138 point de perte),
  19 échecs aux limites combinées, volatilité pouvant presque doubler. Ne pas
  transformer ces diagnostics historiques en garantie ou validation prospective.
- Reconstitution expérimentale : signaux connus avant le début seulement,
  aucun gain antérieur ajouté, vrais achats après le début avec frais/titres entiers.
  Témoin vérifié contre les 19 cas de production archivés, base privée.

## Adoption de l’état lent reconstitué

- L’utilisateur demande explicitement la mise en place après les résultats et
  limites : `slow_defensive_warm_state_v4` désormais active. Rejouer les seuls
  signaux mensuels lents précédant strictement le début, avec leurs scores connus
  et celui de la séance précédente. Sans signal exploitable, état défensif.
- Seul l’état initial lent change ; capital neuf, achat après début avec frais
  et titres entiers. Aucun transfert, changement de période, seuil, cadence,
  budget ou état initial défensif. Ne pas mémoriser les franchissements intramensuels.
- Vérificateur actif : `scripts/verify_sp500_warm_state.py`, 20 cas figés contre
  la recherche sur copie SQLite privée. Les trois vérificateurs précédents
  concernent les versions historiques et ne vérifient plus la production.
- Les scripts de recherche trois ans conservent leur témoin froid v3 et leur
  décision initiale négative. Adoption explicite ne signifie pas critères réussis.

## Affinage de v4 et résumé pleine largeur

- `docs/sp500-v4-refinements-study.md`, `scripts/study_sp500_v4_refinements.py` :
  72 paramétrages supplémentaires (68 distincts), témoin v4 reproduit sur les
  20 cas archivés, 166 départs mensuels, frais doublés, retard supplémentaire,
  diagnostics USD. Aucun candidat ne passe tous les critères fixés avant calcul.
  Production toujours `slow_defensive_warm_state_v4`, paramètres inchangés.
- Sélection figée 85/15, plancher15 %, sortie défensive+1,75 : gain de rendement
  récent, mais DD3/5ans aggravé et USD long moins bon ; non adoptée.
- Deux pistes modestes observées après calcul : sortie défensive+1,75 seule,
  ou avec plancher15 %. Elles améliorent les trois horizons récents mais
  aggravent respectivement 43/15 DD sur166 fenêtres. Contre-exemples DD−15,21 %
  et−12,60 % contre−8,84 % témoin. Ne pas annoncer de supériorité générale ni
  les appliquer sans décision explicite. Rapports complets dans data/backtests.
- Résumé natif S&P condensé, pleine largeur (suppression de la limite78ch),
  deux lignes au format ordinateur testé, retour naturel sur mobile ; règles
  inchangées, pas de troncature ou de badge supplémentaire.

## Onglet de simulation aléatoire S&P 500

- L’utilisateur conserve explicitement la stratégie v4 actuelle ; ne pas adopter
  les pistes1/2 d’affinage. Nouvel onglet Simulation aléatoire uniquement dans
  l’entrée native S&P, avec Validation historique par défaut. Aucune réintroduction
  du S&P comme onglet des stratégies personnelles.
- `docs/sp500-simulation.md`, `portfolio/sp500_simulation.py` : rééchantillonnage
  des rendements ajustés ESE EUR par blocs moyens63séances + petit bruit5 % de
  volatilité quotidienne. Historique réel pour les régressions/état lent initial,
  capital neuf, moteur v4 partagé avec Buy & Hold sur un même parcours, frais et
  titres entiers. Aucun indice USD en remplacement ni écriture de cours fictifs.
- Générer un nouveau parcours produit une nouvelle graine, sans sélectionner un
  résultat favorable. Graines reproductibles côté API ; préfixe identique quand
  on prolonge un horizon avec la même graine. Dates fictives en jours de semaine,
  conventions métriques communes252séances, pas de promesse de prévision.
- Test du générateur sur200parcours5ans : 60DD≥30 %, pas systématiques. Ce compte
  est un diagnostic du modèle et de l’historique, pas une probabilité future.
  Vérificateur sur copie privée : `scripts/verify_sp500_simulation.py`.
- E2E supplémentaire : `tests/e2e/sp500-simulation.spec.ts` (ordinateur/mobile).


## Remplacement ETF et simulations multiples — dernière instruction du 14 novembre 2026

- Cette décision remplace les mentions ESE comme instrument actif ci-dessus :
  **Amundi PEA S&P 500 UCITS ETF Acc, FR0011871128, PSP5.PA, yf-psp5.pa**
  partout dans l’application. BNP ESE et SPY archivés/masqués, pas de cours
  renommés. Historique PSP5 propre depuis2014 ; mêmes règles v4 sans levier.
- Frais par défaut S&P uniquement : **0,12 % par achat/vente**, API0,0012.
  Autres stratégies0,5 %. Respecter les frais explicitement fournis. Ne pas
  confondre coût de transaction et frais internes déjà inclus dans les cours.
- Migration locale des références ESE vers PSP5, sauvegardes des réglages
  suffixées-before-amundi-sp500 ; conserver les quantités numériques saisies
  (pas conversion à valeur constante ni ordre de courtage). Anciens rapports
  ESE/frais0,5 % inchangés et explicitement archivés.
- Simulation S&P : unitaire conservée et mode multiple1à10000 (défaut1000),
  tableau Buy & Hold puis Régression avec moyennes, victoires, égalités et
  dénominateurs valides par indicateur. NDJSON après chaque parcours terminé,
  mêmes marchés/moteur/frais ; arrêt et résultats partiels, aucun filtrage.
- `scripts/verify_sp500_simulation.py` vérifie maintenant PSP5/frais0,12 %,
  9scénarios et par défaut1000parcours5ans ; sortie distincte
  `data/backtests/sp500-amundi-simulation-verification.json`.
  Les anciens vérificateurs à résultats ESE figés restent des archives ; ils
  ne vérifient pas l’instrument actif et ne doivent pas réécrire leurs rapports.

## Recherche Amundi après constat de sous-performance synthétique

- `docs/sp500-amundi-upside-study.md`, scripts `study_sp500_amundi_upside.py` et
  `study_sp500_amundi_regression.py` :405paramétrages (dont un équivalent au témoin),
  aucune règle ne bat le Buy & Hold dix ans ni ne passe les critères combinés.
  24fenêtres cinq ans trimestrielles, frais doublés, retard supplémentaire ;
  1000parcours par horizon pour quatre diagnostics puis100parcours par horizon
  pour v4/continuation. Pas de nouvelle adoption, conserver v4 et le générateur.
- La variante continuation retenue uniquement pour diagnostic ne justifie pas
  un remplacement : rendement synthétique légèrement meilleur avec davantage
  de risque, recul du rendement/drawdown cinq ans réel. Meilleur dix ans observé
  après calcul13,56 % <14,49 % Buy & Hold ; ne pas annoncer une surperformance.
- Selon la dernière demande, simulation S&P sans paragraphes explicatifs, résumé
  du tirage unitaire, ligne Capital final ni légende textuelle de comparaison des
  métriques. Conserver les calculs, courbes, métriques, documentation et graine du lot.


## Recherche rendement et trois ratios après le lot de 100 parcours

- `docs/sp500-ratio-tradeoff-study.md`, scripts `study_sp500_ratio_tradeoff.py`
  et `study_sp500_ratio_costs.py` : 54 puis 144 paramétrages, 100 parcours de
  sélection et 400 réservés par campagne. Objectif assoupli : gain de CAGR
  face à v4, risque modéré et Sharpe/Sortino/Calmar supérieurs au Buy & Hold.
  Aucun candidat ne passe la procédure complète ; aucune adoption.
- Candidat volatilité21/cible14%/plancher50% : +1,53 point de CAGR synthétique
  cinq ans, mais Sharpe/Sortino sous Buy & Hold et DD réel cinq ans−18,56 %
  contre−7,02 % v4. Diagnostic suivant : trois ratios moyens meilleurs sur
  cinq ans seulement, gain CAGR+0,30 point non confirmé, DD réel−14,47 %.
  Ne pas promouvoir ces pistes comme remplacement à risque identique.
- Générateur inchangé : audit1 000marchés, volatilité médiane16,47 % contre
 16,59 % PSP5 réel ; dépendances longues atténuées et calendrier de jours de
 semaine (environ261séances/an contre convention252). Même historique2014+,
 pas de nouvelle preuve économique indépendante grâce aux nouvelles graines.
- Colonne « Paires valides » retirée du tableau à la demande de l'utilisateur.
  Conserver les dénominateurs valides et leur usage dans l'API/calculs.


## Recherche élargie avec risque assoupli — 15 novembre 2026

- Demande utilisateur : explorer d'autres voies, hausse du risque face à v4
  autorisée, priorité à davantage de rendement avec risque sous Buy & Hold et
  retard de rendement limité. Aucun remplacement de production demandé à ce stade.
- `docs/sp500-broader-compromise-study.md`, `study_sp500_broader_compromise.py` :
  62 variantes nouvelles,100marchés de sélection puis300cinq ans/100dix ans réservés.
  Piste figée65%v4/35%passifPSP5 : CAGR12,93/13,34% contre11,14/11,49% v4,
  rendement supérieur dans87,3/96% des parcours ; risque intermédiaire sousBH.
  23/24fenêtres et stress passent. Ratios moyens tous supérieursBH cinq ans,
  Calmar légèrement inférieur dix ans ; aucune domination générale démontrée.
- Procédure formelle non satisfaite : retard cinq ans3,0111points contre3,0000
  maximum. Réel cinq ansCAGR12,06% contre12,34% v4, DD−11,73% contre−7,02% ;
  dix ansCAGR13,04% contre12,20%, DD−20,45% contre−10,95%.
  Pas d'adoption implicite. Le50/50 est un contrôle plus exposé, non qualifié
  historiquement. Conserver les limites et les contre-exemples.
- Extension du moteur de recherche `study_sp500_three_years.simulate` par
  `initial_capital` pour de vrais budgets par variante ; défaut10000 inchangé,
  archives non recalculées. Ne pas mélanger deux courbes10000€ comme si leurs
  arrondis/frais correspondaient à un capital partagé. Production v4 inchangée.
