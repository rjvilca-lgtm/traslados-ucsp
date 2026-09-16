"""
Núcleo de lógica — SIN Streamlit, para poder testear y reemplazar por Azure SQL.
Todo lo marcado como MOCK vive aquí para que la migración a SQL sea un solo archivo.
"""
import json
import uuid
import secrets as _secrets
import datetime as _dt
from pathlib import Path

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

# ------------------------------------------------------- STORE (MOCK: JSON)
# Reemplazar _load/_save por INSERT/UPDATE/SELECT en Azure SQL.
# Nota: last-write-wins; suficiente para un solo servidor / demo.
DATA_DIR = Path(__file__).resolve().parent / "data"
REQ_FILE = DATA_DIR / "requests.json"

def _load(path: Path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def _save(path: Path, data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def list_requests():
    return _load(REQ_FILE)

def requests_for(email: str):
    email = (email or "").lower()
    return [r for r in list_requests() if r.get("created_by", "").lower() == email]

def pending_requests():
    return [r for r in list_requests() if r.get("status") == STATUS_PENDING]

def get_request(rid: str):
    return next((r for r in list_requests() if r.get("id") == rid), None)

def create_request(req: dict):
    data = _load(REQ_FILE)
    data.append(req)
    _save(REQ_FILE, data)
    return req

def update_request(rid: str, **changes):
    data = _load(REQ_FILE)
    for r in data:
        if r.get("id") == rid:
            r.update(changes)
    _save(REQ_FILE, data)
    return get_request(rid)

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
