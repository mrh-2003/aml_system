import pandas as pd
import re
import sqlite3
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
import networkx as nx
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

def limpiar_glosa(glosa):
    if pd.isna(glosa):
        return ""
    glosa_str = str(glosa)
    glosa_limpia = re.sub(r'\d+', '', glosa_str)
    glosa_limpia = re.sub(r'[^\w\s]', ' ', glosa_limpia)
    glosa_limpia = ' '.join(glosa_limpia.split())
    return glosa_limpia.upper()

def cargar_datos(df, codigo_carga, conn, progress_callback=None):
    import time
    cursor = conn.cursor()
    
    try:
        if progress_callback:
            progress_callback(0.1, "Registrando carga en base de datos...")
        
        cursor.execute("INSERT INTO cargas (codigo_carga, registros_totales) VALUES (?, ?)",
                       (codigo_carga, len(df)))
        id_carga = cursor.lastrowid
        
        if progress_callback:
            progress_callback(0.2, f"Limpiando {len(df):,} glosas...")
        
        df['glosa_limpia'] = df['Glosa'].apply(limpiar_glosa)
        
        if progress_callback:
            progress_callback(0.4, "Mapeando columnas...")
        
        columnas_map = {
            'CODUNICOCLI_13_enc': 'codunicocli_13_enc',
            'TIPO DE MARCA': 'tipo_marca',
            'Delito': 'delito',
            'DESTIPDOCUMENTO': 'destipdocumento',
            'DESTIPBANCA': 'destipbanca',
            'SEGMENTO': 'segmento',
            'ACT.ECONOMICA': 'act_economica',
            'CODUNICOCLI_13': 'codunicocli_13',
            'CTACOMERCIAL': 'ctacomercial',
            'CODPRODUCTO': 'codproducto',
            'MONEDA': 'moneda',
            'FECAPERTURA': 'fecapertura',
            'FECCIERRE': 'feccierre',
            'MTOAPERTURA': 'mtoapertura',
            'Fecha': 'fecha',
            'Hora': 'hora',
            'FechaProc': 'fechaproc',
            'Glosa': 'glosa',
            'glosa_limpia': 'glosa_limpia',
            'Grupo': 'grupo',
            'Canal': 'canal',
            'CodAgencia': 'codagencia',
            'Agencia': 'agencia',
            'Monto': 'monto',
            'I / E': 'i_e',
            'TERMINAL': 'terminal',
            'OPERADOR': 'operador',
            'NUMSECUENCIAL': 'numsecuencial',
            'NUMREG': 'numreg'
        }
        
        df_insert = df.rename(columns=columnas_map)
        df_insert['id_carga'] = id_carga
        
        columnas_db = ['id_carga'] + [v for v in columnas_map.values()]
        df_insert = df_insert[columnas_db]
        
        if progress_callback:
            progress_callback(0.6, f"Insertando {len(df_insert):,} registros en base de datos...")
        
        chunk_size = 10000
        total_chunks = len(df_insert) // chunk_size + (1 if len(df_insert) % chunk_size else 0)
        
        for i in range(0, len(df_insert), chunk_size):
            chunk = df_insert.iloc[i:i+chunk_size]
            chunk.to_sql('transacciones', conn, if_exists='append', index=False)
            
            if progress_callback:
                progress = 0.6 + (0.35 * (i + chunk_size) / len(df_insert))
                progress_callback(min(progress, 0.95), 
                                f"Insertando registros: {min(i+chunk_size, len(df_insert)):,} / {len(df_insert):,}")
        
        if progress_callback:
            progress_callback(0.95, "Confirmando transacción...")
        
        conn.commit()
        
        if progress_callback:
            progress_callback(1.0, "¡Carga completada exitosamente!")
        
        return id_carga
        
    except Exception as e:
        conn.rollback()
        raise Exception(f"Error durante la carga de datos: {str(e)}")

