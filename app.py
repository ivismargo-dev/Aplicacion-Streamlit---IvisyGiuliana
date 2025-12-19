import streamlit as st
import pandas as pd
import requests
import altair as alt

# ==================================================
# CONFIGURACIÓN GENERAL
# ==================================================
st.set_page_config(
    page_title="Establecimientos de Salud en Chile",
    layout="wide"
)

st.title("🏥 Establecimientos de Salud en Chile")
st.markdown(
    """
    Aplicación desarrollada en **Python y Streamlit** que analiza la distribución
    territorial de los establecimientos de salud en Chile, utilizando datos oficiales
    del portal **datos.gob.cl**.
    """
)
st.divider()

# ==================================================
# 1️⃣ OBTENER DATASET DESDE DATOS.GOB.CL (CKAN)
# ==================================================
search_url = "https://datos.gob.cl/api/3/action/package_search?q=establecimientos%20salud"
resp = requests.get(search_url).json()

if not resp.get("success") or resp["result"]["count"] == 0:
    st.error("No se pudo encontrar el dataset en datos.gob.cl.")
    st.stop()

dataset = resp["result"]["results"][0]

csv_url = None
for r in dataset.get("resources", []):
    if str(r.get("format", "")).lower() == "csv":
        csv_url = r.get("url")
        break

if not csv_url:
    st.error("El dataset no contiene un archivo CSV.")
    st.stop()

# ==================================================
# 2️⃣ CARGA ROBUSTA DEL CSV
# ==================================================
df = pd.read_csv(
    csv_url,
    sep=";",
    encoding="latin-1",
    engine="python",
    on_bad_lines="skip"
)
df.columns = [c.strip().lower() for c in df.columns]

# ==================================================
# 3️⃣ FUNCIONES AUXILIARES
# ==================================================
def buscar_columna(posibles):
    for c in df.columns:
        for p in posibles:
            if p in c:
                return c
    return None

def arreglar_tildes(txt):
    try:
        return txt.encode("latin-1").decode("utf-8")
    except:
        return txt

def norm_key(s):
    return str(s).strip().lower()

# ==================================================
# 4️⃣ COLUMNAS CLAVE
# ==================================================
col_region_cod = buscar_columna(["regioncodigo"])
col_region_nom = buscar_columna(["regionglosa"])
col_comuna_nom = buscar_columna(["comunaglosa"])
col_estab_nom = buscar_columna(["establecimientoglosa"])

if not all([col_region_cod, col_region_nom, col_comuna_nom, col_estab_nom]):
    st.error("No se pudieron identificar las columnas principales.")
    st.stop()

for c in [col_region_nom, col_comuna_nom, col_estab_nom]:
    df[c] = df[c].astype(str).apply(arreglar_tildes)

# ==================================================
# 5️⃣ ORDEN REGIONES NORTE → SUR
# ==================================================
regiones_ordenadas = (
    df[[col_region_cod, col_region_nom]]
    .drop_duplicates()
    .sort_values(col_region_cod)[col_region_nom]
    .tolist()
)

# ==================================================
# 6️⃣ SIDEBAR
# ==================================================
st.sidebar.title("⚙️ Filtros")

conteo_region = df.groupby(col_region_nom).size().to_dict()
regiones_sidebar = [f"{r} ({conteo_region.get(r,0)})" for r in regiones_ordenadas]

region_label = st.sidebar.selectbox("Región", regiones_sidebar)
region_sel = region_label.rsplit(" (", 1)[0]

top_n_comunas = st.sidebar.slider("Top comunas en el mapa", 5, 25, 15)

top_n_tipos = st.sidebar.radio(
    "Tipos de establecimientos a mostrar",
    [5, 10],
    index=1
)

df_region = df[df[col_region_nom] == region_sel]

# ==================================================
# 7️⃣ MÉTRICAS
# ==================================================
st.header("📌 Indicadores principales")
c1, c2 = st.columns(2)
c1.metric("Establecimientos en la región", int(df_region.shape[0]))
c2.metric("Tipos distintos", int(df_region[col_estab_nom].nunique()))
st.divider()

# ==================================================
# 8️⃣ ANÁLISIS NACIONAL (EJE Y CORRECTO)
# ==================================================
st.header("📊 Análisis Nacional")

conteo_nacional = (
    df.groupby(col_region_nom)
    .size()
    .reindex(regiones_ordenadas)
    .fillna(0)
    .reset_index()
)
conteo_nacional.columns = ["Región", "Cantidad"]

grafico_nacional = (
    alt.Chart(conteo_nacional)
    .mark_bar(color="#6EC1FF")
    .encode(
        x=alt.X(
            "Región:N",
            sort=None,
            axis=alt.Axis(
                title="Regiones de Chile (norte → sur)",
                labelAngle=-45
            )
        ),
        y=alt.Y(
            "Cantidad:Q",
            axis=alt.Axis(
                title="Número total de establecimientos de salud"
            )
        ),
        tooltip=["Región", "Cantidad"]
    )
    .properties(height=450)
)

