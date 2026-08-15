from __future__ import annotations

import calendar
import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import xlsxwriter

APP_ROOT = Path(__file__).resolve().parent
SEED_PATH = APP_ROOT / "historical_energy_seed.json"
MASTER_RELATIVE = Path("Data/02_Output/Rapportages/Energie_verbruik_historie.xlsx")
ARCHIVE_RELATIVE = Path("Data/02_Output/Rapportages/Archief")
SHEET_NAMES = [
    "Dashboard",
    "Dashboard 2026",
    "2026 vs 3 jaar",
    "Jaaroverzicht",
    "Kalenderjaren",
    "Maanddetail",
    "Contractjaren",
    "Zonnepanelen",
    "Apparaatmetingen",
    "Bronnen",
    "Onderhoud",
]

# Explicit historical metadata. These values are not inferred from supplier-year totals.
SUPPLIER_BY_YEAR = {
    2009: "Onbekend",
    2010: "Onbekend",
    2011: "Onbekend",
    2012: "Onbekend → Greenchoice (06-11-2012)",
    2013: "Greenchoice",
    2014: "Greenchoice",
    2015: "Onbekend",
    2016: "Onbekend → Eneco (15-07-2016)",
    2017: "Eneco",
    2018: "Eneco",
    2019: "Eneco → Powerpeers (16-07-2019)",
    2020: "Powerpeers",
    2021: "Powerpeers",
    2022: "Powerpeers",
    2023: "Powerpeers",
    2024: "Powerpeers",
    2025: "Powerpeers",
    2026: "Powerpeers → NextEnergy (15-07-2026)",
}

# The legacy detail periods are already audited. Coverage labels remain explicit so
# partial historical years are never silently promoted to complete calendar years.
COVERAGE_BY_YEAR = {
    2009: ("nov–dec 2009", "PARTIEEL"),
    2010: ("12 maandperioden jan–dec", "VOLLEDIG"),
    2011: ("12 maandperioden jan–dec", "VOLLEDIG"),
    2012: ("12 maandperioden jan–dec", "VOLLEDIG"),
    2013: ("12 maandperioden jan–dec", "VOLLEDIG"),
    2014: ("12 maandperioden jan–dec", "VOLLEDIG"),
    2015: ("12 maandperioden jan–dec", "VOLLEDIG"),
    2016: ("12 maandperioden jan–dec", "VOLLEDIG"),
    2017: ("jan–okt", "PARTIEEL"),
    2018: ("16 jul–31 dec", "PARTIEEL"),
    2019: ("jan–12 mei", "PARTIEEL"),
    2020: ("okt–dec", "PARTIEEL"),
    2021: ("jan–28 aug", "PARTIEEL"),
    2022: ("15 jul–31 dec", "PARTIEEL"),
    2023: ("jan–dec", "VOLLEDIG"),
    2024: ("jan–dec", "VOLLEDIG"),
    2025: ("jan–dec", "VOLLEDIG"),
    2026: ("jan–jul volledig", "PARTIEEL"),
}


def load_seed(path: Path | None = None) -> dict[str, Any]:
    source = path or SEED_PATH
    data = json.loads(source.read_text(encoding="utf-8"))
    if data.get("schema") != "energie_history_seed_v1":
        raise ValueError(f"Onbekend historische seed-schema: {data.get('schema')!r}")
    periods = list(data.get("periods") or [])
    if not periods:
        raise ValueError("Historische seed bevat geen perioden.")
    _validate_period_dates(periods)
    return data


def _parse_iso_date(value: str) -> date:
    return date.fromisoformat(str(value)[:10])


def _validate_period_dates(periods: Iterable[dict[str, Any]]) -> None:
    for item in periods:
        start = _parse_iso_date(item["from"])
        end = _parse_iso_date(item["to"])
        if start < date(2009, 11, 1) or end < date(2009, 11, 1):
            raise ValueError(f"Historische datum vóór 01-11-2009 geblokkeerd: {start}–{end}")
        if end < start:
            raise ValueError(f"Ongeldige periode: {start}–{end}")


