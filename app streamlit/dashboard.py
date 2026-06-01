import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "urgencias.db")

st.set_page_config(page_title="Dashboard Urgencias", layout="wide", page_icon="🏥")

COLORES_TRIAGE = {
    'I': '#FF0000', 'II': '#FF8C00', 'III': '#FFFF00', 'IV': '#008000', 'V': '#0000FF'
}

# ── Carga de datos ────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_morbilidad():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT f.fecha, f.dia_semana, f.mes, f.anio, f.trimestre,
               e.nombre  AS eps,
               r.nombre  AS regimen,
               u.departamento, u.municipio,
               ed.edad_anos, ed.rango AS rango_edad,
               d.codigo  AS cod_diagnostico,
               d.nombre  AS diagnostico,
               s.sexo,
               fm.atencion_count
        FROM Fact_Morbilidad fm
        JOIN Dim_Fecha       f  ON fm.fecha_id      = f.fecha_id
        JOIN Dim_Eps         e  ON fm.eps_id         = e.eps_id
        JOIN Dim_Regimen     r  ON fm.regimen_id     = r.regimen_id
        JOIN Dim_Ubicacion   u  ON fm.ubicacion_id   = u.ubicacion_id
        JOIN Dim_Edad        ed ON fm.edad_id        = ed.edad_id
        JOIN Dim_Diagnostico d  ON fm.diagnostico_id = d.diagnostico_id
        JOIN Dim_Sexo        s  ON fm.sexo_id        = s.sexo_id
    """, conn)
    conn.close()
    return df

@st.cache_data(ttl=3600)
def load_triage():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT f.fecha, f.dia_semana, f.mes, f.anio,
               h.hora,
               t.nivel        AS triage,
               t.color_norma,
               t.limite_minutos,
               i.nombre       AS ips,
               i.red,
               e.nombre       AS eps,
               ft.tiempo_espera_min,
               ft.supera_norma,
               ft.atencion_count
        FROM Fact_Triage ft
        JOIN Dim_Fecha   f  ON ft.fecha_id  = f.fecha_id
        JOIN Dim_Hora    h  ON ft.hora_id   = h.hora_id
        JOIN Dim_Triage  t  ON ft.triage_id = t.triage_id
        JOIN Dim_Ips     i  ON ft.ips_id    = i.ips_id
        JOIN Dim_Eps     e  ON ft.eps_id    = e.eps_id
    """, conn)
    conn.close()
    return df

morb_all = load_morbilidad()
tri_all  = load_triage()

if morb_all.empty and tri_all.empty:
    st.error("No se encontraron datos. Ejecuta primero el ETL.")
    st.stop()

# ── Sidebar: navegación principal ────────────────────────────────────────────
st.sidebar.title("🏥 Urgencias")
vista = st.sidebar.radio(
    "Selecciona vista",
    ["🚨 Triage", "📋 Morbilidad"],
    label_visibility="collapsed"
)
st.sidebar.divider()

