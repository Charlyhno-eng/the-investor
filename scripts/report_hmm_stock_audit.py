"""Export the full failed/accepted economic audit, without excluding losers."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from statistics import median

from audit_hmm_stocks import universe
from investor.analysis.evaluation import majority_acceptance

ROOT = Path(__file__).resolve().parents[1]


def percent(value):
    return f"{100 * value:+.2f} %".replace(".", ",")


def export_csv(path, entries, names, policy=None):
    fields = [
        "asset_id",
        "name",
        "case",
        "policy",
        "train_start",
        "train_end",
        "test_start",
        "test_end",
        "fee_bps",
        "strategy_return",
        "benchmark_return",
        "excess_return",
        "strategy_drawdown",
        "benchmark_drawdown",
        "exposure",
        "transactions",
        "error",
        "data_sha256",
    ]
    with path.open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in entries:
            params = row.get("parameters", {})
            strategy = row.get("strategy", {})
            benchmark = row.get("benchmark", {})
            writer.writerow(
                {
                    "asset_id": row["asset_id"],
                    "name": names[row["asset_id"]],
                    "case": row.get("case", str(row.get("year", "interface_default"))),
                    "policy": row.get("policy", policy),
                    "fee_bps": params.get("fee_bps", row.get("fee_bps", 50)),
                    **{
                        key: params.get(key, row.get(key))
                        for key in (
                            "train_start",
                            "train_end",
                            "test_start",
                            "test_end",
                        )
                    },
                    "strategy_return": strategy.get("total_return"),
                    "benchmark_return": benchmark.get("total_return"),
                    "excess_return": row.get("excess_return"),
                    "strategy_drawdown": strategy.get("maximum_drawdown"),
                    "benchmark_drawdown": benchmark.get("maximum_drawdown"),
                    "exposure": row.get("exposure"),
                    "transactions": row.get("transactions"),
                    "error": row.get("error"),
                    "data_sha256": row.get("data_sha256"),
                }
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/investor.sqlite3")
    parser.add_argument(
        "--input", type=Path, default=ROOT / "data/backtests/hmm-stock-audit"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "docs")
    parser.add_argument("--assert-majority", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    catalog = universe(args.database)
    expected = [asset["id"] for asset, _ in catalog]
    names = {asset["id"]: asset["name"] for asset, _ in catalog}
    production = json.loads((args.input / "production.json").read_text())
    candidate = json.loads((args.input / "candidate.json").read_text())
    development = []
    for file in ("development-policy.json", "development-predictive.json"):
        development.extend(json.loads((args.input / file).read_text())["results"])
    defaults = [r for r in candidate["results"] if r["case"] == "interface_default"]
    active_receipt = majority_acceptance(production["results"], expected)
    candidate_receipt = majority_acceptance(defaults, expected)
    annual = {
        case: majority_acceptance(
            [r for r in candidate["results"] if r["case"] == case], expected
        )
        for case in ("annual_2024", "annual_2025", "annual_2026")
    }
    source_files = [
        *sorted((ROOT / "backend/investor/analysis").glob("*.py")),
        *(
            ROOT / "scripts" / name
            for name in (
                "audit_hmm_stocks.py",
                "research_hmm_stock_policies.py",
                "research_hmm_predictive.py",
                "evaluate_hmm_predictive.py",
                "report_hmm_stock_audit.py",
            )
        ),
    ]
    receipt = {
        "production_version": production["version"],
        "fee_bps_per_order": 50,
        "production": active_receipt,
        "candidate": candidate_receipt,
        "candidate_selected_on_development": candidate["selected"],
        "candidate_promoted": False,
        "annual_candidate_results": annual,
        "development_summary": candidate["development"],
        "development_simulations": len(development),
        "default_and_annual_candidate_simulations": len(candidate["results"]),
        "sources_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source_files
        },
    }
    (args.output / "hmm-stock-acceptance.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    )
    export_csv(
        args.output / "hmm-stock-audit.csv",
        production["results"],
        names,
        production["version"],
    )
    export_csv(
        args.output / "hmm-stock-candidate-evaluation.csv", candidate["results"], names
    )
    export_csv(args.output / "hmm-stock-development.csv", development, names)
    by_id = {r["asset_id"]: r for r in defaults}
    table = []
    for row in production["results"]:
        other = by_id[row["asset_id"]]
        table.append(
            f"| {names[row['asset_id']]} | {percent(row['benchmark']['total_return'])} | {percent(row['strategy']['total_return'])} | {row['transactions']} | {percent(other['strategy']['total_return'])} | {other['transactions']} |"
        )
    summary = []
    for row in candidate["development"]:
        summary.append(
            f"| `{row['policy']}` | {row['wins']}/{row['count']} | {percent(row['median_excess'])} point(s) |"
        )
    annual_table = []
    for case, gate in annual.items():
        group = [r for r in candidate["results"] if r["case"] == case]
        annual_table.append(
            f"| {case} | {gate['wins']}/19 | {percent(median(r['excess_return'] for r in group))} point(s) |"
        )
    gtt = next(r for r in production["results"] if r["asset_id"] == "yf-gtt.pa")
    diag = gtt["diagnostics"]
    document = """# Audit économique du HMM sur toutes les actions — 6 novembre 2026

