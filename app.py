import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import json
from utils import *

st.set_page_config(page_title="Sistema AML", layout="wide", page_icon="🔍")

DB_PATH = 'aml_data.db'

def init_db():
    if 'db_initialized' not in st.session_state:
        import os
        if not os.path.exists(DB_PATH):
            import db_setup
            db_setup.setup_database(DB_PATH)
        st.session_state.db_initialized = True

def get_connection():
    return sqlite3.connect(DB_PATH)

init_db()

st.sidebar.title("🔍 Sistema AML")

menu = st.sidebar.radio(
    "Menú Principal", 
    ["Inicio", "Cargar Datos", "Gestión de Casos", "Análisis de Patrones", "Reportes PDF"]
)

if menu == "Inicio":
    st.title("Sistema de Análisis Anti-Lavado de Dinero")
    st.markdown("### Bienvenido al Sistema de Análisis de la ")
    
    col1, col2, col3 = st.columns(3)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        total_cargas = cursor.execute("SELECT COUNT(*) FROM cargas").fetchone()[0]
        total_casos = cursor.execute("SELECT COUNT(*) FROM casos").fetchone()[0]
        total_transacciones = cursor.execute("SELECT COUNT(*) FROM transacciones").fetchone()[0]
        
        col1.metric("Cargas de Datos", total_cargas)
        col2.metric("Casos Activos", total_casos)
        col3.metric("Transacciones Totales", f"{total_transacciones:,}")
    except:
        st.warning("Base de datos vacía o no inicializada.")
    
    st.markdown("---")
    st.markdown("""
    ### Funcionalidades del Sistema
    - 📊 **Cargar Datos**: Importar archivos Excel (.xlsx) con datos financieros masivos.
    - 📁 **Gestión de Casos**: Crear y administrar casos de investigación.
    - 🔬 **Análisis de Patrones**: Ejecutar análisis especializados de detección.
    - 📄 **Reportes PDF**: Generar informes ejecutivos profesionales.
    """)
    
    conn.close()

elif menu == "Cargar Datos":
    st.title("📊 Carga de Datos")
    
    st.markdown("### Importar Archivo Excel")
    
    codigo_carga = st.text_input("Código de Carga (identificador único)", 
                                  placeholder="Ej: CARGA_2024_001")
    
    uploaded_file = st.file_uploader("Seleccionar archivo Excel", type=['xlsx'])
    
    if uploaded_file and codigo_carga:
        if st.button("Cargar Datos", type="primary"):
            progress_text = "Iniciando proceso de carga..."
            my_bar = st.progress(0, text=progress_text)
            
            try:
                conn = get_connection()
                cursor = conn.cursor()
                existe = cursor.execute("SELECT id_carga FROM cargas WHERE codigo_carga = ?", 
                                      (codigo_carga,)).fetchone()
                
                if existe:
                    st.error("Este código de carga ya existe. Use otro código.")
                    my_bar.empty()
                else:
                    with st.spinner("Leyendo archivo Excel (esto puede tomar unos minutos si el archivo es grande)..."):
                        df = pd.read_excel(uploaded_file, engine='openpyxl')
                    
                    columnas_requeridas = [
                        'CODUNICOCLI_13_enc', 'TIPO DE MARCA', 'DESTIPDOCUMENTO',
                        'DESTIPBANCA', 'SEGMENTO', 'ACT.ECONOMICA', 'Fecha', 'Monto', 'I / E'
                    ]
                    
                    faltantes = [col for col in columnas_requeridas if col not in df.columns]
                    
                    if faltantes:
                        st.error(f"Columnas faltantes: {', '.join(faltantes)}")
                        my_bar.empty()
                    else:
                        st.info(f"Archivo leído. Procesando {len(df):,} registros...")
                        
                        def update_bar(progreso):
                            my_bar.progress(progreso, text=f"Insertando registros en base de datos: {int(progreso*100)}%")
                        
                        id_carga = cargar_datos(df, codigo_carga, conn, progress_callback=update_bar)
                        
                        my_bar.progress(1.0, text="Finalizado!")
                        st.success(f"✅ Datos cargados exitosamente. ID de carga: {id_carga}")
                        st.balloons()
                        
                        st.markdown("### Vista previa de datos")
                        st.dataframe(df.head(10))
                
                conn.close()
                        
            except Exception as e:
                my_bar.empty()
                st.error(f"Error crítico al cargar datos: {str(e)}")
    
    st.markdown("---")
    st.markdown("### Cargas Existentes")
    
    conn = get_connection()
    try:
        df_cargas = pd.read_sql_query("""
            SELECT codigo_carga, fecha_carga, registros_totales 
            FROM cargas 
            ORDER BY fecha_carga DESC
        """, conn)
        
        if not df_cargas.empty:
            st.dataframe(df_cargas, use_container_width=True)
        else:
            st.info("No hay cargas registradas")
    except:
        st.info("No hay cargas registradas o error en tabla")
        
    conn.close()

elif menu == "Gestión de Casos":
    st.title("📁 Gestión de Casos")
    
    tab1, tab2 = st.tabs(["Crear Nuevo Caso", "Ver Casos Existentes"])
    
    with tab1:
        st.markdown("### Crear Nuevo Caso")
        
        nombre_caso = st.text_input("Nombre del Caso", placeholder="Ej: CASO_MINERIA_ILEGAL_2024")
        descripcion_caso = st.text_area("Descripción", placeholder="Descripción detallada del caso...")
        
        metodo_seleccion = st.radio("Método de selección de involucrados", 
                                    ["Por Código de Cliente", "Por Código de Carga"])
        
        conn = get_connection()
        
        if metodo_seleccion == "Por Código de Cliente":
            df_clientes = pd.read_sql_query("""
                SELECT DISTINCT codunicocli_13_enc, destipdocumento, destipbanca, act_economica
                FROM transacciones
                ORDER BY codunicocli_13_enc
            """, conn)
            
            if not df_clientes.empty:
                clientes_seleccionados = st.multiselect(
                    "Seleccionar clientes involucrados",
                    options=df_clientes['codunicocli_13_enc'].tolist(),
                    format_func=lambda x: f"{x[:16]}... ({df_clientes[df_clientes['codunicocli_13_enc']==x]['destipdocumento'].iloc[0]})"
                )
        else:
            df_cargas = pd.read_sql_query("SELECT codigo_carga FROM cargas", conn)
            
            if not df_cargas.empty:
                carga_seleccionada = st.selectbox("Seleccionar carga", 
                                                  df_cargas['codigo_carga'].tolist())
                
                if carga_seleccionada:
                    df_clientes_carga = pd.read_sql_query("""
                        SELECT DISTINCT t.codunicocli_13_enc
                        FROM transacciones t
                        INNER JOIN cargas c ON t.id_carga = c.id_carga
                        WHERE c.codigo_carga = ?
                    """, conn, params=[carga_seleccionada])
                    
                    clientes_seleccionados = df_clientes_carga['codunicocli_13_enc'].tolist()
                    st.info(f"Se agregarán {len(clientes_seleccionados)} clientes de esta carga")
        
        if nombre_caso and st.button("Crear Caso", type="primary"):
            try:
                cursor = conn.cursor()
                
                existe = cursor.execute("SELECT id_caso FROM casos WHERE nombre_caso = ?", 
                                      (nombre_caso,)).fetchone()
                
                if existe:
                    st.error("Ya existe un caso con este nombre")
                else:
                    cursor.execute("""
                        INSERT INTO casos (nombre_caso, descripcion) 
                        VALUES (?, ?)
                    """, (nombre_caso, descripcion_caso))
                    
                    id_caso = cursor.lastrowid
                    
                    if 'clientes_seleccionados' in locals() and clientes_seleccionados:
                        for cliente in clientes_seleccionados:
                            cursor.execute("""
                                INSERT INTO caso_involucrados (id_caso, codunicocli_13_enc)
                                VALUES (?, ?)
                            """, (id_caso, cliente))
                    
                    conn.commit()
                    st.success(f"✅ Caso creado exitosamente con {len(clientes_seleccionados) if 'clientes_seleccionados' in locals() else 0} involucrados")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Error al crear caso: {str(e)}")
        
        conn.close()
    
    with tab2:
        st.markdown("### Casos Existentes")
        
        conn = get_connection()
        df_casos = pd.read_sql_query("""
            SELECT c.id_caso, c.nombre_caso, c.descripcion, c.fecha_creacion,
                   COUNT(ci.codunicocli_13_enc) as num_involucrados
            FROM casos c
            LEFT JOIN caso_involucrados ci ON c.id_caso = ci.id_caso
            GROUP BY c.id_caso
            ORDER BY c.fecha_creacion DESC
        """, conn)
        
        if not df_casos.empty:
            for _, caso in df_casos.iterrows():
                with st.expander(f"📋 {caso['nombre_caso']} ({caso['num_involucrados']} involucrados)"):
                    st.write(f"**Descripción:** {caso['descripcion'] or 'Sin descripción'}")
                    st.write(f"**Fecha creación:** {caso['fecha_creacion']}")
                    
                    df_involucrados = pd.read_sql_query("""
                        SELECT ci.codunicocli_13_enc, t.destipdocumento, t.destipbanca, t.act_economica
                        FROM caso_involucrados ci
                        LEFT JOIN transacciones t ON ci.codunicocli_13_enc = t.codunicocli_13_enc
                        WHERE ci.id_caso = ?
                        GROUP BY ci.codunicocli_13_enc
                    """, conn, params=[caso['id_caso']])
                    
                    if not df_involucrados.empty:
                        st.dataframe(df_involucrados, use_container_width=True)
                    
                    if st.button(f"Eliminar caso", key=f"del_{caso['id_caso']}"):
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM casos WHERE id_caso = ?", (caso['id_caso'],))
                        conn.commit()
                        st.success("Caso eliminado")
                        st.rerun()
        else:
            st.info("No hay casos registrados")
        
        conn.close()

