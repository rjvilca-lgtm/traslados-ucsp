"""
Fase 2a — MOTOR DE CORTE (batch diario). Sin Streamlit, testeable offline.

Regla acordada:
- Un solo corte por día. Solicitudes en estado 'Aprobada', evaluadas en orden de
  llegada (FIFO por created_at).
- Descuento SECUENCIAL: cada solicitud ejecutada modifica una foto en memoria, de
  modo que la siguiente ve el saldo ya reducido (esto evita el sobregiro Juan/María).
- Traslado: cada línea de ORIGEN saca dinero (−) y cada línea de DESTINO mete (+).
  Se ejecuta solo si TODAS las líneas de origen dejan saldo acumulado >= 0 en el mes
  del movimiento. Si alguna no alcanza -> RECHAZO TOTAL (atómico), no se toca la foto.
- Ampliación: no valida saldo (crea presupuesto); suma a la foto y se ejecuta siempre.
- Signos uniformes: ingreso +, gasto −, sin importar origen/destino.

NO genera el archivo de carga (eso es Fase 2b: requiere resolver LINEA). Solo decide.
"""
import copy
import dim_equiv as de

# meses del formulario (español) en orden -> índice 0..11
FORM_MONTHS = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Set","Oct","Nov","Dic"]


def _iter_lines(mov):
    """Devuelve (rol, linea) para cada línea del movimiento. rol in {'origen','destino','single'}."""
    for rol in ("origen", "destino", "single"):
        for ln in (mov.get(rol) or []):
            yield rol, ln


def _key(line):
    return (str(line.get("Centro de costo", "")).strip(),
            str(line.get("Partida", "")).strip(),
            de.normaliza_punteada(line.get("Dimensión", "")))


def _months_of(line):
    """[(idx, monto)] de los meses con monto != 0 en la línea."""
    out = []
    for i, m in enumerate(FORM_MONTHS):
        v = line.get(m, 0)
        try:
            v = float(v or 0)
        except (TypeError, ValueError):
            v = 0.0
        if v != 0:
            out.append((i, v))
    return out


def _cumulative_available(snap, key, month_idx):
    """Σ_{k<=month} (ppto - comp - ejec) con la foto (posiblemente ya mutada)."""
    rec = snap.get(key)
    if rec is None:
        return None  # línea inexistente en el vigente
    total = 0.0
    for k in range(month_idx + 1):
        total += rec["ppto"][k] - rec["comp"][k] - rec["ejec"][k]
    return round(total, 2)


def _apply(snap, key, month_idx, delta):
    """Aplica delta al ppto de la línea en el mes (muta la foto)."""
    snap[key]["ppto"][month_idx] += delta


def evaluate_request(req, snap):
    """
    Evalúa UNA solicitud contra la foto. Si pasa, MUTA snap y devuelve (True, "").
    Si no, devuelve (False, motivo) SIN tocar snap.
    """
    tipo = req.get("tipo")
    mov = req.get("movimiento", {}) or {}

    # Deltas por línea/mes: origen resta, destino/single suma.
    deltas = []  # (key, month_idx, delta, rol)
    faltantes = set()
    for rol, line in _iter_lines(mov):
        key = _key(line)
        if key not in snap:
            faltantes.add(key)
        signo = -1.0 if rol == "origen" else 1.0
        for idx, monto in _months_of(line):
            deltas.append((key, idx, signo * abs(monto), rol))

    if faltantes:
        return False, "Línea(s) inexistente(s) en el vigente: " + ", ".join("/".join(k) for k in sorted(faltantes))

    # Trabajar sobre copia; solo si pasa, se vuelca a snap.
    work = copy.deepcopy(snap)
    for key, idx, delta, _ in deltas:
        _apply(work, key, idx, delta)

    # Ampliación no valida saldo. Traslado sí, solo en las líneas/mes de ORIGEN.
    if tipo != "Ampliación":
        for key, idx, delta, rol in deltas:
            if rol == "origen":
                avail = _cumulative_available(work, key, idx)
                if avail is None or avail < 0:  # regla: acumulado >= 0 en el mes M
                    etq = "/".join(key)
                    return (False,
                            f"Saldo insuficiente en {etq}, mes {FORM_MONTHS[idx]}: "
                            f"acumulado quedaría en S/ {avail:,.2f}")

    # pasa -> commit
    for key in work:
        snap[key]["ppto"] = work[key]["ppto"]
    return True, ""


def run_cutoff(approved_requests, vigente_snapshot):
    """
    approved_requests: lista de solicitudes en estado 'Aprobada'.
    vigente_snapshot: dict {(cc,cuenta): {'ppto':[12],'comp':[12],'ejec':[12], ...}} (de budget_data.load_vigente()).
    Devuelve (resultados, snapshot_final). NO escribe en el store; el caller aplica los estados.
    resultados: [{id, tipo, created_at, created_by, monto, result: 'Ejecutada'|'Rechazada por saldo', motivo}]
    """
    snap = copy.deepcopy(vigente_snapshot)
    ordered = sorted(approved_requests, key=lambda r: str(r.get("created_at", "")))
    resultados = []
    for req in ordered:
        ok, motivo = evaluate_request(req, snap)
        resultados.append({
            "id": req.get("id"), "tipo": req.get("tipo"),
            "created_at": req.get("created_at"), "created_by": req.get("created_by"),
            "monto": req.get("monto"),
            "result": "Ejecutada" if ok else "Rechazada por saldo",
            "motivo": motivo,
        })
    return resultados, snap