def obtener_datos_caso(id_caso, conn, filtros=None):
    query = """
    SELECT t.* 
    FROM transacciones t
    INNER JOIN caso_involucrados ci ON t.codunicocli_13_enc = ci.codunicocli_13_enc
    WHERE ci.id_caso = ?
    """
    
    params = [id_caso]
    
    if filtros:
        if filtros.get('moneda') and filtros['moneda'] != 'AMBOS':
            query += " AND t.moneda = ?"
            params.append(filtros['moneda'])
        
        if filtros.get('tipo_documento') and filtros['tipo_documento'] != 'AMBOS':
            query += " AND t.destipdocumento = ?"
            params.append(filtros['tipo_documento'])
        
        if filtros.get('monto_min') is not None:
            query += " AND t.monto >= ?"
            params.append(filtros['monto_min'])
        
        if filtros.get('monto_max') is not None:
            query += " AND t.monto <= ?"
            params.append(filtros['monto_max'])
        
        if filtros.get('fecha_min'):
            query += " AND t.fecha >= ?"
            params.append(filtros['fecha_min'])
        
        if filtros.get('fecha_max'):
            query += " AND t.fecha <= ?"
            params.append(filtros['fecha_max'])
    
    df = pd.read_sql_query(query, conn, params=params)
    return df

def crear_grafo_coincidencias(df, tolerancia_horas=1):
    df_egresos = df[df['i_e'] == 'Egreso'].copy()
    df_ingresos = df[df['i_e'] == 'Ingreso'].copy()
    
    df_egresos['fecha_hora'] = pd.to_datetime(df_egresos['fecha'].astype(str) + ' ' + df_egresos['hora'].astype(str))
    df_ingresos['fecha_hora'] = pd.to_datetime(df_ingresos['fecha'].astype(str) + ' ' + df_ingresos['hora'].astype(str))
    
    coincidencias = []
    
    for _, egreso in df_egresos.iterrows():
        for _, ingreso in df_ingresos.iterrows():
            if egreso['codunicocli_13_enc'] != ingreso['codunicocli_13_enc']:
                if abs(egreso['monto'] - ingreso['monto']) < 0.01:
                    diff_tiempo = abs((egreso['fecha_hora'] - ingreso['fecha_hora']).total_seconds() / 3600)
                    if diff_tiempo <= tolerancia_horas:
                        coincidencias.append({
                            'origen': egreso['codunicocli_13_enc'][:8],
                            'destino': ingreso['codunicocli_13_enc'][:8],
                            'monto': egreso['monto'],
                            'fecha': egreso['fecha'],
                            'diff_horas': diff_tiempo
                        })
    
    if not coincidencias:
        return None, None
    
    df_coincidencias = pd.DataFrame(coincidencias)
    
    G = nx.DiGraph()
    
    for _, row in df_coincidencias.iterrows():
        if G.has_edge(row['origen'], row['destino']):
            G[row['origen']][row['destino']]['weight'] += 1
            G[row['origen']][row['destino']]['monto_total'] += row['monto']
        else:
            G.add_edge(row['origen'], row['destino'], weight=1, monto_total=row['monto'])
    
    pos = nx.spring_layout(G, k=2, iterations=50)
    
    edge_trace = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        weight = G[edge[0]][edge[1]]['weight']
        monto_total = G[edge[0]][edge[1]]['monto_total']
        
        edge_trace.append(
            go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode='lines',
                line=dict(width=weight*2, color='#888'),
                hoverinfo='text',
                text=f"Transacciones: {weight}<br>Monto total: {monto_total:,.2f}",
                showlegend=False
            )
        )
    
    node_trace = go.Scatter(
        x=[],
        y=[],
        text=[],
        mode='markers+text',
        hoverinfo='text',
        marker=dict(
            showscale=True,
            colorscale='YlOrRd',
            size=[],
            color=[],
            colorbar=dict(
                thickness=15,
                title='Grado del Nodo',
                xanchor='left',
                titleside='right'
            ),
            line_width=2
        ),
        textposition="top center"
    )
    
    for node in G.nodes():
        x, y = pos[node]
        node_trace['x'] += tuple([x])
        node_trace['y'] += tuple([y])
        node_trace['text'] += tuple([node])
        node_trace['marker']['size'] += tuple([20 + G.degree(node) * 5])
        node_trace['marker']['color'] += tuple([G.degree(node)])
    
    fig = go.Figure(data=edge_trace + [node_trace],
                    layout=go.Layout(
                        title='Red de Coincidencias de Transacciones',
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=0,l=0,r=0,t=40),
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        height=600
                    ))
    
    return fig, df_coincidencias

