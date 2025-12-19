import streamlit as st
import pandas as pd
import requests
import altair as alt

# --------------------------------------------------
# Configuración general
# --------------------------------------------------
st.set_page_config(page_title="Establecimientos de Salud en Chile", layout="wide")

st.title("🏥 Establecimientos de Salud en Chile")
st.write(
    """
    Aplicación desarrollada por Ivis Martinez y Giuliana Provoste, en **Python y Streamlit**, la cual analiza la distribución territorial
    de los establecimientos de salud en Chile utilizando datos oficiales del portal **datos.gob.cl**.
    """
)
st.divider()

# --------------------------------------------------
# 1) Buscar dataset (CKAN)
# --------------------------------------------------
search_url = "https://datos.gob.cl/api/3/action/package_search?q=establecimientos%20salud"
resp = requests.get(search_url).json()

if not resp.get("success") or resp["result"]["count"] == 0:
    st.error("No se pudo encontrar el dataset en datos.gob.cl.")
    st.stop()

dataset = resp["result"]["results"][0]

# --------------------------------------------------
# 2) Obtener recurso CSV
# --------------------------------------------------
csv_url = None
for r in dataset.get("resources", []):
    if str(r.get("format", "")).lower() == "csv":
        csv_url = r.get("url")
        break

if not csv_url:
    st.error("El dataset encontrado no tiene un recurso CSV.")
    st.stop()

# --------------------------------------------------
# 3) Cargar CSV (robusto)
# --------------------------------------------------
df = pd.read_csv(
    csv_url,
    sep=";",
    encoding="latin-1",
    engine="python",
    on_bad_lines="skip"
)
df.columns = [c.strip().lower() for c in df.columns]

# --------------------------------------------------
# 4) Helpers
# --------------------------------------------------
def buscar_columna(posibles):
    for col in df.columns:
        for p in posibles:
            if p in col:
                return col
    return None

def arreglar_tildes(texto):
    try:
        return texto.encode("latin-1").decode("utf-8")
    except Exception:
        return texto

def norm_key(s: str) -> str:
    return str(s).strip().lower()

# --------------------------------------------------
# 5) Detectar columnas clave
# --------------------------------------------------
col_region_cod = buscar_columna(["regioncodigo"])
col_region_nom = buscar_columna(["regionglosa"])
col_comuna_nom = buscar_columna(["comunaglosa"])
col_estab_nom = buscar_columna(["establecimientoglosa"])

if not all([col_region_cod, col_region_nom, col_comuna_nom, col_estab_nom]):
    st.error("No se pudieron identificar columnas principales (región/comuna/establecimiento).")
    st.stop()

# Arreglar tildes en glosas
for c in [col_region_nom, col_comuna_nom, col_estab_nom]:
    df[c] = df[c].astype(str).apply(arreglar_tildes)

# --------------------------------------------------
# 6) Orden regiones norte → sur
# --------------------------------------------------
regiones_ordenadas = (
    df[[col_region_cod, col_region_nom]]
    .drop_duplicates()
    .sort_values(col_region_cod)[col_region_nom]
    .tolist()
)

# --------------------------------------------------
# 7) Sidebar (coherente con eje Y)
# --------------------------------------------------
conteo_region_dict = df.groupby(col_region_nom).size().to_dict()
regiones_sidebar = [f"{r} ({conteo_region_dict.get(r,0)})" for r in regiones_ordenadas]

st.sidebar.title("⚙️ Filtros")
st.sidebar.caption("Regiones (norte → sur) + cantidad total de establecimientos")

region_label = st.sidebar.selectbox("Región", regiones_sidebar)
region_sel = region_label.rsplit(" (", 1)[0]

top_n_comunas = st.sidebar.slider("Top comunas a mostrar en el mapa", 5, 30, 15)

st.sidebar.markdown(
    "<small>El número en el selector corresponde a la cantidad total de establecimientos por región.</small>",
    unsafe_allow_html=True
)

df_region = df[df[col_region_nom] == region_sel]

# --------------------------------------------------
# 8) Métricas
# --------------------------------------------------
st.header("📌 Indicadores principales")
c1, c2 = st.columns(2)
c1.metric("Establecimientos en la región", int(df_region.shape[0]))
c2.metric("Tipos distintos", int(df_region[col_estab_nom].nunique()))
st.divider()

# --------------------------------------------------
# 9) Análisis Nacional (Altair con eje Y rotulado al costado)
# --------------------------------------------------
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
    .mark_bar()
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

# --------------------------------------------------
# 10) Análisis Regional por tipo
# --------------------------------------------------
st.header("🏥 Análisis Regional")

conteo_tipo = (
    df_region.groupby(col_estab_nom)
    .size()
    .sort_values(ascending=False)
    .reset_index()
)
conteo_tipo.columns = ["Tipo de establecimiento", "Cantidad"]

