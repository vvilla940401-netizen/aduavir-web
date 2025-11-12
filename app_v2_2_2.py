# app_v2_2_2.py
import streamlit as st
import pandas as pd
import os
import re
import unicodedata
from datetime import datetime
from dotenv import load_dotenv
import io

# ===========================
# CONFIG INICIAL
# ===========================
st.set_page_config(page_title="ADUAVIR 2.2.2", page_icon="🧭", layout="wide")
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SINGLE_USER = {"user": "aduavir_admin", "password": "aduavir2025"}

CATALOG_PATH = "catalogo_errores_unificado_CORREGIDO.xlsx"
LOG_PATH = "consultas_log.csv"
LOGO_URL = "https://raw.githubusercontent.com/vvilla940401-netizen/aduavir-web/main/assets/logo_aduavir.png"

# ===========================
# ESTILOS Y ENCABEZADO
# ===========================
st.markdown(f"""
<style>
:root {{
  --main-blue: #004b97;
  --gold: #d4af37;
  --text-light: #f5f5f5;
  --bg-dark: #000000;
}}
[data-testid="stAppViewContainer"] {{
  background-color: var(--bg-dark);
  background-image: url('{LOGO_URL}');
  background-repeat: no-repeat;
  background-position: center;
  background-size: 70%;
  opacity: 1 !important;
}}
[data-testid="stAppViewContainer"]::before {{
  content: "";
  position: fixed;
  inset: 0;
  background-color: rgba(0,0,0,0.92);
  z-index: 0;
}}
.header {{
  display:flex; align-items:center; gap:18px; padding:10px 0; position:relative; z-index:1;
}}
.header img {{ height:80px; border-radius:10px; }}
.app-title {{
  color: var(--gold);
  font-size:28px;
  margin:0;
  text-shadow: 1px 1px 2px #000;
}}
.app-sub {{
  color: var(--text-light);
  margin:0;
  font-size:15px;
}}
.block {{
  background: rgba(25,25,25,0.85);
  padding:22px;
  border-radius:14px;
  box-shadow:0 6px 20px rgba(212,175,55,0.25);
  color: var(--text-light);
  position:relative;
  z-index:1;
}}
.stTextInput>div>div>input {{
  background-color: #111 !important;
  color: var(--text-light) !important;
  border: 1px solid #555 !important;
}}
.stButton>button {{
  background: linear-gradient(90deg, var(--gold), #ffcc00);
  color: #000;
  font-weight: bold;
  border-radius: 6px;
  box-shadow: 0 0 8px rgba(255,215,0,0.5);
}}
.stButton>button:hover {{
  background: linear-gradient(90deg, #ffcc00, var(--gold));
  transform: scale(1.03);
  transition: all 0.2s ease-in-out;
}}
.result-card {{
  background: rgba(40,40,40,0.95);
  padding:16px;
  border-radius:10px;
  margin-top:15px;
  color: var(--text-light);
  border-left: 4px solid var(--gold);
}}
small, .small-muted {{ color:#ccc; font-size:13px; }}
.stDownloadButton>button {{
  background-color: var(--main-blue);
  color: var(--text-light);
  font-weight:bold;
  border-radius: 6px;
}}
.stDownloadButton>button:hover {{
  background-color: #0056b3;
}}
.stDataFrame {{
  color: var(--text-light) !important;
}}
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="header">
    <img src="{LOGO_URL}" alt="logo">
    <div>
        <h1 class="app-title">🧭 ADUAVIR 2.2.2</h1>
        <div class="app-sub">Su aliado en el cumplimiento</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ===========================
# CARGA DE CATÁLOGO
# ===========================
@st.cache_data
def load_catalog(path=CATALOG_PATH):
    df = pd.read_excel(path, dtype=str).fillna("")
    orig_map = {}

    def _norm_col(c):
        s = str(c).strip()
        s_norm = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
        s_norm = re.sub(r"[^A-Za-z0-9]", "", s_norm).lower()
        orig_map[s_norm] = c
        return s_norm

    df.columns = [_norm_col(c) for c in df.columns]
    return df, orig_map

def normalize_text(text):
    if not isinstance(text, str):
        return ""
    s = text.lower()
    s = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

# ===========================
# CONSULTA Y FILTRO
# ===========================
def detect_column_filter(q):
    qnorm = q.lower()
    col_aliases = {
        "registro": ["registro", "reg"],
        "campo": ["campo", "cam"],
        "codigo": ["codigo", "cod"],
        "tipo": ["tipo", "clase"],
    }
    for key, aliases in col_aliases.items():
        for a in aliases:
            m = re.search(rf"\b{re.escape(a)}\b\W*(\d+)\b", qnorm)
            if m:
                return key, m.group(1)
    return None, None

def parse_numeric_sequence(q):
    nums = re.findall(r"\d+", q)
    if len(nums) >= 4:
        return {"codigo": nums[0], "tipo": nums[1], "registro": nums[2], "campo": nums[3]}
    joined = re.sub(r"\D", "", q)
    if len(joined) == 6:
        return {"codigo": joined[0], "tipo": joined[1], "registro": joined[2:5], "campo": joined[5]}
    return {}

def search_error(df, query, limit=25):
    if df is None or df.empty or not query.strip():
        return df.iloc[0:0]
    qnorm = normalize_text(query)
    expected = {
        "codigo": "codigo", "tipo": "tipo", "registro": "registro", "campo": "campo",
        "descripcion": "descripciondeerror", "solucion": "solucion", "observacion": "observacionejemplo",
    }
    col_key, col_val = detect_column_filter(query)
    seq = parse_numeric_sequence(query)

    def find_col(possible):
        for p in possible:
            if p in df.columns:
                return p
        return None

    if seq:
        mask = pd.Series(True, index=df.index)
        for k, v in seq.items():
            c = find_col([expected.get(k, k), k])
            if c:
                mask &= df[c].astype(str).str.strip() == str(v)
        return df[mask].head(limit)

    if col_key:
        colmap = {"registro": ["registro"], "campo": ["campo"], "codigo": ["codigo"], "tipo": ["tipo", "clase"]}
        c = find_col(colmap[col_key])
        if c:
            mask = df[c].astype(str).str.strip() == str(col_val)
            return df[mask].head(limit)
        return df.iloc[0:0]

    candidate_cols = [c for c in ["descripciondeerror", "solucion", "observacionejemplo", "ejemplo", "llenadoobservaciones"] if c in df.columns]
    mask = pd.Series(False, index=df.index)
    for c in candidate_cols:
        try:
            mask |= df[c].astype(str).apply(normalize_text).str.contains(qnorm, na=False)
        except Exception:
            mask |= df[c].astype(str).str.contains(query, na=False, regex=False)
    return df[mask].head(limit)

# ===========================
# BITÁCORA
# ===========================
def log_query(user, columna, consulta, resultados):
    row = {
        "fecha_hora": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "usuario": user,
        "columna_filtrada": columna or "",
        "consulta": consulta,
        "resultados": int(resultados),
    }
    df_row = pd.DataFrame([row])
    df_row.to_csv(LOG_PATH, mode="a", header=not os.path.exists(LOG_PATH), index=False, encoding="utf-8-sig")

def get_log_bytesio():
    if not os.path.exists(LOG_PATH):
        return None
    with open(LOG_PATH, "rb") as f:
        return io.BytesIO(f.read())

# ===========================
# LOGIN
# ===========================
def simple_login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user = ""
    if st.session_state.logged_in:
        return True
    st.markdown("<div class='block'>", unsafe_allow_html=True)
    st.write("**Acceso restringido — área de pruebas**")
    user = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if user == SINGLE_USER["user"] and pwd == SINGLE_USER["password"]:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ===========================
# MAIN APP
# ===========================
simple_login()
st.markdown("<div class='block'>", unsafe_allow_html=True)

with st.spinner("Cargando catálogo..."):
    df_catalog, orig_map = load_catalog()
st.session_state["orig_map"] = orig_map

if df_catalog.empty:
    st.error("No se pudo cargar el catálogo. Verifica el archivo en la raíz del repo.")
    st.stop()

st.success(f"Catálogo cargado ({len(df_catalog)} filas).")

query = st.text_input("Ingrese código, registro o descripción:",
                      placeholder="Ejemplo: 1 3 353 6 | registro 701 | tipo 1 | describir el error")

if st.button("Buscar"):
    current_user = st.session_state.get("user", SINGLE_USER["user"])
    results = search_error(df_catalog, query, limit=25)
    detected_col, detected_val = detect_column_filter(query)
    seq = parse_numeric_sequence(query)
    col_for_log = ""
    if detected_col:
        col_for_log = f"{detected_col}:{detected_val}"
    elif seq:
        col_for_log = ",".join([f"{k}:{v}" for k, v in seq.items()])

    st.markdown('<div class="result-card">', unsafe_allow_html=True)
    if results is not None and not results.empty:
        prefer = ["tipo", "registro", "campo", "descripciondeerror", "solucion", "observacionejemplo"]
        show_cols = [c for c in prefer if c in results.columns]
        rename_map = {}
        orig_map = st.session_state.get("orig_map", {})
        for c in show_cols:
            orig = orig_map.get(c, c)
            if c == "descripciondeerror":
                nice = "DESCRIPCIÓN DE ERROR"
            elif c in ["observacionejemplo", "ejemplo"]:
                nice = "OBSERVACIÓN / EJEMPLO"
            else:
                nice = orig
            rename_map[c] = nice

        display_df = results[show_cols].reset_index(drop=True).rename(columns=rename_map)
        st.markdown(f"**Consulta:** `{query}`")
        st.write(f"Se encontraron **{len(results)}** coincidencias (máx 25).")
        st.dataframe(display_df, use_container_width=True, height=700)
        log_query(current_user, col_for_log, query, len(results))
    else:
        st.warning("No se encontraron coincidencias para la consulta.")
        log_query(current_user, col_for_log, query, 0)
    st.markdown("</div>", unsafe_allow_html=True)

log_bio = get_log_bytesio()
if log_bio:
    st.download_button("📥 Descargar bitácora (CSV)", data=log_bio, file_name="consultas_log.csv", mime="text/csv")
else:
    st.info("Aún no hay registros en la bitácora.")

st.markdown("---")
st.caption("ADUAVIR — Plataforma interna de consulta © 2025")