st.altair_chart(grafico_nacional, use_container_width=True)
st.divider()

# ==================================================
# 🏥 ANÁLISIS REGIONAL POR MACRO-TIPO
# ==================================================
st.header("🏥 Análisis Regional")

st.markdown(
    """
    Distribución de los **macro-tipos de establecimientos de salud**
    en la región seleccionada.  
    Esta agrupación permite una interpretación más clara de la
    **orientación funcional del sistema de salud regional**.
    """
)

# --------------------------------------------------
# Clasificación por macro-tipo según nombre
# --------------------------------------------------
def clasificar_macro_tipo(nombre):
    nombre = nombre.lower()

    if "hospital" in nombre:
        return "Hospital"
    elif "cesfam" in nombre or "centro de salud familiar" in nombre:
        return "CESFAM"
    elif "posta" in nombre or "sapu" in nombre:
        return "Posta / SAPU"
    elif "laboratorio" in nombre:
        return "Laboratorio"
    elif "clinica" in nombre or "policlinico" in nombre:
        return "Clínica / Policlínico"
    else:
        return "Otros"

df_region["Macro tipo"] = df_region[col_estab_nom].apply(clasificar_macro_tipo)

# --------------------------------------------------
# Agrupar por macro-tipo
# --------------------------------------------------
conteo_macro = (
    df_region.groupby("Macro tipo")
    .size()
    .sort_values(ascending=False)
    .reset_index(name="Cantidad")
)

# --------------------------------------------------
# Gráfico horizontal limpio
# --------------------------------------------------
grafico_macro = (
    alt.Chart(conteo_macro)
    .mark_bar(color="#6EC1FF")
    .encode(
        y=alt.Y(
            "Macro tipo:N",
            sort="-x",
            axis=alt.Axis(title="Tipo de establecimiento")
        ),
        x=alt.X(
            "Cantidad:Q",
            axis=alt.Axis(title="Número de establecimientos")
        ),
        tooltip=["Macro tipo", "Cantidad"]
    )
    .properties(height=300)
)

st.altair_chart(grafico_macro, use_container_width=True)

st.divider()

# ==================================================
# 🔟 MAPA POR COMUNA (TOP COMUNAS)
# ==================================================
st.header("🗺️ Mapa por comuna (Top comunas de la región)")

COMUNA_CENTROS = {
    "santiago": (-33.4489, -70.6693),
    "puente alto": (-33.6117, -70.5758),
    "maipú": (-33.5092, -70.7570),
    "la florida": (-33.5531, -70.5594),
    "las condes": (-33.4080, -70.5660),
    "providencia": (-33.4315, -70.6094),
    "arica": (-18.4783, -70.3126),
    "iquique": (-20.2141, -70.1525),
    "antofagasta": (-23.6509, -70.3975),
    "copiapó": (-27.3665, -70.3320),
    "la serena": (-29.9027, -71.2519),
    "valparaíso": (-33.0472, -71.6127),
    "viña del mar": (-33.0245, -71.5518),
    "concepción": (-36.8270, -73.0498),
    "temuco": (-38.7359, -72.5904),
    "valdivia": (-39.8196, -73.2452),
    "puerto montt": (-41.4717, -72.9390),
    "punta arenas": (-53.1638, -70.9171),
}

conteo_comuna = (
    df_region.groupby(col_comuna_nom)
    .size()
    .sort_values(ascending=False)
    .head(top_n_comunas)
    .reset_index(name="cantidad")
)

mapa_data = []
sin_coord = []

for _, r in conteo_comuna.iterrows():
    comuna = r[col_comuna_nom]
    key = norm_key(comuna)
    if key in COMUNA_CENTROS:
        lat, lon = COMUNA_CENTROS[key]
        mapa_data.append({"lat": lat, "lon": lon})
    else:
        sin_coord.append(comuna)

mapa_df = pd.DataFrame(mapa_data)

if not mapa_df.empty:
    st.map(mapa_df)
else:
    st.warning("No hay comunas con coordenadas disponibles para el mapa.")

if sin_coord:
    st.info("Comunas sin coordenadas aún:\n- " + "\n- ".join(sin_coord[:15]))

st.divider()

# ==================================================
# 1️⃣1️⃣ TABLA DE DETALLE
# ==================================================
st.header("📋 Detalle de establecimientos")
st.dataframe(
    df_region[[col_comuna_nom, col_estab_nom]].reset_index(drop=True),
    use_container_width=True
)

# ==================================================
# 1️⃣2️⃣ CONCLUSIÓN
# ==================================================
st.header("🧠 Conclusión")
st.markdown(
    f"""
    La región **{region_sel}** presenta una concentración diferenciada de establecimientos
    de salud por comuna y por tipo. A nivel nacional, el análisis evidencia una
    **distribución territorial no homogénea**, lo que refleja desigualdades en la
    disponibilidad de infraestructura sanitaria en Chile.
    """
)
