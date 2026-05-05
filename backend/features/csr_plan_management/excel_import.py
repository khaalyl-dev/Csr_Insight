"""
CSR Consolidated Report Excel import parsing + validation.

Key requirements implemented here:
- Strict header validation (order + header names) for the "Group figures" layout.
- Row-by-row validation: numeric types, required fields, and simple coherence checks.

This module does NOT write to the database.
"""

import re
from typing import Any, Optional

import pandas as pd


# Two accepted Excel templates:
# - With "Year" + "Start year" columns (20 columns total).
# - With "Year" removed: only "Start year" exists (19 columns total).
#
# Excel "Year" is the calendar year of that activity's *edition* (stored as edition_year).
# csr_plans.year is always the plan year chosen by the user in step 1 of the import wizard.

TEMPLATE_WITH_YEAR = {
    "activity_number": 0,
    "region": 1,
    "country": 2,
    "site": 3,  # Plant
    "title": 4,  # Activity Title/ description
    "category": 5,
    "collaboration_nature": 6,
    "edition_year": 7,  # Excel column "Year" — year of the edition; not csr_plans.year
    "start_year": 8,
    "edition": 9,
    "participants": 10,  # Nbr of internal Participants (used for both planned_volunteers and realized participants)
    "total_hc": 11,
    "percentage_employees": 12,
    "planned_budget": 13,  # Estimated Budget in €
    "realized_budget": 14,  # Actual Budget in €
    "impact_actual": 15,  # Action Impact In Numbers (also impact_target for planned)
    "impact_unit": 16,
    "organizer": 17,
    "external_partner": 18,
    "number_external_partners": 19,
}

TEMPLATE_WITHOUT_YEAR = {
    "activity_number": 0,
    "region": 1,
    "country": 2,
    "site": 3,  # Plant
    "title": 4,  # Activity Title/ description
    "category": 5,
    "collaboration_nature": 6,
    # "Year" column removed: we only keep "Start year".
    "start_year": 7,
    "edition": 8,
    "participants": 9,
    "total_hc": 10,
    "percentage_employees": 11,
    "planned_budget": 12,
    "realized_budget": 13,
    "impact_actual": 14,
    "impact_unit": 15,
    "organizer": 16,
    "external_partner": 17,
    "number_external_partners": 18,
}

EXPECTED_HEADERS_RAW_WITH_YEAR = [
    "Activity N",
    "Region",
    "country",
    "Plant",
    "Activity Title/ description",
    "Category",
    "Nature of collaboration",
    "Year",
    "Start year",
    "Edition",
    "Nbr of internal Participants",
    "Total HC",
    "Percentage out of all the employees % ",
    "Estimated Budget in €",
    "Actual Budget in €",
    "Action Impact In Numbers",
    "Action Impact Unit",
    "Organizer",
    "External Partner",
    "Number of External Partners",
]

EXPECTED_HEADERS_RAW_WITHOUT_YEAR = [
    "Activity N",
    "Region",
    "country",
    "Plant",
    "Activity Title/ description",
    "Category",
    "Nature of collaboration",
    "Start year",
    "Edition",
    "Nbr of internal Participants",
    "Total HC",
    "Percentage out of all the employees % ",
    "Estimated Budget in €",
    "Actual Budget in €",
    "Action Impact In Numbers",
    "Action Impact Unit",
    "Organizer",
    "External Partner",
    "Number of External Partners",
]


