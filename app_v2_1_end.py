import streamlit as st
import pandas as pd
import os
import re
import unicodedata
from dotenv import load_dotenv

# =====================================
# CONFIGURACIÓN INICIAL
# =====================================
st.set_page_config(page_title="ADUAVIR 2.1.3", page_icon="🧭", layout="centered")

# Carga variables de entorno
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Clave solo desde .env o Render

# =====================================
# FUNCIONES DE UTILIDAD
# =====================================

@st.cache_data
def load_catalog():
    """Carga el catálogo de errores unificado y normaliza encabezados."""
    try:
        df = pd.read_excel("catalogo_errores_unificado.xlsx", dtype=str).fillna("")

        # Normalizar nombres de columna
        def _norm_col(c):
            if not isinstance(c, str):
                c = str(c)
            s = c.strip()
            s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')  # Quitar acentos
            s = re.sub(r'[^a-zA-Z0-9]', '', s)  # Dejar solo letras y números
            return s.lower()

        original_cols = list(df.columns)
        df.columns = [_norm_col(c) for c in df.columns]
        df._original_columns = original_cols
        return df
    except Exception as e:
        st.error(f"⚠️ No se pudo cargar el catálogo: {e}")
        return pd.DataFrame()


def normalize_text(text):
    """Normaliza texto para comparación flexible"""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9áéíóúñü\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def search_error(df, query):
    """Busca coincidencias en el dataframe con columnas normalizadas."""
    q = normalize_text(query)

    # Columnas esperadas (normalizadas)
    c_codigo = "codigo"
    c_clase = "clase"
    c_registro = "normativaregistro"
    c_campo = "camporelacionado"
    posibles_error_cols = ["errordescripcion", "descripcion", "error"]

    codigo = clase = registro = campo = None
    patterns = {
        "codigo": r"codigo\s*(\d+)",
        "clase": r"clase\s*(\d+)",
        "registro": r"registro\s*(\d+)",
        "campo": r"campo\s*(\d+)"
    }

    for key, pat in patterns.items():
        m = re.search(pat, q)
        if m:
            if key == "codigo": codigo = m.group(1)
            elif key == "clase": clase = m.group(1)
            elif key == "registro": registro = m.group(1)
            elif key == "campo": campo = m.group(1)

    if df is None or df.empty:
        return df

    mask = pd.Series([True] * len(df))

    if codigo and c_codigo in df.columns:
        mask &= df[c_codigo].astype(str) == codigo
    if clase and c_clase in df.columns:
        mask &= df[c_clase].astype(str) == clase
    if registro and c_registro in df.columns:
        mask &= df[c_registro].astype(str) == registro
    if campo and c_campo in df.columns:
        mask &= df[c_campo].astype(str) == campo

    if not mask.any():
        parts = []
        if c_codigo in df.columns:
            parts.append(df[c_codigo].astype(str).apply(normalize_text).str.contains(q, na=False))
        for col_try in posibles_error_cols:
            if col_try in df.columns:
                parts.append(df[col_try].astype(str).apply(normalize_text).str.contains(q, na=False))
        if c_clase in df.columns:
            parts.append(df[c_clase].astype(str).apply(normalize_text).str.contains(q, na=False))
        if c_registro in df.columns:
            parts.append(df[c_registro].astype(str).apply(normalize_text).str.contains(q, na=False))
        if c_campo in df.columns:
            parts.append(df[c_campo].astype(str).apply(normalize_text).str.contains(q, na=False))

        if parts:
            combined = parts[0]
            for p in parts[1:]:
                combined = combined | p
            mask = combined
        else:
            return df.iloc[0:0]

    return df[mask]


@st.cache_data
def load_normative_snippets():
    """Carga fragmentos de documentos normativos"""
    base_text = ""
    data_dir = os.path.join(os.getcwd(), "data")
    if os.path.exists(data_dir):
        for fname in os.listdir(data_dir):
            path = os.path.join(data_dir, fname)
            if os.path.isfile(path):
                base_text += f"\n# === {fname} ===\n"
                try:
                    with open(path, "rb") as f:
                        content = f.read(80000)
                        base_text += f"[Fragmento cargado: {len(content)} bytes]"
                except Exception as e:
                    base_text += f"[Error al leer {fname}: {e}]"
    return base_text


def highlight_matches(row, query):
    """Resalta los campos que coinciden con la consulta"""
    q = normalize_text(query)

    def highlight_cell(val):
        val_norm = normalize_text(str(val))
        if val_norm and q and q in val_norm:
            return f"background-color: #FFFACD"
        return ""

    return row.apply(highlight_cell)


# =====================================
# INTERFAZ DE USUARIO
# =====================================
st.title("🧭 ADUAVIR 2.1.3 — Asistente Aduanal Inteligente")
st.markdown("Versión 2.1.3 | Catálogo enriquecido con búsqueda avanzada")

with st.spinner("Cargando catálogo y normativa..."):
    df_catalog = load_catalog()
    normative_context = load_normative_snippets()

if df_catalog.empty:
    st.error("⚠️ No se pudo cargar el catálogo. Verifica el archivo Excel.")
