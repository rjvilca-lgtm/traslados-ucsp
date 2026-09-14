# Prototipo web de solicitudes presupuestales

Aplicación Streamlit para transformar el formato Excel de traslado/ampliación/reducción de presupuesto en una experiencia web.

## Funcionalidades

- Selección de **Traslado / Ampliación / Reducción**.
- Traslado con **Origen y Destino** independientes.
- Cantidad de líneas dinámica: el usuario puede agregar/eliminar tantas filas como necesite.
- Distribución mensual Ene–Dic.
- Cálculo automático de totales.
- Validación de balance para traslados.
- Importación del formato Excel actual.
- Exportación de la solicitud a Excel.
- Diseño responsive.

## Ejecutar localmente

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## Desplegar en Streamlit Community Cloud

1. Sube `app.py`, `requirements.txt` y este README a un repositorio de GitHub.
2. Entra a Streamlit Community Cloud.
3. Selecciona **New app**.
4. Selecciona el repositorio, rama y archivo `app.py`.
5. Despliega.

## Importación de Excel

En la barra lateral selecciona **Importar desde Excel** y carga el archivo.

El importador reconoce la hoja `Formato` del archivo actual y busca las tablas que contienen:

- Centro de costo
- Dimensión
- Partida
- Ene–Dic

Para producción, se recomienda reemplazar los campos libres de centro de costo/partida por selectores conectados a las tablas maestras de la aplicación.

## Siguiente fase recomendada

Conectar:

- usuarios/autenticación
- centros de costo
- dimensiones
- partidas
- presupuesto disponible
- reglas de aprobación
- persistencia en SQL
- historial de solicitudes
- estados: Borrador / En revisión / Aprobado / Observado / Rechazado
