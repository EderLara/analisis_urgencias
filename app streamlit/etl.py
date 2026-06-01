"""
ETL - Sistema de Urgencias
Modelo Estrella con dos tablas de hechos:
  - Fact_Morbilidad : diagnósticos, EPS, régimen, demografía, geografía
  - Fact_Triage     : tiempos de espera, nivel de triage, IPS, red
"""
import pandas as pd
import sqlite3
import numpy as np
import os
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(BASE_DIR, "urgencias.db")
MORB_PATH   = os.path.join(BASE_DIR, "..", "MORBILIDAD_URGENCIAS_20260525 (1).csv")
TRIAGE_PATH = os.path.join(BASE_DIR, "..", "Triage_Urgencias_20260525 (1).csv")

def _elapsed(t0):
    """Retorna string con segundos transcurridos desde t0."""
    return f"{time.time() - t0:.2f}s"

# ─────────────────────────────────────────────────────────────────────────────
# LIMPIEZA
# ─────────────────────────────────────────────────────────────────────────────
def clean_morbilidad(df):
    t0 = time.time()
    logging.info("🔄 [Limpieza Morbilidad] Iniciando...")
    df = df.copy()

    logging.info("   → Convirtiendo edades a años...")
    def to_years(row):
        t = str(row.get('TIPO_EDAD', '')).upper()
        e = pd.to_numeric(row.get('EDAD', 0), errors='coerce') or 0
        if t == 'AÑOS':  return float(e)
        if t == 'MESES': return round(e / 12, 2)
        if t in ('DIAS', '3DIAS'): return round(e / 365, 2)
        return float(e)
    df['EDAD_AÑOS'] = df.apply(to_years, axis=1)

    bins   = [0, 5, 17, 40, 60, 150]
    labels = ['0-5 años', '6-17 años', '18-40 años', '41-60 años', '>60 años']
    df['RANGO_EDAD'] = pd.cut(df['EDAD_AÑOS'], bins=bins, labels=labels, right=True)
    logging.info("   → Rangos de edad calculados.")

    logging.info("   → Unificando variantes de EPS...")
    df['EAPB'] = df['EAPB'].replace({
        'EMSSANAR SAS':        'EMSSANAR',
        'EMSSANAR S.A.S':      'EMSSANAR',
        'EMSSANAR EPS S.A.S':  'EMSSANAR',
        'EMSSANAR EPS':        'EMSSANAR',
        'AIC EPSI':            'AIC',
        'ASOCIACION INDIGENA DEL CAUCA - AIC': 'AIC',
        'MALLAMAS EPSI':       'MALLAMAS',
        'MALLAMAS EPS I':      'MALLAMAS',
        'EPS SANITAS S.A.S':   'EPS SANITAS',
        'EPS SANITAS S.A.S.':  'EPS SANITAS',
        'UNIMAP EU':           'UNIMAP',
    }).fillna('DESCONOCIDO')

    logging.info("   → Normalizando régimen de salud...")
    df['REGIMEN'] = df['REGIMEN'].replace({
        'ESPCIAL':   'ESPECIAL O DE EXCEPCION',
        'ESPECIAL':  'ESPECIAL O DE EXCEPCION',
        'EXCPECION': 'ESPECIAL O DE EXCEPCION',
        'EXCEPCION': 'ESPECIAL O DE EXCEPCION',
    }).fillna('DESCONOCIDO')

    logging.info("   → Parseando fechas y rellenando nulos...")
    df['FECHA_ATENCION'] = pd.to_datetime(df['FECHA_ATENCION'], format='%m/%d/%Y', errors='coerce')
    df['DEPARTAMENTO']   = df['DEPARTAMENTO'].fillna('N/A')
    df['PROCEDENCIA']    = df['PROCEDENCIA'].fillna('N/A')
    df['SEXO']           = df['SEXO'].fillna('N/A')

    logging.info(f"✅ [Limpieza Morbilidad] Completada — {len(df):,} registros — {_elapsed(t0)}")
    return df