grafico_tipo = (
    alt.Chart(conteo_tipo)
    .mark_bar()
    .encode(
        x=alt.X("Tipo de establecimiento:N", sort="-y", axis=alt.Axis(labelAngle=-45, title="Tipo")),
        y=alt.Y("Cantidad:Q", axis=alt.Axis(title="Número de establecimientos")),
        tooltip=["Tipo de establecimiento", "Cantidad"]
    )
    .properties(height=400)
)

st.altair_chart(grafico_tipo, use_container_width=True)
st.divider()

# --------------------------------------------------
# 11) Mapa por comuna (Top comunas) con centros urbanos
# --------------------------------------------------
st.header("🗺️ Mapa por comuna (Top comunas de la región)")

st.markdown(
    """
    El dataset no incluye coordenadas por establecimiento, por lo que este mapa se construye
    usando **coordenadas referenciales del centro urbano de la comuna** para visualizar la
    **concentración por comuna** dentro de la región seleccionada.
    """
)

# Diccionario de centros urbanos (puedes ampliarlo)
COMUNA_CENTROS = {
    # RM
    "santiago": (-33.4489, -70.6693),
    "puente alto": (-33.6117, -70.5758),
    "maipú": (-33.5092, -70.7570),
    "la florida": (-33.5531, -70.5594),
    "las condes": (-33.4080, -70.5660),
    "providencia": (-33.4315, -70.6094),
    "ñuñoa": (-33.4569, -70.5976),
    "san bernardo": (-33.5923, -70.7044),
    "pudahuel": (-33.4308, -70.7864),

    # Norte
    "arica": (-18.4783, -70.3126),
    "iquique": (-20.2141, -70.1525),
    "alto hospicio": (-20.2688, -70.1000),
    "antofagasta": (-23.6509, -70.3975),
    "calama": (-22.4560, -68.9237),
    "copiapó": (-27.3665, -70.3320),
    "la serena": (-29.9027, -71.2519),
    "coquimbo": (-29.9533, -71.3436),

    # Centro
    "valparaíso": (-33.0472, -71.6127),
    "viña del mar": (-33.0245, -71.5518),
    "quilpué": (-33.0475, -71.4436),
    "rancagua": (-34.1701, -70.7406),
    "talca": (-35.4264, -71.6554),
    "chillán": (-36.6063, -72.1034),

    # Sur
    "concepción": (-36.8270, -73.0498),
    "talcahuano": (-36.7175, -73.1169),
    "temuco": (-38.7359, -72.5904),
    "valdivia": (-39.8196, -73.2452),
    "osorno": (-40.5748, -73.1343),
    "puerto montt": (-41.4717, -72.9390),

    # Extremo sur
    "coyhaique": (-45.5712, -72.0683),
    "punta arenas": (-53.1638, -70.9171),
}

conteo_comuna = (
    df_region.groupby(col_comuna_nom)
    .size()
    .sort_values(ascending=False)
    .head(top_n_comunas)
    .reset_index(name="cantidad")
)

mapa_rows = []
sin_coord = []

for _, row in conteo_comuna.iterrows():
    comuna = row[col_comuna_nom]
    key = norm_key(comuna)
    if key in COMUNA_CENTROS:
        lat, lon = COMUNA_CENTROS[key]
        mapa_rows.append({
            "lat": lat,
            "lon": lon,
            "comuna": comuna,
            "cantidad": int(row["cantidad"])
        })
    else:
        sin_coord.append(comuna)

mapa_df = pd.DataFrame(mapa_rows)

if not mapa_df.empty:
    # st.map usa solo lat/lon (no tamaño). Mostramos tabla al lado.
    st.map(mapa_df[["lat", "lon"]])

    st.caption("Top comunas mapeadas (con coordenadas referenciales):")
    st.dataframe(
        mapa_df[["comuna", "cantidad"]].sort_values("cantidad", ascending=False).reset_index(drop=True),
        use_container_width=True
    )
else:
    st.warning("No se pudo mapear ninguna comuna (faltan coordenadas en el diccionario).")

if sin_coord:
    st.info(
        "Comunas del Top sin coordenadas aún (agrégalas al diccionario `COMUNA_CENTROS`):\n\n- "
        + "\n- ".join(sin_coord[:20])
        + ("\n\n(Se muestran hasta 20.)" if len(sin_coord) > 20 else "")
    )

st.divider()

# --------------------------------------------------
# 12) Tabla detalle
# --------------------------------------------------
st.header("📋 Detalle de establecimientos (región seleccionada)")
st.dataframe(
    df_region[[col_comuna_nom, col_estab_nom]].reset_index(drop=True),
    use_container_width=True
)

# --------------------------------------------------
# 13) Conclusión
# --------------------------------------------------
st.header("🧠 Conclusión")
st.markdown(
    f"""
    La región **{region_sel}** presenta una distribución específica de establecimientos de salud,
    con comunas que concentran mayor cantidad de oferta. A nivel nacional, se observan diferencias
    relevantes entre regiones, evidenciando una **distribución territorial no homogénea**.
    """
)
