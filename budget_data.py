"""
Fase 1 — Lector del PRESUPUESTO VIGENTE (Adj 2), solo lectura.
Fuente: hoja de Google Sheets de TI. Expone, por línea (CENTRO_COSTO, CUENTA_CONTABLE),
los arreglos mensuales PPTO / COMP / EJEC. NO calcula saldo (eso es Fase 2).
Sin Streamlit: la app inyecta el worksheet con set_vigente_ws(); así es testeable offline.
"""

# 12 meses en orden. Los índices _1.._12 de la hoja mapean a estos.
MONTH_KEYS = list(range(1, 13))
KEY_COLS = ["CENTRO_COSTO", "CUENTA_CONTABLE"]
ATTR_COLS = ["DEPARTAMENTO", "DESCRIPCION_CC", "DESCRIPCION_CT", "PROYECTO", "DIMENSION", "TIPO"]

_VIG_WS = None       # worksheet inyectado por la app
_CACHE = None        # dict cacheado: (cc, cuenta) -> registro


def build_vigente_ws(sa_info: dict, spreadsheet_id: str, worksheet: str):
    """Abre la hoja vigente de TI (solo lectura) con la cuenta de servicio."""
    import gspread
    from google.oauth2.service_account import Credentials
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(dict(sa_info), scopes=scopes)
    sh = gspread.authorize(creds).open_by_key(spreadsheet_id)
    return sh.worksheet(worksheet)


def set_vigente_ws(ws):
    global _VIG_WS, _CACHE
    _VIG_WS = ws
    _CACHE = None  # invalida cache al cambiar de fuente


def _num(v):
    """Convierte celdas a float tolerando '', None, comas de miles y paréntesis negativos."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(",", "").replace(" ", "")
    try:
        x = float(s)
    except ValueError:
        return 0.0
    return -x if neg else x


def _validate_header(header):
    faltan = [c for c in KEY_COLS if c not in header]
    for m in MONTH_KEYS:
        for pref in ("PPTO", "COMP", "EJEC"):
            col = f"{pref}_{m}"
            if col not in header:
                faltan.append(col)
    if faltan:
        raise ValueError(f"La hoja vigente no tiene las columnas esperadas. Faltan: {faltan}")


def load_vigente(force=False):
    """Lee la hoja y arma un dict {(cc,cuenta): registro}. Cacheado por sesión."""
    global _CACHE
    if _CACHE is not None and not force:
        return _CACHE
    if _VIG_WS is None:
        raise RuntimeError("Vigente no inicializado: la app debe llamar set_vigente_ws() primero.")

    records = _VIG_WS.get_all_records()  # usa la fila 1 como cabecera
    if records:
        _validate_header(list(records[0].keys()))

    data = {}
    for row in records:
        cc = str(row.get("CENTRO_COSTO", "")).strip()
        cuenta = str(row.get("CUENTA_CONTABLE", "")).strip()
        if not cc or not cuenta:
            continue
        key = (cc, cuenta)
        rec = data.setdefault(key, {
            "centro_costo": cc, "cuenta": cuenta,
            "ppto": [0.0] * 12, "comp": [0.0] * 12, "ejec": [0.0] * 12,
            "attrs": {a: row.get(a, "") for a in ATTR_COLS if a in row},
        })
        # si (cc,cuenta) se repite, se suman los meses (defensivo; no debería pasar)
        for i, m in enumerate(MONTH_KEYS):
            rec["ppto"][i] += _num(row.get(f"PPTO_{m}"))
            rec["comp"][i] += _num(row.get(f"COMP_{m}"))
            rec["ejec"][i] += _num(row.get(f"EJEC_{m}"))
    _CACHE = data
    return data


# ---- Consultas que usará la app (Fase 2 construye la validación de saldo sobre estas) ----

def get_line(cc, cuenta):
    """Registro de una línea, o None si no existe en el vigente."""
    return load_vigente().get((str(cc).strip(), str(cuenta).strip()))

def line_exists(cc, cuenta):
    return get_line(cc, cuenta) is not None

def monthly(cc, cuenta, campo):
    """Arreglo de 12 valores de 'ppto' | 'comp' | 'ejec' para la línea (ceros si no existe)."""
    rec = get_line(cc, cuenta)
    return list(rec[campo]) if rec else [0.0] * 12

def cumulative_available(cc, cuenta, month_index):
    """
    Saldo ACUMULADO al mes (0-based) = Σ_{m<=month} (PPTO - COMP - EJEC), SOLO con datos del vigente.
    OJO: esto es el saldo del ERP; la Fase 2 le sumará los movimientos de la app aún no aplicados.
    """
    rec = get_line(cc, cuenta)
    if rec is None:
        return 0.0
    total = 0.0
    for i in range(month_index + 1):
        total += rec["ppto"][i] - rec["comp"][i] - rec["ejec"][i]
    return round(total, 2)
