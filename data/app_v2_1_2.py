# =====================================
# ADUAVIR 2.1.3 — Asistente Aduanal Inteligente
# =====================================

import streamlit as st
import pandas as pd
import os
import re
from dotenv import load_dotenv
from openai import OpenAI

# =====================================
# CONFIGURACIÓN INICIAL
# =====================================
st.set_page_config(page_title="ADUAVIR 2.1.3", page_icon="🧭", layout="centered")
load_dotenv()
# API Key: usar la del .env o temporalmente la nueva directamente
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or "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"

# =====================================
# FUNCIONES DE UTILIDAD
# =====================================
@st.cache_data
def load_catalog():
    """Carga el catálogo de errores unificado"""
    try:
        df = pd.read_excel("catalogo_errores_unificado.xlsx", dtype=str).fillna("")
        df.columns = [c.strip() for c in df.columns]  # Limpia espacios
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
    """Busca coincidencias por código, texto o combinación numérica"""
    q = normalize_text(query)
    mask = (
        df["CODIGO"].astype(str).apply(normalize_text).str.contains(q, na=False)
        | df["Error / Descripción"].astype(str).apply(normalize_text).str.contains(q, na=False)
        | df["Clase"].astype(str).apply(normalize_text).str.contains(q, na=False)
        | df["Normativa / Registro"].astype(str).apply(normalize_text).str.contains(q, na=False)
        | df["Campo Relacionado"].astype(str).apply(normalize_text).str.contains(q, na=False)
    )
    return df[mask]

def interpret_with_openai(query, base_context):
    """Consulta a OpenAI para generar una interpretación del error"""
    if not OPENAI_API_KEY:
        return "⚠️ No se encontró la clave OPENAI_API_KEY. No se puede usar la IA."
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        prompt = f"""
Eres un especialista en comercio exterior mexicano. Analiza el siguiente error o texto relacionado con validación o prevalidación aduanal.

Error o texto ingresado:
{query}

Base normativa de referencia (extracto):
{base_context[:2000]}

Responde con una explicación clara, técnica y profesional, citando fundamentos si los hay (RGCE, Anexo 22, VOCE).
"""
        response = client.responses.create(
            model="gpt-4o-mini",
            input=prompt,
            max_output_tokens=400,
        )
        return response.output_text.strip()
    except Exception as e:
        return f"⚠️ Error al consultar OpenAI: {e}"

@st.cache_data
def load_normative_snippets():
    """Carga fragmentos de documentos normativos"""
    base_text = ""
    data_dir = os.path.join(os.getcwd(), "data")
    for fname in os.listdir(data_dir):
        path = os.path.join(data_dir, fname)
        if os.path.isfile(path):
            base_text += f"\n=== {fname} ===\n"
            try:
                with open(path, "rb") as f:
                    content = f.read(80000)
                    base_text += f"[Fragmento cargado: {len(content)} bytes]"
            except Exception as e:
                base_text += f"[Error al leer {fname}: {e}]"
    return base_text

# =====================================
# INTERFAZ DE USUARIO
# =====================================
st.title("🧭 ADUAVIR 2.1.3 — Asistente Aduanal Inteligente")
st.markdown("Versión 2.1.3 | Catálogo enriquecido con búsqueda avanzada y razonamiento IA")

with st.spinner("Cargando catálogo y normativa..."):
    df_catalog = load_catalog()
    normative_context = load_normative_snippets()
st.success("✅ Catálogo y normativa cargados correctamente.")

query = st.text_input(
    "Ingrese el código o descripción del error:",
    placeholder="Ejemplo: 2 3 500 2 o tipo de cambio",
)

if st.button("🔍 Interpretar error"):
    if not query.strip():
        st.warning("Por favor ingrese un código o descripción válida.")
    else:
        results = search_error(df_catalog, query)

        if not results.empty:
            st.success(f"🔎 Se encontraron {len(results)} coincidencias:")
            for _, row in results.iterrows():
                st.markdown("---")
                st.markdown(f"**Código:** {row.get('CODIGO', '')}")
                st.markdown(f"**Clase:** {row.get('Clase', '')}")
                st.markdown(f"**Normativa / Registro:** {row.get('Normativa / Registro', '')}")
                st.markdown(f"**Campo Relacionado:** {row.get('Campo Relacionado', '')}")
                st.markdown(f"**Descripción del Error:** {row.get('Error / Descripción', '')}")
                st.markdown(f"**Solución:** {row.get('Solución', '')}")
                st.markdown(f"**Ejemplo / Referencia:** {row.get('Ejemplo / Referencia', '')}")
                st.markdown(f"**Criterio Relacionado:** {row.get('Criterio Relacionado', '')}")
                st.markdown(f"**Llenado / Observaciones:** {row.get('Llenado / Observaciones', '')}")

                # ✅ Generar razonamiento IA para cada coincidencia
                razonamiento_ia = interpret_with_openai(row.get('Error / Descripción', ''), normative_context)
                st.markdown(f"**Razonamiento (IA):** {razonamiento_ia}")
        else:
            st.warning("⚠️ No se encontró el error en el catálogo. Consultando con la IA...")
            interpretation = interpret_with_openai(query, normative_context)
            st.markdown("### 💡 Interpretación generada por ADUAVIR IA")
            st.markdown(interpretation)

st.markdown("---")
st.caption("Desarrollado por Vanessa Villa © 2025 | ADUAVIR v2.1.3 — Versión final con razonamiento IA")