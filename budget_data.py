"""
Fase 1/2a-fix — Lector del PRESUPUESTO VIGENTE (Adj 2), solo lectura.
Llave de línea: (CENTRO_COSTO, CUENTA_CONTABLE, DIMENSION_punteada). La dimensión se
lee directo de la columna DIMENSION del vigente (ya viene punteada). Idioma interno =
punteado; la traducción a numérica (dim_equiv) se usa solo al exportar el Adj 1.
Sin Streamlit: la app inyecta el worksheet con set_vigente_ws(); testeable offline.
"""
import dim_equiv as de

# 12 meses en orden. Los índices _1.._12 de la hoja mapean a estos.
MONTH_KEYS = list(range(1, 13))
# Campos que forman la llave de línea. Configurable: si algún día (CC,cuenta) bastara,
# quitar "DIMENSION" de esta tupla y el resto del pipeline sigue funcionando.
KEY_COLS = ["CENTRO_COSTO", "CUENTA_CONTABLE", "DIMENSION"]
ATTR_COLS = ["DEPARTAMENTO", "DESCRIPCION_CC", "DESCRIPCION_CT", "PROYECTO", "DIMENSION", "TIPO"]

def _mkkey(cc, cuenta, dim):
    """Construye la llave respetando KEY_COLS (con o sin dimensión)."""
    parts = {"CENTRO_COSTO": str(cc).strip(),
             "CUENTA_CONTABLE": str(cuenta).strip(),
             "DIMENSION": str(dim).strip()}
    return tuple(parts[c] for c in KEY_COLS)

_VIG_WS = None       # worksheet inyectado por la app
_CACHE = None        # dict cacheado: (cc, cuenta) -> registro

# --- Catálogo CENTRO_COSTO -> LINEA (pestaña del store) ---
_CAT_WS = None
_CAT_CACHE = None

def set_catalogo_ws(ws):
    global _CAT_WS, _CAT_CACHE
    _CAT_WS = ws
    _CAT_CACHE = None

def load_catalogo(force=False):
    """Dict {CENTRO_COSTO: LINEA} desde la pestaña del store. Cacheado."""
    global _CAT_CACHE
    if _CAT_CACHE is not None and not force:
        return _CAT_CACHE
    if _CAT_WS is None:
        raise RuntimeError("Catálogo no inicializado: la app debe llamar set_catalogo_ws().")
    out = {}
    for row in _CAT_WS.get_all_records():
        cc = str(row.get("CENTRO_COSTO", "")).strip()
        lin = str(row.get("LINEA", "")).strip()
        if lin.endswith(".0"):
            lin = lin[:-2]
        if cc:
            out[cc] = lin
    _CAT_CACHE = out
    return out

def linea_de(cc):
    """LINEA del centro de costo, o None si no está en el catálogo."""
    return load_catalogo().get(str(cc).strip())


# --- Presupuesto ORIGINAL (Adj 1) — base del absoluto para el archivo de carga ---
# Meses como fechas (31/01/2026...), dimensión NUMÉRICA (22) -> se traduce a punteada.
_ADJ1_WS = None
_ADJ1_CACHE = None
ADJ1_MONTH_HEADERS = ["31/01/2026", "28/02/2026", "31/03/2026", "30/04/2026", "31/05/2026",
                      "30/06/2026", "31/07/2026", "31/08/2026", "30/09/2026", "31/10/2026",
                      "30/11/2026", "31/12/2026"]

def set_adj1_ws(ws):
    global _ADJ1_WS, _ADJ1_CACHE
    _ADJ1_WS = ws
    _ADJ1_CACHE = None

def load_adj1(force=False):
    """
    Dict {(cc,cuenta,dim_punteada): {'ppto':[12], 'linea', 'tipo', 'dim_num'}} desde Adj 1.
    La dimensión se traduce numérica->punteada para que la llave calce con el vigente.
    """
    global _ADJ1_CACHE
    if _ADJ1_CACHE is not None and not force:
        return _ADJ1_CACHE
    if _ADJ1_WS is None:
        raise RuntimeError("Adj 1 no inicializado: la app debe llamar set_adj1_ws().")
    data = {}
    for row in _ADJ1_WS.get_all_records():
        cc = str(row.get("CENTRO_COSTO", "")).strip()
        cuenta = str(row.get("CUENTA_CONTABLE", "")).strip()
        dim_num = str(row.get("DIMENSION", "")).strip()
        if dim_num.endswith(".0"):
            dim_num = dim_num[:-2]
        dim_punt = de.numerica_a_punteada(dim_num)  # 22 -> 01.03
        if not cc or not cuenta or dim_punt is None:
            continue
        key = _mkkey(cc, cuenta, dim_punt)
        ppto = [_num(row.get(h)) for h in ADJ1_MONTH_HEADERS]
        linea = str(row.get("LINEA", "")).strip()
        if linea.endswith(".0"):
            linea = linea[:-2]
        data[key] = {"ppto": ppto, "linea": linea,
                     "tipo": str(row.get("TIPO", "N")).strip() or "N", "dim_num": dim_num}
    _ADJ1_CACHE = data
    return data

def adj1_line(cc, cuenta, dim):
    """Registro de Adj 1 para la terna (dim punteada), o None."""
    return load_adj1().get(_mkkey(cc, cuenta, dim))


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
        dim = de.normaliza_punteada(row.get("DIMENSION", ""))  # punteada, normalizada
        if not cc or not cuenta:
            continue
        key = _mkkey(cc, cuenta, dim)
        rec = data.setdefault(key, {
            "centro_costo": cc, "cuenta": cuenta, "dimension": dim,
            "ppto": [0.0] * 12, "comp": [0.0] * 12, "ejec": [0.0] * 12,
            "attrs": {a: row.get(a, "") for a in ATTR_COLS if a in row},
        })
        # si la llave se repite (no debería), se suman los meses (defensivo)
        for i, m in enumerate(MONTH_KEYS):
            rec["ppto"][i] += _num(row.get(f"PPTO_{m}"))
            rec["comp"][i] += _num(row.get(f"COMP_{m}"))
            rec["ejec"][i] += _num(row.get(f"EJEC_{m}"))
    _CACHE = data
    return data


# ---- Consultas por línea (CC, cuenta, dimensión punteada) ----

def get_line(cc, cuenta, dim):
    """Registro de una línea, o None si no existe en el vigente."""
    return load_vigente().get(_mkkey(cc, cuenta, dim))

def line_exists(cc, cuenta, dim):
    return get_line(cc, cuenta, dim) is not None

def monthly(cc, cuenta, dim, campo):
    """Arreglo de 12 valores de 'ppto' | 'comp' | 'ejec' (ceros si no existe)."""
    rec = get_line(cc, cuenta, dim)
    return list(rec[campo]) if rec else [0.0] * 12

def cumulative_available(cc, cuenta, dim, month_index):
    """
    Saldo ACUMULADO al mes (0-based) = Σ_{m<=month} (PPTO - COMP - EJEC), SOLO del vigente (ERP).
    El corte (budget_cutoff) le aplica encima los movimientos del día.
    """
    rec = get_line(cc, cuenta, dim)
    if rec is None:
        return 0.0
    total = 0.0
    for i in range(month_index + 1):
        total += rec["ppto"][i] - rec["comp"][i] - rec["ejec"][i]
    return round(total, 2)