**Critère demandé non atteint. Modèle actif rejeté financièrement, prototype également rejeté. Aucun prototype n’a été activé.**

L’audit précédent à 10 pb sur huit actifs ne vérifiait pas le comportement aux frais par défaut de l’interface. L’audit présent couvre les **19 actions du catalogue**, sans filtrage des perdants, à **50 pb = 0,5 % par achat et par vente**. La réussite technique des tests ne vaut pas réussite financière.

## Critère d’acceptation

Pour chaque action, rendement total net de stratégie strictement supérieur à celui du même actif en achat-conservation, sur la même fenêtre et avec les mêmes frais. Une égalité n’est pas une victoire. Il faut **au moins 10 actions sur 19**, sans erreur, omission ou doublon. Le dénominateur vient du catalogue SQLite, pas des seuls résultats réussis. Les métriques de risque ne remplacent pas ce critère de rendement.

- Moteur actif : **3/19** gagnants, 16 perdants, 17 simulations sans aucun ordre. **ÉCHEC**.
- Prototype choisi avant la vérification récente : **5/19** gagnants, 14 perdants, 0 simulation sans ordre. **ÉCHEC**.
- Résultat machine : [hmm-stock-acceptance.json](hmm-stock-acceptance.json), avec empreintes du code. Le contrôle `--assert-majority` sort volontairement avec le code **1**.

## Reproduction de la capture GTT

Du 28 juin 2024 au 6 novembre 2026, après entraînement du 24 décembre 2018 au 27 juin 2024 : **0 % contre +60,19 %**, aucun ordre. La meilleure prévision logarithmique à cinq observations parmi tous les états vaut **MAXFORECAST**, tandis que le seuil de frais aller-retour vaut **THRESHOLD**. Aucun mélange de probabilités ne peut atteindre ce seuil. La règle bloque donc les achats, indépendamment de la qualité de classification des régimes.

Le diagnostic `entry_reachable` expose désormais cette impossibilité. L’interface affiche « Aucun achat possible » et l’échec face à la conservation ; elle ne parle plus d’impossibilité de vente pour une simulation restée entièrement en liquidités. Les calculs de performance du moteur actif ne sont pas modifiés pour rendre les résultats plus favorables.

Le prototype entre bien sur GTT : **+55,81 %**, deux ordres et environ 89,90 % d’exposition. Cela reste inférieur aux **+60,19 %** de la conservation : supprimer le blocage ne suffit pas.

## Comparaison action par action aux périodes par défaut

Les périodes reproduisent exactement le sélecteur de l’interface : au plus 2 016 cours, séparation 70/30. Les historiques plus courts de Palantir et Technip Energies sont conservés. Les dates effectives, métriques, expositions et empreintes des données figurent dans [le CSV du moteur actif](hmm-stock-audit.csv) et [le CSV complet du prototype](hmm-stock-candidate-evaluation.csv).

| Action | Conservation nette | Moteur actif net | Ordres actifs | Prototype net | Ordres prototype |
| --- | ---: | ---: | ---: | ---: | ---: |
TABLE

## Recherche séparée de l’évaluation récente

**16 variantes, 71 fenêtres de développement chacune : 1 136 simulations**, portant uniquement sur les années de test 2020, 2021, 2022 et 2023, avec cinq années antérieures pour l’entraînement lorsque disponibles. Les cinq couples actif/année sans historique suffisant sont Palantir 2020–2021 et Technip Energies 2020–2022. Les 19 actions sont toutes évaluées aux périodes finales par défaut ; aucune n’en est exclue.

Huit politiques conservent le HMM de rendements : prévisions sur 21/63/126 observations ou décisions par probabilités de régime, avec hystérésis et révision quotidienne, toutes les cinq observations ou toutes les 21 observations. Huit autres variantes ajustent un HMM de tendance/volatilité sur des observations causales et apprennent les rendements futurs associés aux probabilités filtrées **sur des résultats d’entraînement déjà réalisés**. Un embargo du nombre d’observations prévu plus une observation exclut les cibles qui déborderaient de l’entraînement. Horizon de tendance 21/63, horizon prévu 21/63, seuil nul ou frais aller-retour ; trois initialisations, révision toutes les cinq observations. Ces variantes sont des expériences, pas des méthodes validées.

