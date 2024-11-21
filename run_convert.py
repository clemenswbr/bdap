import DC_LDNDC_Conversions as dcldndc
import glob
import subprocess
import rasterio
import pandas as pd

#Read N and C data, all the common files and replace no data values
N_data = rasterio.open('../../../LUCAS_N_EU_SW_kgkg_SSPM.tif')
N = N_data.read(1)
N[N < 0] = -99.99   

C_data = rasterio.open('../../../LUCAS_EU_SOC.tif')
C = C_data.read(1)/1000 #Convert from g/kg to kg/kg
C[C < 0] = -99.99

lookup = pd.read_csv('dc_ldndc_lookup.csv', sep='\t')
omad100 = dcldndc.read_dot100('../../../../MODEL/DAYCENT/RUN/DayC/omad.100') 
harv100 = dcldndc.read_dot100('../../../../MODEL/DAYCENT/RUN/DayC/harv.100')
irri100 = dcldndc.read_dot100('../../../../MODEL/DAYCENT/RUN/DayC/irri.100')

#Loop through soil files for simulations
for run in glob.glob('../meteo*.wth')[0]:

    print(run)
    
    row = int(run.split('_')[1])
    col = int(run.split('_')[2])
    
    run_index = f'{row}_{col}'
    meteo_index = int(run.split('_')[3][:-4])

    print('Soil: ', f'../soils_{run_index}.in', f'./test/{run_index}_site.xml', row, col, 'C', 'N')
    print('Meteo: ', f'../meteo_{run_index}_{meteo_index}.wth', f'./test/{run_index}_climate.txt', f'../site_{run_index}.100')
    print('Mana: ', f'../mgt_{run_index}.evt', f'./test/{run_index}_mana.xml', 'omad100', 'harv100', 'irri100', 'lookup')
    print('Setup: ', run_index, f'./test/{run_index}_setup.xml')
    print('LDNDC: ', run_index, f'./test/{run_index}.ldndc', f'./test/{run_index}_mana.xml')
    print('Airchem: ', run_index)
    print('_______________________________')

    dcldndc.convert_dcsoil_ldndcsoil(f'../soils_{run_index}.in', f'./test/{run_index}_site.xml', row, col, C, N)
    dcldndc.convert_wth_climate(f'../meteo_{run_index}_{meteo_index}.wth', f'./test/{run_index}_climate.txt', f'../site_{run_index}.100')
    dcldndc.convert_sch_mana(f'../mgt_{run_index}.evt', f'./test/{run_index}_mana.xml', omad100, harv100, irri100, lookup)
    dcldndc.create_setup(run_index, f'./test/{run_index}_setup.xml')
    dcldndc.create_ldndc(run_index, f'./test/{run_index}.ldndc', f'./test/{run_index}_mana.xml')
    dcldndc.create_airchem(run_index)

N_data.close()
C_data.close()
print('DONE')