else:
    st.success("✅ Catálogo y normativa cargados correctamente.")

query = st.text_input(
    "Ingrese el código o descripción del error:",
    placeholder="Ejemplo: 2 3 500 2 o tipo de cambio",
)

import io
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# ---------- Función para exportar resultados a PDF con marca de agua ----------
def export_results_to_pdf(df, title="Resultado ADUAVIR", watermark_text="ADUAVIR — CONFIDENCIAL"):
    """
    Genera un PDF (en memoria) con las primeras N filas del dataframe y una marca de agua.
    Retorna bytesIO listo para descargar.
    """
    # Limitar filas para no exponer todo (ajustable)
    MAX_ROWS_PDF = 50
    df_to_print = df.head(MAX_ROWS_PDF).copy()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=20, rightMargin=20, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 8))

    # Tabla: primero la cabecera limpia
    data = [list(df_to_print.columns)]
    for _, row in df_to_print.iterrows():
        data.append([str(x) for x in row.tolist()])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("FONTSIZE", (0,0), (-1, -1), 8),
    ]))
    story.append(table)
    story.append(Spacer(1, 6))

    # Pie con aviso
    story.append(Paragraph("Generado desde ADUAVIR — Sólo resumen del resultado. No contiene catálogo completo.", styles["Italic"]))

    # Construir PDF en el buffer
    doc.build(story, onFirstPage=lambda canvas, doc: _draw_watermark(canvas, watermark_text),
                    onLaterPages=lambda canvas, doc: _draw_watermark(canvas, watermark_text))
    buffer.seek(0)
    return buffer

def _draw_watermark(canvas, text):
    canvas.saveState()
    canvas.setFont("Helvetica", 60)
    canvas.setFillColorRGB(0.7, 0.7, 0.7, alpha=0.12)  # gris claro y algo transparente
    canvas.translate(300, 160)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, text)
    canvas.restoreState()

# ---------- UI para búsqueda y visualización segura ----------
if st.button("🔍 Interpretar error"):
    if not query.strip():
        st.warning("Por favor ingrese un código o descripción válida.")
    else:
        results = search_error(df_catalog, query)

        # Si la búsqueda devolvió filas
        if results is not None and not results.empty:
            # Mostramos un número limitado de filas para evitar exponer todo el catálogo
            MAX_DISPLAY_ROWS = 100
            display_df = results.reset_index(drop=True).head(MAX_DISPLAY_ROWS)

            # Mostrar solo columnas relevantes (usar los originales si están disponibles)
            # Si el dataframe tiene ._original_columns, reconstruimos nombres bonitos para la vista
            if hasattr(results, "_original_columns"):
                # mapeo: normalized -> original
                norm_to_orig = {}
                for orig in results._original_columns:
                    key = re.sub(r'[^a-zA-Z0-9]', '', str(orig)).lower()
                    norm_to_orig[key] = orig
                # ordenar columnas por preferencia si existen
                preferidas_norm = ["codigo", "clase", "normativaregistro", "camporelacionado", "errordescripcion", "solucion"]
                cols_to_show = [norm_to_orig[c] for c in preferidas_norm if c in norm_to_orig]
                # si no hay preferidas, tomar primeras 6 columnas
                if not cols_to_show:
                    cols_to_show = list(display_df.columns[:6])
                # mapear display_df a columnas originales si están presentes
                # Primero, si display_df tiene columnas normalizadas, intentar renombrarlas a originales
                try:
                    # busqueda de coincidencias por clave normalizada
                    rename_map = {}
                    for col in display_df.columns:
                        key = re.sub(r'[^a-zA-Z0-9]', '', str(col)).lower()
                        if key in norm_to_orig:
                            rename_map[col] = norm_to_orig[key]
                    display_df = display_df.rename(columns=rename_map)
                except Exception:
                    pass
            else:
                # no hay nombres originales: mostrar primeras 6 columnas
                cols_to_show = list(display_df.columns[:6])

            # finalmente recortar por las columnas elegidas (si existen)
            cols_to_show = [c for c in cols_to_show if c in display_df.columns]
            if cols_to_show:
                safe_view = display_df[cols_to_show]
            else:
                safe_view = display_df

            st.success(f"🔎 Se encontraron {len(results)} coincidencias (mostrando {len(safe_view)} filas).")
            st.dataframe(safe_view)

            # Botón para generar PDF del recorte (solo del resultado actual)
            pdf_buffer = export_results_to_pdf(safe_view, title=f"ADUAVIR — Resultado para: {query}", watermark_text="ADUAVIR — CONFIDENCIAL")
            st.download_button(
                label="📄 Descargar comprobante (PDF) — solo resultado actual",
                data=pdf_buffer,
                file_name=f"aduavir_resultado_{query.replace(' ','_')}.pdf",
                mime="application/pdf"
            )

        else:
            st.warning("⚠️ No se encontró el error en el catálogo.")

st.markdown("---")
st.caption("Desarrollado por Vanessa Villa © 2025 | ADUAVIR v2.1.3 — Solo catálogo y normativa")