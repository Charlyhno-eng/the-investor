"""Publish all slower-HMM results, including an equal-entry passive control."""

import argparse
import csv
import json
from pathlib import Path
from statistics import median

from audit_hmm_stocks import universe
from investor.analysis.evaluation import majority_acceptance

CASES = ("interface_default", "annual_2024", "annual_2025", "annual_2026")
TOLERANCE = 1e-10


def summarize(group):
    valid = [r for r in group if "error" not in r]
    return {
        "count": len(group),
        "errors": len(group) - len(valid),
        "wins": sum(r["excess_return"] > TOLERANCE for r in valid),
        "matched_wins": sum(r["matched_excess_return"] > TOLERANCE for r in valid),
        "matched_ties": sum(
            abs(r["matched_excess_return"]) <= TOLERANCE for r in valid
        ),
        "median_excess": median(r["excess_return"] for r in valid),
        "matched_median_excess": median(r["matched_excess_return"] for r in valid),
        "median_orders": median(r["transactions"] for r in valid),
        "median_drawdown": median(r["strategy"]["maximum_drawdown"] for r in valid),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--adaptive", type=Path, required=True)
    parser.add_argument(
        "--baseline", type=Path, default=Path("data/backtests/hmm-basic/results.json")
    )
    parser.add_argument("--database", type=Path, default=Path("data/investor.sqlite3"))
    parser.add_argument("--output", type=Path, default=Path("docs/hmm-persistent.md"))
    args = parser.parse_args()
    data = json.loads(args.source.read_text())
    adaptive = json.loads(args.adaptive.read_text())
    catalog = {asset["id"]: rows for asset, rows in universe(args.database)}

    def matched(result):
        if "error" in result:
            return result.copy()
        rows = [
            r
            for r in catalog[result["asset_id"]]
            if result["train_start"] <= r["date"] <= result["test_end"]
        ]
        i = next(i for i, r in enumerate(rows) if r["date"] >= result["test_start"])
        bm = (1 + result["benchmark"]["total_return"]) / (
            rows[i]["value"] / rows[i - 1]["value"]
        ) - 1
        return dict(
            result,
            matched_benchmark_return=bm,
            matched_excess_return=result["strategy"]["total_return"] - bm,
        )

    results = [matched(r) for r in data["evaluation"]]
    baseline = []
    for r in json.loads(args.baseline.read_text())["results"]:
        if r["fee_bps"] != 50:
            continue
        params = r["parameters"]
        baseline.append(
            matched(
                dict(
                    r,
                    policy="basic",
                    train_start=params["train_start"],
                    test_start=params["test_start"],
                    test_end=params["test_end"],
                )
            )
        )
    adaptive_rows = [dict(r, policy="adaptive") for r in adaptive["results"]]
    all_rows = results + baseline + adaptive_rows
    ranking = {}
    for case in CASES:
        group = [r for r in all_rows if r["case"] == case]
        policies = sorted({r["policy"] for r in group})
        ranking[case] = [
            dict(policy=p, **summarize([r for r in group if r["policy"] == p]))
            for p in policies
        ]
    receipt = {
        "frozen_global_policy": data["selected"],
        "summary": ranking,
        "matched_acceptance": {},
        "errors": [r for r in all_rows if "error" in r],
    }
    for p in (data["selected"]["policy"], "adaptive", "trend63_dominant_c21"):
        group = [
            dict(r, benchmark={"total_return": r.get("matched_benchmark_return")})
            for r in all_rows
            if r["case"] == "interface_default" and r["policy"] == p
        ]
        receipt["matched_acceptance"][p] = majority_acceptance(group, list(catalog))
    args.output.with_suffix(".json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    )
    fields = [
        "asset_id",
        "name",
        "case",
        "policy",
        "strategy_return",
        "benchmark_return",
        "matched_benchmark_return",
        "excess_return",
        "matched_excess_return",
        "transactions",
        "exposure",
        "selected",
        "validation_advantage",
        "data_sha256",
        "error",
    ]
    with args.output.with_suffix(".csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for r in all_rows:
            row = {f: r.get(f) for f in fields}
            row.update(
                strategy_return=r.get("strategy", {}).get("total_return"),
                benchmark_return=r.get("benchmark", {}).get("total_return"),
            )
            writer.writerow(row)

    selected = data["selected"]["policy"]
    show = [
        "basic",
        selected,
        "trend63_dominant_c21",
        "return5_hysteresis_c21",
        "return21_defensive_c1",
        "adaptive",
        "control_momentum21",
        "control_momentum63",
    ]

    def pct(value):
        return f"{100 * value:+.2f}".replace(".", ",")

    lines = [
        "# Recherche HMM à régimes persistants — 6 novembre 2026",
        "",
        "**Des améliorations existent par rapport au HMM minimal, mais aucune majorité robuste n’est validée. Aucune variante n’est promue dans l’API.**",
        "",
        "## Protocole",
        "",
        "Deux états dans tous les HMM. Cinq représentations : rendement quotidien, blocs non chevauchants de 5 ou 21 séances, tendance normalisée et volatilité sur 21 ou 63 séances. Les observations sont disponibles seulement une fois leur fenêtre terminée. Trois règles : état dominant ; hystérésis (entrée à 70 %, sortie sous 30 %) ; défensive (sortie sous 20 % de probabilité haussière, seulement si l’autre état a une moyenne négative, réentrée à 50 %). Décision quotidienne ou toutes les 21 séances. **30 variantes HMM et deux témoins de tendance sans HMM**, tous évalués sur les mêmes actions.",
        "",
        "Normalisation, moyennes et paramètres appris sur l’entraînement uniquement ; trois initialisations choisies par vraisemblance d’entraînement. Filtre causal, paramètres figés pendant le test. Signal à t, exécution à la clôture t+1. Frais de 0,5 % à chaque achat et vente, liquidation finale, aucun levier ni rendement des liquidités.",
        "",
        f"Sélection globale par taux de victoire puis écart médian sur 2020–2023 : `{selected}` ({data['selected']['wins']}/{data['selected']['count']} cas de développement gagnants). Sur 76 cas action/année possibles, 8 ont un historique insuffisant (Palantir et Technip Energies, quatre années chacun) ; ils sont conservés explicitement dans le fichier source. Les 68 cas admissibles sont identiques pour les 32 règles. Évaluation ultérieure : les 19 actions sur les fenêtres de l’interface et chacune des années 2024–2026, soit 2 432 simulations et aucune exclusion pour cette grille.",
        "",
        "Une extension adaptative sélectionne, pour chaque action, la règle qui aurait dépassé la conservation d’au moins deux points nets sur les 252 dernières séances de son entraînement. Sinon elle conserve l’actif. Elle réestime ensuite le HMM sur tout l’entraînement. Cette extension est exploratoire ; elle ne choisit jamais sur la fenêtre de test correspondante. Les erreurs de validation pour historique insuffisant restent visibles, sans substitution silencieuse.",
        "",
        "Ces historiques ont déjà été consultés dans plusieurs expériences. Les périodes annuelles et celles de l’interface se chevauchent. Les gagnants repérés après inspection sont **exploratoires**, sans valeur de validation indépendante.",
        "",
        "## Vérification qui évite une fausse victoire",
        "",
        "Le benchmark historique entre à la clôture précédant le premier rendement de test ; le HMM ne peut exécuter son premier ordre qu’à la première clôture de test. Une stratégie pratiquement toujours investie peut donc sembler meilleure simplement parce qu’elle évite la première séance. Nous conservons le benchmark historique pour comparer les anciens chiffres, et ajoutons un témoin passif qui entre à la **même première clôture exécutable** que le HMM. Même prix de sortie et deux frais dans les deux cas. Les égalités numériques (tolérance 10⁻¹⁰) ne comptent pas comme victoires.",
        "",
        "## Fenêtres par défaut — 19 actions, frais inclus",
        "",
        "La sélection globale est fixée sur le développement. Les deux autres variantes présentées sont des diagnostics exploratoires : ne pas les confondre avec une sélection validée.",
        "",
        "| Règle | Victoires / benchmark historique | Victoires / entrée identique | Égalités / entrée identique | Écart médian historique (points) | Ordres médians |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for p in show:
        r = next(r for r in ranking["interface_default"] if r["policy"] == p)
        lines.append(
            f"| {p} | {r['wins']}/19 | {r['matched_wins']}/19 | {r['matched_ties']} | {pct(r['median_excess'])} | {r['median_orders']} |"
        )
    lines += [
        "",
        "## Vérification annuelle",
        "",
        "| Période | Règle | Victoires historiques | Victoires à entrée identique | Erreurs |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for case in CASES[1:]:
        for p in ("basic", selected, "trend63_dominant_c21", "adaptive"):
            r = next(r for r in ranking[case] if r["policy"] == p)
            lines.append(
                f"| {case} | {p} | {r['wins']}/19 | {r['matched_wins']}/19 | {r['errors']} |"
            )
    lines += [
        "",
        "## Chaque action — diagnostic exploratoire à tendance de 63 séances",
        "",
        "Ce diagnostic réduit la fréquence des décisions à 21 séances ; il a été repéré après lecture des résultats et n’est pas une preuve de généralisation.",
        "",
        "| Action | Stratégie nette | Conservation historique | Conservation à entrée identique | Ordres |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for r in results:
        if r["case"] == "interface_default" and r["policy"] == "trend63_dominant_c21":
            lines.append(
                f"| {r['name']} | {pct(r['strategy']['total_return'])} % | {pct(r['benchmark']['total_return'])} % | {pct(r['matched_benchmark_return'])} % | {r['transactions']} |"
            )
    lines += [
        "",
        "## Tous les résultats",
        "",
        "Le [CSV exhaustif](hmm-persistent.csv) contient toutes les règles sur chaque action et période, ainsi que le HMM minimal et la variante adaptative. Le [reçu JSON](hmm-persistent.json) contient le classement complet, les erreurs et les contrôles de majorité stricte. Les résultats sources, réglages et empreintes de code/données sont dans `data/backtests/hmm-persistent/`.",
        "",
        "```sh",
        "PYTHONPATH=backend .venv/bin/python scripts/research_hmm_persistent.py --output data/backtests/hmm-persistent/results.json",
        "PYTHONPATH=backend .venv/bin/python scripts/evaluate_hmm_persistent_adaptive.py --source data/backtests/hmm-persistent/results.json --output data/backtests/hmm-persistent/adaptive.json",
        "PYTHONPATH=backend .venv/bin/python scripts/report_hmm_persistent.py --source data/backtests/hmm-persistent/results.json --adaptive data/backtests/hmm-persistent/adaptive.json",
        "```",
        "",
    ]
    args.output.write_text("\n".join(lines))
    print(json.dumps(receipt["matched_acceptance"], indent=2))


if __name__ == "__main__":
    main()
