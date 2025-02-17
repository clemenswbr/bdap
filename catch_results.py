from netCDF4 import Dataset
import os
import numpy as np
import pandas as pd
import datetime as dt
import rasterio


os.chdir('/eos/jeodpp/data/projects/SOIL-NACA/MODEL4')

#Read lat long file
lat_long = rasterio.open('/eos/jeodpp/data/projects/SOIL-NACA/MODEL4/DE_sim/lat_long_clip.tif')
lat = lat_long.read(1)/100
long = lat_long.read(2)/100

#Create file
ncfile = Dataset('results.nc', mode='w', format='NETCDF4_CLASSIC')

#Create dimensions
ncfile.createDimension('lat', len(lat))
ncfile.createDimension('long', len(long))
ncfile.createDimension('time', None)

#Create variables
lat = ncfile.createVariable('lat', np.float32, ('lat',))
lat.units = 'latitude'
long = ncfile.createVariable('long', np.float32, ('long',))
long.units = 'longitude'
time = ncfile.createVariable('time', np.float32, ('time'))
times = pd.date_range(pd.to_datetime('2011-01-04'), pd.to_datetime('2024-12-31'), freq='w')
time[:] = times
time.units = 'Week'
n2o = ncfile.createVariable('n2o', np.float64, ('time', 'lat', 'long'))
n2o.units = 'kg*km^-2*week^-1'

#Create empty array to fill with values
arr = np.full((len(times), lat_long.height, lat_long.width), -99.99)

#Fill array
for r in range(lat_long.height):
    for c in range(lat_long.width):
        print(r, c)
        #Get lat and long
        lat_df = lat[r,c]
        long_df = long[r,c]
        if any(lat_df == lat_long.nodata/100, long_df == lat_long.nodata/100):
            continue
        #Check if file exists
        try:
            df = pd.read_csv(f'test_ldndc_output/{r}_{c}_output/{r}_{c}_soilchemistry-daily.txt', sep='\t')[['datetime', 'dN_n2o_emis[kgNha-1]']]
        except FileNotFoundError:
            continue
        #Read ldndc output, aggregate to weekly resolution, convert from kgNha-1 to kgNkm-2
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        df_weekly = df.resample('W').sum()
        df_weekly['dN_n2o_emis[kgNha-1]'] = df_weekly['dN_n2o_emis[kgNha-1]'] * 0.01
        #Write to array if output is complete
        if len(df_weekly) == len(times):
            arr[:,lat_df,long_df] = df_weekly['dN_n2o_emis[kgNha-1]']

#write to netCDF
n2o[:,:,:] = arr
ncfile.close()