def generar_pdf_reporte(id_caso, conn, reportes_incluidos, progress_callback=None):
    try:
        if progress_callback:
            progress_callback(0.1, "Inicializando documento PDF...")
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=12,
            spaceBefore=12
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=10,
            alignment=TA_JUSTIFY,
            spaceAfter=12
        )
        
        if progress_callback:
            progress_callback(0.2, "Obteniendo información del caso...")
        
        cursor = conn.cursor()
        caso_info = cursor.execute("SELECT nombre_caso, descripcion FROM casos WHERE id_caso = ?", (id_caso,)).fetchone()
        
        story.append(Paragraph("INFORME DE ANÁLISIS FINANCIERO", title_style))
        story.append(Paragraph(f"Caso: {caso_info[0]}", heading_style))
        story.append(Paragraph(f"Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}", body_style))
        story.append(Spacer(1, 0.3*inch))
        
        if progress_callback:
            progress_callback(0.3, "Generando resumen ejecutivo...")
        
        if caso_info[1]:
            story.append(Paragraph("Descripción del Caso", heading_style))
            story.append(Paragraph(caso_info[1], body_style))
            story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph("RESUMEN EJECUTIVO", heading_style))
        
        df_caso = obtener_datos_caso(id_caso, conn)
        
        num_involucrados = df_caso['codunicocli_13_enc'].nunique()
        num_transacciones = len(df_caso)
        monto_total = df_caso['monto'].sum()
        
        resumen_text = f"""
        El presente informe analiza {num_transacciones:,} transacciones correspondientes a {num_involucrados} 
        personas investigadas, con un monto total acumulado de {monto_total:,.2f}. 
        El análisis se enfoca en la detección de patrones sospechosos relacionados con lavado de activos 
        y actividades financieras ilícitas.
        """
        story.append(Paragraph(resumen_text, body_style))
        story.append(PageBreak())
        
        if progress_callback:
            progress_callback(0.5, "Procesando hallazgos principales...")
        
        reportes_query = """
        SELECT tipo_reporte, configuracion, fecha_generacion 
        FROM reportes_generados 
        WHERE id_caso = ? AND incluir_en_pdf = 1
        ORDER BY fecha_generacion
        """
        reportes = cursor.execute(reportes_query, (id_caso,)).fetchall()
        
        story.append(Paragraph("HALLAZGOS PRINCIPALES", heading_style))
        
        for i, (tipo_reporte, config, fecha) in enumerate(reportes, 1):
            story.append(Paragraph(f"{i}. {tipo_reporte}", heading_style))
            story.append(Paragraph(f"Análisis realizado el: {fecha}", body_style))
            story.append(Spacer(1, 0.2*inch))
            
            if progress_callback:
                progress_callback(0.5 + (0.3 * i / len(reportes)), 
                                f"Procesando hallazgo {i}/{len(reportes)}...")
        
        if progress_callback:
            progress_callback(0.85, "Generando conclusiones...")
        
        story.append(PageBreak())
        story.append(Paragraph("CONCLUSIONES", heading_style))
        
        conclusiones = """
        Basado en el análisis exhaustivo de las transacciones financieras, se han identificado 
        patrones de comportamiento que ameritan investigación adicional. Se recomienda profundizar 
        en las relaciones detectadas y realizar verificaciones de campo sobre las actividades 
        económicas declaradas versus las operaciones realizadas.
        """
        story.append(Paragraph(conclusiones, body_style))
        
        if progress_callback:
            progress_callback(0.95, "Construyendo documento PDF...")
        
        doc.build(story)
        buffer.seek(0)
        
        if progress_callback:
            progress_callback(1.0, "¡PDF generado exitosamente!")
        
        return buffer
        
    except Exception as e:
        raise Exception(f"Error al generar PDF: {str(e)}")

def exportar_excel(df, nombre_hoja="Datos"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=nombre_hoja, index=False)
    output.seek(0)
    return output