Le prototype `predictive_w63_h21_cost1` est choisi par proportion de surperformances en développement, puis écart médian pour départager les égalités. Il ne dépasse déjà pas **20/71** en développement. Il est figé avant lecture des résultats de la vérification récente, puis néanmoins évalué intégralement pour documenter l’échec. Aucun paramètre n’est changé après cette vérification.

| Variante de développement | Bat la conservation | Écart médian net |
| --- | ---: | ---: |
SUMMARY

Les [1 136 lignes de développement](hmm-stock-development.csv) sont conservées, pas seulement celles du prototype choisi. Les commandes et sorties détaillées sont disponibles sous `data/backtests/hmm-stock-audit/` dans l’espace de travail.

## Vérification annuelle du prototype figé

En plus des 19 périodes par défaut, tests annuels 2024, 2025 et 2026 sur toutes les actions : **57 simulations**, sans erreur ni exclusion. L’année 2026 est arrêtée au dernier cours disponible du 6 novembre. Les défauts et les fenêtres annuelles se chevauchent et ne sont pas indépendants.

| Période | Bat la conservation | Écart médian net |
| --- | ---: | ---: |
ANNUAL

L’année 2024 atteint la majorité, les années 2025 et 2026 ainsi que les périodes par défaut échouent. Choisir uniquement 2024 masquerait ces échecs. Ces historiques ont déjà été étudiés dans ce dépôt : cette séparation des nouveaux réglages ne crée pas rétroactivement un échantillon totalement vierge. Le catalogue actuel comporte aussi un biais de sélection/survie.

## Exécution et limites

Modèles sans levier et sans vente à découvert. Signal à la clôture, exécution à la clôture suivante, rendement gagné à partir de la clôture encore suivante. Liquidation finale et frais symétriques inclus, liquidités non rémunérées, sans glissement ni impôts. Le benchmark achète à la clôture de référence précédant le premier rendement de test et vend à la dernière clôture. Cette convention reste identique à celle de la capture ; elle n’a pas été changée pour faire passer le contrôle. Aucun cours de test ne sert à entraîner les paramètres ou les cibles du prototype.

La recherche de nombreuses variantes peut produire des succès historiques fortuits ; [Bailey et al., probabilité de surajustement des backtests](https://escholarship.org/uc/item/4w1110bb) en décrit le problème. Ici les résultats échouent déjà aux critères demandés. Ils ne permettent pas de déclarer la stratégie corrigée ou surperformante.

## Reproduire

Depuis la racine du dépôt :

```sh
PYTHONPATH=backend .venv/bin/python scripts/audit_hmm_stocks.py --output /tmp/hmm-all-stocks.json --assert-majority
PYTHONPATH=backend .venv/bin/python scripts/research_hmm_stock_policies.py --output /tmp/hmm-development-policy.json
PYTHONPATH=backend .venv/bin/python scripts/research_hmm_predictive.py --output /tmp/hmm-development-predictive.json
PYTHONPATH=backend .venv/bin/python scripts/evaluate_hmm_predictive.py --policy-development /tmp/hmm-development-policy.json --predictive-development /tmp/hmm-development-predictive.json --output /tmp/hmm-candidate.json
PYTHONPATH=backend .venv/bin/python scripts/report_hmm_stock_audit.py --assert-majority
```

Le dernier script lit les quatre fichiers JSON sous `data/backtests/hmm-stock-audit/` (option `--input` pour un autre dossier) et reconstruit les CSV et la décision d’acceptation. Le prototype rejeté reste hors API. Le moteur actif conserve son calcul pour rendre son échec reproductible ; ses diagnostics et l’avertissement expérimental sont corrigés. **L’objectif de surperformance sur la majorité des actions reste non atteint.**
"""
    document = (
        document.replace("MAXFORECAST", percent(diag["maximum_state_forecast"]))
        .replace("THRESHOLD", percent(diag["round_trip_threshold"]))
        .replace("TABLE\n", "\n".join(table) + "\n")
        .replace("SUMMARY\n", "\n".join(summary) + "\n")
        .replace("ANNUAL\n", "\n".join(annual_table) + "\n")
    )
    (args.output / "hmm-stock-audit.md").write_text(document)
    print(
        json.dumps({"production": active_receipt, "candidate": candidate_receipt}),
        flush=True,
    )
    if args.assert_majority and not (
        active_receipt["passed"] and candidate_receipt["passed"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
