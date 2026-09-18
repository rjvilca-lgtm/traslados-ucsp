"""
Equivalencias de dimensión contable — punteada (formulario/vigente) <-> numérica (Adj 1 / ERP).
Tabla maestra estable (32 dimensiones). Incrustada hoy; migrar a SQL después reemplazando
SOLO el cuerpo de las funciones de abajo (la interfaz no cambia para quien las usa).

Idioma interno del sistema = PUNTEADA. La numérica se usa solo al escribir el archivo Adj 1.
"""

# (punteada, numerica) — verificado 1:1 en ambos sentidos.
_PARES = [
    ("00.00", "1"), ("00.01", "10"), ("00.02", "11"), ("00.03", "12"),
    ("01.00", "2"), ("01.01", "20"), ("01.02", "21"), ("01.03", "22"),
    ("01.04", "23"), ("01.05", "24"),
    ("02.00", "3"), ("02.01", "30"), ("02.02", "31"), ("02.03", "32"),
    ("02.04", "33"), ("02.05", "34"), ("02.06", "35"), ("02.07", "36"),
    ("02.08", "37"), ("02.09", "38"), ("02.10", "39"), ("02.11", "42"),
    ("02.12", "41"), ("02.13", "43"), ("02.14", "44"), ("02.15", "45"),
    ("02.16", "46"), ("02.17", "47"), ("02.18", "48"),
    ("03.00", "4"), ("03.01", "40"),
    ("04.00", "5"), ("04.01", "50"),
]

_PUNT_A_NUM = {p: n for p, n in _PARES}
_NUM_A_PUNT = {n: p for p, n in _PARES}


def normaliza_punteada(v):
    """
    Revierte la deformación de Google Sheets al leer la dimensión como número.
    Sheets convierte '02.10'->'2.1', '02.01'->'2.01', '01.02'->'1.02'.
    Se probó que el re-relleno a NN.NN es reversible sin colisiones.
    '2.1' -> '02.10' · '2.01' -> '02.01' · ya-punteada '02.01' -> '02.01'.
    """
    s = str(v).strip()
    if not s or "." not in s:
        return s
    ent, dec = s.split(".", 1)
    dec = (dec + "00")[:2]          # rellena decimales a 2: '1'->'10', '01'->'01'
    try:
        ent = f"{int(ent):02d}"     # rellena entero a 2: '2'->'02'
    except ValueError:
        return s
    return f"{ent}.{dec}"


def punteada_a_numerica(punteada):
    """'01.03' o '1.03' -> '22'. None si no existe. Normaliza formato deformado."""
    return _PUNT_A_NUM.get(normaliza_punteada(punteada))


def numerica_a_punteada(numerica):
    """'22' -> '01.03'. None si no existe. Normaliza enteros ('22', 22, '22.0')."""
    s = str(numerica).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return _NUM_A_PUNT.get(s)


def es_punteada_valida(punteada):
    return normaliza_punteada(punteada) in _PUNT_A_NUM


def todas_punteadas():
    return list(_PUNT_A_NUM.keys())