def _normalize_header(val: Any) -> str:
    """Normalize Excel header cells for strict comparison (trim + whitespace + newlines)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).replace("\n", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s


EXPECTED_HEADERS_WITH_YEAR = [_normalize_header(x) for x in EXPECTED_HEADERS_RAW_WITH_YEAR]
EXPECTED_HEADERS_WITHOUT_YEAR = [_normalize_header(x) for x in EXPECTED_HEADERS_RAW_WITHOUT_YEAR]


def _parse_int_or_error(val: Any) -> tuple[Optional[int], Optional[str]]:
    """Parse integer-ish values; return (value, error_message)."""
    if val is None:
        return None, None
    s = str(val).strip()
    if not s:
        return None, None
    s_l = s.lower()
    if s_l in {"-", "—", "–", "na", "n/a", "null", "none"}:
        return None, None

    # Keep digits and leading sign; allow decimals but later enforce integer.
    s2 = s.replace(",", ".")
    cleaned = re.sub(r"[^0-9.\-]", "", s2)
    if cleaned in ("", "-", ".") or cleaned.count(".") > 1:
        return None, "doit être un nombre entier"
    try:
        f = float(cleaned)
    except (TypeError, ValueError):
        return None, "doit être un nombre entier"

    if abs(f - round(f)) > 1e-9:
        return None, "doit être un nombre entier"
    return int(round(f)), None


def _parse_float_or_error(val: Any) -> tuple[Optional[float], Optional[str]]:
    """Parse float-ish values; return (value, error_message)."""
    if val is None:
        return None, None
    s = str(val).strip()
    if not s:
        return None, None
    s_l = s.lower()
    if s_l in {"-", "—", "–", "na", "n/a", "null", "none"}:
        return None, None

    s2 = s.replace(",", ".")
    cleaned = re.sub(r"[^0-9.\-]", "", s2)
    if cleaned in ("", "-", ".") or cleaned.count(".") > 1:
        return None, "doit être un nombre"
    try:
        return float(cleaned), None
    except (TypeError, ValueError):
        return None, "doit être un nombre"


def _parse_str_required(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    s_l = s.lower()
    if s_l in {"-", "—", "–", "na", "n/a", "null", "none"}:
        return None
    return s


def _validate_row_values(row: dict[str, Any], row_num: int) -> list[str]:
    """
    Validate types/coherence/required values for a parsed row.
    Returns a list of error strings formatted as: "Activity {row_num}: ...".
    """
    errors: list[str] = []

    # activity_number is mandatory (no fallback to title).
    activity_number_raw = row.get("activity_number")
    activity_number = _parse_str_required(activity_number_raw)
    if not activity_number:
        errors.append(f"Activity {row_num}: activity_number manquant")

    # title is mandatory (do not auto-fill).
    title_raw = row.get("title")
    title = _parse_str_required(title_raw)
    if not title:
        errors.append(f"Activity {row_num}: titre manquant")

    # --- Integers ---
    edition, ed_err = _parse_int_or_error(row.get("edition"))
    if row.get("edition") not in (None, "") and ed_err:
        errors.append(f"Activity {row_num}: édition invalide ({ed_err})")

    # Excel "Year" column → edition_year (year of the edition; not csr_plans.year).
    ey_raw = row.get("edition_year")
    if ey_raw in (None, ""):
        ey_raw = row.get("excel_template_year")
    ey, ey_err = _parse_int_or_error(ey_raw)
    if ey_raw not in (None, "") and ey_err:
        errors.append(f"Activity {row_num}: année d'édition invalide ({ey_err})")
    if ey is not None and (ey < 1900 or ey > 2100):
        errors.append(f"Activity {row_num}: année d'édition invalide {ey}")

    # Plan year is chosen in the import UI. edition (ordinal), edition_year, and start_year are separate.
    start_year_raw = row.get("start_year")
    start_year, start_year_err = _parse_int_or_error(start_year_raw)
    if start_year_raw not in (None, "") and start_year_err:
        errors.append(f"Activity {row_num}: start year invalide ({start_year_err})")
    if start_year is not None and (start_year < 1900 or start_year > 2100):
        errors.append(f"Activity {row_num}: start year invalide {start_year}")

    participants, p_err = _parse_int_or_error(row.get("participants"))
    if row.get("participants") not in (None, "") and p_err:
        errors.append(f"Activity {row_num}: participants invalides ({p_err})")

    total_hc, thc_err = _parse_int_or_error(row.get("total_hc"))
    if row.get("total_hc") not in (None, "") and thc_err:
        errors.append(f"Activity {row_num}: total HC invalide ({thc_err})")

    number_external_partners, nep_err = _parse_int_or_error(row.get("number_external_partners"))
    if row.get("number_external_partners") not in (None, "") and nep_err:
        errors.append(f"Activity {row_num}: number external partners invalide ({nep_err})")

    planned_volunteers, pv_err = _parse_int_or_error(row.get("planned_volunteers"))
    if row.get("planned_volunteers") not in (None, "") and pv_err:
        errors.append(f"Activity {row_num}: planned_volunteers invalide ({pv_err})")

    # --- Floats ---
    planned_budget, pb_err = _parse_float_or_error(row.get("planned_budget"))
    if row.get("planned_budget") not in (None, "") and pb_err:
        errors.append(f"Activity {row_num}: planned budget invalide ({pb_err})")
    realized_budget, rb_err = _parse_float_or_error(row.get("realized_budget"))
    if row.get("realized_budget") not in (None, "") and rb_err:
        errors.append(f"Activity {row_num}: realized budget invalide ({rb_err})")

    impact_actual, ia_err = _parse_float_or_error(row.get("impact_actual"))
    if row.get("impact_actual") not in (None, "") and ia_err:
        errors.append(f"Activity {row_num}: impact actual invalide ({ia_err})")
    impact_target, it_err = _parse_float_or_error(row.get("impact_target"))
    if row.get("impact_target") not in (None, "") and it_err:
        errors.append(f"Activity {row_num}: impact target invalide ({it_err})")

    percentage_employees, pe_err = _parse_float_or_error(row.get("percentage_employees"))
    if row.get("percentage_employees") not in (None, "") and pe_err:
        errors.append(f"Activity {row_num}: percentage employees invalide ({pe_err})")
    if percentage_employees is not None and 0 < percentage_employees <= 1:
        # Excel sometimes stores percent as fraction (0.2 => 20%)
        percentage_employees = percentage_employees * 100
    if percentage_employees is not None and not (0 <= percentage_employees <= 100):
        errors.append(f"Activity {row_num}: percentage employees doit être entre 0 et 100")

    return errors


def validate_rows_values(rows: list[dict[str, Any]]) -> list[str]:
    """Validate current preview rows (used by /import-validate-rows)."""
    errors: list[str] = []
    for i, row in enumerate(rows):
        row_num = i + 2  # 2-based (1 header + 1 row index)
        errors.extend(_validate_row_values(row, row_num))
    return errors


def _safe_int(val: Any) -> Optional[int]:
    if val is None or val == "":
        return None
    if isinstance(val, int):
        return val
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _safe_float(val: Any) -> Optional[float]:
    if val is None or val == "" or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(",", ".")
    if not s:
        return None
    try:
        return float(re.sub(r"[^\d.\-]", "", s))
    except (TypeError, ValueError):
        return None


def _safe_str(val: Any, max_len: int = 255) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:max_len] if max_len else s


def _val_to_python(val: Any) -> Any:
    """Convert pandas/Excel value to plain Python (e.g. numpy types)."""
    if val is None:
        return None
    if pd.isna(val):
        return None
    if hasattr(val, "item"):  # numpy scalar
        val = val.item()
    s = str(val).strip().lower()
    if not s or s == "nan":
        return None
    return val


def _rename_consecutive_duplicate_activity_numbers(rows: list[dict[str, Any]]) -> None:
    """
    If the same activity_number appears on consecutive rows, rename the whole run:
      CSR 94, CSR 94 -> CSR 94.1, CSR 94.2
      CSR 94, CSR 94, CSR 94 -> CSR 94.1, CSR 94.2, CSR 94.3
    This prevents accidental duplicate identifiers from merged/filled Excel blocks.
    """
    i = 0
    n = len(rows)
    while i < n:
        raw = rows[i].get("activity_number")
        base = str(raw).strip() if raw is not None else ""
        if not base:
            i += 1
            continue
        j = i + 1
        while j < n:
            nxt = rows[j].get("activity_number")
            nxt_base = str(nxt).strip() if nxt is not None else ""
            if nxt_base.lower() != base.lower():
                break
            j += 1
        run_len = j - i
        if run_len > 1:
            for k in range(i, j):
                rows[k]["activity_number"] = f"{base}.{k - i + 1}"
        i = j


def parse_excel_rows(file_path: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """
    Parse Excel file using pandas DataFrame.

    Returns:
      - rows: list[dict] (keys = internal keys)
      - structure_errors: errors blocking upload (header/order/template mismatch, unreadable file)
      - row_errors: row-by-row validation errors (types, required values, coherence)
    """
    structure_errors: list[str] = []
    row_errors: list[str] = []
    rows: list[dict[str, Any]] = []
    try:
        # Use object dtype so merged/blank cells remain NA for proper forward-fill.
        df = pd.read_excel(file_path, header=0, engine="openpyxl", dtype=object)
        if df.empty or len(df) < 1:
            structure_errors.append("Le fichier doit contenir une ligne d'en-têtes et au moins une ligne de données")
            return rows, structure_errors, row_errors

        actual_headers = [_normalize_header(c) for c in df.columns]

        template_indices: dict[str, int] | None = None
        if actual_headers == EXPECTED_HEADERS_WITH_YEAR:
            template_indices = TEMPLATE_WITH_YEAR
        elif actual_headers == EXPECTED_HEADERS_WITHOUT_YEAR:
            template_indices = TEMPLATE_WITHOUT_YEAR
        else:
            structure_errors.append(
                "Structure Excel inattendue. En-têtes ne correspondent pas au template CSR Consolidated Report (avec ou sans colonne 'Year')."
            )
            # If header mismatch, we cannot safely map indices.
            return rows, structure_errors, row_errors

        # If the template uses merged cells, pandas may yield blanks for subsequent rows.
        # Forward-fill ONLY grouping columns (never activity_number/title/budgets) to avoid duplicating activities.
        keys_to_ffill = ["region", "country", "site", "start_year"]
        for k in keys_to_ffill:
            if k not in template_indices:
                continue
            idx = template_indices[k]
            col = df.iloc[:, idx]
            # In case strings "nan" appear, convert to NA before ffill.
            col = col.replace("nan", pd.NA)  # type: ignore[assignment]
            df.iloc[:, idx] = col.ffill()

        max_col = len(df.columns)

        for r_idx in range(0, len(df)):
            # Skip Excel summary rows: Activity N == "Total" (case-insensitive).
            # These are typically not activities and should never be imported.
            # Requirement: stop parsing when reaching the Total row (ignore anything after).
            act_cell = df.iloc[r_idx, template_indices["activity_number"]] if template_indices["activity_number"] < max_col else None
            if act_cell is not None:
                act_str = str(act_cell).strip().lower()
                if act_str == "total" or act_str.startswith("total "):
                    break

            row_data: dict[str, Any] = {}
            for key, col_idx in template_indices.items():
                if col_idx >= max_col:
                    continue
                val = _val_to_python(df.iloc[r_idx, col_idx])
                if val is None:
                    continue
                s = str(val).strip()
                if not s:
                    continue
                row_data[key] = val

            # planned_volunteers and impact_target use same columns as participants and impact_actual
            if "participants" in row_data and "planned_volunteers" not in row_data:
                row_data["planned_volunteers"] = row_data["participants"]
            if "impact_actual" in row_data and "impact_target" not in row_data:
                row_data["impact_target"] = row_data["impact_actual"]
            # percentage_employees: normalize fraction to percent (0.2 => 20)
            if "percentage_employees" in row_data:
                pe, pe_err = _parse_float_or_error(row_data.get("percentage_employees"))
                if pe_err is None and pe is not None and 0 < pe <= 1:
                    row_data["percentage_employees"] = round(pe * 100, 6)
            # Skip empty rows / lines without an activity identifier.
            if not row_data.get("site"):
                continue
            if not row_data.get("activity_number") and not row_data.get("title"):
                continue

            rows.append(row_data)

            # Validate row values for preview.
            row_num = r_idx + 2  # 2-based excel row (header=1)
            row_errors.extend(_validate_row_values(row_data, row_num))

        # Auto-disambiguate same activity numbers on consecutive lines.
        _rename_consecutive_duplicate_activity_numbers(rows)

    except Exception as e:
        structure_errors.append(f"Erreur lecture Excel: {e}")

    return rows, structure_errors, row_errors


def build_import_result(
    rows: list[dict],
    site_id_override: Optional[str] = None,
    year_override: Optional[int] = None,
) -> dict[str, Any]:
    """
    From parsed rows, build a structure suitable for the API to apply to DB.
    Returns dict with: site_id, year, plan_id, activities_created, realized_created, errors, warnings.
    Does not perform DB writes; the route will use this to get (site_id, year, rows) and then create plan/activities.
    """
    return {
        "site_id_override": site_id_override,
        "year_override": year_override,
        "rows": rows,
    }
