import streamlit as st
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import xarray as xr
import numpy as np
from datetime import datetime, timedelta
import matplotlib.colors as mcolors

# הגדרות עמוד של Streamlit
st.set_page_config(page_title="מעבדה מטאורולוגית", layout="wide")

st.title("🌍 מחולל מפות סינופטיות - מעבדה")
st.markdown("### מערכת הפקת מפות מבוססת נתוני Global Analysis")

# סרגל צד להגדרות המשתמש
st.sidebar.header("הגדרות הפקה")

year = st.sidebar.slider("שנה", 2020, 2026, 2026)
month = st.sidebar.slider("חודש", 1, 12, 5)
day = st.sidebar.slider("יום", 1, 31, 28)

# בחירת שעה מתוך רשימה קבועה
hour = st.sidebar.selectbox("שעה (UTC)", [0, 6, 12, 18], index=2)

map_type = st.sidebar.radio("סוג מפה", ["surface", "500mb", "850mb"])

if st.sidebar.button("הפק מפה"):
    with st.spinner('מושך נתוני אנליזה גלובליים...'):
        try:
            target_dt = datetime(year, month, day, hour)
            
            # מעבר לשרת האנליזה הגלובלי היציב והפתוח של NOMADS/NCAR
            date_str = target_dt.strftime("%Y%m%d")
            hour_str = target_dt.strftime("%H")
            
            # קישור דינמי לקובץ האנליזה לפי התאריך שנבחר
            url = f"https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{date_str}/gfs_0p25_{hour_str}z"
            
            ds = xr.open_dataset(url)

            # יצירת המפה
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
            title_text = f"{map_info[map_type]}\nValid for: {target_dt.strftime('%Y-%m-%d %H:00')} UTC\nSource: Global Analysis Dataset"

            if map_type == 'surface':
                # prmslmsl = Pressure reduced to MSL
                slp = ds['prmslmsl'].isel(time=0).sel(lat=slice(20, 40), lon=slice(20, 50)) / 100.0
                white_cmap = mcolors.ListedColormap(['white'])
                cf = ax.contourf(slp.lon, slp.lat, slp, cmap=white_cmap, levels=[slp.min(), slp.max()])
                plt.colorbar(cf, orientation='horizontal', pad=0.08, aspect=40).ax.set_visible(False)
                
                cntr = ax.contour(slp.lon, slp.lat, slp, colors='black', levels=np.arange(980, 1040, 2))
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)
                
                # רוחות בגובה 10 מטרים
                u = ds['ugrd10m'].isel(time=0).sel(lat=slice(20, 40), lon=slice(20, 50))
                v = ds['vgrd10m'].isel(time=0).sel(lat=slice(20, 40), lon=slice(20, 50))
                ax.barbs(u.lon[::4], u.lat[::4], u.values[::4, ::4], v.values[::4, ::4], length=6, color='darkblue')

            elif map_type == '850mb':
                # tmpprs = Temperature on pressure levels
                temp = ds['tmpprs'].isel(time=0).sel(lev=850, lat=slice(20, 40), lon=slice(20, 50)) - 273.15
                cf = ax.contourf(temp.lon, temp.lat, temp, cmap='coolwarm', levels=np.arange(-15, 35, 2), extend='both')
                plt.colorbar(cf, label='Temperature (°C)', orientation='horizontal', pad=0.08, aspect=40)
                cntr = ax.contour(temp.lon, temp.lat, temp, colors='black', levels=np.arange(-15, 35, 2), linewidths=0.8)
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)

            elif map_type == '500mb':
                # hgtprs = Geopotential height on pressure levels
                hgt = ds['hgtprs'].isel(time=0).sel(lev=500, lat=slice(20, 40), lon=slice(20, 50))
                cf = ax.contourf(hgt.lon, hgt.lat, hgt, cmap='viridis', levels=np.arange(5100, 6000, 60), extend='both')
                plt.colorbar(cf, label='Geopotential Height (m)', orientation='horizontal', pad=0.08, aspect=40)
                cntr = ax.contour(hgt.lon, hgt.lat, hgt, colors='white', linewidths=1.2, levels=np.arange(5100, 6000, 60))
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)

            plt.title(title_text, fontsize=14, pad=20)
            st.pyplot(fig)
            
        except Exception as e:
            st.error(f"יש שגיאה זמנית בתקשורת או שהנתונים ליום זה טרם עודכנו במערכת. אנא ודאו שהתאריך שנבחר תקין. (Error: {e})")
