#Create lat, long file for meteo observations
import rasterio
import pandas as pd
import numpy as np
import sys

file_in = sys.argv[1]
file_out = sys.argv[2]
print(file_in, ' ---> ', file_out)

lat_long = rasterio.open(file_in)

lat = lat_long.read(1)
long = lat_long.read(2)
#index = np.arange(1, len(lat) + 1, 1)

lat_t = []
long_t = []

for lat_i in range(lat.shape[0]):
    for long_i in range(lat.shape[1]):
        #print(lat_i, long_i)
        lat_t.append(lat[lat_i,long_i])
        long_t.append(long[lat_i,long_i])


df = pd.DataFrame({'index':np.arange(0, len(lat_t)), 'lat':lat_t, 'long':long_t})
df.to_csv(file_out)

print('DONE')