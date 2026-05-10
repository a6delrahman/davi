import streamlit as st
import pandas as pd
import altair as alt
import requests
from vega_datasets import data

# --- Konfiguration der Seite ---
st.set_page_config(
    page_title="Global Sales & Inventory Forecast",
    page_icon="📦",
    layout="wide"
)

# --- API Geocoding Funktion ---
@st.cache_data(show_spinner=False)
def fetch_city_coordinates(city_name):
    """Holt die GPS-Koordinaten einer Stadt über die kostenlose Open-Meteo API."""
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&format=json"
    try:
        response = requests.get(url, timeout=3).json()
        if 'results' in response:
            return response['results'][0]['latitude'], response['results'][0]['longitude']
    except Exception:
        pass 
    return None, None

# --- Phase 1: Data Loading ---
@st.cache_data
def load_data():
    df = pd.read_csv('DaVi/prototype/samsung_global_sales_dataset.csv')
    df['sale_date'] = pd.to_datetime(df['sale_date'])
    return df

try:
    df = load_data()
except FileNotFoundError:
    st.error("Fehler: Die Datei 'samsung_global_sales_dataset.csv' wurde nicht gefunden. Bitte prüfen Sie den Dateipfad.")
    st.stop()

# --- Header ---
st.title("📦 Global Sales & Inventory Forecasting")
st.markdown("""
**Vom reaktiven Reporting zur proaktiven Bestandssteuerung.** Dieses Dashboard dient Supply Chain Managern zur strategischen Entscheidungsfindung.
""")

# --- Phase 2: Optimierte Sidebar (Dynamische & Optionale Filter) ---
st.sidebar.header("Filter & Steuerung")

# 1. Kategorie-Filter (Startet leer)
all_categories = df['category'].unique().tolist()
selected_categories = st.sidebar.multiselect("Produktkategorie:", all_categories, default=[])

# 2. Länder-Filter (Startet leer)
all_countries = sorted(df['country'].unique().tolist())
selected_countries = st.sidebar.multiselect("Land (Hotspots):", all_countries, default=[])

# 3. Kaskadierender Städte-Filter (optional)
if selected_countries:
    available_cities = sorted(df[df['country'].isin(selected_countries)]['city'].unique().tolist())
else:
    available_cities = sorted(df['city'].unique().tolist())

selected_cities = st.sidebar.multiselect("Stadt (optional):", available_cities, default=[])

# 4. Datums-Filter
min_date = df['sale_date'].min().date()
max_date = df['sale_date'].max().date()
start_date, end_date = st.sidebar.date_input("Zeitraum wählen:", value=[min_date, max_date], min_value=min_date, max_value=max_date)

# --- Performance-Schutz (Zero-State) ---
if not selected_categories and not selected_countries:
    st.info("👋 **Willkommen im Dashboard!** \n\nUm Rechenleistung zu sparen, werden die globalen Daten nicht automatisch geladen. Bitte wählen Sie in der Sidebar mindestens eine **Produktkategorie** oder ein **Land** aus, um die Analyse zu starten.")
    st.stop() 

# --- Dynamische Filter-Logik ---
mask = (df['sale_date'].dt.date >= start_date) & (df['sale_date'].dt.date <= end_date)

if selected_categories:
    mask &= df['category'].isin(selected_categories)
if selected_countries:
    mask &= df['country'].isin(selected_countries)
if selected_cities:
    mask &= df['city'].isin(selected_cities)

filtered_df = df[mask]

if filtered_df.empty:
    st.warning("Keine Daten für die gewählten Filter verfügbar. Bitte passen Sie die Auswahl in der Sidebar an.")
    st.stop()

# --- Phase 3: High-Level KPIs ---
st.subheader("📊 Executive Summary")

total_revenue = filtered_df['revenue_usd'].sum()
total_units = filtered_df['units_sold'].sum()
avg_price_per_unit = total_revenue / total_units if total_units > 0 else 0
top_country = filtered_df.groupby('country')['revenue_usd'].sum().idxmax()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Gesamtumsatz", f"${total_revenue:,.0f}")
col2.metric("Verkaufte Einheiten", f"{total_units:,}")
col3.metric("Ø Preis pro Einheit", f"${avg_price_per_unit:,.2f}")
col4.metric("Stärkster Markt", top_country)
st.divider()

