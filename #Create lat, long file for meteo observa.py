#Create lat, long file for meteo observations
import rasterio
import pandas as pd
import numpy as np
import sys

file_in = sys.argv()[1]
file_out = sys.argv()[2]
print(file_in, ' ---> ', file_out)

lat_long = rasterio.open(file_in)

lat = lat_long.read(1)
long = lat_long.read(1)
index = np.arange(1, len(lat) + 1, 1)

df = pd.DataFrame({'index':index, 'lat':lat, 'long':long})
df.to_csv(file_out)

print('DONE')