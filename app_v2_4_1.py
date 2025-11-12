"""
ADUAVIR 2.4.1 — Copilot Aduanal (versión estable para Render)
- Búsqueda precisa por código, tipo, registro, campo o texto
- Multiusuario: admin (descarga) + supervisores (solo consulta)
- Copilot Aduanal (opcional, usa OPENAI_API_KEY)
- Tema oscuro con logo sobrepuesto (no transparente)
"""

import streamlit as st
import pandas as pd
import os, re, unicodedata, io
from datetime import datetime
from dotenv import load_dotenv

try:
    import openai
except ImportError:
    openai = None

# ===============================
# CONFIGURACIÓN BÁSICA
# ===============================
st.set_page_config(page_title="🧭 ADUAVIR 2.4.1 — Copilot Aduanal", page_icon="🧭", layout="wide")
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
if openai and OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

CATALOG_PATH = "catalogo_errores_unificado_CORREGIDO.xlsx"
LOG_PATH = "consultas_log.csv"
LOGO_URL = "https://raw.githubusercontent.com/vvilla940401-netizen/aduavir-web/main/assets/logo_aduavir.png"

USERS = {
    "aduavir_admin": {"pwd": "aduavir2025", "role": "admin"},
    "supervisora": {"pwd": "super2025", "role": "readonly"},
    "supervisor": {"pwd": "super2025", "role": "readonly"},
}

# ===============================
# ESTILOS
# ===============================
st.markdown(f"""
<style>
:root {{
  --accent: #c21b2b;
  --bg: #000;
  --muted: #b8c0cc;
}}
body, [data-testid="stAppViewContainer"] {{
  background-color: var(--bg) !important;
  color: white !important;
}}
.header {{
  display:flex; align-items:center; gap:18px; padding:12px 0;
}}
.header img {{
  height:72px; border-radius:8px; box-shadow:0 4px 16px rgba(0,0,0,0.5);
}}
.app-title {{
  font-size:22px; color:var(--accent); font-weight:700; margin:0;
}}
.app-sub {{
  color:var(--muted); font-size:13px; margin:0;
}}
.block {{
  background: rgba(255,255,255,0.06);
  padding:18px; border-radius:12px; box-shadow: 0 6px 20px rgba(0,0,0,0.4);
}}
.bg-logo {{
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  opacity: 0.18;
  width: 65%;
  max-width: 1000px;
  z-index: 0;
  pointer-events: none;
  filter: contrast(1.1);
}}
.result-card {{
  background: rgba(255,255,255,0.05);
  padding:16px; border-radius:10px; margin-bottom:12px;
}}
</style>
""", unsafe_allow_html=True)