# ─────────────────────────────────────────────────────────────────────────────
# VISTA MORBILIDAD
# ─────────────────────────────────────────────────────────────────────────────
if vista == "📋 Morbilidad":

    # Filtros específicos de morbilidad
    st.sidebar.subheader("Filtros")
    anios = sorted(morb_all['anio'].dropna().unique().tolist())
    sel_anio = st.sidebar.multiselect("Año", anios, default=anios)

    eps_list = sorted(morb_all['eps'].dropna().unique().tolist())
    sel_eps  = st.sidebar.multiselect("EPS", eps_list, default=eps_list)

    reg_list = sorted(morb_all['regimen'].dropna().unique().tolist())
    sel_reg  = st.sidebar.multiselect("Régimen", reg_list, default=reg_list)

    morb = morb_all[
        morb_all['anio'].isin(sel_anio) &
        morb_all['eps'].isin(sel_eps) &
        morb_all['regimen'].isin(sel_reg)
    ].copy()

    # ── KPIs ─────────────────────────────────────────────────────────────────
    st.title("📋 Morbilidad — Atención de Urgencias")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Atenciones",  f"{len(morb):,}")
    k2.metric("EPS Principal",     morb['eps'].mode()[0] if not morb.empty else "—")
    k3.metric("Régimen Principal", morb['regimen'].mode()[0] if not morb.empty else "—")
    subs_pct = len(morb[morb['regimen'] == 'SUBSIDIADO']) / len(morb) * 100 if not morb.empty else 0
    k4.metric("% Subsidiado",      f"{subs_pct:.1f}%")
    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(["📊 General", "👥 Demografía", "🩺 Diagnósticos", "🌍 Geografía"])

    # ── General ───────────────────────────────────────────────────────────────
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            reg = morb.groupby('regimen').size().reset_index(name='Cantidad')
            reg['Porcentaje'] = (reg['Cantidad'] / reg['Cantidad'].sum() * 100).round(2)
            fig = px.bar(reg.sort_values('Cantidad', ascending=True),
                         x='Cantidad', y='regimen', orientation='h',
                         text='Cantidad', color='Cantidad',
                         color_continuous_scale='Magma',
                         title="Carga por Régimen de Salud",
                         custom_data=['Porcentaje'])
            fig.update_traces(
                texttemplate='%{text:,} (%{customdata[0]:.1f}%)',
                textposition='outside'
            )
            fig.update_layout(
                xaxis=dict(range=[0, reg['Cantidad'].max() * 1.35]),
                margin=dict(r=20)
            )
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            top5 = morb['eps'].value_counts().head(5)
            otras = morb['eps'].value_counts().iloc[5:].sum()
            pie_data = pd.concat([top5, pd.Series({'OTRAS': otras})])
            fig = px.pie(values=pie_data.values, names=pie_data.index,
                         title="Distribución por EPS (Top 5 + Otras)", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

    # ── Demografía ────────────────────────────────────────────────────────────
    with tab2:
        COLOR_F = '#f08080'
        COLOR_M = '#4682b4'

        st.subheader("Pirámide Poblacional (Edad vs Sexo)")
        order_edad = ['0-5 años', '6-17 años', '18-40 años', '41-60 años', '>60 años']
        pyr = morb.groupby(['rango_edad', 'sexo']).size().unstack(fill_value=0)
        pyr = pyr.reindex(order_edad, fill_value=0)

        f_vals = pyr.get('F', pd.Series(0, index=pyr.index))
        m_vals = pyr.get('M', pd.Series(0, index=pyr.index))
        total_vals = f_vals + m_vals

        fig_pyr = go.Figure()
        fig_pyr.add_trace(go.Bar(
            name='Femenino', x=pyr.index, y=f_vals,
            marker_color=COLOR_F,
            text=[f"F: {v:,}" for v in f_vals],
            textposition='inside', insidetextanchor='middle'
        ))
        fig_pyr.add_trace(go.Bar(
            name='Masculino', x=pyr.index, y=m_vals,
            marker_color=COLOR_M,
            text=[f"M: {v:,}" for v in m_vals],
            textposition='inside', insidetextanchor='middle'
        ))
        # Etiqueta de total encima de cada barra
        for i, (rango, total) in enumerate(zip(pyr.index, total_vals)):
            fig_pyr.add_annotation(
                x=rango, y=total, text=f"Total: {int(total):,}",
                showarrow=False, yanchor='bottom', font=dict(size=11, color='black')
            )
        fig_pyr.update_layout(
            barmode='stack',
            title="Pirámide Poblacional de Urgencias: Rango de Edad vs Sexo",
            yaxis_title='Cantidad de Atenciones',
            xaxis_title='Rango de Edad',
            legend_title='Sexo'
        )
        st.plotly_chart(fig_pyr, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            sexo_cnt = morb['sexo'].value_counts().reset_index()
            sexo_cnt.columns = ['Sexo', 'Cantidad']
            fig = px.pie(sexo_cnt, names='Sexo', values='Cantidad',
                         color='Sexo',
                         title="Distribución por Sexo", hole=0.4,
                         color_discrete_map={'F': COLOR_F, 'M': COLOR_M})
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            edad_cnt = morb.groupby('rango_edad').size().reindex(order_edad, fill_value=0).reset_index()
            edad_cnt.columns = ['Rango', 'Cantidad']
            fig = px.bar(edad_cnt, x='Rango', y='Cantidad', text='Cantidad',
                         title="Atenciones por Rango de Edad")
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True)

    # ── Diagnósticos ──────────────────────────────────────────────────────────
    with tab3:
        st.subheader("Top 10 Diagnósticos más Frecuentes")
        top10 = morb['diagnostico'].value_counts().head(10).reset_index()
        top10.columns = ['Diagnóstico', 'Cantidad']
        total_diag = len(morb)
        top10['Porcentaje'] = (top10['Cantidad'] / total_diag * 100).round(1)
        top10 = top10.sort_values('Cantidad', ascending=True)
        fig = px.bar(top10, x='Cantidad', y='Diagnóstico', orientation='h',
                     text='Cantidad', color='Cantidad', color_continuous_scale='Reds',
                     title="Motivos de Consulta Principales",
                     custom_data=['Porcentaje'])
        fig.update_traces(
            texttemplate='%{text:,} (%{customdata[0]:.1f}%)',
            textposition='outside'
        )
        fig.update_layout(xaxis=dict(range=[0, top10['Cantidad'].max() * 1.4]))
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Contraste Clínico por Ciclo de Vida")

        rangos_adultos = ['6-17 años', '18-40 años', '41-60 años']
        grupos = [
            ('0-5 años',      morb[morb['rango_edad'] == '0-5 años'],               'Blues'),
            ('>5 y <60 años', morb[morb['rango_edad'].isin(rangos_adultos)],         'Greens'),
            ('>60 años',      morb[morb['rango_edad'] == '>60 años'],                'Oranges'),
        ]

        def bar_ciclo(sub, titulo, palette, total):
            top = sub['diagnostico'].value_counts().head(5).reset_index()
            top.columns = ['Diagnóstico', 'Cantidad']
            top['Porcentaje'] = (top['Cantidad'] / total * 100).round(1)
            top = top.sort_values('Cantidad', ascending=True)
            fig = px.bar(top, x='Cantidad', y='Diagnóstico', orientation='h',
                         title=f"Top 5: {titulo}",
                         text='Cantidad', color='Cantidad',
                         color_continuous_scale=palette,
                         custom_data=['Porcentaje'])
            fig.update_traces(
                texttemplate='%{text:,} (%{customdata[0]:.1f}%)',
                textposition='outside'
            )
            fig.update_layout(xaxis=dict(range=[0, top['Cantidad'].max() * 1.5]),
                              coloraxis_showscale=False)
            return fig

        total_morb = len(morb)

        # Fila 1: primeros dos grupos
        c1, c2 = st.columns(2)
        for col, (titulo, sub, palette) in zip([c1, c2], grupos[:2]):
            if not sub.empty:
                col.plotly_chart(bar_ciclo(sub, titulo, palette, total_morb), use_container_width=True)
            else:
                col.warning(f"Sin datos para {titulo}")

        # Fila 2: tercer grupo alineado a la izquierda
        c3, _ = st.columns(2)
        titulo, sub, palette = grupos[2]
        if not sub.empty:
            c3.plotly_chart(bar_ciclo(sub, titulo, palette, total_morb), use_container_width=True)
        else:
            c3.warning(f"Sin datos para {titulo}")

    # ── Geografía ─────────────────────────────────────────────────────────────
    with tab4:
        st.subheader("Top 10 Municipios de Procedencia (Pareto)")
        geo = morb.groupby(['municipio', 'departamento']).size().reset_index(name='Atenciones')
        geo_top = geo.sort_values('Atenciones', ascending=False).head(10)
        total_geo = len(morb)
        geo_top['Porcentaje'] = (geo_top['Atenciones'] / total_geo * 100).round(1)
        # Ordenar ascendente → Plotly dibuja de abajo hacia arriba, mayor queda en la cima
        geo_top = geo_top.sort_values('Atenciones', ascending=True)
        fig = px.bar(geo_top, x='Atenciones', y='municipio', color='departamento',
                     orientation='h', title="Demanda Geográfica Concentrada",
                     text='Atenciones', custom_data=['Porcentaje'],
                     category_orders={'municipio': geo_top['municipio'].tolist()})
        fig.update_traces(
            texttemplate='%{text:,} (%{customdata[0]:.1f}%)',
            textposition='outside'
        )
        fig.update_layout(
            xaxis=dict(range=[0, geo_top['Atenciones'].max() * 1.4]),
            yaxis=dict(autorange='reversed')
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Atenciones por Departamento")
        dept = morb.groupby('departamento').size().reset_index(name='Atenciones')
        dept = dept.sort_values('Atenciones', ascending=False)
        fig = px.bar(dept, x='departamento', y='Atenciones', text='Atenciones',
                     title="Distribución por Departamento de Procedencia")
        fig.update_traces(textposition='outside')
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# VISTA TRIAGE
# ─────────────────────────────────────────────────────────────────────────────
else:

    # Filtros específicos de triage
    st.sidebar.subheader("Filtros")
    anios_t = sorted(tri_all['anio'].dropna().unique().tolist())
    sel_anio_t = st.sidebar.multiselect("Año", anios_t, default=anios_t)

    tri_list = sorted(tri_all['triage'].dropna().unique().tolist())
    sel_tri  = st.sidebar.multiselect("Nivel Triage", tri_list, default=tri_list)

    ips_list = sorted(tri_all['ips'].dropna().unique().tolist())
    sel_ips  = st.sidebar.multiselect("IPS", ips_list, default=ips_list)

    tri = tri_all[
        tri_all['anio'].isin(sel_anio_t) &
        tri_all['triage'].isin(sel_tri) &
        tri_all['ips'].isin(sel_ips)
    ].copy()

    # ── KPIs ─────────────────────────────────────────────────────────────────
    st.title("🚨 Triage — Tiempos de Espera y Cumplimiento")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Registros",       f"{len(tri):,}")
    k2.metric("Tiempo Espera Prom.",   f"{tri['tiempo_espera_min'].mean():.1f} min" if not tri.empty else "—")
    k3.metric("Mediana Espera",        f"{tri['tiempo_espera_min'].median():.1f} min" if not tri.empty else "—")
    k4.metric("% Incumplimiento",      f"{tri['supera_norma'].mean()*100:.1f}%" if not tri.empty else "—")
    urgentes = len(tri[tri['triage'].isin(['I','II'])]) / len(tri) * 100 if not tri.empty else 0
    k5.metric("% Triage I+II",         f"{urgentes:.1f}%")
    st.divider()

    tab1, tab2, tab3 = st.tabs(["📊 Distribución", "⏱ Tiempos de Espera", "🏨 IPS & Red"])

    # ── Distribución ──────────────────────────────────────────────────────────
    with tab1:
        # Distribución por nivel de triage — ordenada I→V con etiquetas
        nivel_order = ['I', 'II', 'III', 'IV', 'V']
        tri_cnt = (tri['triage'].value_counts()
                   .reindex(nivel_order, fill_value=0)
                   .reset_index())
        tri_cnt.columns = ['triage', 'count']
        total_tri = tri_cnt['count'].sum()
        tri_cnt['pct'] = (tri_cnt['count'] / total_tri * 100).round(1)
        tri_cnt['label'] = tri_cnt.apply(lambda r: f"{r['count']:,}<br>{r['pct']}%", axis=1)

        fig = px.pie(tri_cnt, names='triage', values='count',
                     color='triage', color_discrete_map=COLORES_TRIAGE,
                     title="Distribución por Nivel de Triage",
                     category_orders={'triage': nivel_order})
        fig.update_traces(
            textposition='outside',
            texttemplate='<b>Triage %{label}</b><br>%{value:,} (%{percent:.1%})',
            sort=False
        )
        fig.update_layout(showlegend=True,
                          legend=dict(traceorder='normal',
                                      title='Nivel',
                                      itemsizing='constant'))
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Carga Promedio por Día de la Semana")
        day_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
        day_map   = {'Monday':'Lunes','Tuesday':'Martes','Wednesday':'Miércoles',
                     'Thursday':'Jueves','Friday':'Viernes','Saturday':'Sábado','Sunday':'Domingo'}
        diario = tri.groupby('fecha').size().reset_index(name='Total')
        diario['dia'] = pd.to_datetime(diario['fecha']).dt.day_name()
        prom = diario.groupby('dia')['Total'].mean().reset_index()
        prom['dia_es'] = prom['dia'].map(day_map)
        prom = prom.set_index('dia').reindex(day_order).reset_index()
        fig = px.bar(prom, x='dia_es', y='Total', text='Total',
                     title="Promedio Diario de Atenciones por Día de la Semana",
                     labels={'Total': 'Promedio Atenciones', 'dia_es': 'Día'})
        fig.update_traces(texttemplate='%{text:.1f}', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Atenciones por Hora del Día y Nivel de Triage")
        num_dias  = tri['fecha'].nunique()
        hour_tri  = tri.groupby(['hora', 'triage']).size().unstack(fill_value=0)
        # Asegurar orden I→V y las 24 horas
        hour_tri  = hour_tri.reindex(columns=nivel_order, fill_value=0)
        hour_tri  = hour_tri.reindex(range(24), fill_value=0)
        hour_avg  = (hour_tri / num_dias).round(2) if num_dias > 0 else hour_tri

        fig = px.bar(hour_avg, x=hour_avg.index, y=hour_avg.columns,
                     color_discrete_map=COLORES_TRIAGE, barmode='stack',
                     title="Promedio de Atenciones por Hora y Nivel de Triage",
                     labels={'value': 'Promedio Atenciones', 'hora': 'Hora', 'variable': 'Triage'})
        fig.update_layout(xaxis=dict(tickmode='linear', dtick=1))
        st.plotly_chart(fig, use_container_width=True)

        # Tabla de datos y convenciones — Triage como filas, horas como columnas
        st.markdown("**Tabla de datos — Promedio diario por hora y nivel de triage**")
        tabla_display = hour_avg.T.copy()
        tabla_display.index.name = 'Triage'
        tabla_display.columns = [f"{h:02d}:00" for h in tabla_display.columns]
        tabla_display = tabla_display.reset_index()
        st.dataframe(tabla_display, use_container_width=True, hide_index=True)

        st.markdown("**Convenciones de color — Norma colombiana de triage**")
        conv_data = {
            'Nivel': ['I', 'II', 'III', 'IV', 'V'],
            'Color': ['🔴 Rojo', '🟠 Naranja', '🟡 Amarillo', '🟢 Verde', '🔵 Azul'],
            'Descripción': ['Reanimación', 'Emergencia', 'Urgencia', 'Menos urgente', 'No urgente'],
            'Límite normativo': ['Inmediato (0 min)', '≤ 30 min', '≤ 60 min', '≤ 120 min', '≤ 360 min'],
        }
        st.dataframe(pd.DataFrame(conv_data), use_container_width=True, hide_index=True)

    # ── Tiempos de Espera ─────────────────────────────────────────────────────
    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            wait = tri.groupby('triage')['tiempo_espera_min'].agg(
                Promedio='mean', Mediana='median', Total='count'
            ).reset_index().round(1)
            fig = px.bar(wait, x='triage', y='Promedio', text='Promedio',
                         color='triage', color_discrete_map=COLORES_TRIAGE,
                         title="Tiempo Promedio de Espera por Triage (min)")
            fig.update_traces(texttemplate='%{text:.1f}', textposition='outside')
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            # Cumplimiento normativo con etiquetas de datos
            norma = tri.groupby('triage').agg(
                Total=('atencion_count', 'sum'),
                Supera=('supera_norma', 'sum')
            ).reset_index()
            norma['Cumple'] = norma['Total'] - norma['Supera']
            norma['% Incumplimiento'] = (norma['Supera'] / norma['Total'] * 100).round(1)
            norma['% Cumple'] = (norma['Cumple'] / norma['Total'] * 100).round(1)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='Cumple', x=norma['triage'], y=norma['Cumple'],
                marker_color='#2ecc71',
                text=[f"{v:,}<br>({p}%)" for v, p in zip(norma['Cumple'], norma['% Cumple'])],
                textposition='inside', insidetextanchor='middle'
            ))
            fig.add_trace(go.Bar(
                name='Supera norma', x=norma['triage'], y=norma['Supera'],
                marker_color='#e74c3c',
                text=[f"{v:,}<br>({p}%)" for v, p in zip(norma['Supera'], norma['% Incumplimiento'])],
                textposition='inside', insidetextanchor='middle'
            ))
            fig.update_layout(barmode='stack',
                              title="Cumplimiento vs Incumplimiento Normativo",
                              xaxis_title='Triage', yaxis_title='Atenciones',
                              legend_title='Estado')
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Tabla Comparativa: Promedio Interno vs Límite Normativo")
        limites = {'I': 0, 'II': 30, 'III': 60, 'IV': 120, 'V': 360}

        # Calcular promedio interno por triage y pacientes sobre ese promedio
        def sobre_promedio(grupo):
            prom = grupo['tiempo_espera_min'].mean()
            sobre = (grupo['tiempo_espera_min'] > prom).sum()
            return pd.Series({'Sobre_Promedio': sobre})

        sp = tri.groupby('triage').apply(sobre_promedio).reset_index()

        resumen = tri.groupby('triage').agg(
            Total_Atenciones=('tiempo_espera_min', 'count'),
            Promedio_Min=('tiempo_espera_min', 'mean'),
            Supera_Norma=('supera_norma', 'sum')
        ).reset_index().round(1)
        resumen = resumen.merge(sp, on='triage')
        resumen['Limite_Norma_Min']       = resumen['triage'].map(limites)
        resumen['% Incumplimiento_Norma'] = (resumen['Supera_Norma'] / resumen['Total_Atenciones'] * 100).round(1)
        resumen['% Sobre_Promedio']       = (resumen['Sobre_Promedio'] / resumen['Total_Atenciones'] * 100).round(1)

        resumen = resumen.rename(columns={
            'triage':                  'Triage',
            'Total_Atenciones':        'Total Atenciones',
            'Promedio_Min':            'Promedio Espera (min)',
            'Limite_Norma_Min':        'Límite Norma (min)',
            'Supera_Norma':            'Supera Norma',
            '% Incumplimiento_Norma':  '% Incumplimiento Norma',
            'Sobre_Promedio':          'Sobre Promedio Interno',
            '% Sobre_Promedio':        '% Sobre Promedio Interno',
        })
        cols_tabla = ['Triage', 'Total Atenciones', 'Promedio Espera (min)',
                      'Límite Norma (min)', 'Supera Norma', '% Incumplimiento Norma',
                      'Sobre Promedio Interno', '% Sobre Promedio Interno']
        st.dataframe(resumen[cols_tabla], use_container_width=True, hide_index=True)

    # ── IPS & Red ─────────────────────────────────────────────────────────────
    with tab3:
        c1, c2 = st.columns(2)
        with c1:
            ips_cnt = tri.groupby(['ips', 'red']).size().reset_index(name='Atenciones')
            fig = px.bar(ips_cnt, x='Atenciones', y='ips', color='red',
                         orientation='h', title="Atenciones por IPS y Red",
                         text='Atenciones')
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            red_cnt = tri.groupby('red').size().reset_index(name='Atenciones')
            fig = px.pie(red_cnt, names='red', values='Atenciones',
                         title="Distribución por Red", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Tiempo de Espera Promedio por IPS")
        ips_wait = tri.groupby('ips')['tiempo_espera_min'].mean().reset_index()
        ips_wait.columns = ['IPS', 'Promedio (min)']
        ips_wait = ips_wait.sort_values('Promedio (min)', ascending=True)
        fig = px.bar(ips_wait, x='Promedio (min)', y='IPS', orientation='h',
                     text='Promedio (min)', title="Tiempo Promedio de Espera por IPS")
        fig.update_traces(texttemplate='%{text:.1f}', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("Dashboard Urgencias · Modelo Estrella SQLite · ETL Python · Streamlit")
