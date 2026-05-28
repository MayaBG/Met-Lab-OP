import streamlit as st
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import xarray as xr
import numpy as np
from datetime import datetime
import matplotlib.colors as mcolors

# הגדרות עמוד של Streamlit
st.set_page_config(page_title="מעבדה מטאורולוגית", layout="wide")

st.title("🌍 מחולל מפות סינופטיות - מעבדה")
st.markdown("### מערכת הפקת מפות מבוססת נתוני ריאנליזה גלובלית MERRA-2 (NASA)")

# סרגל צד להגדרות המשתמש
st.sidebar.header("הגדרות הפקה")

year = st.sidebar.slider("שנה", 1980, 2026, 2026)
month = st.sidebar.slider("חודש", 1, 12, 4)
day = st.sidebar.slider("יום", 1, 31, 27)

# בחירת שעה מתוך רשימה קבועה
hour = st.sidebar.selectbox("שעה (UTC)", [0, 6, 12, 18], index=2)

map_type = st.sidebar.radio("סוג מפה", ["surface", "500mb", "850mb"])

if st.sidebar.button("הפק מפה"):
    with st.spinner('מושך נתוני ריאנליזה משרתי NASA...'):
        try:
            target_dt = datetime(year, month, day, hour)
            date_str = target_dt.strftime("%Y%m%d")
            
            # הגדרת שרתי הנתונים הפתוחים של נאס"א (MERRA-2)
            # מאגר זה רציף לחלוטין ופתוח ללא הגבלות
            if map_type == 'surface':
                # קובץ נתוני קרקע (לחץ ורוחות)
                url = f"https://goldsmr4.gesdisc.eosdis.nasa.gov/opendap/MERRA2/M2I3NVASM.5.12.4/{year}/{month:02d}/MERRA2_400.inst3_3d_asm_Np.{date_str}.nc4"
            else:
                # קובץ מפלסי לחץ (רום 500 ו-850)
                url = f"https://goldsmr4.gesdisc.eosdis.nasa.gov/opendap/MERRA2/M2I3NPASM.5.12.4/{year}/{month:02d}/MERRA2_400.inst3_3d_asm_Np.{date_str}.nc4"
            
            ds = xr.open_dataset(url)
            
            # חילוץ אינדקס השעה המדויק (MERRA-2 שומר 8 קריאות ביום, כל 3 שעות)
            time_idx = hour // 3

            # בניית מפה ועיבוד נתונים
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
            title_text = f"{map_info[map_type]}\nValid for: {target_dt.strftime('%Y-%m-%d %H:00')} UTC\nSource: NASA MERRA-2 Reanalysis"

            if map_type == 'surface':
                # SLP ב-MERRA-2 מגיע בפסקל, מחלקים ב-100 לקבלת hPa
                slp = ds['SLP'].isel(time=time_idx).sel(lat=slice(20, 40), lon=slice(20, 50)) / 100.0
                
                white_cmap = mcolors.ListedColormap(['white'])
                cf = ax.contourf(slp.lon, slp.lat, slp, cmap=white_cmap, levels=[slp.min(), slp.max()])
                plt.colorbar(cf, orientation='horizontal', pad=0.08, aspect=40).ax.set_visible(False)
                
                cntr = ax.contour(slp.lon, slp.lat, slp, colors='black', levels=np.arange(980, 1040, 2))
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)
                
                # רוחות קרקע (רכיבי U ו-V בגובה 10 מטרים)
                u = ds['U10M'].isel(time=time_idx).sel(lat=slice(20, 40), lon=slice(20, 50))
                v = ds['V10M'].isel(time=time_idx).sel(lat=slice(20, 40), lon=slice(20, 50))
                ax.barbs(u.lon[::2], u.lat[::2], u.values[::2, ::2], v.values[::2, ::2], length=6, color='darkblue')

            elif map_type == '850mb':
                # טמפרטורה מגיעה בקלווין, ממירי הצלזיוס. מפלס 850hPa
                temp = ds['T'].isel(time=time_idx).sel(lev=850, lat=slice(20, 40), lon=slice(20, 50)) - 273.15
                cf = ax.contourf(temp.lon, temp.lat, temp, cmap='coolwarm', levels=np.arange(-15, 35, 2), extend='both')
                plt.colorbar(cf, label='Temperature (°C)', orientation='horizontal', pad=0.08, aspect=40)
                cntr = ax.contour(temp.lon, temp.lat, temp, colors='black', levels=np.arange(-15, 35, 2), linewidths=0.8)
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)

            elif map_type == '500mb':
                # גובה גיאופוטנציאלי במפלס 500hPa. MERRA-2 נותן H המרה למטרים
                hgt = ds['H'].isel(time=time_idx).sel(lev=500, lat=slice(20, 40), lon=slice(20, 50))
                cf = ax.contourf(hgt.lon, hgt.lat, hgt, cmap='viridis', levels=np.arange(5100, 6000, 60), extend='both')
                plt.colorbar(cf, label='Geopotential Height (m)', orientation='horizontal', pad=0.08, aspect=40)
                cntr = ax.contour(hgt.lon, hgt.lat, hgt, colors='white', linewidths=1.2, levels=np.arange(5100, 6000, 60))
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)

            plt.title(title_text, fontsize=14, pad=20)
            st.pyplot(fig)
            
        except Exception as e:
            st.error(f"שגיאה זמנית בתקשורת עם שרתי NASA או שהנתונים ליום זה טרם שוחררו. אנא ודאו שהתאריך תקין. (Error: {e})")
