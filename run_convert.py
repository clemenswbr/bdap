import DC_LDNDC_Conversions as dcldndc
import glob
import subprocess
import rasterio
import pandas as pd
import os


os.chdir('/eos/jeodpp/data/projects/SOIL-NACA/MODEL4')

#Read N and C data, N deposition
N_data = rasterio.open('DE_sim/EU_N_kgkg_clip.tif')
N = N_data.read(1)
N[N < 0] = -99.99   
C_data = rasterio.open('DE_sim/EU_C_kgkg_clip.tif')
C = C_data.read(1)/1000 #Convert from g/kg to kg/kg
C[C < 0] = -99.99
N_deposition_data = rasterio.open('DE_sim/DDEP_RDN_m2Grid_repro_clip.tif')
N_deposition = N_deposition_data.read(1)
#Read other common files
lookup = pd.read_csv('bdap/dc_ldndc_lookup.csv', sep='\t')
omad100 = dcldndc.read_dot100('../MODEL/DAYCENT/RUN/DayC/omad.100') 
harv100 = dcldndc.read_dot100('../MODEL/DAYCENT/RUN/DayC/harv.100')
irri100 = dcldndc.read_dot100('../MODEL/DAYCENT/RUN/DayC/irri.100')

#Loop through soil files for simulations
for run in glob.glob('OUT/test/site_*_*.100'):
    print('RUN: ', run)
    row = int(run.split('_')[1])
    col = int(run.split('_')[2].split('.')[0])
    print('Row:', row, 'Col: ', col)

    #Get topsoil organic C and N from additional files
    corg_ts = C[row, col]
    norg_ts = N[row, col]
    N_deposition = N_deposition[row, col]
    run_index = f'{row}_{col}'

    print('Corg: ', corg_ts, 'Norg: ', norg_ts)
    print('Soil: ', f'OUT/test/soils_{row}_{col}.in', f'test_ldndc/{row}_{col}_site.xml', 'corg_ts=corg_ts, norg_ts=norg_ts')
    print('Meteo: ', f'OUT/test/meteo_{row}_{col}.wth', f'test_ldndc/{row}_{col}_climate.txt', '2015', f'OUT/test/site_{row}_{col}.100')
    print('Mana: ', f'OUT/test/mgt_{row}_{col}.evt', f'test_ldndc/{row}_{col}_mana.xml', 'omad100', 'harv100', 'irri100', 'lookup', 'start_year=2015', 'end_year=2024')
    print('Setup: ', row, col, f'OUT/test/{row}_{col}_setup.xml')
    print('LDNDC: ', row, col, f'test_ldndc/{row}_{col}_mana.xml')
    print('Airchem: ', f'OUT/test/site_{row}_{col}.100', f'test_ldndc/{row}_{col}_airchemistry.txt', start_year, end_year)
    print('_______________________________')

    dcldndc.convert_dcsoil_ldndcsoil(f'OUT/test/soils_{row}_{col}.in', f'test_ldndc/{row}_{col}_site.xml', norg_ts=norg_ts, corg_ts=corg_ts)
    dcldndc.convert_wth_climate_jrc(f'OUT/test/meteo_{row}_{col}.wth', f'test_ldndc/{row}_{col}_climate.txt', 2015, f'OUT/test/site_{row}_{col}.100')
    dcldndc.convert_evt_mana(f'OUT/test/mgt_{row}_{col}.evt', f'test_ldndc/{row}_{col}_mana.xml', omad100, harv100, irri100, lookup, start_year=2015, end_year=2024)
    dcldndc.create_setup(row, col, f'test_ldndc/{row}_{col}_setup.xml')
    dcldndc.create_ldndc(row, col, f'test_ldndc/{row}_{col}.ldndc', 2015, 2024)
    dcldndc.create_airchem(f'test_ldndc/{row}_{col}_airchem.txt', 2015, 2024, N_deposition)

N_data.close()
C_data.close()
print('DONE')