"""Publish an honest local report, verifying the archived experiment sources."""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/backtests/hmm-adaptive"


def pct(value, signed=True):
    return (f"{value * 100:+.2f}" if signed else f"{value * 100:.2f}").replace(
        ".", ","
    ) + " %"


def main():
    plan = json.loads((OUT / "plan.json").read_text())
    snapshot = json.loads(
        (ROOT / "data/backtests/hmm-literature/data.json").read_text()
    )
    assert (
        hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        == plan["data_sha256"]
    )
    for name, expected in plan["sources"].items():
        assert (
            hashlib.sha256((OUT / "sources" / name).read_bytes()).hexdigest()
            == expected
        )
    results = json.loads((OUT / "results.json").read_text())["results"]
    totals = json.loads((OUT / "summary.json").read_text())
    assert len(results) == 298 and not any("error" in r for r in results)
    normal = [r for r in results if r["fee_multiple"] == 1]
    wins = sum(
        r["result"]["strategy_metrics"]["total_return"]
        > r["result"]["benchmark_metrics"]["total_return"] + 1e-10
        for r in normal
    )
    ledger_error = max(r["ledger_error"] for r in results)
    default = [
        r
        for r in results
        if r["case"] == "interface_default" and r["fee_multiple"] == 1
    ]
    fields = [
        "asset",
        "case",
        "fee_multiple",
        "return",
        "benchmark_return",
        "exposure",
        "orders",
        "maximum_drawdown",
    ]
    with (OUT / "comparison.csv").open("w") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in results:
            value = row["result"]
            writer.writerow(
                {
                    **{f: row[f] for f in fields[:3]},
                    "return": value["strategy_metrics"]["total_return"],
                    "benchmark_return": value["benchmark_metrics"]["total_return"],
                    "exposure": value["exposure"],
                    "orders": len(value["trades"]),
                    "maximum_drawdown": value["strategy_metrics"]["maximum_drawdown"],
                }
            )
    text = """# Pourquoi le HMM ressemble à l’achat-conservation

6 novembre 2026. **Le défaut est confirmé, mais aucune version surperformante dans l’extrême majorité des cas n’a été obtenue.** La nouvelle variante de tendance reste une expérience locale ; elle n’a pas remplacé le moteur de simulation. Les modifications actives portent sur le diagnostic, la comparaison nette et la visibilité des régimes et positions.

## Reproduction du cas Air Liquide

La fenêtre par défaut du 28 juin 2024 au 6 novembre 2026 donne +30,68 % contre +29,99 %, deux ordres (un aller-retour), 99,67 % d’exposition. Ce n’est pas un défaut du tracé : la stratégie détient presque constamment le même actif que la référence. Son écart net n’est que de **+0,69 point**, sans preuve de valeur ajoutée répétable.

Le HMM apprend un état négatif (moyenne logarithmique quotidienne −0,0814 %) et un état positif (+0,0870 %). Mais leurs avantages de continuation valent respectivement environ −0,1244 % et +0,5732 %, tandis que le seuil de sortie est −0,5013 %. Toute combinaison probabiliste reste au-dessus de ce seuil : **aucun régime ne peut faire vendre**, même un état défavorable certain. La liquidation finale explique la deuxième transaction. Sur les 22 actifs par défaut, 11 souffrent de cette impossibilité structurelle ; trois ont uniquement des moyennes d’état positives.

Cette règle répond à une approximation d’espérance après frais et transitions ; elle ne traduit pas directement « état négatif ⇒ sortie ». La qualifier simplement de détection de baisse masquait cette différence. De plus, ajuster la densité des rendements ne démontre pas une capacité de prévision directionnelle.

## Deux vérifications supplémentaires

Une correction minimale, exploratoire, conserve le HMM figé et la règle d’entrée précédente, exige un état dominant positif pour entrer et sort dès que l’état dominant est négatif. Les frais ne peuvent pas bloquer cette sortie. Sur Air Liquide, elle produit 18 ordres et 91,23 % d’exposition, mais seulement **+9,23 %** net. Sur BE Semiconductor, elle produit 192 ordres. Elle ne bat la conservation que sur 5 actifs sur 22. Faire respecter mécaniquement l’état négatif ne suffit donc pas à résoudre le problème de frais et de rentabilité. Code exact et résultats conservés localement dans `data/backtests/hmm-direct-policy/`.

Une seconde expérience cherche explicitement des régimes de tendance : trois états gaussiens sur le ratio moyenne/écart-type exponentiels des rendements logarithmiques, span 30 fixé. L’idée des moments lissés vient de [Werge, sections 4–5](https://arxiv.org/html/2107.05535v1), mais **placer le ratio lui-même dans les observations est notre adaptation**, pas une reproduction de ses résultats. Ajustement avec [GaussianHMM de hmmlearn](https://hmmlearn.readthedocs.io/en/stable/tutorial.html), trois graines 17/41/83 départagées par vraisemblance d’entraînement. Normalisation apprise sur le passé. Réentraînement toutes les 63 observations, sur au plus 1 260 observations antérieures au signal.

États réordonnés à chaque ajustement, filtre forward causal, aucune réécriture des probabilités passées. État défavorable dominant et centre négatif : sortie, sans veto des frais. État favorable dominant et centre positif : entrée seulement si le mouvement indicatif sur sa durée moyenne apprise couvre les deux frais. État intermédiaire : maintien. Cette estimation des coûts est une heuristique, sans promesse de gain. Pas de MACD, de stop, de quota de transactions, de cible d’exposition, de position courte ou de levier. Les noms d’état désignent la tendance observée, pas une prévision garantie.

## Comparaison nette sur toutes les fenêtres

22 actifs, 149 fenêtres admissibles, chacun aux frais normaux puis doublés : **298 nouveaux backtests**. Les fenêtres sont les mêmes que dans [l’étude précédente](hmm-literature.md) : continu 2022–2025, tests annuels 2022–2026, périodes par défaut de l’interface. Les cinq fenêtres sans historique suffisant d’Hyperliquid restent exclues. Crypto : 0,01 % par achat et par vente ; action : 0,5 %. Signal à la clôture t, ordre à la clôture t+1, premier rendement t+2 ; liquidation finale et frais de la référence inclus.

| Fenêtre, frais normaux | Actifs | Bat conservation | Rendement médian | Conservation médiane | Exposition médiane | Ordres médians |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
"""
    for row in totals:
        if row["fee_multiple"] == 1:
            text += f"| {row['case']} | {row['count']} | {row['wins']} | {pct(row['median_return'])} | {pct(row['median_hold_return'])} | {pct(row['median_exposure'], False)} | {row['median_orders']:g} |\n"
    text += f"""
**{wins}/149 surperformances aux frais normaux**, sur des fenêtres qui se chevauchent. Sur les fenêtres par défaut : 6/22, rendement médian −2,78 % contre +32,65 %, exposition médiane 39,40 %, 14 ordres médians. Aucun actif n’y reste investi à ≥95 % ou en liquidités à ≥95 %. Les courbes diffèrent, mais le résultat financier se dégrade. Avec les frais doublés : 5/22, rendement médian −8,27 %. Aucun groupe ne passe le critère de 80 % de surperformances. **Cette variante est rejetée.**

## Détail des fenêtres par défaut, frais normaux

| Actif | Stratégie candidate | Conservation | Exposition | Ordres |
| --- | ---: | ---: | ---: | ---: |
"""
    for row in default:
        value = row["result"]
        text += f"| {row['name']} | {pct(value['strategy_metrics']['total_return'])} | {pct(value['benchmark_metrics']['total_return'])} | {pct(value['exposure'], False)} | {len(value['trades'])} |\n"
    text += f"""
## Vérifications et conséquence pour l’application

Zéro erreur de simulation et zéro recalibration abandonnée. Les rendements nets de la conservation correspondent à ceux de l’expérience archivée sur les mêmes prix. Une reconstruction indépendante par liquidités et quantités détenues, depuis les prix et ordres, retrouve les **298 courbes et expositions** ; écart maximal de capital {ledger_error:.3g} pour une base initiale 1.

Le moteur numérique actif conserve ses règles antérieures : **aucune amélioration financière n’est annoncée**. En revanche, le résultat signale désormais une sortie structurellement impossible et l’exposition quasi permanente ; le cache est versionné à nouveau pour ajouter ces diagnostics. L’interface montre l’écart net en points et une chronologie séparant le régime dominant de la position réellement détenue après clôture. Une moyenne d’état négative ne signifie pas que la règle de continuation vende, et une probabilité d’état favorable n’est pas une probabilité de gain.

Les seuils de 95 % pour le diagnostic d’exposition et de 80 % pour l’évaluation ne changent aucun ordre. Il n’y a aucun objectif forcé de transactions.

Vérifications logicielles : 105 tests backend réussis, dont les invariants de causalité à travers les recalibrations, le réordonnancement des états, la conservation du dernier modèle après échec et la réentrée sans verrou. 22 tests navigateur de l’espace de travail réussis sur ordinateur et mobile, dont le diagnostic d’une exposition presque permanente et la séparation des régimes et positions. Build de production, Ruff et vérification des espaces du diff réussis. Les tests navigateur utilisent le binaire Chromium déjà disponible via `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` ; le binaire attendu par défaut par la version installée de Playwright est absent. Ces tests ne démontrent pas la rentabilité.

Données et résultats complets : `data/backtests/hmm-adaptive/`, ignoré par Git. `plan.json` et `sources/` conservent le code exact de l’expérience, y compris le script avant sa correction ultérieure de liaison de variable signalée par Ruff et l’ajout de l’archivage automatique des sources. Ces modifications du lanceur ne changent pas les calculs ; le résumé a été recalculé à l’identique. `comparison.csv` permet les comparaisons actif par actif. Le moteur candidat se trouve dans `backend/investor/analysis/adaptive.py`, sans connexion à l’API.

Les paramètres sont fixés pour cette expérience, sans grille de recherche sur les performances de test. **Ce nouvel essai intervient après les cinq variantes précédentes et après lecture de trois cas de contrôle** ; l’historique est réutilisé, les fenêtres se recouvrent et l’univers actuel comporte un biais de survivance. Les observations lissées se chevauchent et les probabilités ne sont pas validées comme probabilités de prévision. Ni l’absence de surapprentissage ni la rentabilité future ne sont établies. Ces résultats négatifs ne justifient pas d’ajuster encore les paramètres jusqu’à embellir les mêmes tests.

Aucun push GitHub.
"""
    (ROOT / "docs/hmm-passivity.md").write_text(text)


if __name__ == "__main__":
    main()