elif menu == "Análisis de Patrones":
    st.title("🔬 Análisis de Patrones")
    
    conn = get_connection()
    df_casos = pd.read_sql_query("SELECT id_caso, nombre_caso FROM casos", conn)
    
    if df_casos.empty:
        st.warning("No hay casos disponibles. Cree un caso primero.")
        conn.close()
    else:
        caso_seleccionado = st.selectbox("Seleccionar Caso", 
                                        df_casos['nombre_caso'].tolist())
        
        id_caso = df_casos[df_casos['nombre_caso'] == caso_seleccionado]['id_caso'].iloc[0]
        
        st.sidebar.markdown("### Filtros Generales")
        
        filtro_moneda = st.sidebar.selectbox("Moneda", ["AMBOS", "SOLES", "DOLARES"])
        filtro_tipo_doc = st.sidebar.selectbox("Tipo Documento", ["AMBOS", "DNI", "RUC"])

        # Obtener segmentos disponibles para el caso
        df_segmentos = pd.read_sql_query("""
            SELECT DISTINCT t.segmento 
            FROM transacciones t
            INNER JOIN caso_involucrados ci ON t.codunicocli_13_enc = ci.codunicocli_13_enc
            WHERE ci.id_caso = ?
            ORDER BY t.segmento
        """, conn, params=[int(id_caso)])
        
        segmentos_disponibles = sorted([s for s in df_segmentos['segmento'].dropna().unique() if s])
        filtro_segmento = st.sidebar.multiselect("Segmento", segmentos_disponibles, default=segmentos_disponibles)
        
        col1, col2 = st.sidebar.columns(2)
        filtro_monto_min = col1.number_input("Monto Mínimo", min_value=0.0, value=0.0)
        filtro_monto_max = col2.number_input("Monto Máximo", min_value=0.0, value=1000000.0)
        fecha_inicio_default = date(2016, 1, 1)

        filtro_fecha_min = st.sidebar.date_input(
            "Fecha Mínima",
            value=fecha_inicio_default
        )
        #filtro_fecha_min = st.sidebar.date_input("Fecha Mínima")
        filtro_fecha_max = st.sidebar.date_input("Fecha Máxima")
        
        filtros = {
            'moneda': filtro_moneda,
            'tipo_documento': filtro_tipo_doc,
            'segmento': filtro_segmento,
            'monto_min': filtro_monto_min,
            'monto_max': filtro_monto_max,
            'fecha_min': filtro_fecha_min.strftime('%Y-%m-%d') if filtro_fecha_min else None,
            'fecha_max': filtro_fecha_max.strftime('%Y-%m-%d') if filtro_fecha_max else None
        }
        
        df_caso = obtener_datos_caso(id_caso, conn, filtros)
        
        st.info(f"Total de transacciones en el caso: {len(df_caso):,}")
        
        tipo_analisis = st.selectbox("Seleccionar Tipo de Análisis", [
            "Top 10 General",
            "1. Detección de Falsos Transportistas",
            "2. Segmento Bancario vs Volumen",
            "3. Actividad Económica vs Efectivo",
            "4. Concentración de Efectivo por Agencia",
            "5. Pitufeo Digital (Yape/Plin)",
            "6. Retiros Hormiga en Cajeros",
            "7. Preferencia por Operador",
            "8. Red de Proveedores Comunes",
            "9. Cuentas Descartables",
            "10. Velocidad del Dinero",
            "11. Comportamiento por Marca",
            "12. Divisa por Delito",
            "13. Cuentas Puente",
            "14. Matriz Colusión Cliente-Operador",
            "15. Explosión de Pitufeo",
            "16. Minería de Texto en Glosas"
        ])
        
        agregar_reporte = False
        
        if tipo_analisis == "Top 10 General":
            st.markdown("### 📊 Top 10 - Análisis General")
            
            categoria = st.selectbox("Seleccionar Categoría", [
                "Agentes", "Actividades Económicas", "Canales", "Agencias",
                "Tipos de Operación (Grupo)", "Operadores", "Segmentos"
            ])
            
            if st.button("Generar Top 10"):
                mapeo_columnas = {
                    "Agentes": "canal",
                    "Actividades Económicas": "act_economica",
                    "Canales": "canal",
                    "Agencias": "agencia",
                    "Tipos de Operación (Grupo)": "grupo",
                    "Operadores": "operador",
                    "Segmentos": "segmento"
                }
                
                columna = mapeo_columnas[categoria]
                
                df_top = df_caso.groupby(columna).agg({
                    'monto': 'sum',
                    'id_transaccion': 'count'
                }).reset_index()
                
                df_top.columns = [categoria, 'Monto Total', 'Cantidad Operaciones']
                df_top = df_top.sort_values('Monto Total', ascending=False).head(10)
                
                df_soles = df_caso[df_caso['moneda'] == 'SOLES'].groupby(columna)['monto'].sum()
                df_dolares = df_caso[df_caso['moneda'] == 'DOLARES'].groupby(columna)['monto'].sum()
                
                df_top['Monto Soles'] = df_top[categoria].map(df_soles).fillna(0)
                df_top['Monto Dólares'] = df_top[categoria].map(df_dolares).fillna(0)
                
                st.dataframe(df_top, use_container_width=True)
                
                fig = px.bar(df_top, x=categoria, y='Monto Total',
                           title=f'Top 10 {categoria} por Monto Total',
                           color='Cantidad Operaciones',
                           color_continuous_scale='Viridis')
                st.plotly_chart(fig, use_container_width=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button("📥 Exportar Excel", 
                                     exportar_excel(df_top, "Top10"),
                                     file_name=f"top10_{categoria}.xlsx")
        
        elif tipo_analisis == "1. Detección de Falsos Transportistas":
            st.markdown("### 🚛 Detección de Falsos Transportistas/Constructores")
            
            col_kw, col_freq = st.columns([3, 1])
            
            with col_freq:
                st.markdown("##### 🔝 Glosas Frecuentes")
                # Obtener palabras frecuentes en glosas de egresos
                df_glosas = df_caso[df_caso['i_e'] == 'Egreso']['glosa_limpia'].value_counts().reset_index()
                df_glosas.columns = ['Glosa Completa', 'Cant']
                st.dataframe(df_glosas, use_container_width=True, height=400)

            with col_kw:
                # Pre-calcular tokens únicos para autocompletado 
                all_tokens = set()
                # Usar una muestra si es muy grande para no bloquear
                sample_glosas = df_caso[df_caso['i_e'] == 'Egreso']['glosa_limpia'].dropna().astype(str)
                # Tokenizar para sugerencias de palabras
                for g in sample_glosas: 
                    all_tokens.update(g.split())
                
                defaults = ["FERREYROS", "VOLVO", "SCANIA", "KOMATSU", "MAQUINARIA", "CATERPILLAR"]
                opciones_filtro = sorted(list(all_tokens.union(set(defaults))))
                
                keywords_sel = st.multiselect(
                    "Keywords de búsqueda (Selecciona o escribe)", 
                    options=opciones_filtro,
                    default=[]
                )
            
            if st.button("Analizar"):
                keywords_list = keywords_sel
                
                # Buscar en todos los egresos, sin filtrar por actividad económica inicial
                df_egresos = df_caso[df_caso['i_e'] == 'Egreso'].copy()
                
                # Identificar coincidencias
                df_egresos['match_keyword'] = df_egresos['glosa_limpia'].apply(
                    lambda x: any(kw in str(x) for kw in keywords_list) if pd.notna(x) else False
                )
                
                df_sospechosos = df_egresos[df_egresos['match_keyword']]
                
                if not df_sospechosos.empty:
                    st.warning(f"⚠️ Se encontraron {len(df_sospechosos)} transacciones coinciden con las palabras clave")
                    
                    # 1. Agrupar sospechosos por cliente
                    df_resumen_cliente = df_sospechosos.groupby('codunicocli_13_enc').agg({
                        'monto': 'sum',
                        'id_transaccion': 'count',
                        'act_economica': 'first', # Tomamos la primera actividad registrada
                        'glosa_limpia': lambda x: ', '.join(sorted(list(set(x)))) # Glosas únicas encontradas
                    }).reset_index()
                    df_resumen_cliente.rename(columns={'monto': 'Monto en Glosas Seleccionadas', 'id_transaccion': 'Cant. Ops'}, inplace=True)
                    
                    # 2. Calcular promedio general de montos "normales" para estos clientes (toda su historia)
                    clientes_sospechosos = df_resumen_cliente['codunicocli_13_enc'].unique()
                    df_historia_clientes = df_caso[df_caso['codunicocli_13_enc'].isin(clientes_sospechosos)]
                    
                    df_promedios = df_historia_clientes.groupby('codunicocli_13_enc')['monto'].mean().reset_index()
                    df_promedios.rename(columns={'monto': 'Promedio Monto General'}, inplace=True)
                    
                    # 3. Cruzar información
                    df_final = pd.merge(df_resumen_cliente, df_promedios, on='codunicocli_13_enc')
                    
                    # Reordenar columnas
                    cols = ['codunicocli_13_enc', 'act_economica', 'Monto en Glosas Seleccionadas', 'Cant. Ops', 'Promedio Monto General', 'glosa_limpia']
                    df_final = df_final[cols]
                    df_final.columns = ['Cliente', 'Actividad Económica', 'Monto en Glosas', 'Cant. Ops', 'Promedio General', 'Glosas Encontradas']
                    
                    st.markdown("### 📊 Clientes y Actividades Relacionadas")
                    st.dataframe(df_final, use_container_width=True)
                    
                    # Top Actividades Económicas
                    st.markdown("### 🏭 Top Actividades Económicas Detectadas")
                    df_top_act = df_final.groupby('Actividad Económica').agg({
                        'Monto en Glosas': 'sum',
                        'Cliente': 'count'
                    }).reset_index().sort_values('Monto en Glosas', ascending=False).head(10)
                    
                    fig = px.bar(df_top_act, x='Actividad Económica', y='Monto en Glosas',
                               color='Cliente',
                               title='Total Monto por Actividad (Glosas Seleccionadas)',
                               labels={'Cliente': 'Num Clientes'},
                               color_continuous_scale='Reds')
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("### 🔍 Detalle Transaccional")
                    st.dataframe(df_sospechosos[['codunicocli_13_enc', 'act_economica', 'fecha', 
                                                'glosa_limpia', 'monto', 'moneda']].head(50))
                    
                    agregar_reporte = st.checkbox("✅ Incluir en reporte PDF")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.download_button("📥 Exportar Resumen Clientes", 
                                         exportar_excel(df_final, "Resumen_Clientes_Glosas"),
                                         file_name="resumen_clientes_glosas.xlsx")
                    with col2:
                        st.download_button("📥 Exportar Detalle Transacciones", 
                                         exportar_excel(df_sospechosos, "Detalle_Glosas"),
                                         file_name="detalle_glosas.xlsx")
                else:
                    st.success("No se encontraron patrones sospechosos")
        
        elif tipo_analisis == "2. Segmento Bancario vs Volumen":
            st.markdown("### 💰 Segmento Bancario vs Volumen Transaccional")
            
            if st.button("Analizar"):
                df_personal = df_caso[df_caso['destipbanca'] == 'BANCA PERSONAL']
                df_alto_monto = df_personal[df_personal['monto'] > 5000]
                
                if not df_alto_monto.empty:
                    st.warning(f"⚠️ Se encontraron {len(df_alto_monto)} transacciones de Banca Personal > 5000")
                    
                    fig = px.box(df_caso, x='destipbanca', y='monto',
                               title='Distribución de Montos por Tipo de Banca',
                               color='destipbanca',
                               color_discrete_sequence=px.colors.qualitative.Set2)
                    fig.update_yaxes(type="log")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    fig2 = px.scatter(df_alto_monto, x='fecha', y='monto',
                                    color='segmento',
                                    size='monto',
                                    title='Transacciones de Alto Monto en Banca Personal',
                                    hover_data=['codunicocli_13_enc', 'grupo'])
                    st.plotly_chart(fig2, use_container_width=True)
                    
                    agregar_reporte = st.checkbox("✅ Incluir en reporte PDF")
                    
                    st.download_button("📥 Exportar Excel", 
                                     exportar_excel(df_alto_monto, "Alto_Volumen"),
                                     file_name="alto_volumen_banca_personal.xlsx")
                else:
                    st.success("No se encontraron anomalías")
        
        elif tipo_analisis == "3. Actividad Económica vs Efectivo":
            st.markdown("### 💵 Actividad Económica vs Uso de Efectivo")
            
            # Obtener actividades únicas
            actividades_unicas = sorted([str(a) for a in df_caso['act_economica'].dropna().unique()])
            
            # Pre-seleccionar actividades que NO son mineras por defecto
            actividades_default = [a for a in actividades_unicas if 'MINERA' not in a.upper() and 'MINERIA' not in a.upper()]
            
            actividades_sel = st.multiselect(
                "Filtrar Actividades Económicas (Por defecto excluye Minería)",
                actividades_unicas,
                default=actividades_default
            )
            
            if st.button("Analizar"):
                if actividades_sel:
                    df_filtrado = df_caso[df_caso['act_economica'].isin(actividades_sel)]
                    
                    st.markdown(f"### 📊 Análisis para {len(actividades_sel)} actividades seleccionadas")
                    
                    # Ranking por Tipo de Operación (Grupo)
                    df_ranking_grupo = df_filtrado.groupby('grupo').agg({
                        'id_transaccion': 'count',
                        'monto': 'sum'
                    }).reset_index()
                    
                    df_ranking_grupo.columns = ['Tipo Operación', 'Cantidad Operaciones', 'Monto Total']
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### Top por Monto")
                        df_monto = df_ranking_grupo.sort_values('Monto Total', ascending=False).head(10)
                        st.dataframe(df_monto[['Tipo Operación', 'Monto Total']], use_container_width=True)
                        fig_monto = px.bar(df_monto, x='Tipo Operación', y='Monto Total',
                                         title='Top Operaciones por Monto',
                                         color='Monto Total', color_continuous_scale='Viridis')
                        st.plotly_chart(fig_monto, use_container_width=True)
                        
                    with col2:
                        st.markdown("#### Top por Cantidad")
                        df_cantidad = df_ranking_grupo.sort_values('Cantidad Operaciones', ascending=False).head(10)
                        st.dataframe(df_cantidad[['Tipo Operación', 'Cantidad Operaciones']], use_container_width=True)
                        fig_cant = px.bar(df_cantidad, x='Tipo Operación', y='Cantidad Operaciones',
                                        title='Top Operaciones por Frecuencia',
                                        color='Cantidad Operaciones', color_continuous_scale='Magma')
                        st.plotly_chart(fig_cant, use_container_width=True)

                    # Tabla Resumen Original (Opcional, pero útil)
                    st.markdown("---")
                    st.markdown("### 📋 Desglose por Actividad Económica")
                    
                    df_resumen_act = df_filtrado.groupby(['act_economica', 'grupo', 'i_e']).agg({
                         'monto': 'sum',
                         'id_transaccion': 'count'
                    }).reset_index()
                    st.dataframe(df_resumen_act, use_container_width=True)
                    
                    df_merged = df_ranking_grupo # Para exportar el general
                    
                    st.markdown("---")
                    st.markdown("### 💵 Porcentaje de Uso de Efectivo vs Total")
                    
                    # Calcular % de Efectivo para las actividades seleccionadas
                    df_efectivo_filtrado = df_filtrado[df_filtrado['grupo'].isin(['RETIRO', 'DEPOSITO', 'DISP EFECTIVO'])]
                    
                    df_por_actividad = df_filtrado.groupby('act_economica').agg({
                        'monto': 'sum',
                        'id_transaccion': 'count'
                    }).reset_index()
                    df_por_actividad.columns = ['Actividad', 'Monto Total', 'Total Ops']
                    
                    df_efectivo_act = df_efectivo_filtrado.groupby('act_economica').agg({
                        'monto': 'sum',
                        'id_transaccion': 'count'
                    }).reset_index()
                    df_efectivo_act.columns = ['Actividad', 'Monto Efectivo', 'Ops Efectivo']
                    
                    df_comparativo = pd.merge(df_por_actividad, df_efectivo_act, on='Actividad', how='left').fillna(0)
                    df_comparativo['% Efectivo'] = (df_comparativo['Monto Efectivo'] / df_comparativo['Monto Total'] * 100).round(2)
                    df_comparativo = df_comparativo.sort_values('% Efectivo', ascending=False)
                    
                    st.dataframe(df_comparativo, use_container_width=True)
                    
                    fig_comp = px.bar(df_comparativo, x='Actividad', y=['Monto Efectivo', 'Monto Total'],
                               title='Comparación Efectivo vs Total por Actividad Económica',
                               barmode='group',
                               color_discrete_sequence=['#FF6B6B', '#4ECDC4'])
                    st.plotly_chart(fig_comp, use_container_width=True)
                else:
                    st.warning("Seleccione al menos una actividad económica")
                    df_merged = pd.DataFrame() # Empty for export check logic filter
                
                agregar_reporte = st.checkbox("✅ Incluir en reporte PDF")
                
                st.download_button("📥 Exportar Excel", 
                                 exportar_excel(df_merged, "Uso_Efectivo"),
                                 file_name="uso_efectivo.xlsx")
        
        elif tipo_analisis == "4. Concentración de Efectivo por Agencia":
            st.markdown("### 🏦 Concentración de Efectivo por Agencia")
            
            if st.button("Analizar"):
                df_efectivo = df_caso[df_caso['grupo'].isin(['RETIRO', 'DEPOSITO'])]
                
                df_agencias = df_efectivo.groupby('agencia').agg({
                    'monto': 'sum',
                    'id_transaccion': 'count'
                }).reset_index()
                df_agencias.columns = ['Agencia', 'Monto Total', 'Num Operaciones']
                df_agencias = df_agencias.sort_values('Monto Total', ascending=False).head(10)
                
                st.dataframe(df_agencias, use_container_width=True)
                
                fig = px.bar(df_agencias, x='Agencia', y='Monto Total',
                           color='Num Operaciones',
                           title='Top 10 Agencias por Volumen de Efectivo',
                           color_continuous_scale='OrRd')
                fig.update_xaxes(tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
                
                # Filtrar data para el heatmap usando solo las Top Agencias
                top_agencias_list = df_agencias['Agencia'].tolist()
                df_efectivo_top = df_efectivo[df_efectivo['agencia'].isin(top_agencias_list)]
                
                pivot_data = df_efectivo_top.pivot_table(
                    values='monto',
                    index='agencia',
                    columns='grupo',
                    aggfunc='sum',
                    fill_value=0
                )
                
                fig2 = px.imshow(pivot_data,
                               title='Heatmap: Efectivo por Agencia y Tipo',
                               color_continuous_scale='YlOrRd',
                               aspect='auto')
                st.plotly_chart(fig2, use_container_width=True)
                
                agregar_reporte = st.checkbox("✅ Incluir en reporte PDF")
                
                st.download_button("📥 Exportar Excel", 
                                 exportar_excel(df_agencias, "Concentracion_Agencias"),
                                 file_name="concentracion_agencias.xlsx")
        
        elif tipo_analisis == "5. Pitufeo Digital (Yape/Plin)":
            st.markdown("### 📱 Detección de Pitufeo Digital")
            
            tipo_billetera = st.radio("Seleccionar Billetera Digital", ["AMBOS", "YAPE", "PLIN"], horizontal=True)
            monto_max_pitufeo = st.slider("Monto máximo por operación", 0, 1000, 500)
            
            if st.button("Analizar"):
                if tipo_billetera == "AMBOS":
                    grupos_busqueda = ['YAPE', 'PLIN']
                else:
                    grupos_busqueda = [tipo_billetera]

                df_digital = df_caso[
                    (df_caso['grupo'].isin(grupos_busqueda)) &
                    (df_caso['monto'] < monto_max_pitufeo)
                ]
                
                if not df_digital.empty:
                    if tipo_billetera == "AMBOS":
                        total_ops = len(df_digital)
                        counts = df_digital['grupo'].value_counts()
                        
                        col1, col2 = st.columns(2)
                        
                        yape_count = counts.get('YAPE', 0)
                        plin_count = counts.get('PLIN', 0)
                        
                        yape_pct = (yape_count / total_ops) * 100 if total_ops > 0 else 0
                        plin_pct = (plin_count / total_ops) * 100 if total_ops > 0 else 0
                        
                        col1.metric("YAPE", f"{yape_pct:.1f}%", f"{yape_count} ops")
                        col2.metric("PLIN", f"{plin_pct:.1f}%", f"{plin_count} ops")
                        
                        fig_pie = px.pie(df_digital, names='grupo', title='Distribución YAPE vs PLIN',
                                       color='grupo',
                                       color_discrete_map={'YAPE': '#7D3C98', 'PLIN': '#3498DB'})
                        st.plotly_chart(fig_pie, use_container_width=True)
                    else:
                        col1, col2 = st.columns(2)
                        col1.metric(f"Total Ops {tipo_billetera}", f"{len(df_digital)}")
                        col2.metric(f"Monto Total {tipo_billetera}", f"S/ {df_digital['monto'].sum():,.2f}")

                    df_por_cliente = df_digital.groupby('codunicocli_13_enc').agg({
                        'id_transaccion': 'count',
                        'monto': 'sum'
                    }).reset_index()
                    df_por_cliente.columns = ['Cliente', 'Num Operaciones', 'Monto Total']
                    df_por_cliente = df_por_cliente.sort_values('Num Operaciones', ascending=False)
                    
                    st.markdown("### Top Clientes por Frecuencia")
                    st.dataframe(df_por_cliente.head(50), use_container_width=True)

                    sospechosos = df_por_cliente[df_por_cliente['Num Operaciones'] > 50]
                    
                    if not sospechosos.empty:
                        st.warning(f"⚠️ {len(sospechosos)} clientes con más de 50 micropagos")

                    df_digital['fecha_dt'] = pd.to_datetime(df_digital['fecha'])
                    df_diario = df_digital.groupby('fecha_dt').size().reset_index()
                    df_diario.columns = ['Fecha', 'Cantidad']
                    
                    fig = px.line(df_diario, x='Fecha', y='Cantidad',
                                title='Frecuencia Diaria de Micropagos Digitales',
                                markers=True)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    fig2 = px.histogram(df_digital, x='monto', nbins=50,
                                      title='Distribución de Montos en Operaciones Digitales',
                                      color_discrete_sequence=['#8B5CF6'])
                    st.plotly_chart(fig2, use_container_width=True)
                    
                    agregar_reporte = st.checkbox("✅ Incluir en reporte PDF")
                    
                    st.download_button("📥 Exportar Excel", 
                                     exportar_excel(df_por_cliente, "Pitufeo_Digital"),
                                     file_name="pitufeo_digital.xlsx")
                else:
                    st.info("No se encontraron operaciones de este tipo")
        
        elif tipo_analisis == "6. Retiros Hormiga en Cajeros":
            st.markdown("### 🏧 Patrón de Retiros Hormiga")
            
            # Inicializar estado si no existe
            if 'analisis_retiros_activo' not in st.session_state:
                st.session_state.analisis_retiros_activo = False

            if st.button("Analizar"):
                st.session_state.analisis_retiros_activo = True
            
            if st.session_state.analisis_retiros_activo:
                df_cajeros = df_caso[
                    (df_caso['canal'] == 'CAJEROS AUTOMATICOS') &
                    (df_caso['i_e'] == 'Egreso')
                ]
                
                if not df_cajeros.empty:
                    df_cajeros['fecha_dt'] = pd.to_datetime(df_cajeros['fecha'])
                    df_cajeros['hora_num'] = pd.to_datetime(df_cajeros['hora'], format='mixed', errors='coerce').dt.hour
                    df_cajeros = df_cajeros.dropna(subset=['hora_num'])
                    df_por_cliente_dia = df_cajeros.groupby(
                        ['codunicocli_13_enc', 'fecha_dt']
                    ).agg({
                        'id_transaccion': 'count',
                        'monto': 'sum'
                    }).reset_index()
                    df_por_cliente_dia.columns = ['Cliente', 'Fecha', 'Num Retiros', 'Monto Total']
                    
                    sospechosos = df_por_cliente_dia[df_por_cliente_dia['Num Retiros'] >= 5]
                    
                    if not sospechosos.empty:
                        st.warning(f"⚠️ {len(sospechosos)} casos de múltiples retiros en un día")
                        st.dataframe(sospechosos.sort_values('Num Retiros', ascending=False).head(20))
                        
                        fig = px.scatter(df_cajeros, x='hora_num', y='fecha_dt',
                                       color='monto', size='monto',
                                       title='Patrón Temporal de Retiros en Cajeros',
                                       labels={'hora_num': 'Hora del día', 'fecha_dt': 'Fecha'},
                                       color_continuous_scale='Reds')
                        st.plotly_chart(fig, use_container_width=True)
                        
                        st.markdown("---")
                        col_cajero, col_operador = st.columns(2)
                        
                        with col_cajero:
                            st.markdown("### 🏧 Top Cajeros")
                            # Top Cajeros (CodAgencia/Agencia)
                            df_top_cajeros = df_cajeros.groupby('agencia').agg({
                                'id_transaccion': 'count',
                                'monto': 'sum',
                                'grupo': lambda x: ', '.join(sorted(x.astype(str).unique()))
                            }).reset_index().sort_values('id_transaccion', ascending=False).head(10)
                            
                            df_top_cajeros.columns = ['Agencia', 'Num Operaciones', 'Monto Total', 'Tipos Operación']
                            st.dataframe(df_top_cajeros, use_container_width=True)
                            
                            cajeros_list = df_top_cajeros['Agencia'].tolist()
                            cajero_sel = st.selectbox("Seleccionar Cajero", cajeros_list)
                            
                            if cajero_sel:
                                df_cajero_ops = df_cajeros[df_cajeros['agencia'] == cajero_sel].groupby('grupo').agg({
                                    'id_transaccion': 'count'
                                }).reset_index().sort_values('id_transaccion', ascending=False)
                                
                                fig_cajero = px.bar(df_cajero_ops, x='grupo', y='id_transaccion',
                                                  title=f'Operaciones en {cajero_sel}',
                                                  labels={'grupo': 'Tipo Operación', 'id_transaccion': 'Cantidad'})
                                st.plotly_chart(fig_cajero, use_container_width=True)

                        with col_operador:
                            st.markdown("### 👤 Top Operadores")
                            # Top Operadores
                            df_top_operadores = df_cajeros.groupby('operador').agg({
                                'id_transaccion': 'count',
                                'monto': 'sum',
                                'grupo': lambda x: ', '.join(sorted(x.astype(str).unique()))
                            }).reset_index().sort_values('id_transaccion', ascending=False).head(10)
                            
                            df_top_operadores.columns = ['Operador', 'Num Operaciones', 'Monto Total', 'Tipos Operación']
                            st.dataframe(df_top_operadores, use_container_width=True)
                            
                            operadores_list = df_top_operadores['Operador'].tolist()
                            operador_sel = st.selectbox("Seleccionar Operador", operadores_list)
                            
                            if operador_sel:
                                df_operador_ops = df_cajeros[df_cajeros['operador'] == operador_sel].groupby('grupo').agg({
                                    'id_transaccion': 'count'
                                }).reset_index().sort_values('id_transaccion', ascending=False)
                                
                                fig_operador = px.bar(df_operador_ops, x='grupo', y='id_transaccion',
                                                    title=f'Operaciones de {operador_sel}',
                                                    labels={'grupo': 'Tipo Operación', 'id_transaccion': 'Cantidad'},
                                                    color_discrete_sequence=['#FF9F43'])
                                st.plotly_chart(fig_operador, use_container_width=True)
                        
                        st.markdown("---")
                        
                        agregar_reporte = st.checkbox("✅ Incluir en reporte PDF")
                        
                        st.download_button("📥 Exportar Excel", 
                                         exportar_excel(sospechosos, "Retiros_Hormiga"),
                                         file_name="retiros_hormiga.xlsx")
                    else:
                        st.success("No se detectaron patrones sospechosos")
                else:
                    st.info("No hay retiros en cajeros")
        
        elif tipo_analisis == "7. Preferencia por Operador":
            st.markdown("### 👤 Análisis de Preferencia por Operador")
            
            # Inicializar estado si no existe
            if 'analisis_operador_activo' not in st.session_state:
                st.session_state.analisis_operador_activo = False

            if st.button("Analizar"):
                st.session_state.analisis_operador_activo = True

            if st.session_state.analisis_operador_activo:
                df_ventanilla = df_caso[
                    (df_caso['canal'] == 'VENTANILLA') &
                    (df_caso['operador'].notna())
                ]
                
                if not df_ventanilla.empty:
                    df_matriz = df_ventanilla.pivot_table(
                        values='id_transaccion',
                        index='codunicocli_13_enc',
                        columns='operador',
                        aggfunc='count',
                        fill_value=0
                    )
                    
                    st.dataframe(df_matriz.head(20))
                    
                    if len(df_matriz.columns) <= 50:
                        fig = px.imshow(df_matriz,
                                      title='Matriz de Colusión: Cliente vs Operador',
                                      color_continuous_scale='Reds',
                                      aspect='auto')
                        st.plotly_chart(fig, use_container_width=True)
                    
                    criterio_top = st.radio("Ordenar Top por:", ["Monto Total", "Cantidad de Operaciones", "Clientes Únicos"], horizontal=True)

                    df_ops_operador = df_ventanilla.groupby('operador').agg({
                        'codunicocli_13_enc': 'nunique',
                        'id_transaccion': 'count',
                        'monto': 'sum'
                    }).reset_index()
                    df_ops_operador.columns = ['Operador', 'Clientes Únicos', 'Total Operaciones', 'Monto Total']
                    
                    if criterio_top == "Monto Total":
                        columna_orden = 'Monto Total'
                        color_col = 'Total Operaciones'
                    elif criterio_top == "Cantidad de Operaciones":
                        columna_orden = 'Total Operaciones'
                        color_col = 'Monto Total'
                    else:
                        columna_orden = 'Clientes Únicos'
                        color_col = 'Total Operaciones'

                    df_ops_operador = df_ops_operador.sort_values(columna_orden, ascending=False).head(15)
                    
                    st.dataframe(df_ops_operador, use_container_width=True)

                    fig2 = px.bar(df_ops_operador, x='Operador', y=columna_orden,
                                color=color_col,
                                title=f'Top Operadores por {criterio_top}',
                                color_continuous_scale='YlOrRd')
                    st.plotly_chart(fig2, use_container_width=True)
                    
                    agregar_reporte = st.checkbox("✅ Incluir en reporte PDF")
                    
                    st.download_button("📥 Exportar Excel", 
                                     exportar_excel(df_ops_operador, "Preferencia_Operador"),
                                     file_name="preferencia_operador.xlsx")
                else:
                    st.info("No hay operaciones en ventanilla")
        
        elif tipo_analisis == "8. Red de Proveedores Comunes":
            st.markdown("### 🕸️ Red de Proveedores Comunes")
            
            min_clientes = st.slider("Mínimo de clientes que comparten proveedor", 2, 10, 3)
            
            if st.button("Analizar"):
                df_egresos = df_caso[df_caso['i_e'] == 'Egreso']
                
                if not df_egresos.empty:
                    df_egresos['palabras'] = df_egresos['glosa_limpia'].str.split()
                    
                    palabras_todas = []
                    for idx, row in df_egresos.iterrows():
                        if isinstance(row['palabras'], list):
                            for palabra in row['palabras']:
                                if len(palabra) > 4:
                                    palabras_todas.append({
                                        'cliente': row['codunicocli_13_enc'][:8],
                                        'palabra': palabra,
                                        'monto': row['monto']
                                    })
                    
                    df_palabras = pd.DataFrame(palabras_todas)
                    
                    if not df_palabras.empty:
                        df_proveedores = df_palabras.groupby('palabra').agg({
                            'cliente': lambda x: list(set(x)),
                            'monto': 'sum'
                        }).reset_index()
                        
                        df_proveedores['num_clientes'] = df_proveedores['cliente'].apply(len)
                        df_proveedores = df_proveedores[df_proveedores['num_clientes'] >= min_clientes]
                        df_proveedores = df_proveedores.sort_values('num_clientes', ascending=False).head(20)
                        
                        if not df_proveedores.empty:
                            st.warning(f"⚠️ Se encontraron {len(df_proveedores)} posibles proveedores compartidos")
                            
                            df_display = df_proveedores[['palabra', 'num_clientes', 'monto']].copy()
                            df_display.columns = ['Proveedor/Entidad', 'Clientes', 'Monto Total']
                            st.dataframe(df_display, use_container_width=True)
                            
                            fig = px.treemap(df_display, path=['Proveedor/Entidad'],
                                           values='Monto Total',
                                           color='Clientes',
                                           title='Proveedores Comunes por Monto y Clientes',
                                           color_continuous_scale='Reds')
                            st.plotly_chart(fig, use_container_width=True)
                            
                            agregar_reporte = st.checkbox("✅ Incluir en reporte PDF")
                            
                            st.download_button("📥 Exportar Excel", 
                                             exportar_excel(df_display, "Proveedores_Comunes"),
                                             file_name="proveedores_comunes.xlsx")
                        else:
                            st.info("No se encontraron proveedores compartidos")
                    else:
                        st.info("No se pudieron extraer palabras clave")
                else:
                    st.info("No hay egresos")
        
        elif tipo_analisis == "9. Cuentas Descartables":
            st.markdown("### ⏱️ Análisis de Cuentas Descartables")
            
            meses_max = st.slider("Duración máxima de cuenta (meses)", 1, 12, 6)
            
            if st.button("Analizar"):

                # Convertir fechas antes de agrupar para evitar errores de tipo
                df_caso['fecapertura'] = pd.to_datetime(df_caso['fecapertura'], errors='coerce')
                df_caso['feccierre'] = pd.to_datetime(df_caso['feccierre'], errors='coerce')

                # Agregación inicial para obtener fechas y cuenta
                df_cuentas = df_caso.groupby('codunicocli_13_enc').agg({
                    'fecapertura': 'max',
                    'feccierre': 'max',
                    'ctacomercial': 'first', # Asumimos una cuenta principal por cliente en este contexto
                    'monto': 'sum'
                }).reset_index()
                
                # Obtener Monto Apertura (Primer movimiento) y Glosas Principales
                # Para esto necesitamos ordenar las transacciones por fecha
                df_sorted = df_caso.sort_values('fecha')
                df_detalles = df_sorted.groupby('codunicocli_13_enc').agg({
                    'monto': 'first', # Monto de apertura aproximado (primer movimiento)
                    'glosa': lambda x: ', '.join(x.value_counts().head(3).index.astype(str))
                }).rename(columns={'monto': 'monto_apertura', 'glosa': 'top_glosas'})
                
                df_cuentas = pd.merge(df_cuentas, df_detalles, on='codunicocli_13_enc')

                df_cuentas['fecapertura'] = pd.to_datetime(df_cuentas['fecapertura'], errors='coerce')
                df_cuentas['feccierre'] = pd.to_datetime(df_cuentas['feccierre'], errors='coerce')
                
                df_cerradas = df_cuentas[df_cuentas['feccierre'].notna()].copy()
                
                if not df_cerradas.empty:
                    # Corrección: Eliminar fechas inconsistentes
                    df_cerradas = df_cerradas[df_cerradas['feccierre'] >= df_cerradas['fecapertura']]
                    
                    df_cerradas['duracion_dias'] = (df_cerradas['feccierre'] - df_cerradas['fecapertura']).dt.days
                    df_cerradas['duracion_meses'] = df_cerradas['duracion_dias'] / 30
                    
                    df_sospechosas = df_cerradas[df_cerradas['duracion_meses'] <= meses_max]
                    
                    if not df_sospechosas.empty:
                        st.warning(f"⚠️ {len(df_sospechosas)} cuentas cerradas en menos de {meses_max} meses")
                        
                        df_display = df_sospechosas[['codunicocli_13_enc', 'ctacomercial', 'fecapertura', 'feccierre', 
                                                    'monto_apertura', 'monto', 'top_glosas', 'duracion_meses']].copy()
                        df_display.columns = ['Cliente', 'Cuenta', 'Apertura', 'Cierre', 
                                            'Monto 1er Mov', 'Monto Total Movido', 'Principales Operaciones', 'Duración (meses)']
                        
                        df_display = df_display.sort_values('Monto Total Movido', ascending=False)
                        
                        st.dataframe(df_display, use_container_width=True)
                        
                        fig = px.scatter(df_sospechosas, x='duracion_meses', y='monto',
                                       size='monto',
                                       hover_data=['ctacomercial', 'top_glosas'],
                                       title='Relación Duración vs Monto Movido',
                                       labels={'duracion_meses': 'Duración (meses)', 'monto': 'Monto Total'},
                                       color_discrete_sequence=['#E74C3C'])
                        st.plotly_chart(fig, use_container_width=True)
                        
                        agregar_reporte = st.checkbox("✅ Incluir en reporte PDF")
                        
                        st.download_button("📥 Exportar Excel", 
                                         exportar_excel(df_display, "Cuentas_Descartables"),
                                         file_name="cuentas_descartables.xlsx")
                    else:
                        st.success("No se encontraron cuentas descartables")
                else:
                    st.info("No hay cuentas cerradas")
        
        elif tipo_analisis == "10. Velocidad del Dinero":
            st.markdown("### 💸 Análisis de Velocidad del Dinero (Pass-Through)")
            
            if st.button("Analizar"):
                df_caso['fecha_dt'] = pd.to_datetime(df_caso['fecha'])
                
                df_diario = df_caso.groupby(['codunicocli_13_enc', 'fecha_dt', 'i_e']).agg({
                    'monto': 'sum'
                }).reset_index()
                
                df_pivot = df_diario.pivot_table(
                    index=['codunicocli_13_enc', 'fecha_dt'],
                    columns='i_e',
                    values='monto',
                    fill_value=0
                ).reset_index()
                
                if 'Ingreso' in df_pivot.columns and 'Egreso' in df_pivot.columns:
                    df_pivot['diferencia'] = abs(df_pivot['Ingreso'] - df_pivot['Egreso'])
                    df_pivot['porcentaje_match'] = (1 - df_pivot['diferencia'] / 
                                                   df_pivot[['Ingreso', 'Egreso']].max(axis=1)) * 100
                    
                    df_sospechoso = df_pivot[
                        (df_pivot['porcentaje_match'] > 80) &
                        (df_pivot['Ingreso'] > 1000)
                    ]
                    
                    if not df_sospechoso.empty:
                        st.warning(f"⚠️ {len(df_sospechoso)} días con patrón de paso rápido de dinero")
                        
                        st.dataframe(df_sospechoso, use_container_width=True)
                        
                        st.markdown("### 🏆 Top 10 Clientes con Mayor Frecuencia")
                        
                        df_top_velocidad = df_sospechoso.groupby('codunicocli_13_enc').agg({
                            'fecha_dt': 'count',
                            'Ingreso': 'sum'
                        }).reset_index()
                        
                        df_top_velocidad.columns = ['Cliente', 'Días con Patrón', 'Monto Total Ingresado']
                        df_top_velocidad = df_top_velocidad.sort_values('Días con Patrón', ascending=False).head(10)
                        
                        st.dataframe(df_top_velocidad, use_container_width=True)
                        
                        fig_top = px.bar(df_top_velocidad, x='Cliente', y='Días con Patrón',
                                       title='Top 10 Clientes por Frecuencia de "Pass-Through"',
                                       color='Monto Total Ingresado',
                                       color_continuous_scale='Reds')
                        st.plotly_chart(fig_top, use_container_width=True)
                        
                        for cliente in df_sospechoso['codunicocli_13_enc'].unique()[:3]:
                            df_cliente = df_pivot[df_pivot['codunicocli_13_enc'] == cliente].sort_values('fecha_dt')
                            
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(x=df_cliente['fecha_dt'], y=df_cliente['Ingreso'],
                                                   mode='lines+markers', name='Ingresos',
                                                   line=dict(color='green', width=2)))
                            fig.add_trace(go.Scatter(x=df_cliente['fecha_dt'], y=df_cliente['Egreso'],
                                                   mode='lines+markers', name='Egresos',
                                                   line=dict(color='red', width=2)))
                            fig.update_layout(title=f'Velocidad del Dinero - Cliente {cliente[:8]}',
                                            xaxis_title='Fecha', yaxis_title='Monto')
                            st.plotly_chart(fig, use_container_width=True)
                        
                        agregar_reporte = st.checkbox("✅ Incluir en reporte PDF")
                        
                        st.download_button("📥 Exportar Excel", 
                                         exportar_excel(df_sospechoso, "Velocidad_Dinero"),
                                         file_name="velocidad_dinero.xlsx")
                    else:
                        st.success("No se detectó patrón de paso rápido")
                else:
                    st.info("No hay suficientes datos de ingresos/egresos")
        
        elif tipo_analisis == "11. Comportamiento por Marca":
            st.markdown("### 🏷️ Comportamiento Diferenciado por Marca")
            
            # 1. Filtro afuera
            marcas_disponibles = ['TODAS'] + sorted([str(m) for m in df_caso['tipo_marca'].dropna().unique()])
            marca_seleccionada = st.selectbox("Filtrar por Tipo de Marca", marcas_disponibles)

            if st.button("Analizar"):
                # 2. Porcentaje del total de operaciones de toda la muestra por cada tipo de marca
                total_ops_global = len(df_caso)
                total_monto_global = df_caso['monto'].sum()
                
                df_resumen_marcas = df_caso.groupby('tipo_marca').agg({
                    'id_transaccion': 'count',
                    'monto': 'sum'
                }).reset_index()
                
                df_resumen_marcas['% Operaciones'] = (df_resumen_marcas['id_transaccion'] / total_ops_global) * 100
                df_resumen_marcas['% Monto'] = (df_resumen_marcas['monto'] / total_monto_global) * 100
                
                st.markdown("#### 📊 Distribución Global por Marca")
                
                # Display metrics summary
                df_display_resumen = df_resumen_marcas.copy()
                df_display_resumen['% Operaciones'] = df_display_resumen['% Operaciones'].map('{:.2f}%'.format)
                df_display_resumen['% Monto'] = df_display_resumen['% Monto'].map('{:.2f}%'.format)
                df_display_resumen = df_display_resumen.sort_values('% Operaciones', ascending=False)
                
                st.dataframe(df_display_resumen, use_container_width=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    fig_pie_ops = px.pie(df_resumen_marcas, values='id_transaccion', names='tipo_marca', 
                                       title='Distribución por Cantidad de Ops')
                    st.plotly_chart(fig_pie_ops, use_container_width=True)
                with col2:
                    fig_pie_monto = px.pie(df_resumen_marcas, values='monto', names='tipo_marca', 
                                         title='Distribución por Monto')
                    st.plotly_chart(fig_pie_monto, use_container_width=True)

                st.markdown("---")
                
                # Filter for detailed analysis
                if marca_seleccionada != 'TODAS':
                    df_analisis = df_caso[df_caso['tipo_marca'] == marca_seleccionada]
                    st.markdown(f"#### Detalle para: {marca_seleccionada}")
                else:
                    df_analisis = df_caso
                    st.markdown("#### Detalle Global")

                # Existing Detailed Analysis (breakdown by Group)
                df_por_marca_grupo = df_analisis.groupby(['tipo_marca', 'grupo']).agg({
                    'monto': 'sum',
                    'id_transaccion': 'count'
                }).reset_index()
                
                st.dataframe(df_por_marca_grupo, use_container_width=True)
                
                if marca_seleccionada == 'TODAS':
                    fig = px.bar(df_por_marca_grupo, x='tipo_marca', y='monto',
                               color='grupo',
                               title='Distribución de Operaciones por Tipo de Marca y Grupo',
                               barmode='stack')
                    
                    fig2 = px.sunburst(df_por_marca_grupo, path=['tipo_marca', 'grupo'],
                                     values='monto',
                                     title='Composición de Operaciones por Marca')
                else:
                    # Filtrar Top 10 para mejor visualización
                    df_top10_grupo = df_por_marca_grupo.sort_values('monto', ascending=False).head(10)
                    
                    fig = px.bar(df_top10_grupo, x='grupo', y='monto',
                               title=f'Top 10: Distribución de Operaciones por Grupo ({marca_seleccionada})',
                               labels={'grupo': 'Tipo de Operación', 'monto': 'Monto Total'},
                               color='grupo')
                    
                    fig2 = px.pie(df_top10_grupo, names='grupo', values='monto',
                                title=f'Top 10: Composición de Operaciones por Grupo ({marca_seleccionada})')
                
                st.plotly_chart(fig, use_container_width=True)
                st.plotly_chart(fig2, use_container_width=True)
                
                agregar_reporte = st.checkbox("✅ Incluir en reporte PDF")
                
                st.download_button("📥 Exportar Excel", 
                                 exportar_excel(df_por_marca_grupo, "Comportamiento_Marca"),
                                 file_name="comportamiento_marca.xlsx")
        
        elif tipo_analisis == "12. Divisa por Delito":
            st.markdown("### 💱 Análisis de Divisa por Delito")
            
            if st.button("Analizar"):
                df_delito_moneda = df_caso.groupby(['delito', 'moneda']).agg({
                    'monto': 'sum',
                    'id_transaccion': 'count'
                }).reset_index()
                
                if not df_delito_moneda.empty:
                    st.dataframe(df_delito_moneda, use_container_width=True)
                    
                    fig = px.bar(df_delito_moneda, x='delito', y='monto',
                               color='moneda',
                               title='Monto Acumulado por Delito y Moneda',
                               barmode='group',
                               color_discrete_map={'SOLES': '#3498DB', 'DOLARES': '#27AE60'})
                    st.plotly_chart(fig, use_container_width=True)
                    
                    fig2 = px.treemap(df_delito_moneda, path=['delito', 'moneda'],
                                    values='monto',
                                    title='Distribución de Montos: Delito y Moneda')
                    st.plotly_chart(fig2, use_container_width=True)
                    
                    agregar_reporte = st.checkbox("✅ Incluir en reporte PDF")
                    
                    st.download_button("📥 Exportar Excel", 
                                     exportar_excel(df_delito_moneda, "Divisa_Delito"),
                                     file_name="divisa_delito.xlsx")
                else:
                    st.info("No hay datos de delitos")
        

        elif tipo_analisis == "13. Cuentas Puente":
            st.markdown("### 🌉 Detección de Cuentas Puente")
            
            if st.button("Analizar"):
                df_caso['fecha_dt'] = pd.to_datetime(df_caso['fecha'])
                
                df_filtrado = df_caso[df_caso['grupo'].isin(['TRANSFERENCIA', 'TT OTRA CTA', 'CHEQUE'])]
                
                df_diario = df_filtrado.groupby(['codunicocli_13_enc', 'act_economica', 'fecha_dt', 'i_e']).agg({
                    'monto': 'sum'
                }).reset_index()
                
                df_pivot = df_diario.pivot_table(
                    index=['codunicocli_13_enc', 'act_economica', 'fecha_dt'],
                    columns='i_e',
                    values='monto',
                    fill_value=0
                ).reset_index()
                
                if 'Ingreso' in df_pivot.columns and 'Egreso' in df_pivot.columns:
                    df_pivot['saldo_diario'] = df_pivot['Ingreso'] - df_pivot['Egreso']
                    df_pivot['volumen_diario'] = df_pivot['Ingreso'] + df_pivot['Egreso']
                    
                    # Filtrar cuentas puente: alto volumen pero el saldo final del día es casi 0
                    df_puente = df_pivot[
                        (abs(df_pivot['saldo_diario']) < 100) &
                        (df_pivot['volumen_diario'] > 5000)
                    ]
                    
                    if not df_puente.empty:
                        st.warning(f"⚠️ {len(df_puente)} días con patrón de cuenta puente")
                         
                        
                        st.dataframe(df_puente.head(20), use_container_width=True)
                        
                        # 1. Top Actividades Económicas
                        st.markdown("### 🏭 Top Actividades Económicas Involucradas")
                        df_top_actividades = df_puente.groupby('act_economica').agg({
                            'codunicocli_13_enc': 'nunique',
                            'volumen_diario': 'sum',
                            'fecha_dt': 'count'
                        }).reset_index()
                        
                        df_top_actividades.columns = ['Actividad', 'Clientes Únicos', 'Volumen Total', 'Días con Patrón']
                        df_top_actividades = df_top_actividades.sort_values('Volumen Total', ascending=False).head(10)
                        
                        fig_act = px.bar(df_top_actividades, x='Actividad', y='Volumen Total',
                                       color='Clientes Únicos',
                                       title='Top 10 Actividades por Volumen en Cuentas Puente',
                                       text_auto='.2s',
                                       color_continuous_scale='Viridis')
                        st.plotly_chart(fig_act, use_container_width=True)

                        # 2. Top Clientes
                        st.markdown("### 🏆 Top Clientes Identificados")
                        df_top_clientes = df_puente.groupby('codunicocli_13_enc').agg({
                            'volumen_diario': 'sum',
                            'fecha_dt': 'count',
                            'act_economica': 'first'
                        }).reset_index()
                        
                        df_top_clientes.columns = ['Cliente', 'Volumen Total', 'Días Detectados', 'Actividad']
                        df_top_clientes = df_top_clientes.sort_values('Días Detectados', ascending=False).head(10)
                        
                        fig_cli = px.bar(df_top_clientes, y='Cliente', x='Días Detectados',
                                       orientation='h',
                                       color='Volumen Total',
                                       title='Top 10 Clientes por Frecuencia de Patrón',
                                       text='Actividad',
                                       color_continuous_scale='Reds')
                        st.plotly_chart(fig_cli, use_container_width=True)

                        
                        agregar_reporte = st.checkbox("✅ Incluir en reporte PDF")
                        
                        st.download_button("📥 Exportar Excel", 
                                         exportar_excel(df_puente, "Cuentas_Puente"),
                                         file_name="cuentas_puente.xlsx")
                    else:
                        st.success("No se detectaron cuentas puente")
                else:
                    st.info("No hay suficientes datos")
        
        elif tipo_analisis == "14. Matriz Colusión Cliente-Operador":
            st.markdown("### 🔗 Matriz de Colusión Cliente-Operador")
            
            if st.button("Generar Matriz"):
                df_efectivo = df_caso[
                    (df_caso['grupo'].isin(['RETIRO', 'DEPOSITO', 'DISP EFECTIVO'])) &
                    (df_caso['operador'].notna())
                ]
                
                if not df_efectivo.empty:

                    df_operador_cliente = df_efectivo.groupby(['operador', 'codunicocli_13_enc']).agg({
                        'id_transaccion': 'count',
                        'monto': 'sum'
                    }).reset_index()
                    df_operador_cliente.columns = ['Operador', 'Cliente', 'Operaciones', 'Monto Total']
                    df_operador_cliente['Operador'] = df_operador_cliente['Operador'].astype(str)
                    
                    st.markdown("### Top Clientes y sus Operadores Favoritos")
                    
                    metric_op = st.radio("Metrica para gráficos:", ["Cantidad de Operaciones", "Monto Total"], horizontal=True)
                    col_metric = 'Operaciones' if metric_op == "Cantidad de Operaciones" else 'Monto Total'

                    # Obtener Top Clientes con más interacciones
                    top_clientes = df_operador_cliente.groupby('Cliente')[col_metric].sum().sort_values(ascending=False).head(10).index.tolist()
                    
                    st.info(f"Mostrando Top 10 Clientes con mayor {metric_op}")
                    
                    for cliente in top_clientes:
                        df_cli = df_operador_cliente[df_operador_cliente['Cliente'] == cliente].copy()
                        df_cli = df_cli.sort_values(col_metric, ascending=False).head(10)
                        
                        fig = px.bar(df_cli, x='Operador', y=col_metric,
                                   title=f'Top 10 Operadores para Cliente {cliente[:10]}...',
                                   color=col_metric,
                                   labels={'Operador': 'Código Operador'},
                                   color_continuous_scale='Viridis' if metric_op == "Cantidad de Operaciones" else 'Sunset')
                        fig.update_xaxes(type='category')
                        st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("### Detalle Completo")
                    st.dataframe(df_operador_cliente.sort_values(col_metric, ascending=False).head(50), use_container_width=True)
                    
                    agregar_reporte = st.checkbox("✅ Incluir en reporte PDF")
                    
                    st.download_button("📥 Exportar Excel", 
                                     exportar_excel(df_operador_cliente, "Relacion_Cliente_Operador"),
                                     file_name="cliente_operador.xlsx") 
                else:
                    st.info("No hay operaciones de efectivo con operador")
        
        elif tipo_analisis == "15. Explosión de Pitufeo":
            st.markdown("### 💥 Análisis de Explosión de Pitufeo (Bursts)")
            
            ventana_horas = st.slider("Ventana de tiempo (horas)", 1, 6, 2)
            monto_max = st.number_input("Monto máximo por operación", value=3000)
            
            if st.button("Analizar"):
                df_bajo_monto = df_caso[
                    (df_caso['monto'] < monto_max) &
                    (df_caso['canal'].isin(['CAJEROS AUTOMATICOS', 'AGENTE BCP', 'YAPE']))
                ].copy()
                
                if not df_bajo_monto.empty: 
                    # SOLUCIÓN: Usar errors='coerce' para manejar horas inválidas como 99:99:99
                    df_bajo_monto['fecha_hora'] = pd.to_datetime(
                        df_bajo_monto['fecha'].astype(str) + ' ' + df_bajo_monto['hora'].astype(str),
                        errors='coerce'
                    )
                    
                    # Eliminar registros con datos de tiempo corruptos
                    df_bajo_monto = df_bajo_monto.dropna(subset=['fecha_hora'])
                    df_bajo_monto = df_bajo_monto.sort_values('fecha_hora')
                    
                    bursts = []
                    all_burst_ops = [] # Para el top de glosas
                    
                    for cliente in df_bajo_monto['codunicocli_13_enc'].unique():
                        df_cliente = df_bajo_monto[df_bajo_monto['codunicocli_13_enc'] == cliente].sort_values('fecha_hora').reset_index(drop=True)
                        
                        i = 0
                        while i < len(df_cliente):
                            ventana_inicio = df_cliente.iloc[i]['fecha_hora']
                            ventana_fin = ventana_inicio + pd.Timedelta(hours=ventana_horas)
                            
                            ops_en_ventana = df_cliente[
                                (df_cliente['fecha_hora'] >= ventana_inicio) &
                                (df_cliente['fecha_hora'] <= ventana_fin)
                            ]
                            
                            if len(ops_en_ventana) >= 10:
                                # Obtener glosas más comunes en esta ráfaga
                                top_glosas = ops_en_ventana['glosa'].value_counts().head(3).index.tolist()
                                top_glosas_str = ", ".join([str(g) for g in top_glosas])
                                
                                bursts.append({
                                    'cliente': cliente[:8],
                                    'fecha_inicio': ventana_inicio,
                                    'num_operaciones': len(ops_en_ventana),
                                    'monto_total': ops_en_ventana['monto'].sum(),
                                    'glosas_frecuentes': top_glosas_str
                                })
                                
                                all_burst_ops.append(ops_en_ventana)
                                
                                # Saltar para evitar duplicados: dejar al menos 1 hora de diferencia tras la ventana
                                min_next_time = ventana_fin + pd.Timedelta(hours=1)
                                
                                # Encontrar el índice de la siguiente transacción válida
                                next_ops = df_cliente[df_cliente['fecha_hora'] > min_next_time]
                                if not next_ops.empty:
                                    i = next_ops.index[0]
                                else:
                                    break
                            else:
                                i += 1
                    
                    if bursts:
                        df_bursts = pd.DataFrame(bursts)
                        
                        st.warning(f"⚠️ Se detectaron {len(df_bursts)} ráfagas de operaciones (Pitufeo)")
                        st.dataframe(df_bursts.sort_values('num_operaciones', ascending=False), 
                                   use_container_width=True)
                        
                        # Análisis de Glosas
                        st.markdown("### 📝 Top Glosas en Operaciones de Pitufeo")
                        if all_burst_ops:
                            df_all_ops = pd.concat(all_burst_ops)
                            df_top_glosas = df_all_ops['glosa'].value_counts().reset_index()
                            df_top_glosas.columns = ['Glosa', 'Frecuencia']
                            df_top_glosas = df_top_glosas.head(10)
                            
                            col_glosa1, col_glosa2 = st.columns([1, 2])
                            
                            with col_glosa1:
                                st.dataframe(df_top_glosas, use_container_width=True)
                            
                            with col_glosa2:
                                fig_glosa = px.bar(df_top_glosas, x='Frecuencia', y='Glosa',
                                                 orientation='h',
                                                 title='Glosas más utilizadas en Pitufeo',
                                                 color='Frecuencia',
                                                 color_continuous_scale='Magma')
                                fig_glosa.update_layout(yaxis={'categoryorder':'total ascending'})
                                st.plotly_chart(fig_glosa, use_container_width=True)

                        df_timeline = df_bajo_monto.copy()
                        #df_timeline['hora_num'] = pd.to_datetime(df_timeline['hora'], format='%H:%M:%S').dt.hour

                        df_timeline['hora_num'] = df_timeline['fecha_hora'].dt.hour
                        
                        fig = px.line(df_timeline.groupby('fecha_hora').size().reset_index(),
                                    x='fecha_hora', y=0,
                                    title='Frecuencia de Operaciones en el Tiempo (Detección de Bursts)',
                                    markers=True)
                        st.plotly_chart(fig, use_container_width=True)
                        
                        agregar_reporte = st.checkbox("✅ Incluir en reporte PDF")
                        
                        st.download_button("📥 Exportar Excel", 
                                         exportar_excel(df_bursts, "Bursts_Pitufeo"),
                                         file_name="bursts_pitufeo.xlsx")
                    else:
                        st.success("No se detectaron ráfagas sospechosas")
                else:
                    st.info("No hay operaciones de bajo monto")
        
        
        elif tipo_analisis == "16. Minería de Texto en Glosas":
            st.markdown("### 📝 Minería de Texto en Glosas")
            
            palabras_excluir = st.text_input("Palabras a excluir (separadas por coma)", 
                                            value="PAGO,TRANSFERENCIA,EFECTIVO,RETIRO,DEPOSITO")
            
            if st.button("Analizar"):
                df_egresos = df_caso[df_caso['i_e'] == 'Egreso'].copy()
                
                if not df_egresos.empty:
                    excluir = [p.strip().upper() for p in palabras_excluir.split(',')]
                    
                    palabras_freq = {}
                    
                    for _, row in df_egresos.iterrows():
                        if pd.notna(row['glosa_limpia']):
                            palabras = str(row['glosa_limpia']).split()
                            for palabra in palabras:
                                if len(palabra) > 4 and palabra not in excluir:
                                    if palabra not in palabras_freq:
                                        palabras_freq[palabra] = {
                                            'count': 0,
                                            'clientes': set(),
                                            'monto': 0
                                        }
                                    palabras_freq[palabra]['count'] += 1
                                    palabras_freq[palabra]['clientes'].add(row['codunicocli_13_enc'][:8])
                                    palabras_freq[palabra]['monto'] += row['monto']
                    
                    df_palabras = pd.DataFrame([
                        {
                            'Palabra': k,
                            'Frecuencia': v['count'],
                            'Num Clientes': len(v['clientes']),
                            'Monto Total': v['monto']
                        }
                        for k, v in palabras_freq.items()
                    ])
                    
                    df_palabras = df_palabras[df_palabras['Num Clientes'] >= 2]
                    df_palabras = df_palabras.sort_values('Num Clientes', ascending=False).head(30)
                    
                    if not df_palabras.empty:
                        st.dataframe(df_palabras, use_container_width=True)
                        
                        fig = px.scatter(df_palabras, x='Frecuencia', y='Num Clientes',
                                       size='Monto Total', text='Palabra',
                                       title='Palabras Clave Compartidas entre Clientes',
                                       color='Monto Total',
                                       color_continuous_scale='Reds')
                        fig.update_traces(textposition='top center')
                        st.plotly_chart(fig, use_container_width=True)
                        
                        fig2 = px.treemap(df_palabras.head(15),
                                        path=['Palabra'],
                                        values='Monto Total',
                                        color='Num Clientes',
                                        title='Entidades Beneficiarias Comunes',
                                        color_continuous_scale='YlOrRd')
                        st.plotly_chart(fig2, use_container_width=True)
                        
                        agregar_reporte = st.checkbox("✅ Incluir en reporte PDF")
                        
                        st.download_button("📥 Exportar Excel", 
                                         exportar_excel(df_palabras, "Mineria_Texto"),
                                         file_name="mineria_texto.xlsx")
                    else:
                        st.info("No se encontraron palabras compartidas")
                else:
                    st.info("No hay egresos")
        
        if agregar_reporte and st.button("💾 Guardar análisis para reporte PDF"):
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reportes_generados (id_caso, tipo_reporte, configuracion, incluir_en_pdf)
                VALUES (?, ?, ?, 1)
            """, (id_caso, tipo_analisis, json.dumps(filtros)))
            conn.commit()
            st.success("✅ Análisis guardado para el reporte PDF")
        
        conn.close()

elif menu == "Reportes PDF":
    st.title("📄 Generación de Reportes PDF")
    
    conn = get_connection()
    df_casos = pd.read_sql_query("SELECT id_caso, nombre_caso FROM casos", conn)
    
    if df_casos.empty:
        st.warning("No hay casos disponibles")
        conn.close()
    else:
        caso_seleccionado = st.selectbox("Seleccionar Caso para Reporte", 
                                        df_casos['nombre_caso'].tolist())
        
        id_caso = df_casos[df_casos['nombre_caso'] == caso_seleccionado]['id_caso'].iloc[0]
        
        df_reportes_incluidos = pd.read_sql_query("""
            SELECT tipo_reporte, fecha_generacion 
            FROM reportes_generados 
            WHERE id_caso = ? AND incluir_en_pdf = 1
            ORDER BY fecha_generacion
        """, conn, params=[id_caso])
        
        if not df_reportes_incluidos.empty:
            st.markdown("### Análisis incluidos en el reporte:")
            st.dataframe(df_reportes_incluidos, use_container_width=True)
            
            if st.button("📄 Generar Reporte PDF", type="primary"):
                report_bar = st.progress(0, text="Iniciando generación de PDF...")
                
                try:
                    def update_report_bar(progreso):
                        report_bar.progress(progreso, text=f"Generando documento: {int(progreso*100)}%")
                    
                    pdf_buffer = generar_pdf_reporte(id_caso, conn, df_reportes_incluidos, progress_callback=update_report_bar)
                    
                    st.success("✅ Reporte PDF generado exitosamente")
                    
                    st.download_button(
                        label="📥 Descargar Reporte PDF",
                        data=pdf_buffer,
                        file_name=f"Informe_AML_{caso_seleccionado}_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    report_bar.empty()
                    st.error(f"Error al generar PDF: {str(e)}")
        else:
            st.info("No hay análisis marcados para incluir en el reporte. Ejecute análisis y márquelos para inclusión.")
        
        conn.close()