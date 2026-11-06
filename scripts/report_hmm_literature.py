"""Render the frozen research results; no fitting, selection or trading here."""

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/backtests"
NAMES = {
    "current_hmm": "HMM actuel",
    "ewm_frozen_pesr": "Moments lissés, figé",
    "ewm_rolling_pesr": "Moments lissés, réentraîné",
    "ewm_rolling_cost": "Moments lissés, réentraîné, frais",
    "volatility_frozen": "Filtre volatilité, figé",
    "volatility_rolling": "Filtre volatilité, réentraîné",
}


def pct(value):
    return f"{100 * value:+.2f} %".replace(".", ",")


def exposure(value):
    return f"{100 * value:.1f} %".replace(".", ",")


def points(value):
    return f"{100 * value:+.2f} points".replace(".", ",")


def main():
    studies = [
        json.loads((DATA / d / "results.json").read_text())
        for d in ("hmm-literature", "hmm-volatility")
    ]
    for study in studies:
        for path, expected in study["plan"]["sources"].items():
            actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError(f"Numerical source changed since run: {path}")
    results = [r for study in studies for r in study["results"]]
    summaries = [
        r
        for d in ("hmm-literature", "hmm-volatility")
        for r in json.loads((DATA / d / "summary.json").read_text())
    ]
    audit = json.loads((DATA / "hmm-literature/current_model_audit.json").read_text())
    defaults = {
        pol: [
            r
            for r in results
            if r["policy"] == pol
            and r["case"] == "interface_default"
            and r["fee_multiple"] == 1
        ]
        for pol in NAMES
    }
    by_asset = {pol: {r["asset"]: r for r in group} for pol, group in defaults.items()}
    header = "| Modèle | Bat conservation | Gain net médian | Écart médian apparié | Exposition médiane | Ordres médians | Exposition ≥95 % |"
    table = [header, "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for pol, name in NAMES.items():
        r = next(
            r
            for r in summaries
            if r["policy"] == pol
            and r["case"] == "interface_default"
            and r["fee_multiple"] == 1
        )
        table.append(
            f"| {name} | {r['wins']} / {r['count']} | {pct(r['median_return'])} | {points(r['median_excess_return'])} | {exposure(r['median_exposure'])} | {r['median_orders']:g} | {r['nearly_always_invested']} / {r['count']} |"
        )
    annual = [
        "| Fenêtre | Actifs | Actuel | Lissé figé | Lissé réentraîné | Lissé réentraîné + frais | Volatilité figée | Volatilité réentraînée |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    cases = list(dict.fromkeys(r["case"] for r in summaries))
    for case in cases:
        group = {
            r["policy"]: r
            for r in summaries
            if r["case"] == case and r["fee_multiple"] == 1
        }
        annual.append(
            f"| {case} | {group['current_hmm']['count']} | "
            + " | ".join(str(group[p]["wins"]) for p in NAMES)
            + " |"
        )
    detailed = [
        "| Actif | Conservation | Actuel | Lissé réentraîné + frais | Exposition actuel → candidat | Ordres actuel → candidat |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for old in defaults["current_hmm"]:
        new = by_asset["ewm_rolling_cost"][old["asset"]]
        detailed.append(
            f"| {old['name']} | {pct(old['benchmark_metrics']['total_return'])} | {pct(old['strategy_metrics']['total_return'])} | {pct(new['strategy_metrics']['total_return'])} | {exposure(old['exposure'])} → {exposure(new['exposure'])} | {len(old['trades'])} → {len(new['trades'])} |"
        )
    stress = [
        "| Modèle, frais doublés | Bat conservation | Gain médian | Exposition médiane | Ordres médians |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for pol, name in NAMES.items():
        r = next(
            r
            for r in summaries
            if r["policy"] == pol
            and r["case"] == "interface_default"
            and r["fee_multiple"] == 2
        )
        stress.append(
            f"| {name} | {r['wins']} / {r['count']} | {pct(r['median_return'])} | {exposure(r['median_exposure'])} | {r['median_orders']:g} |"
        )
    totalwins = {
        p: sum(
            r["excess_return"] > 1e-10
            for r in results
            if r["policy"] == p and r["fee_multiple"] == 1 and "error" not in r
        )
        for p in NAMES
    }
    failed_refreshes = sum(
        a["failure"] is not None
        for r in results
        if r["policy"] == "ewm_rolling_cost" and r["fee_multiple"] == 1
        for a in r["calibrations"]
    )
    separation = sum(
        r["future_separation"] is not None and r["future_separation"] > 0
        for r in defaults["ewm_rolling_cost"]
    )
    with (DATA / "hmm-literature/comparison.csv").open("w") as f:
        fields = [
            "asset",
            "name",
            "category",
            "case",
            "policy",
            "fee_multiple",
            "fee_bps",
            "return",
            "hold_return",
            "excess_return",
            "exposure",
            "orders",
            "drawdown",
            "hold_drawdown",
            "future_separation",
            "error",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            row = {k: r.get(k) for k in fields}
            if "error" not in r:
                row.update(
                    {
                        "return": r["strategy_metrics"]["total_return"],
                        "hold_return": r["benchmark_metrics"]["total_return"],
                        "orders": len(r["trades"]),
                        "drawdown": r["strategy_metrics"]["maximum_drawdown"],
                        "hold_drawdown": r["benchmark_metrics"]["maximum_drawdown"],
                    }
                )
            writer.writerow(row)
    report = f"""# Recherche HMM : détection, exposition et performance nette

6 novembre 2026. **L’objectif de surperformance dans l’extrême majorité des cas n’est pas atteint. Aucun candidat n’a été installé dans l’application.** Le moteur actif reste celui décrit dans [la revue précédente](hmm-directional.md), qui ne doit pas être présenté comme validé financièrement.

## Diagnostic du moteur actuel

Sur les 22 fenêtres par défaut, l’exposition médiane est de 98,6 %, 16 actifs dépassent 95 % d’exposition et le nombre médian d’ordres est deux. Le constat de l’utilisateur est confirmé : ce résultat ressemble souvent à une conservation presque permanente.

L’audit des paramètres révèle un problème plus précis que le nombre d’ordres : **pour {sum(r["no_state_can_trigger_exit"] for r in audit)} actifs sur 22, aucun état du modèle actuel ne peut déclencher une vente par sa règle de continuation**, même avec une probabilité de 100 % dans cet état. Le calcul de continuation reste au-dessus du seuil de sortie dans tous les états. Pour {sum(r["no_negative_drift_state"] for r in audit)} actifs, toutes les moyennes d’état sont positives. Dans les autres cas concernés, la prévision après transitions et la règle de frais absorbent l’état défavorable. Avec des paramètres figés pendant le test, cette propriété persiste.

Les rendements seuls sont retenus pour 20 actifs sur 22. Séparer des distributions quotidiennes surtout par leur volatilité, puis obtenir une meilleure densité prédictive, ne démontre pas une capacité à anticiper les tendances. Il ne suffit donc pas de supprimer des frais ou de forcer davantage de transactions.

Audit numérique local : `data/backtests/hmm-literature/current_model_audit.json`, avec moyennes, transitions, valeurs de continuation et seuils par actif.

## Recherches et code effectivement examinés

- [Werge, 2021, sections 4 et 5](https://arxiv.org/html/2107.05535v1) : HMM à trois états sur moments exponentiellement lissés, normalisation sur entraînement, espérance d’un ratio rendement/risque par état. L’auteur examine notamment des spans 15, 30 et 60 et souligne que l’amélioration du risque ne garantit pas celle du rendement cumulé. Ici, span 30 fixé pour tous les actifs, moyenne et écart-type central exponentiels, sans recherche du meilleur span. C’est une adaptation, pas une reproduction de ses résultats.
- [Code Python de recalibration causale](https://github.com/mehmetoaltekin/hmm-regime-detection/blob/main/src/hmm_model.py) : lecture de l’ajustement multi-initialisations, de `predict_filtered_proba` et de `WalkForwardHMM`. Idée retenue : réajuster sur le passé, réinitialiser la croyance avec l’historique du nouveau modèle et ne jamais transporter aveuglément les indices des anciens états.
- [Exemple Python officiel QuantConnect](https://www.quantconnect.com/docs/v2/research-environment/machine-learning/popular-libraries/hmmlearn) et [notebook](https://github.com/QuantConnect/Research/blob/master/Research2Production/Python/07%20Hidden%20Markov%20Models.ipynb) : rendements quotidiens, deux états, réajustement. Les graphiques à base de `predict` ne constituent pas à eux seuls des signaux causaux de backtest. Nous testons aussi un filtre de risque fondé sur l’état de plus faible variance.
- [Autre moteur Python et son backtest](https://github.com/az9713/hmm-regime-trader) : son moteur utilise un filtre forward et des réentraînements. Dans le fichier `backtest/backtester.py` consulté, `_simulate_oos` multiplie les allocations par des rendements logarithmiques, puis compose `1 + strategy_returns`. Le traitement des coûts dans cette fonction ne justifie pas de reprendre ses chiffres affichés comme preuve de rentabilité.
- [Implémentation annonçant un CAGR de 24,14 %](https://github.com/ayaanzeeshan514/systematic-regime-switching-trading-strategy/blob/main/strategy.py) : le fichier consulté utilise `hmm.predict` sur des blocs de test, puis un filtre hybride calculé avec les prix du jour pour sélectionner les rendements de ce même jour. Il combine également Random Forest, règles techniques et positions courtes. Ces résultats ne démontrent donc pas la surperformance d’un HMM long/liquidités causal comparable à notre demande.
- [Allocation HMM publiée sur le Nifty](https://github.com/SahilMotyar/Dynamic-Regime-Allocation) : ce projet rapporte lui-même un rendement inférieur au benchmark, malgré une exposition réduite. Cela constitue une limite utile à vérifier, pas une preuve universelle d’échec ou de réussite des HMM.

La [documentation hmmlearn](https://hmmlearn.readthedocs.io/en/stable/tutorial.html) sert de référence pour l’API, les initialisations et les paramètres. Aucun code distant n’a été exécuté. Les sources consultées ont été lues ; les candidats locaux sont des implémentations indépendantes.

## Hypothèses testées

Trois premières variantes spécifiées ensemble : moments lissés avec modèle figé, mêmes moments avec réentraînement, puis mêmes réentraînements avec décision tenant compte des frais. Trois états, covariance complète, initialisations 17/41/83 départagées par vraisemblance d’entraînement, 29 observations de mise en place. Normalisation et estimation utilisent uniquement les données disponibles avant chaque segment.

Le signal PESR pondère les ratios par état par les probabilités filtrées et deux transitions, pour respecter le délai d’exécution. Le modèle avec frais reprend l’approximation de continuation existante, appliquée cette fois aux moyennes de rendement lissé. Les deux ne constituent pas des espérances de rendement garanties calibrées.

Les réentraînements surviennent toutes les 63 observations, sur au plus 1 260 observations précédentes. Ce calendrier de calcul ne limite pas les transactions : un nouveau signal est évalué chaque jour. La première calibration respecte la période d’entraînement demandée ; les suivantes apprennent au fil du passé déjà observé. Aucun ancien signal n’est réécrit.

Deux variantes supplémentaires évaluent le filtre de volatilité classique : deux états sur rendement quotidien, investissement lorsque l’état de plus faible variance est le plus probable, sinon liquidités ; paramètres figés ou mêmes réentraînements. Le seuil 0,5 correspond au choix entre deux états, sans optimisation d’un seuil de trading. Les frais sont appliqués à chaque ordre. **Cette seconde expérience a été définie après lecture des résultats de la première**, et ne constitue pas une confirmation indépendante.

Il n’y a ni quota de transactions, ni cible d’exposition imposée, ni stop, ni MACD, ni position courte, ni levier. Seuls les frais sont ceux demandés : **0,5 % par ordre pour les actions, 0,01 % pour les cryptos**, puis scénario doublé. Signal à la clôture t, exécution à la clôture t+1, premier rendement perçu à t+2. Liquidation finale et frais du benchmark inclus. Liquidités non rémunérées, glissement et fiscalité exclus.

## Protocole et verdict

22 actifs actuels, Cardano et XRP exclus ; 149 fenêtres admissibles : continu 2022–2025, années 2022 à 2026 séparées, fenêtres par défaut de l’interface. Les cinq fenêtres indisponibles d’Hyperliquid sont exclues explicitement. Les dates par défaut varient selon l’actif et ne constituent pas uniformément cinq ans de test.

**{len(results)} comparaisons modèle/fenêtre/frais** : 298 références archivées du moteur actuel, 894 nouveaux calculs sur moments lissés et 596 nouveaux calculs du filtre de volatilité. {sum("error" in r for r in results)} échec de simulation. Les comparaisons utilisent les mêmes prix et dates, avec vérification des empreintes des données et de l’égalité des performances du benchmark. Les plans et empreintes du code ont été écrits avant chaque série. {failed_refreshes} rafraîchissement du candidat lissé avec frais a échoué au scénario normal ; le dernier modèle utilisable a été conservé, et l’échec figure dans le journal.

Le critère d’acceptation interprète « extrême majorité » comme au moins 80 % de surperformances nettes, dans chaque famille de fenêtres et chaque scénario de frais, avec au plus 20 % d’expositions dégénérées (≥95 % en actif ou ≤5 % en actif), et zéro erreur. Ces seuils évaluent les résultats et ne modifient jamais les ordres. **Aucun candidat ne passe ce critère.**

## Fenêtres par défaut : performance face à la conservation

Conservation : rendement médian {pct(float(np.median([r["benchmark_metrics"]["total_return"] for r in defaults["current_hmm"]])))}. Les écarts médians sont calculés actif par actif, avant la médiane : ils diffèrent généralement de la différence entre deux médianes.

{chr(10).join(table)}

Le candidat lissé réentraîné avec frais répond au problème de passivité, mais **ne démontre pas la surperformance demandée**. L’augmentation des sorties et réentrées ne suffit pas. Sur les rendements réellement accessibles deux observations après le signal, sa séparation moyenne favorable/défavorable est positive pour {separation} actifs sur 22 seulement. C’est un diagnostic descriptif sur les tests réutilisés, sans preuve de calibration ou de causalité économique.

## Nombre d’actifs battant la conservation, par fenêtre

{chr(10).join(annual)}

Sur les 149 fenêtres, aux frais normaux : {", ".join(f"{NAMES[p]} {totalwins[p]}/149" for p in NAMES)}. Ces fenêtres se chevauchent : ce ne sont pas 149 expériences indépendantes.

## Détail par actif, candidat lissé avec frais

Cette variante est détaillée parce qu’elle est la plus directement comparable au moteur actuel tenant compte des coûts ; elle n’est pas déclarée gagnante ni choisie pour l’application sur la base de ces résultats.

{chr(10).join(detailed)}

## Frais doublés, fenêtres par défaut

{chr(10).join(stress)}

## Livrables et vérifications

Les scripts `scripts/hmm_regime_candidates.py`, `scripts/backtest_hmm_literature.py`, `scripts/backtest_hmm_volatility.py` et `scripts/report_hmm_literature.py` restent locaux. Les deux premiers moteurs de recherche sont séparés de l’API : **aucun changement du modèle actif de l’application dans cette recherche**.

Les données, plans, résultats complets, ordres, courbes, calendriers de calibration et tableaux CSV se trouvent dans `data/backtests/hmm-literature/` et `data/backtests/hmm-volatility/`, ignorés par Git. `comparison.csv` réunit les six modèles, toutes fenêtres et tous frais. Le générateur de ce rapport refuse une différence entre le code numérique courant et ses empreintes d’expérience. Les scripts de calcul refusent d’écraser une expérience déjà gelée.

Commandes :

```sh
PYTHONPATH=backend .venv/bin/python scripts/backtest_hmm_literature.py
PYTHONPATH=backend .venv/bin/python scripts/backtest_hmm_volatility.py
.venv/bin/python scripts/report_hmm_literature.py
.venv/bin/pytest -q
```

98 tests backend réussis, dont six nouveaux tests vérifiant les moments exponentiels contre des poids explicites, l’invariance des signaux passés après modification du futur y compris lors des recalibrations, la continuité après échec de calibration, la parité des ordres/coûts avec le moteur actif, l’exposition sur les barres réellement détenues et le rejet d’une stratégie presque toujours investie ou perdante par le critère d’évaluation. Les tests synthétiques ne démontrent pas la rentabilité sur les actifs réels. Une reconstruction indépendante par comptabilité de liquidités et de quantités de titres, à partir des seuls prix et ordres, concorde avec les 1 788 courbes et expositions : écart absolu maximal de capital inférieur à 5 × 10⁻¹⁴. Ruff et la vérification des espaces du diff passent. Le frontend n’a pas changé dans cette recherche.

Les données ont déjà servi à la recherche, les fenêtres se recouvrent et le catalogue actuel comporte un biais de survivance. Les covariables lissées chevauchent le passé et ne satisfont pas exactement l’indépendance conditionnelle supposée par le HMM. Les cinq nouvelles variantes s’ajoutent aux essais précédents : une sélection du meilleur résultat de cette recherche demanderait une nouvelle validation indépendante. **Aucune absence de surapprentissage n’est affirmée. Aucune version rentable dans l’extrême majorité des cas n’a été obtenue. Aucun push GitHub.**
"""
    (ROOT / "docs/hmm-literature.md").write_text(report)
    print("Report written;", len(results), "cases; numerical source hashes verified")


if __name__ == "__main__":
    main()
