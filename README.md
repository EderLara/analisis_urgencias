# Dashboard de Atención de Urgencias

Panel de control interactivo construido con **Streamlit** para el análisis de morbilidad y triage en servicios de urgencias. Los datos se procesan mediante un ETL que construye un modelo semántico estrella en SQLite, separando los dos datasets en sus propias tablas de hechos.

---

## Estructura del proyecto

```
urgencias/
├── app streamlit/
│   ├── etl.py          # Proceso ETL: limpieza, transformación y carga al modelo estrella
│   ├── dashboard.py    # Aplicación Streamlit con las visualizaciones
│   ├── lanzador.py     # Menú interactivo para ejecutar el ETL y/o el dashboard
│   ├── requirements.txt
│   └── urgencias.db    # Base de datos SQLite generada por el ETL (no versionada)
├── MORBILIDAD_URGENCIAS_*.csv   # Dataset de morbilidad (no versionado)
├── Triage_Urgencias_*.csv       # Dataset de triage (no versionado)
├── Proyecto_atención_urgencias.ipynb
├── .gitignore
└── README.md
```

---

## Modelo estrella

El ETL construye dos tablas de hechos independientes, ya que los datasets no comparten claves directas:

| Tabla de hechos   | Descripción                                              |
|-------------------|----------------------------------------------------------|
| `Fact_Morbilidad` | Diagnósticos, EPS, régimen, demografía y geografía       |
| `Fact_Triage`     | Tiempos de espera, nivel de triage, IPS y red            |

**Dimensiones compartidas:** `Dim_Fecha`, `Dim_Hora`, `Dim_Eps`

**Dimensiones exclusivas de Morbilidad:** `Dim_Regimen`, `Dim_Ubicacion`, `Dim_Edad`, `Dim_Diagnostico`, `Dim_Sexo`

**Dimensiones exclusivas de Triage:** `Dim_Triage`, `Dim_Ips`

---

## Requisitos

- Python 3.9+
- Instalar dependencias:

```bash
pip install -r "app streamlit/requirements.txt"
```

---

## Uso

### Opción 1 — Lanzador interactivo (recomendado)

```bash
cd "app streamlit"
python lanzador.py
```

Muestra el menú:
```
1. Iniciar todo (ETL + Dashboard)
2. Solo ETL
3. Solo Dashboard
0. Salir
```

### Opción 2 — Ejecución manual

```bash
# 1. Ejecutar el ETL para generar la base de datos
cd "app streamlit"
python etl.py

# 2. Lanzar el dashboard
streamlit run dashboard.py
```

> Los archivos CSV deben estar en la carpeta `urgencias/` (un nivel arriba de `app streamlit/`).

---

## Vistas del dashboard

### 🚨 Triage
- Distribución por nivel de triage (I–V) con colores normativos colombianos
- Carga promedio por día de la semana y por hora del día
- Tabla de datos y convenciones de color
- Tiempos de espera promedio vs límite normativo
- Cumplimiento e incumplimiento normativo con etiquetas
- Tabla comparativa con pacientes sobre el promedio interno
- Análisis por IPS y red de atención

### 📋 Morbilidad
- Distribución por régimen de salud y participación por EPS
- Pirámide poblacional por rango de edad y sexo
- Top 10 diagnósticos más frecuentes
- Contraste clínico por ciclo de vida (0–5 años, >5 y <60 años, >60 años)
- Top 10 municipios de procedencia con análisis de Pareto
- Distribución por departamento
