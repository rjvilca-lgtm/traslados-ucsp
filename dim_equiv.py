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
    ("02.16", "46"), ("02.17", "47"),
    ("03.00", "4"), ("03.01", "40"),
    ("04.00", "5"), ("04.01", "50"),
]

_PUNT_A_NUM = {p: n for p, n in _PARES}
_NUM_A_PUNT = {n: p for p, n in _PARES}


def punteada_a_numerica(punteada):
    """'01.03' -> '22'. None si no existe."""
    return _PUNT_A_NUM.get(str(punteada).strip())


def numerica_a_punteada(numerica):
    """'22' -> '01.03'. None si no existe. Normaliza enteros ('22', 22, '22.0')."""
    s = str(numerica).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return _NUM_A_PUNT.get(s)


def es_punteada_valida(punteada):
    return str(punteada).strip() in _PUNT_A_NUM


def todas_punteadas():
    return list(_PUNT_A_NUM.keys())