def _sum_numeric(rows: Iterable[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    if not values:
        return None
    return round(sum(values), 3)


def _year_periods(periods: Iterable[dict[str, Any]], year: int) -> list[dict[str, Any]]:
    return [item for item in periods if _parse_iso_date(item["from"]).year == year]


def _coverage_for_year(year: int, rows: list[dict[str, Any]]) -> tuple[str, str]:
    # Preserve explicitly audited legacy coverage through 2025.
    if year in COVERAGE_BY_YEAR and year <= 2025:
        return COVERAGE_BY_YEAR[year]
    full_months: set[int] = set()
    partial_months: set[int] = set()
    for row in rows:
        month = _parse_iso_date(row["from"]).month
        if str(row.get("status") or "").upper() == "VOLLEDIG":
            full_months.add(month)
        else:
            partial_months.add(month)
    if len(full_months) == 12 and not partial_months:
        return "jan–dec", "VOLLEDIG"
    if year == 2026 and full_months == set(range(1, 8)) and not partial_months:
        return "jan–jul volledig", "PARTIEEL"
    if year == 2026 and set(range(1, 8)).issubset(full_months) and 8 in partial_months:
        return "jan–jul volledig; aug partieel", "PARTIEEL"
    if full_months or partial_months:
        months = sorted(full_months | partial_months)
        labels = [calendar.month_abbr[m].lower() for m in months]
        return f"{labels[0]}–{labels[-1]}", "PARTIEEL"
    return "geen data", "PARTIEEL"


def build_calendar_year_rows(periods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    _validate_period_dates(periods)
    years = sorted({_parse_iso_date(item["from"]).year for item in periods})
    result: list[dict[str, Any]] = []
    for year in years:
        rows = _year_periods(periods, year)
        coverage, status = _coverage_for_year(year, rows)
        result.append({
            "year": year,
            "coverage": coverage,
            "status": status,
            "supplier": SUPPLIER_BY_YEAR.get(year, "Onbekend"),
            "import_kwh": _sum_numeric(rows, "import_kwh"),
            "export_kwh": _sum_numeric(rows, "export_kwh"),
            "net_kwh": _sum_numeric(rows, "net_kwh"),
            "gas_m3": _sum_numeric(rows, "gas_m3"),
            "airco_kwh": _sum_numeric(rows, "airco_kwh"),
            "extra_pv_kwh": _sum_numeric(rows, "extra_pv_kwh"),
        })
    return result


def _complete_month_value(periods: list[dict[str, Any]], year: int, month: int, key: str) -> float:
    rows = [
        item for item in periods
        if _parse_iso_date(item["from"]).year == year
        and _parse_iso_date(item["from"]).month == month
        and str(item.get("status") or "").upper() == "VOLLEDIG"
    ]
    value = _sum_numeric(rows, key)
    return float(value or 0.0)


def build_equal_month_comparison(
    periods: list[dict[str, Any]],
    current_year: int,
    *,
    years_back: int = 3,
) -> dict[str, Any]:
    candidates: list[int] = []
    for month in range(1, 13):
        rows = [
            item for item in periods
            if _parse_iso_date(item["from"]).year == current_year
            and _parse_iso_date(item["from"]).month == month
            and str(item.get("status") or "").upper() == "VOLLEDIG"
        ]
        if rows:
            candidates.append(month)
        else:
            break
    through = max(candidates) if candidates else 0
    if through == 0:
        return {"through_month": 0, "years": [], "monthly_net": [], "monthly_gas": []}

    years = list(range(current_year - years_back, current_year + 1))
    year_rows: list[dict[str, Any]] = []
    for year in years:
        year_rows.append({
            "year": year,
            "period": f"01-01 t/m {calendar.monthrange(year, through)[1]:02d}-{through:02d}",
            "status": f"{through} volledige maanden",
            "import_kwh": round(sum(_complete_month_value(periods, year, m, "import_kwh") for m in range(1, through + 1)), 3),
            "export_kwh": round(sum(_complete_month_value(periods, year, m, "export_kwh") for m in range(1, through + 1)), 3),
            "net_kwh": round(sum(_complete_month_value(periods, year, m, "net_kwh") for m in range(1, through + 1)), 3),
            "gas_m3": round(sum(_complete_month_value(periods, year, m, "gas_m3") for m in range(1, through + 1)), 3),
        })
    monthly_net: list[dict[Any, Any]] = []
    monthly_gas: list[dict[Any, Any]] = []
    for month in range(1, through + 1):
        net: dict[Any, Any] = {"month": month}
        gas: dict[Any, Any] = {"month": month}
        for year in years:
            net[year] = _complete_month_value(periods, year, month, "net_kwh")
            gas[year] = _complete_month_value(periods, year, month, "gas_m3")
        monthly_net.append(net)
        monthly_gas.append(gas)
    return {
        "through_month": through,
        "years": year_rows,
        "monthly_net": monthly_net,
        "monthly_gas": monthly_gas,
    }


def _dutch_number(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(".", "").replace(",", ".")
    if not text or text == "-":
        return None
    return float(text)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _smp_csv_month_actuals(month_dir: Path, month_key: str) -> dict[str, Any] | None:
    elec = sorted(month_dir.glob("elektriciteit_*_*.csv"))
    gas_files = sorted(month_dir.glob("gas_*_*.csv"))
    if not elec or not gas_files:
        return None
    import_kwh = 0.0
    export_kwh = 0.0
    gas_m3 = 0.0
    day_dates: set[date] = set()

    for csv_path in elec:
        interval_import = 0.0
        interval_export = 0.0
        first_import_reading: float | None = None
        first_export_reading: float | None = None
        first_import_usage = 0.0
        first_export_usage = 0.0
        last_import_reading: float | None = None
        last_export_reading: float | None = None
        usage_index = 0
        first_reading_index: int | None = None
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                usages = json.loads(row.get("usages") or "[]")
                if row.get("_date"):
                    day_dates.add(date.fromisoformat(row["_date"]))
                for usage in usages:
                    delivery = (_dutch_number(usage.get("delivery_high")) or 0.0) + (_dutch_number(usage.get("delivery_low")) or 0.0)
                    returned = (_dutch_number(usage.get("returned_delivery_high")) or 0.0) + (_dutch_number(usage.get("returned_delivery_low")) or 0.0)
                    interval_import += delivery
                    interval_export += returned
                    import_reading = _dutch_number(usage.get("delivery_reading_combined"))
                    export_reading = _dutch_number(usage.get("returned_delivery_reading_combined"))
                    if import_reading is not None and export_reading is not None:
                        if first_import_reading is None:
                            first_import_reading = import_reading
                            first_export_reading = export_reading
                            first_import_usage = delivery
                            first_export_usage = returned
                            first_reading_index = usage_index
                        last_import_reading = import_reading
                        last_export_reading = export_reading
                    usage_index += 1
        if (
            first_reading_index == 0
            and first_import_reading is not None
            and first_export_reading is not None
            and last_import_reading is not None
            and last_export_reading is not None
            and last_import_reading >= first_import_reading - first_import_usage
            and last_export_reading >= first_export_reading - first_export_usage
        ):
            # SMP-detailverbruiken zijn afgerond op 0,01. Over een hele maand kan
            # de som daarvan afwijken van de echte meterstanddelta. Gebruik daarom
            # de cumulatieve meterstanden aan de grenzen; de eerste intervalwaarde
            # reconstrueert de meterstand op het begin van de maand.
            import_kwh += last_import_reading - first_import_reading + first_import_usage
            export_kwh += last_export_reading - first_export_reading + first_export_usage
        else:
            import_kwh += interval_import
            export_kwh += interval_export

    for csv_path in gas_files:
        interval_gas = 0.0
        first_gas_reading: float | None = None
        first_gas_usage = 0.0
        last_gas_reading: float | None = None
        usage_index = 0
        first_reading_index: int | None = None
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                usages = json.loads(row.get("usages") or "[]")
                for usage in usages:
                    delivery = _dutch_number(usage.get("delivery")) or 0.0
                    interval_gas += delivery
                    gas_reading = _dutch_number(usage.get("delivery_reading"))
                    if gas_reading is not None:
                        if first_gas_reading is None:
                            first_gas_reading = gas_reading
                            first_gas_usage = delivery
                            first_reading_index = usage_index
                        last_gas_reading = gas_reading
                    usage_index += 1
        if (
            first_reading_index == 0
            and first_gas_reading is not None
            and last_gas_reading is not None
            and last_gas_reading >= first_gas_reading - first_gas_usage
        ):
            gas_m3 += last_gas_reading - first_gas_reading + first_gas_usage
        else:
            gas_m3 += interval_gas

    year, month = (int(part) for part in month_key.split("_"))
    expected_days = calendar.monthrange(year, month)[1]
    complete = len(day_dates) == expected_days
    last_day = max(day_dates).day if day_dates else 1
    return {
        "month": month_key,
        "status": "VOLLEDIG" if complete else "PARTIEEL",
        "period_start": f"{year:04d}-{month:02d}-01",
        "period_end": f"{year:04d}-{month:02d}-{expected_days if complete else last_day:02d}",
        "import_kwh": round(import_kwh, 3),
        "export_kwh": round(export_kwh, 3),
        "net_kwh": round(import_kwh - export_kwh, 3),
        "gas_m3": round(gas_m3, 3),
        "source": str(month_dir),
    }


def read_project_month_actuals(project_root: Path, month_key: str) -> dict[str, Any] | None:
    month_dir = project_root / "Data" / "01_Input" / month_key / "HomeAssistant" / "SlimmeMeterPortal"
    if not month_dir.is_dir():
        return None
    prepared = month_dir / "historical_energy_month_actuals.json"
    if prepared.is_file():
        return _load_json(prepared)
    coverage = month_dir / "content_coverage_report.json"
    if coverage.is_file():
        coverage_data = _load_json(coverage)
        if coverage_data.get("status") == "ok":
            actuals = _smp_csv_month_actuals(month_dir, month_key)
            if actuals is not None:
                actuals["status"] = (
                    "VOLLEDIG"
                    if coverage_data.get("available_through") == coverage_data.get("calendar_expected_through")
                    and not coverage_data.get("missing_days")
                    and not coverage_data.get("empty_days")
                    else "PARTIEEL"
                )
                return actuals
    return _smp_csv_month_actuals(month_dir, month_key)


def _month_tuple(month_key: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{4})_(0[1-9]|1[0-2])", str(month_key))
    if not match:
        raise ValueError(f"Ongeldige maandcode: {month_key!r}")
    return int(match.group(1)), int(match.group(2))


def periods_for_publish(
    project_root: Path,
    month_key: str,
    *,
    include_partial_current: bool,
) -> tuple[list[dict[str, Any]], str | None]:
    """Bouw de historische perioden door alle gevalideerde projectmaanden t/m target te hergebruiken."""
    seed = load_seed()
    periods = list(seed["periods"])
    target_tuple = _month_tuple(month_key)
    latest_seed_start = max(_parse_iso_date(item["from"]) for item in periods)
    floor_tuple = (latest_seed_start.year, latest_seed_start.month)
    input_root = project_root / "Data" / "01_Input"
    target_status: str | None = None

    month_keys: list[str] = []
    if input_root.is_dir():
        for child in input_root.iterdir():
            if not child.is_dir() or not re.fullmatch(r"\d{4}_(0[1-9]|1[0-2])", child.name):
                continue
            key_tuple = _month_tuple(child.name)
            if floor_tuple <= key_tuple <= target_tuple:
                month_keys.append(child.name)

    # De targetmaand moet ook beoordeeld worden als hij alleen in de seed bestaat.
    if month_key not in month_keys:
        month_keys.append(month_key)

    for key in sorted(set(month_keys), key=_month_tuple):
        actuals = read_project_month_actuals(project_root, key)
        if actuals is None:
            continue
        status = str(actuals.get("status") or "PARTIEEL").upper()
        key_tuple = _month_tuple(key)
        if key_tuple < target_tuple and status != "VOLLEDIG":
            # Een oudere onvolledige maand wordt nooit duurzaam in de historie opgenomen.
            continue
        if key_tuple == target_tuple:
            target_status = status
            if status == "PARTIEEL" and not include_partial_current:
                continue
        periods = merge_periods(periods, [_actuals_to_period(actuals)])

    if target_status is None:
        year, month = target_tuple
        matching = [
            item for item in periods
            if _parse_iso_date(item["from"]).year == year
            and _parse_iso_date(item["from"]).month == month
        ]
        if matching:
            target_status = (
                "VOLLEDIG"
                if all(str(item.get("status") or "").upper() == "VOLLEDIG" for item in matching)
                else "PARTIEEL"
            )

    return periods, target_status


def _actuals_to_period(actuals: dict[str, Any]) -> dict[str, Any]:
    start = _parse_iso_date(actuals["period_start"])
    end = _parse_iso_date(actuals["period_end"])
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "days": (end - start).days + 1,
        "import_kwh": actuals.get("import_kwh"),
        "export_kwh": actuals.get("export_kwh"),
        "net_kwh": actuals.get("net_kwh"),
        "gas_m3": actuals.get("gas_m3"),
        "airco_kwh": actuals.get("airco_kwh"),
        "extra_pv_kwh": actuals.get("extra_pv_kwh"),
        "source_type": actuals.get("source_type") or ("SlimmeMeterPortal" if actuals.get("status") == "VOLLEDIG" else "Home Assistant/P1"),
        "status": str(actuals.get("status") or "PARTIEEL").upper(),
        "source": actuals.get("source") or "project month actuals",
    }


def merge_periods(base_periods: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = deepcopy(base_periods)
    for candidate in incoming:
        c_start = _parse_iso_date(candidate["from"])
        c_end = _parse_iso_date(candidate["to"])
        same_month = [
            item for item in merged
            if _parse_iso_date(item["from"]).year == c_start.year
            and _parse_iso_date(item["from"]).month == c_start.month
        ]
        full_existing = [item for item in same_month if str(item.get("status") or "").upper() == "VOLLEDIG"]
        candidate_full = str(candidate.get("status") or "").upper() == "VOLLEDIG"
        if full_existing and not candidate_full:
            continue
        if full_existing and candidate_full:
            existing = full_existing[0]
            numeric_keys = ("import_kwh", "export_kwh", "net_kwh", "gas_m3")
            if all(
                existing.get(key) is None or candidate.get(key) is None
                or abs(float(existing[key]) - float(candidate[key])) < 0.02
                for key in numeric_keys
            ):
                # Preserve audited existing full actuals when equivalent.
                continue
            raise ValueError(f"Volledige historische actual wijkt af voor {c_start:%Y-%m}; handmatige bronreview vereist.")
        merged = [item for item in merged if item not in same_month]
        merged.append(deepcopy(candidate))
    merged.sort(key=lambda item: (_parse_iso_date(item["from"]), _parse_iso_date(item["to"])))
    _validate_period_dates(merged)
    return merged


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sheet_names_from_xlsx(zf: zipfile.ZipFile) -> list[str]:
    root = ET.fromstring(zf.read("xl/workbook.xml"))
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    return [node.attrib["name"] for node in root.findall("x:sheets/x:sheet", ns)]


def validate_xlsx(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    formula_count = 0
    external_link_count = 0
    vba_present = False
    has_2008_date = False
    sheet_names: list[str] = []
    try:
        with zipfile.ZipFile(path, "r") as zf:
            bad = zf.testzip()
            if bad:
                errors.append(f"ZIP CRC fout: {bad}")
            names = set(zf.namelist())
            sheet_names = _sheet_names_from_xlsx(zf)
            if sheet_names != SHEET_NAMES:
                errors.append(f"Onverwachte sheetset: {sheet_names}")
            external_link_count = sum(1 for name in names if name.startswith("xl/externalLinks/"))
            vba_present = "xl/vbaProject.bin" in names
            for name in names:
                if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                    text = zf.read(name).decode("utf-8", errors="replace")
                    formula_count += len(re.findall(r"<f(?:\s|>)", text))
                    if "2008-" in text or "31-10-2008" in text:
                        has_2008_date = True
            if "xl/sharedStrings.xml" in names:
                text = zf.read("xl/sharedStrings.xml").decode("utf-8", errors="replace")
                if "2008-" in text or "31-10-2008" in text:
                    has_2008_date = True
    except Exception as exc:
        errors.append(f"XLSX lezen mislukt: {type(exc).__name__}: {exc}")
    if formula_count:
        errors.append(f"Werkbladformules niet toegestaan: {formula_count}")
    if external_link_count:
        errors.append(f"Externe links niet toegestaan: {external_link_count}")
    if vba_present:
        errors.append("VBA-project niet toegestaan")
    if has_2008_date:
        errors.append("2008-datumregressie gedetecteerd")
    return {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "sheet_names": sheet_names,
        "formula_count": formula_count,
        "external_link_count": external_link_count,
        "vba_present": vba_present,
        "has_2008_date": has_2008_date,
    }


def _formats(workbook: xlsxwriter.Workbook) -> dict[str, Any]:
    return {
        "title": workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#1F4E78", "font_size": 18, "valign": "vcenter"}),
        "subtitle": workbook.add_format({"italic": True, "font_color": "#1F2937", "bg_color": "#F3F6F9", "text_wrap": True, "valign": "vcenter"}),
        "header": workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#5B9BD5", "align": "center", "valign": "vcenter", "text_wrap": True}),
        "note": workbook.add_format({"bold": True, "font_color": "#1F2937", "bg_color": "#E2F0D9", "text_wrap": True, "valign": "vcenter"}),
        "warn": workbook.add_format({"font_color": "#1F2937", "bg_color": "#FFF2CC", "text_wrap": True}),
        "text": workbook.add_format({"font_color": "#1F2937", "valign": "vcenter"}),
        "wrap": workbook.add_format({"font_color": "#1F2937", "text_wrap": True, "valign": "vcenter"}),
        "num": workbook.add_format({"num_format": "0.00", "font_color": "#1F2937"}),
        "date": workbook.add_format({"num_format": "dd-mm-yyyy", "font_color": "#1F2937"}),
        "datetime": workbook.add_format({"num_format": "dd-mm-yyyy hh:mm", "font_color": "#1F2937"}),
        "full": workbook.add_format({"bg_color": "#E2F0D9", "font_color": "#1F2937"}),
        "partial": workbook.add_format({"bg_color": "#FFF2CC", "font_color": "#1F2937"}),
        "card_head": workbook.add_format({"bold": True, "font_color": "#1F2937", "bg_color": "#D9EAF7", "align": "center", "valign": "vcenter", "text_wrap": True}),
        "card_value": workbook.add_format({"bold": True, "font_color": "#1F2937", "font_size": 16, "align": "center", "valign": "vcenter"}),
    }


def _write_title(ws: Any, formats: dict[str, Any], title: str, subtitle: str, end_col: int) -> None:
    ws.merge_range(0, 0, 0, end_col, title, formats["title"])
    ws.merge_range(1, 0, 1, end_col, subtitle, formats["subtitle"])
    ws.set_row(0, 30)
    ws.set_row(1, 30)


def _write_headers(ws: Any, row: int, headers: list[str], formats: dict[str, Any]) -> None:
    for col, value in enumerate(headers):
        ws.write(row, col, value, formats["header"])
    ws.set_row(row, 28)


def _write_value(ws: Any, row: int, col: int, value: Any, formats: dict[str, Any], *, wrap: bool = False) -> None:
    if value is None:
        ws.write_blank(row, col, None, formats["text"])
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        ws.write_number(row, col, float(value), formats["num"])
    elif isinstance(value, datetime):
        ws.write_datetime(row, col, value, formats["datetime"])
    else:
        ws.write(row, col, str(value), formats["wrap"] if wrap else formats["text"])


def _seed_metadata() -> dict[str, Any]:
    return load_seed()


def build_historical_energy_workbook(
    project_root: Path,
    month_key: str,
    *,
    periods: list[dict[str, Any]],
    output_path: Path,
) -> dict[str, Any]:
    del project_root
    _validate_period_dates(periods)
    seed = _seed_metadata()
    calendar_rows = build_calendar_year_rows(periods)
    calmap = {row["year"]: row for row in calendar_rows}
    comparison = build_equal_month_comparison(periods, 2026, years_back=3)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(output_path), {"constant_memory": False})
    workbook.set_properties({"title": "Energieverbruik historie", "subject": "Kalenderjaar en historische energieactuals"})
    fmt = _formats(workbook)

    # Dashboard
    ws = workbook.add_worksheet("Dashboard")
    _write_title(ws, fmt, "Energiedashboard – kalenderjaren", "Kalenderjaar is de primaire vergelijkingsbasis. PARTIEEL is nooit een volledig jaar; contract- en leveranciersperioden staan apart.", 13)
    _write_headers(ws, 3, ["Dekking", "Waarde", "Status"], fmt)
    info = [
        ["Historische reeks", "vanaf nov 2009", "aanwezig"],
        ["Afname/terug apart", "vanaf 2013", "waar bron dit ondersteunt"],
        ["Laatste volledig kalenderjaar", "2025", "VOLLEDIG"],
        ["Actueel jaar", str(max(calmap)), calmap[max(calmap)]["status"]],
    ]
    for r_idx, row in enumerate(info, 4):
        for c_idx, value in enumerate(row):
            _write_value(ws, r_idx, c_idx, value, fmt, wrap=True)
    y2025 = calmap.get(2025, {})
    for start_col, label, value in [
        (4, "2025 KALENDERJAAR – AFNAME", y2025.get("import_kwh")),
        (7, "2025 KALENDERJAAR – TERUG", y2025.get("export_kwh")),
        (10, "2025 KALENDERJAAR – GAS", y2025.get("gas_m3")),
    ]:
        ws.merge_range(3, start_col, 3, start_col + 2, label, fmt["card_head"])
        unit = "m³" if "GAS" in label else "kWh"
        text = "—" if value is None else f"{value:,.0f} {unit}".replace(",", ".")
        ws.merge_range(4, start_col, 5, start_col + 2, text, fmt["card_value"])
    ws.merge_range(9, 0, 10, 13, "Alle jaarvergelijkingen in de dashboards gebruiken kalenderjaren. PARTIELE jaren worden niet als volledig jaar voorgesteld.", fmt["note"])
    dash_headers = ["Kalenderjaar", "Dekking", "Status", "Afname kWh", "Teruglevering kWh", "Netto kWh", "Gas m³", "Leverancier(s)"]
    _write_headers(ws, 13, dash_headers, fmt)
    for r_idx, row in enumerate(calendar_rows, 14):
        values = [row["year"], row["coverage"], row["status"], row["import_kwh"], row["export_kwh"], row["net_kwh"], row["gas_m3"], row["supplier"]]
        for c_idx, value in enumerate(values):
            cell_fmt = fmt["full"] if c_idx == 2 and row["status"] == "VOLLEDIG" else fmt["partial"] if c_idx == 2 else None
            if cell_fmt:
                ws.write(r_idx, c_idx, value, cell_fmt)
            else:
                _write_value(ws, r_idx, c_idx, value, fmt, wrap=c_idx in {1,7})
    ws.set_column("A:A", 13); ws.set_column("B:B", 31); ws.set_column("C:C", 14); ws.set_column("D:G", 15); ws.set_column("H:H", 36)
    ws.freeze_panes(14, 0)
    full_chart_rows = [row for row in calendar_rows if row["status"] == "VOLLEDIG" and row["import_kwh"] is not None and row["export_kwh"] is not None]
    helper_row = 34
    _write_headers(ws, helper_row, ["Jaar", "Afname", "Terug"], fmt)
    for idx, row in enumerate(full_chart_rows, helper_row + 1):
        ws.write_number(idx, 9, row["year"]); ws.write_number(idx, 10, row["import_kwh"]); ws.write_number(idx, 11, row["export_kwh"])
    chart = workbook.add_chart({"type": "column"})
    first, last = helper_row + 2, helper_row + 1 + len(full_chart_rows)
    chart.add_series({"name": "Afname kWh", "categories": f"='Dashboard'!$J${first}:$J${last}", "values": f"='Dashboard'!$K${first}:$K${last}"})
    chart.add_series({"name": "Teruglevering kWh", "categories": f"='Dashboard'!$J${first}:$J${last}", "values": f"='Dashboard'!$L${first}:$L${last}"})
    chart.set_title({"name": "Afname en teruglevering – volledige kalenderjaren"}); chart.set_legend({"position": "bottom"})
    ws.insert_chart("J14", chart, {"x_scale": 1.12, "y_scale": 1.0})

    # Dashboard 2026
    ws = workbook.add_worksheet("Dashboard 2026")
    current_year = 2026
    ycur = calmap.get(current_year, {})
    _write_title(ws, fmt, "Dashboard kalenderjaar 2026 – lopend", "Januari t/m juli zijn volledige kalendermaanden in de historische basis. Een later lopend deel van augustus blijft PARTIEEL.", 13)
    cards = [
        (0, "AFNAME YTD", ycur.get("import_kwh"), "kWh"),
        (3, "TERUG YTD", ycur.get("export_kwh"), "kWh"),
        (6, "NETTO YTD", ycur.get("net_kwh"), "kWh"),
        (9, "GAS YTD", ycur.get("gas_m3"), "m³"),
    ]
    for col, label, value, unit in cards:
        ws.merge_range(3, col, 3, col + 1, label, fmt["card_head"])
        text = "—" if value is None else f"{value:,.1f} {unit}".replace(",", "X").replace(".", ",").replace("X", ".")
        ws.merge_range(4, col, 5, col + 1, text, fmt["card_value"])
    ws.merge_range(7, 0, 7, 1, "AIRCO t/m brondekking", fmt["card_head"]); ws.merge_range(8,0,9,1, "—" if ycur.get("airco_kwh") is None else f"{ycur['airco_kwh']:.0f} kWh", fmt["card_value"])
    ws.merge_range(7, 3, 7, 4, "EXTRA PV t/m brondekking", fmt["card_head"]); ws.merge_range(8,3,9,4, "—" if ycur.get("extra_pv_kwh") is None else f"{ycur['extra_pv_kwh']:.0f} kWh", fmt["card_value"])
    ws.merge_range(11, 0, 12, 13, "Kalenderbasis: volledige maanden worden als VOLLEDIG getoond; een lopende maand blijft PARTIEEL en telt niet mee in de gelijke-maandenvergelijking.", fmt["note"])
    _write_headers(ws, 15, ["Maand", "Afname kWh", "Teruglevering kWh", "Netto kWh", "Gas m³", "Dekking", "Status"], fmt)
    current_rows = _year_periods(periods, current_year)
    for idx, month in enumerate(range(1, 13), 16):
        rows = [row for row in current_rows if _parse_iso_date(row["from"]).month == month]
        if not rows:
            continue
        status = "VOLLEDIG" if all(str(row.get("status")).upper() == "VOLLEDIG" for row in rows) else "PARTIEEL"
        start = min(_parse_iso_date(row["from"]) for row in rows); end = max(_parse_iso_date(row["to"]) for row in rows)
        label = calendar.month_abbr[month].capitalize()
        values = [label, _sum_numeric(rows,"import_kwh"), _sum_numeric(rows,"export_kwh"), _sum_numeric(rows,"net_kwh"), _sum_numeric(rows,"gas_m3"), "hele maand" if status == "VOLLEDIG" else f"{start.day}–{end.day} {label.lower()}", status]
        for c_idx, value in enumerate(values):
            cell_fmt = fmt["full"] if c_idx == 6 and status == "VOLLEDIG" else fmt["partial"] if c_idx == 6 else None
            if cell_fmt: ws.write(idx, c_idx, value, cell_fmt)
            else: _write_value(ws, idx, c_idx, value, fmt)
    ws.set_column("A:A", 12); ws.set_column("B:E", 16); ws.set_column("F:F", 18); ws.set_column("G:G", 14)
    chart = workbook.add_chart({"type": "column"})
    chart.add_series({"name": "Afname kWh", "categories": "='Dashboard 2026'!$A$17:$A$23", "values": "='Dashboard 2026'!$B$17:$B$23"})
    chart.add_series({"name": "Teruglevering kWh", "categories": "='Dashboard 2026'!$A$17:$A$23", "values": "='Dashboard 2026'!$C$17:$C$23"})
    chart.set_title({"name": "2026 afname / teruglevering – volledige maanden"}); chart.set_legend({"position":"bottom"})
    ws.insert_chart("I16", chart)

    # 2026 vs 3 jaar
    ws = workbook.add_worksheet("2026 vs 3 jaar")
    through = comparison["through_month"]
    month_label = calendar.month_name[through].lower() if through else "geen volledige maand"
    _write_title(ws, fmt, "2026 versus de drie voorgaande kalenderjaren", f"Eerlijke vergelijking: voor alle vier jaren exact dezelfde volledig afgesloten kalendermaanden, januari t/m {month_label}.", 13)
    _write_headers(ws, 3, ["Kalenderjaar", "Vergelijkingsperiode", "Status", "Afname kWh", "Teruglevering kWh", "Netto kWh", "Gas m³"], fmt)
    for r_idx, row in enumerate(comparison["years"], 4):
        values=[row["year"],row["period"],row["status"],row["import_kwh"],row["export_kwh"],row["net_kwh"],row["gas_m3"]]
        for c_idx,value in enumerate(values): _write_value(ws,r_idx,c_idx,value,fmt,wrap=c_idx in {1,2})
    ws.merge_range(9,0,10,6,f"Vergelijking stopt na {calendar.month_name[through]} zolang de volgende kalendermaand niet volledig is.",fmt["note"])
    _write_headers(ws,13,["Maand",2023,2024,2025,2026],fmt)
    for r_idx,row in enumerate(comparison["monthly_net"],14):
        vals=[calendar.month_abbr[row["month"]].capitalize()]+[row[y] for y in (2023,2024,2025,2026)]
        for c_idx,value in enumerate(vals): _write_value(ws,r_idx,c_idx,value,fmt)
    _write_headers(ws,24,["Maand",2023,2024,2025,2026],fmt)
    for r_idx,row in enumerate(comparison["monthly_gas"],25):
        vals=[calendar.month_abbr[row["month"]].capitalize()]+[row[y] for y in (2023,2024,2025,2026)]
        for c_idx,value in enumerate(vals): _write_value(ws,r_idx,c_idx,value,fmt)
    chart=workbook.add_chart({"type":"column"})
    chart.add_series({"name":"Afname kWh","categories":"='2026 vs 3 jaar'!$A$5:$A$8","values":"='2026 vs 3 jaar'!$D$5:$D$8"})
    chart.add_series({"name":"Teruglevering kWh","categories":"='2026 vs 3 jaar'!$A$5:$A$8","values":"='2026 vs 3 jaar'!$E$5:$E$8"})
    chart.set_title({"name":f"Jan–{calendar.month_abbr[through]}: afname en teruglevering"}); chart.set_legend({"position":"bottom"})
    ws.insert_chart("I4",chart)
    line=workbook.add_chart({"type":"line"})
    for col,year in zip("BCDE",(2023,2024,2025,2026)):
        line.add_series({"name":str(year),"categories":f"='2026 vs 3 jaar'!$A$15:$A${14+through}","values":f"='2026 vs 3 jaar'!${col}$15:${col}${14+through}"})
    line.set_title({"name":"Netto elektriciteit per maand"}); line.set_legend({"position":"bottom"}); ws.insert_chart("G14",line)

    # Jaaroverzicht and Kalenderjaren
    for sheet_name, detailed in (("Jaaroverzicht", False),("Kalenderjaren",True)):
        ws=workbook.add_worksheet(sheet_name)
        subtitle = "Kalenderjaar is de hoofdindeling. PARTIEEL is geen heel jaar; contract-/afrekenperioden staan op Contractjaren."
        _write_title(ws,fmt,f"{sheet_name} – kalenderjaren",subtitle,11 if not detailed else 10)
        headers=["Kalenderjaar","Dekking","Status","Leverancier(s)","Afname kWh","Teruglevering kWh","Netto kWh","Gas m³","Airco kWh","Extra PV kWh","Bron"]
        if not detailed: headers.append("Opmerking")
        _write_headers(ws,3,headers,fmt)
        for r_idx,row in enumerate(calendar_rows,4):
            source="Maanddetail"
            note_text=""
            if row["year"]<=2016: source="Oude maandmeterreeks"
            elif row["year"] in (2023,2024,2025): source="Energie(5).xlsx / Maanddetail"
            elif row["year"]==2026: source="Energie(5).xlsx + SMP/HA"
            values=[row["year"],row["coverage"],row["status"],row["supplier"],row["import_kwh"],row["export_kwh"],row["net_kwh"],row["gas_m3"],row["airco_kwh"],row["extra_pv_kwh"],source]
            if not detailed:
                if row["year"]<=2012: note_text="Elektriciteit alleen netto beschikbaar."
                if row["year"]==2026: note_text="Lopend kalenderjaar; apparaatvelden volgen hun beschikbare brondekking."
                values.append(note_text)
            for c_idx,value in enumerate(values):
                cell_fmt=fmt["full"] if c_idx==2 and row["status"]=="VOLLEDIG" else fmt["partial"] if c_idx==2 else None
                if cell_fmt: ws.write(r_idx,c_idx,value,cell_fmt)
                else: _write_value(ws,r_idx,c_idx,value,fmt,wrap=c_idx in {1,3,10,11})
        ws.set_column("A:A",13);ws.set_column("B:B",31);ws.set_column("C:C",14);ws.set_column("D:D",36);ws.set_column("E:J",15);ws.set_column("K:K",38)
        if not detailed: ws.set_column("L:L",48)
        ws.freeze_panes(4,0)

    # Maanddetail
    ws=workbook.add_worksheet("Maanddetail")
    _write_title(ws,fmt,"Maand- en meetperiodedetail","Elke regel heeft een expliciete Van/Tot-periode. Juli 2026 is een volledige SMP-maand; lopende maanden blijven PARTIEEL.",11)
    headers=["Periode van","Periode t/m","Dagen","Afname kWh","Teruglevering kWh","Netto kWh","Gas m³","Airco kWh","Extra PV kWh","Bronsoort","Status","Bron"]
    _write_headers(ws,3,headers,fmt)
    for r_idx,row in enumerate(sorted(periods,key=lambda p:(_parse_iso_date(p["from"]),_parse_iso_date(p["to"]))),4):
        start=datetime.combine(_parse_iso_date(row["from"]),datetime.min.time()); end=datetime.combine(_parse_iso_date(row["to"]),datetime.min.time())
        ws.write_datetime(r_idx,0,start,fmt["date"]); ws.write_datetime(r_idx,1,end,fmt["date"])
        vals=[row.get("days"),row.get("import_kwh"),row.get("export_kwh"),row.get("net_kwh"),row.get("gas_m3"),row.get("airco_kwh"),row.get("extra_pv_kwh"),row.get("source_type"),row.get("status"),row.get("source")]
        for c_idx,value in enumerate(vals,2):
            cell_fmt=fmt["full"] if c_idx==10 and row.get("status")=="VOLLEDIG" else fmt["partial"] if c_idx==10 else None
            if cell_fmt: ws.write(r_idx,c_idx,value,cell_fmt)
            else: _write_value(ws,r_idx,c_idx,value,fmt,wrap=c_idx in {9,11})
    ws.set_column("A:B",15);ws.set_column("C:C",9);ws.set_column("D:I",15);ws.set_column("J:K",19);ws.set_column("L:L",58);ws.freeze_panes(4,0)

    # Contractjaren
    ws=workbook.add_worksheet("Contractjaren")
    _write_title(ws,fmt,"Contractjaren / afrekenperioden – géén kalenderjaren","Alleen voor jaarnota’s, leverancierswissels, contractperiodes en kostencontrole.",10)
    headers=["Periode","Van","Tot","Leverancier","Afname kWh","Teruglevering kWh","Netto kWh","Gas m³","Kwaliteit","Bronsoort","Opmerking"]
    _write_headers(ws,3,headers,fmt)
    for r_idx,row in enumerate(seed.get("contract_periods") or [],4):
        vals=[row.get("period"),row.get("from"),row.get("to"),row.get("supplier"),row.get("import_kwh"),row.get("export_kwh"),row.get("net_kwh"),row.get("gas_m3"),row.get("quality"),row.get("source_type"),row.get("note")]
        for c_idx,value in enumerate(vals): _write_value(ws,r_idx,c_idx,value,fmt,wrap=c_idx in {8,9,10})
    ws.set_column("A:A",13);ws.set_column("B:C",17);ws.set_column("D:D",20);ws.set_column("E:H",16);ws.set_column("I:I",25);ws.set_column("J:J",30);ws.set_column("K:K",48);ws.freeze_panes(4,0)

    # Zonnepanelen
    ws=workbook.add_worksheet("Zonnepanelen")
    _write_title(ws,fmt,"Zonnepanelen – opwek per expliciete periode","Opwek is niet hetzelfde als net-teruglevering. Alleen regels met volledig kalenderjaar mogen als jaaractual worden gelezen.",5)
    _write_headers(ws,3,["Periode","Opwek kWh","Set","Status","Bron","Volledig kalenderjaar?"],fmt)
    for r_idx,row in enumerate(seed.get("solar_periods") or [],4):
        vals=[row.get("period"),row.get("production_kwh"),row.get("set"),row.get("status"),row.get("source"),"JA" if row.get("full_calendar_year") else "NEE"]
        for c_idx,value in enumerate(vals): _write_value(ws,r_idx,c_idx,value,fmt,wrap=c_idx in {0,2,3,4})
    ws.set_column("A:A",29);ws.set_column("B:B",15);ws.set_column("C:D",24);ws.set_column("E:E",36);ws.set_column("F:F",20)

    # Apparaatmetingen
    ws=workbook.add_worksheet("Apparaatmetingen")
    _write_title(ws,fmt,"Apparaatmetingen – meetperiodes, geen jaaractuals","Start en Einde bepalen de echte meetperiode. Jaarindicatie is alleen een extrapolatie van een proefmeting.",8)
    _write_headers(ws,3,["Apparaat","Meetpunt","Locatie","Start","Einde","Gemeten kWh","Jaarindicatie kWh","Opmerking","Type bron"],fmt)
    for r_idx,row in enumerate(seed.get("device_periods") or [],4):
        starts=row.get("start"); ends=row.get("end")
        vals=[row.get("device"),row.get("measurement_point"),row.get("location"),starts,ends,row.get("measured_kwh"),row.get("annualized_kwh"),row.get("note"),row.get("source_type")]
        for c_idx,value in enumerate(vals):
            if c_idx in {3,4} and value:
                try: ws.write_datetime(r_idx,c_idx,datetime.fromisoformat(str(value)),fmt["datetime"])
                except ValueError: _write_value(ws,r_idx,c_idx,value,fmt)
            else: _write_value(ws,r_idx,c_idx,value,fmt,wrap=c_idx in {0,1,7,8})
    ws.set_column("A:A",30);ws.set_column("B:B",33);ws.set_column("C:C",17);ws.set_column("D:E",19);ws.set_column("F:G",18);ws.set_column("H:H",55);ws.set_column("I:I",30)

    # Bronnen
    ws=workbook.add_worksheet("Bronnen")
    _write_title(ws,fmt,"Bronnen en datakwaliteit","Een jaartal in een bronnaam betekent niet automatisch kalenderjaar. Alleen complete dekking krijgt VOLLEDIG.",6)
    _write_headers(ws,3,["Periode","Bron","Datumcontrole","Type","Kwaliteit","Gebruik","Classificatie"],fmt)
    for r_idx,row in enumerate(seed.get("sources") or [],4):
        vals=[row.get("period"),row.get("source"),row.get("date_check"),row.get("type"),row.get("quality"),row.get("usage"),row.get("classification")]
        for c_idx,value in enumerate(vals): _write_value(ws,r_idx,c_idx,value,fmt,wrap=True)
    ws.set_column("A:A",18);ws.set_column("B:B",43);ws.set_column("C:C",18);ws.set_column("D:E",21);ws.set_column("F:F",58);ws.set_column("G:G",20)

    # Onderhoud
    ws=workbook.add_worksheet("Onderhoud")
    _write_title(ws,fmt,"Onderhoudsinstructie masterbestand","Vaste regels voor toekomstige updates. Workbook wordt telkens schoon vanaf nul opgebouwd.",1)
    _write_headers(ws,3,["Regel","Instructie"],fmt)
    rules=[
        ("Primaire jaarbasis","Dashboard, Jaaroverzicht en vergelijkingen gebruiken kalenderjaar; contractjaren blijven apart."),
        ("VOLLEDIG/PARTIEEL","VOLLEDIG alleen bij aantoonbare complete kalenderdekking. Anders exacte dekking + PARTIEEL."),
        ("Vergelijkingsregel","2026 vs 3 jaar gebruikt alleen dezelfde volledig afgesloten kalendermaanden voor alle jaren."),
        ("Maanddetail","Nieuwe gevalideerde maandactuals worden eerst als periodedetail toegevoegd; daarna worden dashboards opnieuw opgebouwd."),
        ("Datumcontrole","De bedoelde brondatum blijft exact behouden. Een datum vóór 01-11-2009 wordt geblokkeerd tenzij later met nieuwe primaire bron bewezen."),
        ("Geen dubbeltelling","Overlappende bronnen worden niet opgeteld; best gevalideerde bron voor dezelfde periode is leidend."),
        ("Geen schattingen","Prognoses, offertes, fabrikantwaarden en jaar-extrapolaties worden nooit als actual opgeslagen."),
        ("Numbers-compatibiliteit","Schone XLSX met waarden, standaardopmaak en eenvoudige grafieken; geen macro’s, PowerQuery of werkbladformules."),
        ("Corruptiepreventie","Nooit een bestaand masterbestand patchen/re-exporteren. Iedere run bouwt een nieuw tijdelijk workbook en publiceert pas na validatie atomair."),
    ]
    for r_idx,(rule,text) in enumerate(rules,4):
        ws.write(r_idx,0,rule,fmt["card_head"]);ws.write(r_idx,1,text,fmt["wrap"])
    ws.set_column("A:A",30);ws.set_column("B:B",100);ws.freeze_panes(4,0)

    workbook.close()
    validation = validate_xlsx(output_path)
    if validation["status"] != "ok":
        raise RuntimeError("XLSX-validatie mislukt: " + "; ".join(validation["errors"]))
    return {"status":"ok","path":str(output_path),"month":month_key,"validation":validation}


def latest_complete_month_key(project_root: Path) -> str:
    """Return the newest fully validated calendar month available to the project."""
    candidates: set[tuple[int, int]] = set()

    for item in load_seed()["periods"]:
        if str(item.get("status") or "").upper() != "VOLLEDIG":
            continue
        start = _parse_iso_date(item["from"])
        candidates.add((start.year, start.month))

    input_root = project_root / "Data" / "01_Input"
    if input_root.is_dir():
        for child in input_root.iterdir():
            if not child.is_dir() or not re.fullmatch(r"\d{4}_(0[1-9]|1[0-2])", child.name):
                continue
            actuals = read_project_month_actuals(project_root, child.name)
            if actuals is None:
                continue
            if str(actuals.get("status") or "").upper() == "VOLLEDIG":
                candidates.add(_month_tuple(child.name))

    if not candidates:
        raise RuntimeError("Geen volledig gevalideerde maand beschikbaar voor Energiehistorie-bootstrap.")
    year, month = max(candidates)
    return f"{year:04d}_{month:02d}"


def _build_missing_archive_without_replacing_master(project_root: Path, month_key: str) -> dict[str, Any]:
    reports = project_root / MASTER_RELATIVE.parent
    archive_root = project_root / ARCHIVE_RELATIVE
    archive_root.mkdir(parents=True, exist_ok=True)
    periods, target_status = periods_for_publish(project_root, month_key, include_partial_current=False)
    if target_status != "VOLLEDIG":
        raise RuntimeError(f"Bootstrap-archief vereist VOLLEDIG, gevonden: {target_status}")
    archive_path = archive_root / f"Energie_verbruik_historie_{month_key}.xlsx"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{archive_path.stem}.", suffix=".xlsx", dir=archive_root)
    os.close(fd)
    temp_path = Path(tmp_name)
    try:
        build_historical_energy_workbook(project_root, month_key, periods=periods, output_path=temp_path)
        validation = validate_xlsx(temp_path)
        if validation.get("status") != "ok":
            raise RuntimeError("XLSX-validatie mislukt: " + "; ".join(validation.get("errors") or []))
        temp_path.replace(archive_path)
        return {
            "status": "completed_archive_only",
            "month": month_key,
            "archive": str(archive_path),
            "archive_sha256": _hash_file(archive_path),
            "master_preserved": True,
        }
    finally:
        temp_path.unlink(missing_ok=True)


def bootstrap_historical_energy_workbook(project_root: Path) -> dict[str, Any]:
    """Ensure the first master and latest complete-month archive exist after app startup."""
    month_key = latest_complete_month_key(project_root)
    master = project_root / MASTER_RELATIVE
    archive = project_root / ARCHIVE_RELATIVE / f"Energie_verbruik_historie_{month_key}.xlsx"

    master_ok = master.is_file() and validate_xlsx(master).get("status") == "ok"
    archive_ok = archive.is_file() and validate_xlsx(archive).get("status") == "ok"
    if master_ok and archive_ok:
        return {
            "status": "skipped_existing",
            "month": month_key,
            "master": str(master),
            "archive": str(archive),
        }

    if not master_ok:
        result = publish_historical_energy_workbook(
            project_root,
            month_key,
            include_partial_current=False,
        )
        result = dict(result)
        result["bootstrap"] = True
        return result

    result = _build_missing_archive_without_replacing_master(project_root, month_key)
    result["master"] = str(master)
    result["bootstrap"] = True
    return result


def publish_historical_energy_workbook(
    project_root: Path,
    month_key: str,
    *,
    include_partial_current: bool,
) -> dict[str, Any]:
    periods, target_status = periods_for_publish(
        project_root,
        month_key,
        include_partial_current=include_partial_current,
    )

    reports = project_root / MASTER_RELATIVE.parent
    archive_root = project_root / ARCHIVE_RELATIVE
    reports.mkdir(parents=True, exist_ok=True)
    archive_root.mkdir(parents=True, exist_ok=True)
    master = project_root / MASTER_RELATIVE
    fd, tmp_name = tempfile.mkstemp(prefix=".Energie_verbruik_historie.", suffix=".xlsx", dir=reports)
    os.close(fd)
    temp_path = Path(tmp_name)
    try:
        build_historical_energy_workbook(project_root, month_key, periods=periods, output_path=temp_path)
        validation = validate_xlsx(temp_path)
        if validation.get("status") != "ok":
            raise RuntimeError("XLSX-validatie mislukt: " + "; ".join(validation.get("errors") or []))
        temp_path.replace(master)
        master_sha = _hash_file(master)
        archive_path: Path | None = None
        archive_sha: str | None = None
        archive_status = "skipped_partial"
        if target_status == "VOLLEDIG":
            archive_path = archive_root / f"Energie_verbruik_historie_{month_key}.xlsx"
            archive_tmp = archive_path.with_name(f".{archive_path.name}.tmp")
            shutil.copyfile(master, archive_tmp)
            archive_sha = _hash_file(archive_tmp)
            if archive_sha != master_sha:
                archive_tmp.unlink(missing_ok=True)
                raise RuntimeError("Maandarchief SHA-256 wijkt af van master.")
            archive_tmp.replace(archive_path)
            archive_status = "completed"
        return {
            "status":"completed",
            "month":month_key,
            "target_status":target_status,
            "master":str(master),
            "master_sha256":master_sha,
            "archive":str(archive_path) if archive_path else None,
            "archive_status":archive_status,
            "archive_sha256":archive_sha,
            "period_count":len(periods),
        }
    finally:
        temp_path.unlink(missing_ok=True)