# --- Phase 4: Geografie (Altair) & Produkttiefe (Altair) ---
col_map, col_bar = st.columns(2)

with col_map:
    st.subheader("🌍 Geografische Verteilung")
    st.caption("Logistik-Hubs der aktuellen Auswahl (Größe & Farbe nach Umsatz).")
    
    # Daten für die API vorbereiten
    city_sales = filtered_df.groupby('city')[['revenue_usd', 'units_sold']].sum().reset_index()
    
    # Performance-Schutz
    if len(city_sales) > 50:
        st.info(f"Es sind {len(city_sales)} Städte im Filter. Zeige die Top 50 Hubs.")
        city_sales = city_sales.sort_values(by='revenue_usd', ascending=False).head(50)
    
    with st.spinner('Lade Koordinaten für die Karte...'):
        coords = city_sales['city'].apply(fetch_city_coordinates)
        city_sales['lat'] = [c[0] for c in coords]
        city_sales['lon'] = [c[1] for c in coords]
    
    city_sales_mapped = city_sales.dropna(subset=['lat', 'lon'])

    # Weltkarte laden (Hintergrund)
    world = alt.topo_feature(data.world_110m.url, 'countries')

    base_map = alt.Chart(world).mark_geoshape(
        fill='#F0F0F0', stroke='white', strokeWidth=0.5
    ).project('naturalEarth1')

    # Rote Pins/Blasen zeichnen
    if not city_sales_mapped.empty:
        points = alt.Chart(city_sales_mapped).mark_circle(
            opacity=0.8, stroke='white', strokeWidth=1
        ).encode(
            longitude='lon:Q', 
            latitude='lat:Q',
            # 1. Größe der Blase basierend auf Umsatz
            size=alt.Size('revenue_usd:Q', scale=alt.Scale(range=[20, 500]), legend=None),
            # 2. Farbe der Blase basierend auf Umsatz (Das erzeugt die COLOR BAR rechts!)
            color=alt.Color('revenue_usd:Q', 
                            scale=alt.Scale(scheme='reds'), 
                            legend=alt.Legend(title='Umsatz (USD)', orient='right', format='$,.0f')),
            tooltip=[
                alt.Tooltip('city:N', title='Stadt'),
                alt.Tooltip('revenue_usd:Q', title='Umsatz', format='$,.0f'),
                alt.Tooltip('units_sold:Q', title='Einheiten')
            ]
        )
        altair_map = (base_map + points).properties(height=350)
    else:
        altair_map = base_map.properties(height=350)
    
    st.altair_chart(altair_map, use_container_width=True)

with col_bar:
    st.subheader("📦 Bestseller Modelle")
    st.caption("Umsatzstärkste spezifische Produkte (Grundlage für Produktionspriorisierung).")
    
    bar_chart = alt.Chart(filtered_df).mark_bar(cornerRadiusEnd=4).encode(
        x=alt.X('sum(revenue_usd):Q', title='Gesamtumsatz (USD)'),
        y=alt.Y('product_name:N', sort='-x', title='', axis=alt.Axis(labelLimit=0)), 
        color=alt.Color('category:N', scale=alt.Scale(scheme='tealblues'), legend=alt.Legend(title="Kategorie", orient='bottom')),
        tooltip=[alt.Tooltip('product_name', title='Produkt'), alt.Tooltip('sum(revenue_usd):Q', title='Umsatz', format='$,.0f')]
    ).properties(height=350)
    st.altair_chart(bar_chart, use_container_width=True)

st.divider()

# --- Phase 5: Zeitreihe & Heatmap (Altair) ---
st.subheader("📈 Zeitreihenanalyse & Forecasting")
st.caption("Historische Verkaufsdaten kombiniert mit einem 3-Monats-Trend zur proaktiven Bestandserkennung.")

time_df = filtered_df.copy()
time_df['YearMonth'] = time_df['sale_date'].dt.to_period('M')
monthly_sales = time_df.groupby('YearMonth')['revenue_usd'].sum().reset_index()
monthly_sales['YearMonth'] = monthly_sales['YearMonth'].dt.to_timestamp()
monthly_sales['MA_Trend'] = monthly_sales['revenue_usd'].rolling(window=3).mean()

