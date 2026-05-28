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
st.markdown("### מערכת הפקת מפות מבוססת נתוני NCEP Reanalysis המעודכנים")

# סרגל צד להגדרות המשתמש
st.sidebar.header("הגדרות הפקה")

year = st.sidebar.slider("שנה", 1979, 2026, 2026)
month = st.sidebar.slider("חודש", 1, 12, 5)
day = st.sidebar.slider("יום", 1, 31, 28)

# בחירת שעה מתוך רשימה קבועה למניעת שגיאות בשרת
hour = st.sidebar.selectbox("שעה (UTC)", [0, 6, 12, 18], index=2)

map_type = st.sidebar.radio("סוג מפה", ["surface", "500mb", "850mb"])

if st.sidebar.button("הפק מפה"):
    with st.spinner('מושך נתוני ריאנליזה מעודכנים...'):
        try:
            target_dt = datetime(year, month, day, hour)
            
            # שימוש במאגר הריאנליזה הנתמך והרציף של NOAA (מונע את חסימת מרץ)
            urls = {
                'slp': f"https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis2/surface/mslp.{year}.nc",
                'hgt': f"https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis2/pressure/hgt.{year}.nc",
                'air': f"https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis2/pressure/air.{year}.nc",
                'uwnd': f"https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis2/surface/uwnd.sig995.{year}.nc",
                'vwnd': f"https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis2/surface/vwnd.sig995.{year}.nc"
            }

            # פתיחת הנתונים לפי תאריך ושעה מדויקים
            ds = xr.open_dataset(urls['slp'] if map_type == 'surface' else (urls['hgt'] if map_type == '500mb' else urls['air']))
            
            # התאמה דינמית של הזמן במאגר החדש
            time_idx = np.abs(ds.time.values - np.datetime64(target_dt)).argmin()

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
            title_text = f"{map_info[map_type]}\nValid for: {target_dt.strftime('%Y-%m-%d %H:00')} UTC\nSource: NCEP Reanalysis 2"

            if map_type == 'surface':
                slp = ds['mslp'].isel(time=time_idx).sel(lat=slice(40, 20), lon=slice(20, 50)) / 100.0
                white_cmap = mcolors.ListedColormap(['white'])
                cf = ax.contourf(slp.lon, slp.lat, slp, cmap=white_cmap, levels=[slp.min(), slp.max()])
                plt.colorbar(cf, orientation='horizontal', pad=0.08, aspect=40).ax.set_visible(False)
                
                cntr = ax.contour(slp.lon, slp.lat, slp, colors='black', levels=np.arange(980, 1040, 2))
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)
                
                ds_u = xr.open_dataset(urls['uwnd'])
                ds_v = xr.open_dataset(urls['vwnd'])
                u = ds_u['uwnd'].isel(time=time_idx).sel(lat=slice(40, 20), lon=slice(20, 50))
                v = ds_v['vwnd'].isel(time=time_idx).sel(lat=slice(40, 20), lon=slice(20, 50))
                ax.barbs(u.lon[::2], u.lat[::2], u.values[::2, ::2], v.values[::2, ::2], length=6, color='darkblue')

            elif map_type == '850mb':
                temp = ds['air'].isel(time=time_idx).sel(level=850, lat=slice(40, 20), lon=slice(20, 50)) - 273.15
                cf = ax.contourf(temp.lon, temp.lat, temp, cmap='coolwarm', levels=np.arange(-15, 35, 2), extend='both')
                plt.colorbar(cf, label='Temperature (°C)', orientation='horizontal', pad=0.08, aspect=40)
                cntr = ax.contour(temp.lon, temp.lat, temp, colors='black', levels=np.arange(-15, 35, 2), linewidths=0.8)
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)

            elif map_type == '500mb':
                hgt = ds['hgt'].isel(time=time_idx).sel(level=500, lat=slice(40, 20), lon=slice(20, 50))
                cf = ax.contourf(hgt.lon, hgt.lat, hgt, cmap='viridis', levels=np.arange(5100, 6000, 60), extend='both')
                plt.colorbar(cf, label='Geopotential Height (m)', orientation='horizontal', pad=0.08, aspect=40)
                cntr = ax.contour(hgt.lon, hgt.lat, hgt, colors='white', linewidths=1.2, levels=np.arange(5100, 6000, 60))
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)

            plt.title(title_text, fontsize=14, pad=20)
            st.pyplot(fig)
            
        except Exception as e:
            st.error(f"יש שגיאה זמנית בתקשורת או שהנתונים ליום זה טרם עודכנו בריאנליזה. אנא נסו שוב בעוד מספר דקות. (Error: {e})")
