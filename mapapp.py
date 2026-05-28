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
import urllib3

# ביטול אזהרות SSL בדפדפן הפנימי
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# הגדרות עמוד של Streamlit
st.set_page_config(page_title="מעבדה מטאורולוגית", layout="wide")

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
    with st.spinner('מתחבר לשרת האירופי ומושך נתוני ERA5 מאומתים...'):
        try:
            target_dt = datetime(year, month, day, hour)
            
            # משיכת המפתח המאובטח מהכספת של סטריםלייט
            cds_key = st.secrets["CDS_KEY"]
            
            # הגדרת החיבור הרשמי עם ביטול בדיקת SSL
            c = cdsapi.Client(url="https://cds-beta.climate.copernicus.eu/api", key=cds_key, verify=False)
            
            temp_filename = "era5_temp.nc"
            
            # עדכון שמות המאגרים לפורמט ה-Beta החדש (בלי הקידומת reanalysis-)
            if map_type == 'surface':
                c.retrieve(
                    'era5-single-levels',
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
                
                ds = xr.open_dataset(temp_filename)
                slp = ds['msl'].sel(latitude=slice(40, 20), longitude=slice(20, 50)) / 100.0
                u = ds['u10'].sel(latitude=slice(40, 20), longitude=slice(20, 50))
                v = ds['v10'].sel(latitude=slice(40, 20), longitude=slice(20, 50))
                
            else:
                var_name = 'temperature' if map_type == '850mb' else 'geopotential'
                lev_val = '850' if map_type == '850mb' else '500'
                
                c.retrieve(
                    'era5-pressure-levels',
                    {
                        'product_type': 'reanalysis',
                        'format': 'netcdf',
                        'variable': var_name,
                        'pressure_level': lev_val,
                        'year': str(year),
                        'month': f"{month:02d}",
                        'day': f"{day:02d}",
                        'time': f"{hour:02d}:00",
                    },
                    temp_filename)
                
                ds = xr.open_dataset(temp_filename)

            # בניית המפה הגרפית
            fig = plt.figure(figsize=(14, 10))
            ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
            ax.set_extent([20, 50, 20, 40], crs=ccrs.PlateCarree())
            
            ax.add_feature(cfeature.COASTLINE.with_scale('50m'), linewidth=1.5)
            ax.add_feature(cfeature.BORDERS, linestyle=':')
            gl = ax.gridlines(draw_labels=True, linestyle='--', alpha=0.6)
            gl.top_labels = False
            gl.right_labels = False

            map_info = {
                'surface': "Surface MSLP (hPa) & Wind Barbs",
                '500mb': "500hPa Geopotential Height (m)",
                '850mb': "850hPa Temperature (°C)"
            }
            title_text = f"{map_info[map_type]}\nValid for: {target_dt.strftime('%Y-%m-%d %H:00')} UTC\nSource: ECMWF ERA5 Reanalysis"

            if map_type == 'surface':
                white_cmap = mcolors.ListedColormap(['white'])
                cf = ax.contourf(slp.longitude, slp.latitude, slp, cmap=white_cmap, levels=[slp.min(), slp.max()])
                plt.colorbar(cf, orientation='horizontal', pad=0.08, aspect=40).ax.set_visible(False)
                
                cntr = ax.contour(slp.longitude, slp.latitude, slp, colors='black', levels=np.arange(980, 1040, 2))
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)
                ax.barbs(u.longitude[::2], u.latitude[::2], u.values[::2, ::2], v.values[::2, ::2], length=6, color='darkblue')

            elif map_type == '850mb':
                temp = ds['t'].sel(latitude=slice(40, 20), longitude=slice(20, 50)) - 273.15
                cf = ax.contourf(temp.longitude, temp.latitude, temp, cmap='coolwarm', levels=np.arange(-15, 35, 2), extend='both')
                plt.colorbar(cf, label='Temperature (°C)', orientation='horizontal', pad=0.08, aspect=40)
                cntr = ax.contour(temp.longitude, temp.latitude, temp, colors='black', levels=np.arange(-15, 35, 2), linewidths=0.8)
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)

            elif map_type == '500mb':
                hgt = ds['z'].sel(latitude=slice(40, 20), longitude=slice(20, 50)) / 9.80665
                cf = ax.contourf(hgt.longitude, hgt.latitude, hgt, cmap='viridis', levels=np.arange(5100, 6000, 60), extend='both')
                plt.colorbar(cf, label='Geopotential Height (m)', orientation='horizontal', pad=0.08, aspect=40)
                cntr = ax.contour(hgt.longitude, hgt.latitude, hgt, colors='white', linewidths=1.2, levels=np.arange(5100, 6000, 60))
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)

            plt.title(title_text, fontsize=14, pad=20)
            st.pyplot(fig)
            
            ds.close()
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
            
        except Exception as e:
            st.error(f"שגיאה במשיכת הנתונים הרשמיים משרת קופרניקוס האירופי. (Error: {e})")
