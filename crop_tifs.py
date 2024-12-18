import os
import glob

tifs = glob.glob('*.tif')

for tif in tifs:

    os.system(f"gdalwarp -cutline DE_mask.shp -crop_to_cutline {tif} {tif[:-4] + '_clip.tif'}")

print('DONE')