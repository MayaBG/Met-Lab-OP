import streamlit as st
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import xarray as xr
import numpy as np
from datetime import datetime
import matplotlib.colors as mcolors
import cdsapi
import os
from scipy.ndimage import gaussian_filter

# הגדרות עמוד של Streamlit
st.set_page_config(page_title="מעבדה מטאורולוגית", layout="wide")

# קוד CSS עדין וממוקד: מחיל RTL רק על טקסטים וכותרות למניעת שבירת ממשק
st.markdown(
    """
    <style>
    h1, h2, h3, h4, h5, h6, p, span, label, .stMarkdown, [data-testid="stWidgetLabel"] p {
        direction: RTL !important;
        text-align: right !important;
    }
    div[data-testid="stSlider"], div[data-testid="stRadio"] {
        direction: LTR;
    }
    div[data-testid="stRadio"] label {
        direction: RTL !important;
        text-align: right !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🌍 מחולל מפות סינופטיות - מעבדה")
st.markdown("### מערכת הפקת מפות מבוססת נתוני ריאנליזה גלובלית ERA5 (ECMWF הרשמי)")

# סרגל צד להגדרות המשתמש
st.sidebar.header("הגדרות הפקה")

year = st.sidebar.slider("שנה", 1979, 2026, 2026)
month = st.sidebar.slider("חודש", 1, 12, 4)
day = st.sidebar.slider("יום", 1, 31, 27)
hour = st.sidebar.selectbox("שעה (UTC)", [0, 6, 12, 18], index=2)

map_type = st.sidebar.radio("סוג מפה", ["surface", "500mb", "850mb"])

if st.sidebar.button("הפק מפה"):
    if "CDS_KEY" not in st.secrets:
        st.error("🔑 מפתח ה-API (CDS_KEY) אינו מוגדר בהגדרות האפליקציה (Secrets). אנא הזיני את המפתח כדי לאפשר הפקת מפות.")
    else:
        with st.spinner('מתחבר לשרת האירופי ומושך נתוני ERA5...'):
            try:
                target_dt = datetime(year, month, day, hour)
                cds_key = st.secrets["CDS_KEY"]
                c = cdsapi.Client(url="https://cds.climate.copernicus.eu/api", key=cds_key)
                
                temp_filename = f"era5_{map_type}_temp.nc"
                
                # --- בניית מפת קרקע (Surface) ---
                if map_type == 'surface':
                    c.retrieve(
                        'reanalysis-era5-single-levels',
                        {
                            'product_type': 'reanalysis',
                            'format': 'netcdf',
                            'variable': ['mean_sea_level_pressure', '10m_u_component_of_wind', '10m_v_component_of_wind'],
                            'year': str(year),
                            'month': f"{month:02d}",
                            'day': f"{day:02d}",
                            'time': f"{hour:02d}:00",
                        },
                        temp_filename)
                    
                    ds = xr.open_dataset(temp_filename).sortby('latitude')
                    slp = ds['msl'].sel(latitude=slice(20, 40), longitude=slice(20, 50)).squeeze() / 100.0
                    u = ds['u10'].sel(latitude=slice(20, 40), longitude=slice(20, 50)).squeeze()
                    v = ds['v10'].sel(latitude=slice(20, 40), longitude=slice(20, 50)).squeeze()
                    slp_smoothed = gaussian_filter(slp.values, sigma=1.2)
                    
                    fig = plt.figure(figsize=(14, 11))
                    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
                    ax.set_extent([20, 50, 20, 40], crs=ccrs.PlateCarree())
                    
                    # רקע לבן נקי לחלוטין למפה
                    ax.set_facecolor('white')
                    
                    # קווי לחץ שחורים וברורים
                    cntr = ax.contour(slp.longitude, slp.latitude, slp_smoothed, colors='black', levels=np.arange(980, 1040, 2), linewidths=1.6, zorder=2)
                    ax.clabel(cntr, inline=True, fmt='%i', fontsize=11)
                    
                    # דגלוני רוח שחורים, מודגשים ובולטים מעל הרקע הלבן
                    ax.barbs(u.longitude[::5], u.latitude[::5], u.values[::5, ::5], v.values[::5, ::5], length=6.0, color='black', linewidth=1.1, zorder=3)
                    
                    title_text = f"Surface MSLP (hPa) & 10m Wind Barbs\nValid for: {target_dt.strftime('%Y-%m-%d %H:00')} UTC | Source: ECMWF ERA5 Reanalysis"

                # --- בניית מפת 850mb ---
                elif map_type == '850mb':
                    c.retrieve(
                        'reanalysis-era5-pressure-levels',
                        {
                            'product_type': 'reanalysis',
                            'format': 'netcdf',
                            'variable': ['temperature'],
                            'pressure_level': '850',
                            'year': str(year),
                            'month': f"{month:02d}",
                            'day': f"{day:02d}",
                            'time': f"{hour:02d}:00",
                        },
                        temp_filename)
                    
                    ds = xr.open_dataset(temp_filename).sortby('latitude')
                    temp_data = ds['t'].sel(latitude=slice(20, 40), longitude=slice(20, 50)).squeeze() - 273.15
                    temp_smoothed = gaussian_filter(temp_data.values, sigma=1.5)
                    
                    fig = plt.figure(figsize=(14, 11))
                    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
                    ax.set_extent([20, 50, 20, 40], crs=ccrs.PlateCarree())
                    
                    cf = ax.contourf(temp_data.longitude, temp_data.latitude, temp_data, cmap='coolwarm', levels=np.arange(-15, 35, 2), extend='both', zorder=1)
                    plt.colorbar(cf, label='Temperature (°C)', orientation='horizontal', pad=0.08, aspect=40)
                    cntr = ax.contour(temp_data.longitude, temp_data.latitude, temp_smoothed, colors='black', levels=np.arange(-15, 35, 2), linewidths=1.2, zorder=2)
                    ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)
                    
                    title_text = f"850hPa Temperature (°C)\nValid for: {target_dt.strftime('%Y-%m-%d %H:00')} UTC | Source: ECMWF ERA5 Reanalysis"

                # --- בניית מפת 500mb ---
                elif map_type == '500mb':
                    c.retrieve(
                        'reanalysis-era5-pressure-levels',
                        {
                            'product_type': 'reanalysis',
                            'format': 'netcdf',
                            'variable': ['geopotential'],
                            'pressure_level': '500',
                            'year': str(year),
                            'month': f"{month:02d}",
                            'day': f"{day:02d}",
                            'time': f"{hour:02d}:00",
                        },
                        temp_filename)
                    
                    ds = xr.open_dataset(temp_filename).sortby('latitude')
                    hgt = ds['z'].sel(latitude=slice(20, 40), longitude=slice(20, 50)).squeeze() / 9.80665
                    hgt_smoothed = gaussian_filter(hgt.values, sigma=1.2)
                    
                    fig = plt.figure(figsize=(14, 11))
                    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
                    ax.set_extent([20, 50, 20, 40], crs=ccrs.PlateCarree())
                    
                    cf = ax.contourf(hgt.longitude, hgt.latitude, hgt, cmap='viridis', levels=np.arange(5100, 6000, 60), extend='both', zorder=1)
                    plt.colorbar(cf, label='Geopotential Height (m)', orientation='horizontal', pad=0.08, aspect=40)
                    cntr = ax.contour(hgt.longitude, hgt.latitude, hgt_smoothed, colors='white', linewidths=1.6, levels=np.arange(5100, 6000, 60), zorder=2)
                    ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)
                    
                    title_text = f"500hPa Geopotential Height (m)\nValid for: {target_dt.strftime('%Y-%m-%d %H:00')} UTC | Source: ECMWF ERA5 Reanalysis"

                # --- שכבה גאוגרפית משותפת לכל המפלסים ---
                ax.add_feature(cfeature.COASTLINE.with_scale('50m'), linewidth=1.3, edgecolor='black', zorder=4)
                ax.add_feature(cfeature.BORDERS, linestyle=':', linewidth=1.0, edgecolor='#444444', zorder=4)
                
                gl = ax.gridlines(draw_labels=True, linestyle='--', alpha=0.4, color='#bdc3c7', zorder=3)
                gl.top_labels = False
                gl.right_labels = False

                # קיבוע ידני של מיקום המפה והשוליים - מונע קריסה בשחור-לבן
                fig.subplots_adjust(top=0.88, bottom=0.15, left=0.05, right=0.95)
                fig.suptitle(title_text, fontsize=14, weight='bold', x=0.06, y=0.96, ha='left')
                
                st.pyplot(fig)
                
                ds.close()
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                
            except Exception as e:
                st.error(f"שגיאה בהפקת המפה או במשיכת הנתונים: {e}")
