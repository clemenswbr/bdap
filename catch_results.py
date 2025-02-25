import xarray as xr
import numpy as np
import pandas as pd


def csvToNetCDF(df, maskFileName, outputFileName):
    # The netCDF Outline including the ids
    ds = xr.open_dataset(maskFileName)
    #print(ds)
    # Create a Dataframe with the ids and the (lat,lon)
    dm = {}
    for ila, la in enumerate(ds.lat.values):
        for ilo, lo in enumerate(ds.lon.values):

            the_id = ds.ID[ila,ilo].values
            if np.isnan(the_id) == False:
                dm[int(the_id)] = (la,lo)
    #
    # Store the dm dictionary into data according to the id
    df["coords"] = df.id.map(dm)
    # add lat and lon from the coords touple
    df[['lat', 'lon']] = pd.DataFrame(df['coords'].tolist(), index=df.index) 
    del df["coords"]
    data2 = df.copy(deep=True)
    data2 = data2[~ np.isnan(data2.lat)]
    # Correct the datatime in the data Dataframe
    #data2['date'] = pd.to_datetime(data2['datetime']).dt.date 
    # Set the Index to 'datetime','lat','lon'
    data2 = data2.set_index(['date','lat','lon'])
    # Create an empty Dataset and fill it with data2 Dataframe and use index as coordinates. 
    dsout = xr.Dataset()
    dsout = dsout.from_dataframe(data2)
    #print(dsout)
    # # Group the content of dsout by year-sums 
    # dsout2 = dsout.groupby('datetime.year').sum(dim='datetime')
    # Save the new Dataset to a netCDF file.
    dsout.to_netcdf(outputFileName)
    #print("Done.")
#