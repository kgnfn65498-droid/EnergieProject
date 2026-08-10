#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

REQUIRED_TOP = ["rapport", "contract", "samenvatting", "kpi_boven", "kpi_onder", "maand", "score", "efficientie", "batterij"]
COLORS = {"rood", "groen", "oranje", "blauw", "paars", "turkoois"}

class DataValidationError(ValueError):
    pass

def _need(obj: dict[str, Any], keys: list[str], path: str) -> None:
    missing = [k for k in keys if k not in obj]
    if missing:
        raise DataValidationError(f"{path}: ontbrekende velden: {', '.join(missing)}")

def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataValidationError(f"{path}: verwacht getal")
    return float(value)

def _text(value: Any, path: str, max_len: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataValidationError(f"{path}: verwacht niet-lege tekst")
    if len(value) > max_len:
        raise DataValidationError(f"{path}: maximaal {max_len} tekens om de vaste template te behouden")
    return value

def validate(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise DataValidationError("Bovenste niveau moet een object zijn")
    _need(data, REQUIRED_TOP, "root")
    _need(data["rapport"], ["periode", "rapportdatum", "maand"], "rapport")
    _text(data["rapport"]["periode"], "rapport.periode", 45)
    _text(data["rapport"]["rapportdatum"], "rapport.rapportdatum", 28)
    _text(data["rapport"]["maand"], "rapport.maand", 24)
    _need(data["contract"], ["start", "type"], "contract")
    _text(data["contract"]["start"], "contract.start", 24)
    _text(data["contract"]["type"], "contract.type", 34)

    summaries = data["samenvatting"]
    if not isinstance(summaries, list) or not (1 <= len(summaries) <= 8):
        raise DataValidationError("samenvatting: verwacht 1 t/m 8 regels")
    for i, item in enumerate(summaries):
        _need(item, ["kleur", "tekst"], f"samenvatting[{i}]")
        if item["kleur"] not in {"groen", "oranje", "rood"}:
            raise DataValidationError(f"samenvatting[{i}].kleur: ongeldige kleur")
        _text(item["tekst"], f"samenvatting[{i}].tekst", 170)

    for key, expected in (("kpi_boven", 7), ("kpi_onder", 6)):
        items = data[key]
        if not isinstance(items, list) or len(items) != expected:
            raise DataValidationError(f"{key}: exact {expected} items vereist voor vaste layout")
        for i, item in enumerate(items):
            req = ["titel", "waarde", "kleur"] + (["icoon", "eenheid", "delta"] if key == "kpi_boven" else ["sub"])
            _need(item, req, f"{key}[{i}]")
            _text(item["titel"], f"{key}[{i}].titel", 30)
            _text(str(item["waarde"]), f"{key}[{i}].waarde", 18)
            if item["kleur"] not in COLORS:
                raise DataValidationError(f"{key}[{i}].kleur: ongeldige kleur")

    month = data["maand"]
    _need(month, ["verbruik", "teruglevering", "gas", "netto_maanden"], "maand")
    for key in ("verbruik", "teruglevering", "gas"):
        obj = month[key]
        _need(obj, ["waarde", "delta", "jaren"], f"maand.{key}")
        _number(obj["waarde"], f"maand.{key}.waarde")
        _number(obj["delta"], f"maand.{key}.delta")
        if not isinstance(obj["jaren"], list) or len(obj["jaren"]) != 4:
            raise DataValidationError(f"maand.{key}.jaren: exact 4 waarden vereist")
        for j, value in enumerate(obj["jaren"]): _number(value, f"maand.{key}.jaren[{j}]")
    if not isinstance(month["netto_maanden"], list) or len(month["netto_maanden"]) != 12:
        raise DataValidationError("maand.netto_maanden: exact 12 maandwaarden vereist")

    score = data["score"]
    _need(score, ["totaal", "onderdelen"], "score")
    total = _number(score["totaal"], "score.totaal")
    if not 0 <= total <= 100: raise DataValidationError("score.totaal: bereik 0..100")
    if not isinstance(score["onderdelen"], list) or len(score["onderdelen"]) != 5:
        raise DataValidationError("score.onderdelen: exact 5 onderdelen vereist")
    for i, pair in enumerate(score["onderdelen"]):
        if not isinstance(pair, list) or len(pair) != 2: raise DataValidationError(f"score.onderdelen[{i}]: [naam, waarde]")
        _text(pair[0], f"score.onderdelen[{i}][0]", 38)
        val = _number(pair[1], f"score.onderdelen[{i}][1]")
        if not 0 <= val <= 100: raise DataValidationError(f"score.onderdelen[{i}][1]: bereik 0..100")

    eff = data["efficientie"]
    _need(eff, ["zelfvoorziening", "delta_zelf", "eigen_verbruik", "delta_eigen", "gas", "delta_gas"], "efficientie")
    for key in eff: _number(eff[key], f"efficientie.{key}")

    bat = data["batterij"]
    _need(bat, ["score", "ontwikkeling", "capaciteit", "benutting", "besparing", "investering", "terugverdientijd"], "batterij")
    bscore = _number(bat["score"], "batterij.score")
    if not 0 <= bscore <= 100: raise DataValidationError("batterij.score: bereik 0..100")
    if not isinstance(bat["ontwikkeling"], list) or len(bat["ontwikkeling"]) != 6:
        raise DataValidationError("batterij.ontwikkeling: exact 6 waarden vereist")
    for i, value in enumerate(bat["ontwikkeling"]): _number(value, f"batterij.ontwikkeling[{i}]")
    for key in ("capaciteit", "benutting", "besparing", "investering", "terugverdientijd"):
        _text(str(bat[key]), f"batterij.{key}", 34)

def load_and_validate(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DataValidationError(f"Bestand niet gevonden: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DataValidationError(f"Ongeldige JSON op regel {exc.lineno}, kolom {exc.colno}: {exc.msg}") from exc
    validate(data)
    return data

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Valideer maanddata zonder PDF te bouwen")
    p.add_argument("maanddata")
    args = p.parse_args()
    load_and_validate(Path(args.maanddata))
    print("Maanddata geldig")
