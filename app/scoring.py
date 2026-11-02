"""Modelo de medición del riesgo frente al FEN.

Cada criterio se responde en escala ordinal de 3 niveles:
  0 = No se presenta
  1 = Se presenta parcialmente (hay medidas, pero insuficientes)
  2 = Se presenta plenamente (sin medidas de control)

Índice de riesgo (0–100) = puntaje / puntaje máximo × 100
  0–33   Bajo riesgo
  34–66  Riesgo moderado
  67–100 Alto riesgo

Alerta crítica: si un criterio crítico (daño del mamógrafo, electricidad,
grupo electrógeno, inundación de consultorios) obtiene 2, el establecimiento
sube como mínimo a "Riesgo moderado" y se marca para seguimiento prioritario.
"""

ESCALA = [
    (0, "No", "No se presenta"),
    (1, "Parcial", "Se presenta parcialmente / con medidas insuficientes"),
    (2, "Sí", "Se presenta plenamente / sin medidas de control"),
]

DIMENSIONES = [
    ("Vulnerabilidad del establecimiento", [
        "Ubicado en distrito con riesgo alto o muy alto de inundación",
        "Infraestructura expuesta (techos, muros, drenaje pluvial)",
    ]),
    ("Daños físicos y falta de operatividad", [
        "Exposición a lluvias intensas, desbordes de ríos y huaicos",
        "Amenaza de inundación en el área de mamografía / consultorios",
        "Posible daño del mamógrafo (humedad, ubicación, falta de protección)",
        "Interrupción del acceso al local",
        "Interrupción del servicio de electricidad",
        "Interrupción de los servicios de agua y saneamiento",
    ]),
    ("Sobrecarga del sistema", [
        "Desplazamiento de población hacia el establecimiento",
    ]),
    ("Fallos logísticos", [
        "Brechas de personal (tecnólogo, radiólogo, mantenimiento)",
        "Desabastecimiento de insumos y/o medicamentos",
        "Carencia de equipos de respaldo (grupo electrógeno, UPS, estabilizador)",
        "Dificultad para asegurar agua segura durante la emergencia",
    ]),
]

PREGUNTAS = [q for _, qs in DIMENSIONES for q in qs]
N = len(PREGUNTAS)
MAX = N * 2
# Índices (0-based) de criterios críticos para la operatividad del mamógrafo
CRITICOS = [3, 4, 6, 11]


def nivel_por_indice(indice: float) -> str:
    if indice >= 67:
        return "Alto riesgo"
    if indice >= 34:
        return "Riesgo moderado"
    return "Bajo riesgo"


def calcular(respuestas: list[int]) -> dict:
    if len(respuestas) != N or any(r not in (0, 1, 2) for r in respuestas):
        raise ValueError("Respuestas inválidas")
    puntaje = sum(respuestas)
    indice = round(puntaje / MAX * 100, 1)
    nivel = nivel_por_indice(indice)
    criticos = [i + 1 for i in CRITICOS if respuestas[i] == 2]
    if criticos and nivel == "Bajo riesgo":
        nivel = "Riesgo moderado"
    dims, k = {}, 0
    for nombre, qs in DIMENSIONES:
        sub = respuestas[k:k + len(qs)]
        dims[nombre] = round(sum(sub) / (len(qs) * 2) * 100, 1)
        k += len(qs)
    return {"puntaje": puntaje, "maximo": MAX, "indice": indice, "nivel": nivel,
            "alerta_critica": bool(criticos), "criticos": criticos, "dimensiones": dims}
