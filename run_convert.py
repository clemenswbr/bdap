import DC_LDNDC_Conversions as dcldndc
import glob
import subprocess
import rasterio

#Read N dataset
N_data = rasterio.open('../../../LUCAS_N_EU_SW_kgkg_SSPM.tif')
N = N_data.read(1)

C_data = rasterio.open('../../../../MODEL/SptLYR/soil_LCS.tif')
C = C_data.read(5) 

irri100 = '../../../../MODEL/DAYCENT/RUN/DayC/irri.100'
harv100 = '../../../../MODEL/DAYCENT/RUN/DayC/harv.100'
omad100 = '../../../../MODEL/DAYCENT/RUN/DayC/omad.100'

for run in glob.glob('../soils*.in'):

    row = int(run.split('_')[1])
    col = int(run.split('_')[2][:-3])
    
    run_index = f'{row}_{col}'

    print(run_index)
    print(f'../soils_{run_index}.in', f'./test/{run_index}_site.xml')
    print(f'../meteo_{run_index}.wth', f'./test/{run_index}_climate.txt', f'../site_{run_index}.100')
    print(f'../mgt_{run_index}.evt', f'./test/{run_index}_mana.xml', f'dirComad_{run_index}.in', harv100, irri100, 'dc_ldndc_lookup.csv')
    print(run_index, f'./test/{run_index}_setup.xml')
    print(run_index, f'./test/{run_index}.ldndc', f'./test/{run_index}_mana.xml')
    print('_______________________________')

    dcldndc.convert_dcsoil_ldndcsoil(f'../soils_{run_index}.in', f'./test/{run_index}_site.xml', row, col, C, N)
    dcldndc.convert_wth_climate(f'../meteo_{run_index}.wth', f'./test/{run_index}_climate.txt', f'../site_{run_index}.100')
    dcldndc.convert_sch_mana(f'../mgt_{run_index}.evt', f'./test/{run_index}_mana.xml', f'../dirComad_{run_index}.in', harv100, irri100, 'dc_ldndc_lookup.csv')
    dcldndc.create_setup(run_index, f'./test/{run_index}_setup.xml')
    dcldndc.create_ldndc(run_index, f'./test/{run_index}.ldndc', f'./test/{run_index}_mana.xml')
    dcldndc.create_airchem(run_index)

N_data.close()
C_data.close()
print('DONE')