st.markdown(f'<img class="bg-logo" src="{LOGO_URL}" alt="logo">', unsafe_allow_html=True)
st.markdown(f"""
<div class="header">
  <img src="{LOGO_URL}" alt="logo">
  <div>
    <div class="app-title">🧭 ADUAVIR 2.4.1 — Copilot Aduanal</div>
    <div class="app-sub">Su aliado en el cumplimiento</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ===============================
# FUNCIONES
# ===============================
@st.cache_data
def load_catalog(path=CATALOG_PATH):
    try:
        df = pd.read_excel(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame(), {}
    orig_map = {}
    def _norm(c):
        s = str(c).strip()
        s_norm = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
        s_norm = re.sub(r"[^A-Za-z0-9]", "", s_norm).lower()
        orig_map[s_norm] = c
        return s_norm
    df.columns = [_norm(c) for c in df.columns]
    return df, orig_map

def normalize_text(t):
    if not isinstance(t, str): return ""
    s = unicodedata.normalize("NFKD", t.lower()).encode("ASCII", "ignore").decode("ASCII")
    return re.sub(r"[^a-z0-9\s]", " ", s).strip()

def detect_column_filter(q):
    q = q.lower()
    for k, pats in {"registro":["registro"],"campo":["campo"],"tipo":["tipo","clase"],"codigo":["codigo","cod"]}.items():
        for p in pats:
            m = re.search(rf"{p}\s*(\d+)", q)
            if m: return k, m.group(1)
    return None, None

def parse_numeric_sequence(q):
    nums = re.findall(r"\d+", q)
    if len(nums)>=4:
        return {"codigo":nums[0],"tipo":nums[1],"registro":nums[2],"campo":nums[3]}
    return {}

def search_error(df, q, limit=40):
    if df.empty or not q.strip(): return df.iloc[0:0]
    seq = parse_numeric_sequence(q)
    ck, cv = detect_column_filter(q)
    expected = {"codigo":"codigo","tipo":"tipo","registro":"registro","campo":"campo"}
    if seq:
        mask = pd.Series(True,index=df.index)
        for k,v in seq.items():
            c = expected.get(k,k)
            if c in df.columns: mask &= df[c].astype(str)==str(v)
        return df[mask].head(limit)
    if ck:
        c = expected.get(ck, ck)
        if c in df.columns:
            return df[df[c].astype(str)==str(cv)].head(limit)
    qn = normalize_text(q)
    mask = pd.Series(False,index=df.index)
    for c in df.columns:
        mask |= df[c].astype(str).apply(normalize_text).str.contains(qn,na=False)
    return df[mask].head(limit)

def log_query(user, col, consulta, resultados):
    row = pd.DataFrame([{
        "fecha_hora": datetime.utcnow().isoformat(timespec="seconds")+"Z",
        "usuario": user, "columna": col or "", "consulta": consulta, "resultados": resultados
    }])
    if not os.path.exists(LOG_PATH): row.to_csv(LOG_PATH,index=False,encoding="utf-8-sig")
    else: row.to_csv(LOG_PATH,mode="a",header=False,index=False,encoding="utf-8-sig")

def get_log():
    return io.BytesIO(open(LOG_PATH,"rb").read()) if os.path.exists(LOG_PATH) else None

def copilot_interpretation(prompt):
    if not (openai and OPENAI_API_KEY): return None
    try:
        r=openai.ChatCompletion.create(
            model=OPENAI_MODEL,
            messages=[
                {"role":"system","content":"Eres un especialista en glosa aduanal de México. Explica brevemente el error, la interpretación y la acción correcta."},
                {"role":"user","content":prompt}
            ], max_tokens=300, temperature=0.2)
        return r.choices[0].message.content.strip()
    except Exception as e:
        st.warning(f"Copilot no disponible: {e}")
        return None

# ===============================
# LOGIN
# ===============================
if "auth" not in st.session_state:
    st.session_state.auth=False
    st.session_state.user=None
    st.session_state.role=None

if not st.session_state.auth:
    st.markdown("<div class='block'>",unsafe_allow_html=True)
    u=st.text_input("Usuario")
    p=st.text_input("Contraseña",type="password")
    if st.button("Ingresar"):
        if u in USERS and p==USERS[u]["pwd"]:
            st.session_state.auth=True
            st.session_state.user=u
            st.session_state.role=USERS[u]["role"]
            st.success("✅ Acceso concedido.")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.stop()

# ===============================
# MAIN
# ===============================
st.markdown("<div class='block'>",unsafe_allow_html=True)
df, orig_map = load_catalog()
if df.empty:
    st.error("No se pudo cargar el catálogo.")
    st.stop()

st.success(f"Catálogo cargado ({len(df)} filas).")
query = st.text_input("Ingrese código, registro o descripción:",placeholder="Ejemplo: 1 3 353 6 | registro 701 | campo 3 | tipo 1")

col1,col2=st.columns([4,1])
if col2.button("Buscar"):
    res=search_error(df,query,limit=40)
    user=st.session_state.user
    col, _ = detect_column_filter(query)
    seq=parse_numeric_sequence(query)
    col_for_log = col or ",".join([f"{k}:{v}" for k,v in seq.items()])
    if not res.empty:
        st.write(f"**{len(res)} coincidencias encontradas.**")
        st.dataframe(res,use_container_width=True,height=700)
        log_query(user,col_for_log,query,len(res))
        if len(res)==1 or seq:
            prompt=f"Consulta: {query}\nDatos: {res.iloc[0].to_dict()}"
            ai=copilot_interpretation(prompt)
            if ai: st.markdown("### 🤖 Copilot Aduanal"); st.write(ai)
    else:
        st.warning("Sin coincidencias.")
        log_query(user,col_for_log,query,0)

if st.session_state.role=="admin":
    log=get_log()
    if log:
        st.download_button("📥 Descargar bitácora",log,"consultas_log.csv","text/csv")

st.markdown("---")
st.caption("ADUAVIR — Plataforma interna © 2025 — Copilot Aduanal")