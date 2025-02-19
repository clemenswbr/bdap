from netCDF4 import Dataset
import os
import numpy as np
import pandas as pd
import datetime as dt
import rasterio


os.chdir('/eos/jeodpp/data/projects/SOIL-NACA/MODEL4')

#Dimensions (time, x, y)
n_time = 730
n_row = 866
n_col = 639

ncfile = Dataset('netcdf_template.nc', mode='a', format='netCDF4_classic', clobber=True)
#times = pd.date_range(pd.to_datetime('2011-01-04'), pd.to_datetime('2024-12-31'), freq='w')

#Fill array
for r in range(n_row):
    for c in [309,310]:
        print(r, c)
        try:
            df = pd.read_csv(f'test_ldndc_output/{r}_{c}_output/{r}_{c}_soilchemistry-daily.txt', sep='\t')[['datetime', 'dN_n2o_emis[kgNha-1]']]
        except FileNotFoundError:
            continue
        #Read ldndc output, aggregate to weekly resolution, convert from kgNha-1 to kgNkm-2
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        df_weekly = df.resample('W').sum()
        df_weekly['dN_n2o_emis[kgNha-1]'] = df_weekly['dN_n2o_emis[kgNha-1]'] * 0.01
        #Write to file if output is complete
        if len(df_weekly) == n_time:
            ncfile['n2o'][:,r,c] = df_weekly['dN_n2o_emis[kgNha-1]']

ncfile.close()