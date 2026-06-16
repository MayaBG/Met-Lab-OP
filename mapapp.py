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
                    
                    # זיהוי דינמי ובטוח של שמות המשתנים
                    msl_var = [v for v in ds.data_vars if 'msl' in v.lower() or 'press' in v.lower()][0]
                    u_var = [v for v in ds.data_vars if 'u' in v.lower()][0]
                    v_var = [v for v in ds.data_vars if 'v' in v.lower()][0]
                    
                    slp = ds[msl_var].sel(latitude=slice(20, 40), longitude=slice(20, 50)).squeeze()
                    if slp.max() > 2000:  # המרה לפסקל אם צריך
                        slp = slp / 100.0
                        
                    u = ds[u_var].sel(latitude=slice(20, 40), longitude=slice(20, 50)).squeeze()
                    v = ds[v_var].sel(latitude=slice(20, 40), longitude=slice(20, 50)).squeeze()
                    slp_smoothed = gaussian_filter(slp.values, sigma=1.2)
                    
                    # יצירת רשת קואורדינטות מלאה כדי למנוע קריסה של דגלוני הרוח
                    lons, lats = np.meshgrid(slp.longitude.values, slp.latitude.values)
                    
                    fig = plt.figure(figsize=(14, 11))
                    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
                    ax.set_extent([20, 50, 20, 40], crs=ccrs.PlateCarree())
                    
                    # --- טריק העיגון! שתי נקודות שקופות בפינות שמכריחות את המפה להישאר פתוחה ---
                    ax.plot([20, 50], [20, 40], '.', alpha=0.0, transform=ccrs.PlateCarree())
                    
                    ax.add_feature(cfeature.LAND, facecolor='#f5f5f5', zorder=0)
                    ax.add_feature(cfeature.OCEAN, facecolor='#ffffff', zorder=0)
                    
                    # קווי לחץ
                    cntr = ax.contour(lons, lats, slp_smoothed, colors='black', levels=np.arange(980, 1040, 2), linewidths=1.6, zorder=2, transform=ccrs.PlateCarree())
                    ax.clabel(cntr, inline=True, fmt='%i', fontsize=11)
                    
                    # דגלוני רוח
                    skip = 5
                    ax.barbs(lons[::skip, ::skip], lats[::skip, ::skip], u.values[::skip, ::skip], v.values[::skip, ::skip], length=6.0, color='black', linewidth=1.1, zorder=3, transform=ccrs.PlateCarree())
                    
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
                    t_var = [v for v in ds.data_vars if 't' in v.lower()][0]
                    
                    temp_data = ds[t_var].sel(latitude=slice(20, 40), longitude=slice(20, 50)).squeeze() - 273.15
                    temp_smoothed = gaussian_filter(temp_data.values, sigma=1.5)
                    lons, lats = np.meshgrid(temp_data.longitude.values, temp_data.latitude.values)
                    
                    fig = plt.figure(figsize=(14, 11))
                    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
                    ax.set_extent([20, 50, 20, 40], crs=ccrs.PlateCarree())
                    
                    cf = ax.contourf(lons, lats, temp_data, cmap='coolwarm', levels=np.arange(-15, 35, 2), extend='both', zorder=1, transform=ccrs.PlateCarree())
                    plt.colorbar(cf, label='Temperature (°C)', orientation='horizontal', pad=0.08, aspect=40)
                    cntr = ax.contour(lons, lats, temp_smoothed, colors='black', levels=np.arange(-15, 35, 2), linewidths=1.2, zorder=2, transform=ccrs.PlateCarree())
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
                    z_var = [v for v in ds.data_vars if 'z' in v.lower() or 'geo' in v.lower()][0]
                    
                    hgt = ds[z_var].sel(latitude=slice(20, 40), longitude=slice(20, 50)).squeeze() / 9.80665
                    hgt_smoothed = gaussian_filter(hgt.values, sigma=1.2)
                    lons, lats = np.meshgrid(hgt.longitude.values, hgt.latitude.values)
                    
                    fig = plt.figure(figsize=(14, 11))
                    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
                    ax.set_extent([20, 50, 20, 40], crs=ccrs.PlateCarree())
                    
                    cf = ax.contourf(lons, lats, hgt, cmap='viridis', levels=np.arange(5100, 6000, 60), extend='both', zorder=1, transform=ccrs.PlateCarree())
                    plt.colorbar(cf, label='Geopotential Height (m)', orientation='horizontal', pad=0.08, aspect=40)
                    cntr = ax.contour(lons, lats, hgt_smoothed, colors='white', linewidths=1.6, levels=np.arange(5100, 6000, 60), zorder=2, transform=ccrs.PlateCarree())
                    ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)
                    
                    title_text = f"500hPa Geopotential Height (m)\nValid for: {target_dt.strftime('%Y-%m-%d %H:00')} UTC | Source: ECMWF ERA5 Reanalysis"

                # --- שכבה גאוגרפית משותפת לכל המפלסים ---
                ax.add_feature(cfeature.COASTLINE.with_scale('50m'), linewidth=1.3, edgecolor='black', zorder=4)
                ax.add_feature(cfeature.BORDERS, linestyle=':', linewidth=1.0, edgecolor='#444444', zorder=4)
                
                gl = ax.gridlines(draw_labels=True, linestyle='--', alpha=0.4, color='#bdc3c7', zorder=3)
                gl.top_labels = False
                gl.right_labels = False

                fig.subplots_adjust(top=0.88, bottom=0.15, left=0.05, right=0.95)
                fig.suptitle(title_text, fontsize=14, weight='bold', x=0.06, y=0.96, ha='left')
                
                st.pyplot(fig)
                
                ds.close()
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                
            except Exception as e:
                st.error(f"שגיאה בהפקת המפה או במשיכת הנתונים: {e}")
