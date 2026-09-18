"""
Núcleo de lógica — SIN Streamlit, para poder testear y reemplazar por Azure SQL.
Store en Google Sheets; la app inyecta el worksheet con set_worksheet().
"""
import json
import uuid
import secrets as _secrets
import datetime as _dt

MONTHS = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Set","Oct","Nov","Dic"]
TEXT_COLS = ["Centro de costo", "Dimensión", "Partida"]
LINE_COLS = TEXT_COLS + MONTHS

APPROVER_EMAIL = "rjvilca@ucsp.edu.pe"
DOMAIN = "ucsp.edu.pe"

# --------------------------------------------------------------------- REGLAS
# Cambiar aquí ajusta todo el flujo de aprobación.
TRASLADO_THRESHOLD = 2500.0        # traslado requiere aprobación si supera este monto
REDUCCION_REQUIERE_APROBACION = False  # ASUNCIÓN — confirmar con negocio

def needs_approval(tipo: str, monto: float) -> bool:
    if tipo == "Ampliación":
        return True                         # siempre
    if tipo == "Traslado":
        return monto > TRASLADO_THRESHOLD   # solo si supera el umbral
    if tipo == "Reducción":
        return REDUCCION_REQUIERE_APROBACION
    return True

# ----------------------------------------------------------- USUARIOS (MOCK)
# Reemplazar por SELECT ... FROM usuarios / permisos_centro_costo en Azure SQL.
# cost_centers: lista de prefijos permitidos. "*" = todos (aprobador/admin).
MOCK_USERS = {
    "rjvilca@ucsp.edu.pe": {"name": "Robert Vilca", "role": "aprobador", "cost_centers": ["*"]},
    "jefe.ingenieria@ucsp.edu.pe": {"name": "Jefe de Ingeniería", "role": "solicitante", "cost_centers": ["03.08.01"]},
    "jefe.derecho@ucsp.edu.pe": {"name": "Jefe de Derecho", "role": "solicitante", "cost_centers": ["03.02"]},
    "jefe.salud@ucsp.edu.pe": {"name": "Jefe de Ciencias de la Salud", "role": "solicitante", "cost_centers": ["03.05"]},
}

def get_user(email: str):
    email = (email or "").strip().lower()
    rec = MOCK_USERS.get(email)
    if rec is None:
        return None
    return {**rec, "email": email}

def is_approver(user: dict) -> bool:
    return bool(user) and user.get("role") in ("aprobador", "admin")

def allowed_cost_center(cc: str, user: dict) -> bool:
    ccs = user.get("cost_centers", [])
    if "*" in ccs:
        return True
    cc = str(cc).strip()
    if not cc:
        return True  # celda vacía: se valida en otra parte
    return any(cc.startswith(p) for p in ccs)

def disallowed_ccs(cc_list, user: dict):
    """CCs que el usuario NO tiene permiso de tocar."""
    seen = []
    for cc in cc_list:
        cc = str(cc).strip()
        if cc and not allowed_cost_center(cc, user) and cc not in seen:
            seen.append(cc)
    return seen

# ---------------------------------------------------------------- ESTADOS
STATUS_PENDING = "Pendiente de aprobación"
STATUS_APPROVED = "Aprobada"
STATUS_AUTO = "Aprobada (automática)"
STATUS_REJECTED = "Rechazada"
STATUS_EJECUTADA = "Ejecutada"
STATUS_RECH_SALDO = "Rechazada por saldo"

# ------------------------------------------------- STORE (Google Sheets)
# Una fila por solicitud. Columnas legibles + 'payload' con el JSON completo.
# La interfaz (list/create/update/...) es la misma que tendrá la versión SQL.
# Métodos de gspread usados: append_row, get_all_records, col_values, batch_update
# (estables en gspread 5/6). El core NO importa streamlit: la app construye el
# worksheet (cacheado) y se lo inyecta con set_worksheet().
SHEET_HEADERS = ["id", "created_at", "created_by", "tipo", "status", "monto", "payload"]
_WS = None  # worksheet inyectado por la app