base_line = alt.Chart(monthly_sales).encode(x=alt.X('YearMonth:T', title='Datum'))
line_revenue = base_line.mark_line(color='#1f77b4', strokeWidth=3).encode(
    y=alt.Y('revenue_usd:Q', title='Umsatz (USD)'),
    tooltip=[alt.Tooltip('YearMonth:T', title='Monat', format='%Y-%m'), alt.Tooltip('revenue_usd:Q', title='Umsatz', format='$,.0f')]
)
line_trend = base_line.mark_line(color='#ff7f0e', strokeDash=[5, 5], strokeWidth=3).encode(
    y=alt.Y('MA_Trend:Q'),
    tooltip=[alt.Tooltip('MA_Trend:Q', title='3-Monats-Trend', format='$,.0f')]
)
combined_line_chart = (line_revenue + line_trend).properties(height=350)
st.altair_chart(combined_line_chart, use_container_width=True)

st.subheader("🗓️ Saisonalität & Bestellzyklen")
heatmap_df = filtered_df.copy()
heatmap_df['Monat'] = heatmap_df['sale_date'].dt.month
heatmap_data = heatmap_df.groupby(['category', 'Monat'])['units_sold'].sum().reset_index()

heatmap = alt.Chart(heatmap_data).mark_rect().encode(
    x=alt.X('Monat:O', title='Monat (1-12)', axis=alt.Axis(labelAngle=0)),
    y=alt.Y('category:N', title='Kategorie'),
    color=alt.Color('units_sold:Q', scale=alt.Scale(scheme='oranges'), title='Verkaufte Einheiten'),
    tooltip=['Monat', 'category', 'units_sold']
).properties(height=250)
st.altair_chart(heatmap, use_container_width=True)

st.divider()

# --- Phase 6: Actionable Data & Fazit ---
col_table, col_fazit = st.columns([1.5, 1])

with col_table:
    st.subheader("📍 Logistik-Hotspots (Kategorie-Detailansicht)")
    st.caption("Verteilung der Lagerbestände pro Stadt, aufgeschlüsselt nach Produktkategorie.")
    
    # 1. Daten nach Land, Stadt UND Kategorie gruppieren
    hotspot_cat = filtered_df.groupby(['country', 'city', 'category'])['units_sold'].sum().reset_index()
    
    # 2. Pivot Table erstellen (Kategorien werden zu Spalten)
    pivot_table = hotspot_cat.pivot(index=['country', 'city'], columns='category', values='units_sold').fillna(0)
    
    # 3. Eine "Gesamt" Spalte hinzufügen
    pivot_table['Gesamt Einheiten'] = pivot_table.sum(axis=1)
    
    # 4. Nach Land und dann nach Gesamteinheiten sortieren
    pivot_table = pivot_table.sort_values(by=['country', 'Gesamt Einheiten'], ascending=[True, False]).reset_index()
    
    # Dynamischer Index ab 1
    pivot_table.index = range(1, len(pivot_table) + 1) 
    
    # --- Visuelle Unterscheidung der Städte (Color Mapping) ---
    unique_cities = pivot_table['city'].unique()
    pastel_colors = ['#E3F2FD', '#FFF3E0', '#E8F5E9', '#FCE4EC', '#F3E5F5', '#FFFDE7']
    city_colors = {city: f'background-color: {pastel_colors[i % len(pastel_colors)]}; font-weight: bold; color: black;' for i, city in enumerate(unique_cities)}
    
    def style_cities(val):
        return city_colors.get(val, '')
    
    # Kompatibilitäts-Check
    try:
        styler = pivot_table.style.map(style_cities, subset=['city'])
    except AttributeError:
        styler = pivot_table.style.applymap(style_cities, subset=['city'])
        
    st.dataframe(
        styler.background_gradient(subset=['Gesamt Einheiten'], cmap='Blues').format(precision=0),
        use_container_width=True
    )

with col_fazit:
    st.subheader("💡 Handlungsempfehlung")
    st.info("""
    **Vom Report zur Aktion:**
    1. **Fokus:** Identifizieren Sie im Balkendiagramm die Bestseller und allozieren Sie Budgets entsprechend.
    2. **Timing:** Nutzen Sie die Heatmap und den Trend-Indikator, um Bestellungen auszulösen, *bevor* die Nachfragespitze eintritt.
    3. **Dezentrale Logistik:** Die Hotspot-Tabelle (links) zeigt exakt, *welche* Produktkategorien in welchen Städten benötigt werden. Farblich markierte Städte erleichtern die Unterscheidung lokaler Hubs beim Scrollen.
    """)
