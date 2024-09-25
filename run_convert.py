import DC_LDNDC_Conversions as dcldndc
import glob
import subprocess

#run_numbers = [int(n[8:-3]) for n in glob.glob('../soils*')]
run_numbers = [4947675] 

irri100 = '../../../../MODEL/DAYCENT/RUN/DayC/irri.100'
harv100 = '../../../../MODEL/DAYCENT/RUN/DayC/harv.100'
omad100 = '../../../../MODEL/DAYCENT/RUN/DayC/omad.100'

for run_number in run_numbers:

    print(run_number)
    print(f'../soils{run_number}.in', f'./test/{run_number}_site.xml')
    print(f'../meteo{run_number}.wth', f'./test/{run_number}_climate.txt', f'../site{run_number}.100')
    print(f'../mgt{run_number}.evt', f'./test/{run_number}_mana.xml', f'dirComad{run_number}.in', harv100, irri100, 'dc_ldndc_lookup.csv')
    print(run_number, f'./test/{run_number}_setup.xml')
    print(run_number, f'./test/{run_number}.ldndc', f'./test/{run_number}_mana.xml')
    print('_______________________________')

    dcldndc.convert_dcsoil_ldndcsoil(f'../soils{run_number}.in', f'./test/{run_number}_site.xml')
    dcldndc.convert_wth_climate(f'../meteo{run_number}.wth', f'./test/{run_number}_climate.txt', f'../site{run_number}.100')
    dcldndc.convert_sch_mana(f'../mgt{run_number}.evt', f'./test/{run_number}_mana.xml', f'../dirComad{run_number}.in', harv100, irri100, 'dc_ldndc_lookup.csv')
    dcldndc.create_setup(run_number, f'./test/{run_number}_setup.xml')
    dcldndc.create_ldndc(run_number, f'./test/{run_number}.ldndc', f'./test/{run_number}_mana.xml')
    dcldndc.create_airchem(run_number)