def build_worksheet(sa_info: dict, spreadsheet_id: str, worksheet: str = "solicitudes"):
    """Autentica con la cuenta de servicio y devuelve el worksheet (asegura cabecera)."""
    import gspread
    from google.oauth2.service_account import Credentials
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(dict(sa_info), scopes=scopes)
    sh = gspread.authorize(creds).open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet(worksheet)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet, rows=2000, cols=len(SHEET_HEADERS))
    if ws.row_values(1) != SHEET_HEADERS:
        ws.append_row(SHEET_HEADERS)
    return ws

def set_worksheet(ws):
    global _WS
    _WS = ws

def _require_ws():
    if _WS is None:
        raise RuntimeError("Store no inicializado: la app debe llamar set_worksheet() primero.")
    return _WS

def _req_to_row(req: dict):
    return [str(req.get("id", "")), req.get("created_at", ""), req.get("created_by", ""),
            req.get("tipo", ""), req.get("status", ""), req.get("monto", 0),
            json.dumps(req, ensure_ascii=False)]

# Caché de un solo rerun: evita releer la hoja completa varias veces por interacción
# (la causa del error 429 de cuota). La app llama invalidate_cache() al inicio de cada
# rerun; toda escritura la invalida también.
_REQ_CACHE = None

def invalidate_cache():
    global _REQ_CACHE
    _REQ_CACHE = None

def list_requests():
    global _REQ_CACHE
    if _REQ_CACHE is not None:
        return _REQ_CACHE
    out = []
    for row in _require_ws().get_all_records():
        payload = row.get("payload")
        if payload:
            try:
                out.append(json.loads(payload)); continue
            except Exception:
                pass
        out.append({k: row.get(k) for k in SHEET_HEADERS if k != "payload"})
    _REQ_CACHE = out
    return out

def _row_number(rid: str):
    """Número de fila (1-based) de la solicitud, o None. Deriva de la caché, sin leer la hoja."""
    for i, r in enumerate(list_requests()):
        if str(r.get("id")) == str(rid):
            return i + 2  # +1 por cabecera, +1 porqué enumerate empieza en 0
    return None

def requests_for(email: str):
    email = (email or "").lower()
    return [r for r in list_requests() if str(r.get("created_by", "")).lower() == email]

def pending_requests():
    return [r for r in list_requests() if r.get("status") == STATUS_PENDING]

def get_request(rid: str):
    return next((r for r in list_requests() if str(r.get("id")) == str(rid)), None)

def create_request(req: dict):
    _require_ws().append_row(_req_to_row(req), value_input_option="RAW")
    invalidate_cache()
    return req

def update_request(rid: str, **changes):
    r = get_request(rid)
    if r is None:
        return None
    r.update(changes)
    row_i = _row_number(rid)
    if row_i is None:
        return None
    _require_ws().batch_update([{"range": f"A{row_i}:G{row_i}", "values": [_req_to_row(r)]}])
    invalidate_cache()
    return r

def bulk_update(updates):
    """
    Aplica varios cambios en UNA sola llamada de escritura (evita el 429 en el corte).
    updates: lista de (rid, dict_de_cambios). Lee la hoja una vez, arma todos los rangos
    y los manda en un solo batch_update.
    """
    reqs = {str(r.get("id")): r for r in list_requests()}
    # mapa id -> número de fila (desde la caché, sin releer)
    row_of = {}
    for i, r in enumerate(list_requests()):
        row_of[str(r.get("id"))] = i + 2
    body = []
    for rid, changes in updates:
        rid = str(rid)
        r = reqs.get(rid)
        if r is None or rid not in row_of:
            continue
        r.update(changes)
        body.append({"range": f"A{row_of[rid]}:G{row_of[rid]}", "values": [_req_to_row(r)]})
    if body:
        _require_ws().batch_update(body)
        invalidate_cache()
    return len(body)

def new_request(user, tipo, periodo, unidad, solicitante, monto, movimiento):
    na = needs_approval(tipo, monto)
    return {
        "id": uuid.uuid4().hex[:10],
        "token": _secrets.token_urlsafe(16),
        "created_by": user["email"],
        "created_by_name": user.get("name", ""),
        "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "tipo": tipo,
        "periodo": periodo,
        "unidad": unidad,
        "solicitante": solicitante,
        "monto": round(float(monto), 2),
        "needs_approval": na,
        "status": STATUS_PENDING if na else STATUS_AUTO,
        "movimiento": movimiento,   # {"origen":[...], "destino":[...]} o {"single":[...]}
        "approver": None,
        "decided_at": None,
        "decision_note": "",
    }