def clean_triage(df):
    t0 = time.time()
    logging.info("🔄 [Limpieza Triage] Iniciando...")
    df = df.copy()

    logging.info("   → Normalizando nombres de EPS...")
    df['Nom_Admini'] = df['Nom_Admini'].replace({
        'EMSSANAR S.A.S': 'EMSSANAR', 'EMSSANAR SAS': 'EMSSANAR'
    }).fillna('DESCONOCIDO')

    logging.info("   → Parseando fechas y horas...")
    df['Fecha_Ing_DT']      = pd.to_datetime(df['Fecha_Ing'],      format='mixed', errors='coerce')
    df['Fecha_Atencion_DT'] = pd.to_datetime(df['Fecha_Atencion'], format='mixed', errors='coerce')
    df['Hora_Ing_DT']       = pd.to_datetime(df['Hora_Ingre'],     format='mixed', errors='coerce')
    df['Hora_Aten_DT']      = pd.to_datetime(df['Hora_Atencion'],  format='mixed', errors='coerce')

    logging.info("   → Calculando tiempos de espera...")
    df['Tiempo_Espera_Min'] = (df['Fecha_Atencion_DT'] - df['Fecha_Ing_DT']).dt.total_seconds() / 60
    antes = len(df)
    df = df[df['Tiempo_Espera_Min'] >= 0].copy()
    descartados = antes - len(df)
    logging.info(f"   → {descartados:,} registros descartados por tiempo negativo.")

    df['Fecha_Solo'] = df['Fecha_Ing_DT'].dt.date
    df['Hora_Solo']  = df['Hora_Ing_DT'].dt.hour
    df['Dia_Semana'] = df['Fecha_Ing_DT'].dt.day_name()
    df['Anio']       = df['Fecha_Ing_DT'].dt.year
    df['Mes']        = df['Fecha_Ing_DT'].dt.month

    logging.info("   → Calculando cumplimiento normativo...")
    limites = {'I': 0, 'II': 30, 'III': 60, 'IV': 120, 'V': 360}
    df['Limite_Norma'] = df['Triage'].map(limites)
    df['Supera_Norma'] = df['Tiempo_Espera_Min'] > df['Limite_Norma']

    df['Ips'] = df['Ips'].fillna('N/A')
    df['Red'] = df['Red'].fillna('N/A')

    logging.info(f"✅ [Limpieza Triage] Completada — {len(df):,} registros — {_elapsed(t0)}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# ESQUEMA
# ─────────────────────────────────────────────────────────────────────────────
def create_schema(conn):
    t0 = time.time()
    logging.info("🔄 [Esquema] Creando modelo estrella en SQLite...")
    cur = conn.cursor()
    tables = ['Dim_Fecha', 'Dim_Hora', 'Dim_Triage', 'Dim_Eps', 'Dim_Regimen',
              'Dim_Ubicacion', 'Dim_Edad', 'Dim_Diagnostico', 'Dim_Sexo',
              'Dim_Ips', 'Fact_Morbilidad', 'Fact_Triage']
    for t in tables:
        cur.execute(f"DROP TABLE IF EXISTS {t}")

    cur.executescript("""
    CREATE TABLE Dim_Fecha (
        fecha_id    INTEGER PRIMARY KEY,
        fecha       TEXT,
        dia_semana  TEXT,
        mes         INTEGER,
        anio        INTEGER,
        trimestre   INTEGER,
        es_fin_semana INTEGER
    );
    CREATE TABLE Dim_Hora (
        hora_id INTEGER PRIMARY KEY,
        hora    INTEGER
    );
    CREATE TABLE Dim_Triage (
        triage_id       INTEGER PRIMARY KEY,
        nivel           TEXT,
        color_norma     TEXT,
        limite_minutos  INTEGER
    );
    CREATE TABLE Dim_Eps (
        eps_id  INTEGER PRIMARY KEY,
        nombre  TEXT
    );
    CREATE TABLE Dim_Regimen (
        regimen_id  INTEGER PRIMARY KEY,
        nombre      TEXT
    );
    CREATE TABLE Dim_Ubicacion (
        ubicacion_id    INTEGER PRIMARY KEY,
        departamento    TEXT,
        municipio       TEXT
    );
    CREATE TABLE Dim_Edad (
        edad_id     INTEGER PRIMARY KEY,
        edad_anos   REAL,
        rango       TEXT
    );
    CREATE TABLE Dim_Diagnostico (
        diagnostico_id  INTEGER PRIMARY KEY,
        codigo          TEXT,
        nombre          TEXT
    );
    CREATE TABLE Dim_Sexo (
        sexo_id INTEGER PRIMARY KEY,
        sexo    TEXT
    );
    CREATE TABLE Dim_Ips (
        ips_id  INTEGER PRIMARY KEY,
        nombre  TEXT,
        red     TEXT
    );
    CREATE TABLE Fact_Morbilidad (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_id        INTEGER REFERENCES Dim_Fecha(fecha_id),
        eps_id          INTEGER REFERENCES Dim_Eps(eps_id),
        regimen_id      INTEGER REFERENCES Dim_Regimen(regimen_id),
        ubicacion_id    INTEGER REFERENCES Dim_Ubicacion(ubicacion_id),
        edad_id         INTEGER REFERENCES Dim_Edad(edad_id),
        diagnostico_id  INTEGER REFERENCES Dim_Diagnostico(diagnostico_id),
        sexo_id         INTEGER REFERENCES Dim_Sexo(sexo_id),
        atencion_count  INTEGER DEFAULT 1
    );
    CREATE TABLE Fact_Triage (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_id            INTEGER REFERENCES Dim_Fecha(fecha_id),
        hora_id             INTEGER REFERENCES Dim_Hora(hora_id),
        triage_id           INTEGER REFERENCES Dim_Triage(triage_id),
        ips_id              INTEGER REFERENCES Dim_Ips(ips_id),
        eps_id              INTEGER REFERENCES Dim_Eps(eps_id),
        tiempo_espera_min   REAL,
        supera_norma        INTEGER,
        atencion_count      INTEGER DEFAULT 1
    );
    """)
    conn.commit()
    logging.info(f"✅ [Esquema] {len(tables)} tablas creadas — {_elapsed(t0)}")


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def make_dim(series, id_col, name_col='nombre'):
    vals = series.dropna().unique()
    df = pd.DataFrame({name_col: vals})
    df[id_col] = range(1, len(df) + 1)
    return df, dict(zip(df[name_col], df[id_col]))


# ─────────────────────────────────────────────────────────────────────────────
# CARGA
# ─────────────────────────────────────────────────────────────────────────────
def load_to_db(morb, tri):
    t_total = time.time()
    logging.info("=" * 60)
    logging.info("🚀 [ETL] Iniciando carga al modelo estrella...")
    logging.info("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)

    # ── Dim_Fecha ─────────────────────────────────────────────────────────────
    t0 = time.time()
    logging.info("🔄 [Dim_Fecha] Construyendo dimensión de fechas...")
    fechas_morb   = morb['FECHA_ATENCION'].dropna()
    fechas_triage = pd.to_datetime(tri['Fecha_Solo'].dropna().astype(str), errors='coerce')
    todas_fechas  = pd.concat([fechas_morb, fechas_triage]).drop_duplicates().dropna()

    dim_fecha = pd.DataFrame({'fecha': todas_fechas})
    dim_fecha['dia_semana']    = dim_fecha['fecha'].dt.day_name()
    dim_fecha['mes']           = dim_fecha['fecha'].dt.month
    dim_fecha['anio']          = dim_fecha['fecha'].dt.year
    dim_fecha['trimestre']     = dim_fecha['fecha'].dt.quarter
    dim_fecha['es_fin_semana'] = dim_fecha['dia_semana'].isin(['Saturday','Sunday']).astype(int)
    dim_fecha['fecha']         = dim_fecha['fecha'].astype(str)
    dim_fecha['fecha_id']      = range(1, len(dim_fecha) + 1)
    dim_fecha.to_sql('Dim_Fecha', conn, if_exists='append', index=False)
    mapa_fecha = dict(zip(dim_fecha['fecha'], dim_fecha['fecha_id']))
    logging.info(f"✅ [Dim_Fecha] {len(dim_fecha):,} fechas únicas — {_elapsed(t0)}")

    # ── Dim_Hora ──────────────────────────────────────────────────────────────
    t0 = time.time()
    logging.info("🔄 [Dim_Hora] Construyendo dimensión de horas...")
    dim_hora = pd.DataFrame({'hora': range(24), 'hora_id': range(1, 25)})
    dim_hora.to_sql('Dim_Hora', conn, if_exists='append', index=False)
    mapa_hora = dict(zip(dim_hora['hora'], dim_hora['hora_id']))
    logging.info(f"✅ [Dim_Hora] 24 horas cargadas — {_elapsed(t0)}")

    # ── Dim_Triage ────────────────────────────────────────────────────────────
    t0 = time.time()
    logging.info("🔄 [Dim_Triage] Construyendo dimensión de triage...")
    triage_meta = [
        ('I',   '#FF0000', 0),
        ('II',  '#FF8C00', 30),
        ('III', '#FFFF00', 60),
        ('IV',  '#008000', 120),
        ('V',   '#0000FF', 360),
    ]
    dim_tri = pd.DataFrame(triage_meta, columns=['nivel','color_norma','limite_minutos'])
    dim_tri['triage_id'] = range(1, len(dim_tri) + 1)
    dim_tri.to_sql('Dim_Triage', conn, if_exists='append', index=False)
    mapa_tri = dict(zip(dim_tri['nivel'], dim_tri['triage_id']))
    logging.info(f"✅ [Dim_Triage] 5 niveles cargados — {_elapsed(t0)}")

    # ── Dim_Eps ───────────────────────────────────────────────────────────────
    t0 = time.time()
    logging.info("🔄 [Dim_Eps] Construyendo dimensión de EPS (unión de ambos datasets)...")
    eps_morb   = morb['EAPB'].dropna().unique().tolist()
    eps_triage = tri['Nom_Admini'].dropna().unique().tolist()
    todas_eps  = list(set(eps_morb + eps_triage))
    dim_eps = pd.DataFrame({'nombre': todas_eps})
    dim_eps['eps_id'] = range(1, len(dim_eps) + 1)
    dim_eps.to_sql('Dim_Eps', conn, if_exists='append', index=False)
    mapa_eps = dict(zip(dim_eps['nombre'], dim_eps['eps_id']))
    logging.info(f"✅ [Dim_Eps] {len(dim_eps):,} EPS únicas — {_elapsed(t0)}")

    # ── Dim_Regimen ───────────────────────────────────────────────────────────
    t0 = time.time()
    logging.info("🔄 [Dim_Regimen] Construyendo dimensión de régimen...")
    dim_reg, mapa_reg = make_dim(morb['REGIMEN'], 'regimen_id')
    dim_reg.to_sql('Dim_Regimen', conn, if_exists='append', index=False)
    logging.info(f"✅ [Dim_Regimen] {len(dim_reg):,} regímenes — {_elapsed(t0)}")

    # ── Dim_Ubicacion ─────────────────────────────────────────────────────────
    t0 = time.time()
    logging.info("🔄 [Dim_Ubicacion] Construyendo dimensión de ubicación...")
    dim_ubi = morb[['DEPARTAMENTO','PROCEDENCIA']].drop_duplicates().rename(
        columns={'DEPARTAMENTO':'departamento','PROCEDENCIA':'municipio'})
    dim_ubi['ubicacion_id'] = range(1, len(dim_ubi) + 1)
    dim_ubi.to_sql('Dim_Ubicacion', conn, if_exists='append', index=False)
    mapa_ubi = dict(zip(
        dim_ubi.apply(lambda r: f"{r['departamento']}|{r['municipio']}", axis=1),
        dim_ubi['ubicacion_id']
    ))
    logging.info(f"✅ [Dim_Ubicacion] {len(dim_ubi):,} combinaciones depto/municipio — {_elapsed(t0)}")

    # ── Dim_Edad ──────────────────────────────────────────────────────────────
    t0 = time.time()
    logging.info("🔄 [Dim_Edad] Construyendo dimensión de edad...")
    dim_edad = morb[['EDAD_AÑOS','RANGO_EDAD']].drop_duplicates().rename(
        columns={'EDAD_AÑOS':'edad_anos','RANGO_EDAD':'rango'})
    dim_edad['edad_id'] = range(1, len(dim_edad) + 1)
    dim_edad.to_sql('Dim_Edad', conn, if_exists='append', index=False)
    mapa_edad = dict(zip(
        dim_edad.apply(lambda r: f"{r['edad_anos']}|{r['rango']}", axis=1),
        dim_edad['edad_id']
    ))
    logging.info(f"✅ [Dim_Edad] {len(dim_edad):,} combinaciones edad/rango — {_elapsed(t0)}")

    # ── Dim_Diagnostico ───────────────────────────────────────────────────────
    t0 = time.time()
    logging.info("🔄 [Dim_Diagnostico] Construyendo dimensión de diagnósticos...")
    dim_diag = morb[['DIAGNOSTICO','NOMBRE_DIAGNOSTICO']].dropna().drop_duplicates(
        subset=['NOMBRE_DIAGNOSTICO']).rename(
        columns={'DIAGNOSTICO':'codigo','NOMBRE_DIAGNOSTICO':'nombre'})
    dim_diag['diagnostico_id'] = range(1, len(dim_diag) + 1)
    dim_diag.to_sql('Dim_Diagnostico', conn, if_exists='append', index=False)
    mapa_diag = dict(zip(dim_diag['nombre'], dim_diag['diagnostico_id']))
    logging.info(f"✅ [Dim_Diagnostico] {len(dim_diag):,} diagnósticos únicos — {_elapsed(t0)}")

    # ── Dim_Sexo ──────────────────────────────────────────────────────────────
    t0 = time.time()
    logging.info("🔄 [Dim_Sexo] Construyendo dimensión de sexo...")
    dim_sexo, mapa_sexo = make_dim(morb['SEXO'], 'sexo_id', 'sexo')
    dim_sexo.to_sql('Dim_Sexo', conn, if_exists='append', index=False)
    logging.info(f"✅ [Dim_Sexo] {len(dim_sexo):,} categorías — {_elapsed(t0)}")

    # ── Dim_Ips ───────────────────────────────────────────────────────────────
    t0 = time.time()
    logging.info("🔄 [Dim_Ips] Construyendo dimensión de IPS...")
    dim_ips = tri[['Ips','Red']].drop_duplicates().rename(
        columns={'Ips':'nombre','Red':'red'})
    dim_ips['ips_id'] = range(1, len(dim_ips) + 1)
    dim_ips.to_sql('Dim_Ips', conn, if_exists='append', index=False)
    mapa_ips = dict(zip(
        dim_ips.apply(lambda r: f"{r['nombre']}|{r['red']}", axis=1),
        dim_ips['ips_id']
    ))
    logging.info(f"✅ [Dim_Ips] {len(dim_ips):,} IPS únicas — {_elapsed(t0)}")

    # ── Fact_Morbilidad ───────────────────────────────────────────────────────
    t0 = time.time()
    logging.info("🔄 [Fact_Morbilidad] Construyendo tabla de hechos de morbilidad...")
    fm = morb.copy()
    fm['fecha_id']       = fm['FECHA_ATENCION'].astype(str).map(mapa_fecha)
    fm['eps_id']         = fm['EAPB'].map(mapa_eps)
    fm['regimen_id']     = fm['REGIMEN'].map(mapa_reg)
    fm['ubicacion_id']   = fm.apply(lambda r: mapa_ubi.get(f"{r['DEPARTAMENTO']}|{r['PROCEDENCIA']}", 1), axis=1)
    fm['edad_id']        = fm.apply(lambda r: mapa_edad.get(f"{r['EDAD_AÑOS']}|{r['RANGO_EDAD']}", 1), axis=1)
    fm['diagnostico_id'] = fm['NOMBRE_DIAGNOSTICO'].map(mapa_diag)
    fm['sexo_id']        = fm['SEXO'].map(mapa_sexo)
    fm['atencion_count'] = 1

    cols_fm = ['fecha_id','eps_id','regimen_id','ubicacion_id','edad_id',
               'diagnostico_id','sexo_id','atencion_count']
    fm[cols_fm].to_sql('Fact_Morbilidad', conn, if_exists='append', index=False)
    logging.info(f"✅ [Fact_Morbilidad] {len(fm):,} registros cargados — {_elapsed(t0)}")

    # ── Fact_Triage ───────────────────────────────────────────────────────────
    t0 = time.time()
    logging.info("🔄 [Fact_Triage] Construyendo tabla de hechos de triage...")
    ft = tri.copy()
    ft['fecha_id']          = ft['Fecha_Solo'].astype(str).map(mapa_fecha)
    ft['hora_id']           = ft['Hora_Solo'].map(lambda h: mapa_hora.get(int(h) if pd.notna(h) else 8, 9))
    ft['triage_id']         = ft['Triage'].map(mapa_tri)
    ft['ips_id']            = ft.apply(lambda r: mapa_ips.get(f"{r['Ips']}|{r['Red']}", 1), axis=1)
    ft['eps_id']            = ft['Nom_Admini'].map(mapa_eps)
    ft['tiempo_espera_min'] = ft['Tiempo_Espera_Min']
    ft['supera_norma']      = ft['Supera_Norma'].astype(int)
    ft['atencion_count']    = 1

    cols_ft = ['fecha_id','hora_id','triage_id','ips_id','eps_id',
               'tiempo_espera_min','supera_norma','atencion_count']
    ft[cols_ft].to_sql('Fact_Triage', conn, if_exists='append', index=False)
    logging.info(f"✅ [Fact_Triage] {len(ft):,} registros cargados — {_elapsed(t0)}")

    conn.commit()
    conn.close()

    logging.info("=" * 60)
    logging.info(f"🏁 [ETL] Proceso completado exitosamente — Tiempo total: {_elapsed(t_total)}")
    logging.info("=" * 60)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    t_inicio = time.time()
    logging.info("=" * 60)
    logging.info("🚀 [ETL] Iniciando proceso ETL — Sistema de Urgencias")
    logging.info("=" * 60)

    if not os.path.exists(MORB_PATH):
        logging.error("❌ Archivos CSV no encontrados. Verifica las rutas.")
    else:
        # ── Lectura de archivos ───────────────────────────────────────────────
        t0 = time.time()
        logging.info("🔄 [Lectura] Cargando archivo de Morbilidad...")
        morb = pd.read_csv(MORB_PATH)
        logging.info(f"✅ [Lectura] Morbilidad: {len(morb):,} registros — {_elapsed(t0)}")

        t0 = time.time()
        logging.info("🔄 [Lectura] Cargando archivo de Triage...")
        tri = pd.read_csv(TRIAGE_PATH) if os.path.exists(TRIAGE_PATH) else pd.DataFrame()
        if not tri.empty:
            logging.info(f"✅ [Lectura] Triage: {len(tri):,} registros — {_elapsed(t0)}")
        else:
            logging.warning("⚠️  Archivo de Triage no encontrado. Se omitirá.")

        # ── Limpieza ──────────────────────────────────────────────────────────
        morb = clean_morbilidad(morb)
        if not tri.empty:
            tri = clean_triage(tri)

        # ── Carga ─────────────────────────────────────────────────────────────
        load_to_db(morb, tri)

        logging.info(f"⏱  Tiempo total del proceso ETL: {_elapsed(t_inicio)}")
