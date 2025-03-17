import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import re
import os
import math

##Reads a *.100 (or similarly structured) file into a nested dictionary
##Other conversion functions require this structure
##Keys and parameters are always upper case
##Is called by *.wth conversion
def read_dot100(in_file_name):
    in_file = open(in_file_name, 'r')
    lines = [line for line in in_file.readlines() if not line.startswith('#') and line.strip()]
    lines = [l.replace('#', '') for l in lines]
    lines = [l.replace('*** ', '') for l in lines]
    lines = [re.sub(' +', ' ', l) for l in lines]
    lines = [l.replace('*', '') for l in lines]
    lines = [l.replace("'", "") for l in lines]
    in_dict = {}
    
    for line in lines: 
        if line.split()[0][0].isalpha():
            key = line.split()[0].upper()
            in_dict[key] = {}
        else:
            in_dict[key][line.split()[1].upper()] = float(line.split()[0])

    return in_dict


##Conversion for DayCent soil file (soils.in) to LandscapeDNDC site file (*site.xml)
##DayCent soil does not contain Norg and Corg (depends on the version), they can be specified as optional arguments if needed
##Measurment depth: Within this depth the value for Corg and Norg is constant, lower than that it declines exponentially. Default is 200[mm]
##Naming convention: corg_ts: topsoil organic carbon, norg_ts: topsoil organic nitrogen
##Only works if corg_ts and norg_ts are supplied and are both > 0 (and not -99.99)
def convert_dcsoil_ldndcsoil(dcsoil_file_name, ldndcsoil_file_name, measurement_depth=200, **kwargs):
    #Defaults
    CN_min = 8 #Minimum allowed C:N ratio
    
    #Read DayCent soil file
    dc_soil = pd.read_csv(dcsoil_file_name, sep='\t', header=None)
    dc_soil.columns = ['upper_depth', 'lower_depth', 'bd', 'wcmax', 'wcmin', 'evaporation', 'root_fraction', 'sand', 'clay', 'organic_matter', 'deltamin', 'sks', 'ph']
    dc_soil.insert(0, 'depth', value=(dc_soil['lower_depth']*10 - dc_soil['upper_depth']*10))
    dc_soil = dc_soil.drop(['upper_depth', 'lower_depth', 'evaporation', 'root_fraction', 'organic_matter', 'deltamin'], axis='columns')
    #Convert wcmax, wcmin cm^3/cm^3 -> dm^3/m^3
    dc_soil['wcmax'] = dc_soil['wcmax']*1000
    dc_soil['wcmin'] = dc_soil['wcmin']*1000 
    #Convert sks cm/sec -> cm/min
    dc_soil['sks'] = dc_soil['sks']*60
    #Add norg and corg from LUCAS data
    depths = np.cumsum(dc_soil['depth'])

    #Build corg and norg
    try:
        corg_ts = kwargs['corg_ts']
        norg_ts = kwargs['norg_ts']
    except KeyError:
        print('No corg_ts and norg_ts supplied -> -99.99')
        corg_ts = -99.99
        norg_ts = -99.99
        
    if any([corg_ts <= 0, norg_ts <= 0]):
        corg = np.tile(-99.99, len(depths))
        norg = np.tile(-99.99, len(depths))
    else:
        if corg_ts/norg_ts <= CN_min: #Threshold for lowest allowed C:N ratio; adjust norg_ts
            norg_ts = corg_ts/CN_min
        #Gradient function for organic C and N with depth
        corg = [max(round(corg_ts * np.exp(-0.003 * max(0, d - measurement_depth)), 8), 0.00000000001) for d in depths]
        norg = [max(round(norg_ts * np.exp(-0.003 * max(0, d - measurement_depth)), 8), 0.00000000001) for d in depths]

    dc_soil['norg'] = norg
    dc_soil['corg'] = corg
    #Write to *site.xml
    top = ET.Element('site')
    soil = ET.SubElement(top, 'soil')
    layers = ET.SubElement(soil, 'layers')

    for row in range(len(dc_soil)):
        stratum = dc_soil.iloc[row]
        stratum_ldndc = ET.SubElement(layers, 'layer')
        for par, value in zip(dc_soil.columns, stratum):
            stratum_ldndc.set(par, str(value))

    tree = ET.ElementTree(top)
    ET.indent(tree)
    tree.write(ldndcsoil_file_name, xml_declaration=True)
    print(f'Created file {ldndcsoil_file_name}')


##Conversion of DayCent *.wth to LDNDC *climate.txt
##Number of defined columns have to be specified in the function call (minimum is 7)
## *args takes the site100 file, which may contain information about the lat, long, elevation
##tavg can be estimated as (tmax - tmin)/2 if estimate tavg = True
def convert_wth_climate(wth_file_name, microclimate_file_name, *args, columns=7, estimate_tavg=False):
    #Read DayCent *.wth file
    wth_file = pd.read_csv(wth_file_name, sep='\t', header=None)
    wth_file = wth_file.iloc[:,:columns]
    wth_file.columns = ['day', 'month', 'year', 'doy', 'tmax', 'tmin', 'prec', 'rad', 'rel_humidity', 'wind'][:columns]
    wth_file = wth_file.drop(['rel_humidity'], axis='columns', errors='ignore')
    wth_file = wth_file.astype({'day':int, 'month':int, 'year':int})
    wth_file['prec'] = wth_file['prec']/10 #Convert from cm to mm
    wth_file['day'] = [str(d).zfill(2) for d in wth_file['day']]
    wth_file['month'] = [str(d).zfill(2) for d in wth_file['month']]
    if columns > 7:
        wth_file['rad'] = wth_file['rad'] * 0.485 #Convert from Langley/d to W*m^-2
        wth_file['wind'] = round(wth_file['wind'] * 1.609344, 4) #Convert from miles/hour to km/hour
    start_time =  f"{wth_file['year'][0]}-{wth_file['month'][0]}-{wth_file['day'][0]}"
    wth_file = wth_file.drop(['day', 'month', 'year', 'doy'], axis='columns')
    wth_file = wth_file.round(2)
    #Insert estimation of tavg
    if estimate_tavg:
        tavg = round((wth_file['tmax'] + wth_file['tmin'])/2, 2)
        wth_file.insert(2, column='tavg', value=tavg)

    #Get lat and long from site.100 file
    if len(args) > 0:
        site100 = read_dot100(args[0])
        site100['SITE'].setdefault('SITLAT', -99.99)
        site100['SITE'].setdefault('SITLNG', -99.99)
        site100['SITE'].setdefault('ELEV', -99.99)
        lat = site100['SITE']['SITLAT']
        long = site100['SITE']['SITLNG']
        elev = site100['SITE']['ELEV']
    
    wth_file = wth_file.reset_index(drop=True)

    with open(microclimate_file_name, 'w') as f:
        f.write('%global\n')
        f.write(f'        time = "{start_time}/1"\n')
        f.write('\n')
        f.write('%climate\n')
        f.write('        id = 0\n')
        f.write('\n')
        if len(args) > 0:
            f.write('%attributes\n')
            f.write(f'        elevation = "{elev}"\n')
            f.write(f'        latitude = "{lat}"\n')
            f.write(f'        longitude = "{long}"\n')
            f.write('\n')         
        f.write('%data\n')
        wth_file.to_csv(f, index=False, header=True, sep='\t')

    print(f'Created file {microclimate_file_name}')


##Function to convert DayCent *.sch/*.evt file to LDNDC *.mana file
##Grass is always PERG
##Fertilization is always nh4 unless urea is recognized in DAYCENT input
##Grazing is generic
##Tillage depth is always 0.2m
##Non N fertilization and cultivations other than tillage are ignored
##Automatic irrigation is ignored
##kwargs are start_year, end_year, graz.100 for grassland simulations; writes events in mana file only in range(start_year, end_year + 1)
def convert_evt_mana(sch_file_name, mana_file_name, omad100, harv100, irri100, lookup, **kwargs):
    #Defaults
    fert_type = 'nh4' #Type of fertilizer in FERT event
    manure_type = 'generic' #Type of manure to be applied
    till_depth = 0.2 #Tillage depth
    ni_amount = 4.0 #NI amount for nitrification inhibitors
    do_harvest = False #Changes to True, once a crop is planted, prevents harvest when there is no crop
    do_till = True #Changes to False once a crop is planted, prevents tilling while a crop is on the field
    
    with open(sch_file_name, 'r') as events_in, open(mana_file_name, 'wb') as events_out:
        #Start xml
        top = ET.Element('event')
        
        #Clean and homogenize lines; Make list of blocks
        in_lines = events_in.readlines()
        in_lines = [re.sub(' +', ' ', line).lstrip(' ') for line in in_lines if line.strip()]
        in_block_lines = []
        block_last_years = []
        block_start_years = []
        start = 0
        block = 1
        plant_grass = True

        for i, line in enumerate(in_lines):
            if 'Option' in line:
                start = i + 1
            elif 'Output starting year' in line:
                block_start_years.append(int(line.split()[0]))
            elif 'Last year' in line:
                block_last_years.append(int(line.split()[0]))
            elif all((re.findall(r'CROP G\d', line), block == 1, plant_grass)):
                #Grassland simulation, plant PERG at the beginning of the simulation with initbiom=200
                ldndc_event = ET.SubElement(top, 'event')
                ldndc_event.set('type', 'plant')
                ldndc_event.set('time', f'{block_start_years[0]}-01-01')
                ldndc_event_info = ET.SubElement(ldndc_event, 'plant')
                ldndc_event_info.set('type', 'PERG')
                ldndc_event_info.set('name', 'PERG')
                ldndc_event_subinfo = ET.SubElement(ldndc_event_info, 'grass')
                ldndc_event_subinfo.set('initialbiomass', str(200))
                do_harvest = True
                plant_grass = False
                ldndc_crop = 'PERG'
            elif '-999 -999 X' in line:
                block_lines = [l for l in in_lines[start:i] if len(l.split()) >= 3]
                block_lines = [l for l in block_lines if all([l.split()[0].lstrip('-').isdigit(), 
                                                              l.split()[1].isdigit()])]
                in_block_lines.append(block_lines)
                start = i + 1
                block += 1

        try:
            start_year = kwargs['start_year']
            end_year = kwargs['end_year']
        except KeyError:
            start_year = block_start_years[0]
            end_year = block_last_years[-1]

        #Loop over blocks and write to mana_file_name
        for i, block in enumerate(in_block_lines):
            block_last_year = block_last_years[i]
            count_year = block_start_years[i]
            while count_year <= block_last_year:
                for line in block:
                    block_year = int(line.split()[0])
                    evt_year = count_year + block_year - 1
                    if evt_year in range(start_year, end_year + 1):
                        event = line.split()[2]
                        doy = int(line.split()[1])
                        date = pd.to_datetime(pd.to_datetime(f'{evt_year}-01-01') + pd.Timedelta(days=doy-1))
                        #Convert events in block
                        if event == 'FERT':
                            try:
                                f_amount = float(line.split()[3].split('N')[0][1:]) * 10000 * 0.001 #Conversion from g * m^-2 to kg * ha^-1
                                fert_type = 'urea' if any([re.findall(r'U\d', line.split()[3]), 'UREA' in line.split()[3]]) else fert_type
                            except:
                                print('Could not access fertilization info for:', line)
                                continue
                            ldndc_event = ET.SubElement(top, 'event')
                            ldndc_event.set('type', 'fertilize')
                            ldndc_event.set('time', str(date)[:-9])
                            ldndc_event_info = ET.SubElement(ldndc_event, 'fertilize')
                            ldndc_event_info.set('amount', str(f_amount))
                            ldndc_event_info.set('type', fert_type)
                            # For inhibitors
                            if any(('I' in line.split()[3], 'SU' in line.split()[3])):
                                ldndc_event_info.set('ni_amount', str(ni_amount))
                        #Get crop for planting event
                        elif event == 'CROP':
                            crop = line.split()[3].upper()
                            try:
                                ldndc_crop = lookup[lookup['dc_crop'] == crop]['ldndc_crop'].iloc[0]
                                ldndc_initbiom = lookup[lookup['dc_crop'] == crop]['initbiom'].iloc[0]
                            except:
                                #Throw error and print crop, when it does not exist in lookup; avoid hard error
                                #Set crop and biomass to -99.99 so something is written to *mana.xml and it is clear the crop is not left empty on purpose
                                print('Crop not in lookup:', line)
                                ldndc_crop = '-99.99'
                                ldndc_initbiom = '-99.99'
                        #Plant event
                        elif event == 'PLTM':
                            ldndc_event = ET.SubElement(top, 'event')
                            ldndc_event.set('type', 'plant')
                            ldndc_event.set('time', str(date)[:-9])
                            ldndc_event_info = ET.SubElement(ldndc_event, 'plant')
                            ldndc_event_info.set('type', ldndc_crop)
                            ldndc_event_info.set('name', ldndc_crop)
                            ldndc_event_subinfo = ET.SubElement(ldndc_event_info, 'grass' if ldndc_crop == 'PERG' else 'crop')
                            ldndc_event_subinfo.set('initialbiomass', str(ldndc_initbiom))
                            do_harvest = True
                            do_till = False
                        #Organic matter input (manure)
                        elif event == 'OMAD':
                            ldndc_event = ET.SubElement(top, 'event')
                            ldndc_event.set('type', 'manure')
                            ldndc_event.set('time', str(date)[:-9])
                            ldndc_event_info = ET.SubElement(ldndc_event, 'manure')
                            ldndc_event_info.set('type', manure_type)
                            omad_type = line.split()[3].upper()
                            C = omad100[omad_type]['ASTGC']
                            C = C/1000 * 10000 #Convert g C m^-2 -> kg C ha^-2
                            CN = omad100[omad_type]['ASTREC(1)']
                            ldndc_event_info.set('c', str(C))
                            ldndc_event_info.set('cn', str(CN))
                        #Harvest event
                        elif all((event == 'HARV', do_harvest == True)):
                            harv_type = line.split()[3].upper()
                            #Cut event; HARV H in DayCent
                            if ldndc_crop == 'PERG':
                                harvest = float(harv100[harv_type]['RMVSTR'])
                                remains = str(round(1 - harvest, 3))
                                ldndc_event = ET.SubElement(top, 'event')
                                ldndc_event.set('type', 'cut')
                                ldndc_event.set('time', str(date)[:-9])
                                ldndc_event_info = ET.SubElement(ldndc_event, 'cut')
                                ldndc_event_info.set('type', ldndc_crop)
                                ldndc_event_info.set('name', ldndc_crop)
                                ldndc_event_info.set('remains_relative', remains)
                            #Harvest event for crops
                            else:
                                residue = float(harv100[harv_type]['RMVSTR'])
                                remains = str(1 - residue)
                                ldndc_event = ET.SubElement(top, 'event')
                                ldndc_event.set('type', 'harvest')
                                ldndc_event.set('time', str(date)[:-9])
                                ldndc_event_info = ET.SubElement(ldndc_event, 'harvest')
                                ldndc_event_info.set('type', ldndc_crop)
                                ldndc_event_info.set('name', ldndc_crop)
                                ldndc_event_info.set('remains', remains)
                                do_harvest = False
                        #Irrigation event
                        elif event == 'IRIG':
                            #Ignore irrigation to field capacity
                            if line.split()[3].upper()[-2] == 'L':
                                continue
                            else:
                                i_amount = float(line.split()[3].split(',')[-1][:-1])
                                i_amount = i_amount * 10 #Convert from cm to mm    
                                ldndc_event = ET.SubElement(top, 'event')
                                ldndc_event.set('type', 'irrigate')
                                ldndc_event.set('time', str(date)[:-9])
                                ldndc_event_info = ET.SubElement(ldndc_event, 'irrigate')
                                ldndc_event_info.set('amount', str(i_amount))
                        #Irrigation event
                        elif event == 'IRRI':
                            irri_type = line.split()[3].upper()
                            if irri100[irri_type]['AUIRRI'] == 2.0:
                                i_amount = irri100['IRRAUT'] * 10
                            elif irri100[irri_type]['AUIRRI'] == 0.0:
                                i_amount = irri100[irri_type]['IRRAMT'] * 10
                            else:
                                i_amount = -99.99
                            ldndc_event = ET.SubElement(top, 'event')
                            ldndc_event.set('type', 'irrigate')
                            ldndc_event.set('time', str(date)[:-9])
                            ldndc_event_info = ET.SubElement(ldndc_event, 'irrigate')
                            ldndc_event_info.set('amount', str(i_amount))
                        #Cultivation event; is always till
                        elif event == 'CULT':
                            cult_type = line.split()[3].upper()
                            if cult_type == 'HERB':
                                continue
                            elif cult_type == 'SHRD':
                                #90% of crop remains on field, but is tilled into the soil
                                #Harvest with 90% remains
                                ldndc_event = ET.SubElement(top, 'event')
                                ldndc_event.set('type', 'harvest')
                                ldndc_event.set('time', str(date)[:-9])
                                ldndc_event_info = ET.SubElement(ldndc_event, 'harvest')
                                ldndc_event_info.set('type', ldndc_crop)
                                ldndc_event_info.set('name', ldndc_crop)
                                ldndc_event_info.set('remains', 0.9)
                                #Tilling
                                ldndc_event = ET.SubElement(top, 'event')
                                ldndc_event.set('type', 'till')
                                ldndc_event.set('time', str(date)[:-9])
                                ldndc_event_info = ET.SubElement(ldndc_event, 'till')
                                ldndc_event_info.set('depth', str(till_depth))
                            elif do_till:
                                ldndc_event = ET.SubElement(top, 'event')
                                ldndc_event.set('type', 'till')
                                ldndc_event.set('time', str(date)[:-9])
                                ldndc_event_info = ET.SubElement(ldndc_event, 'till')
                                ldndc_event_info.set('depth', str(till_depth))
                        elif event == 'GRAZ':
                            graz_type = line.split()[3].upper()
                            try:
                                graz100 = kwargs['graz100']
                                graz_type = line.split()[3].upper()
                                remains_relative = round(math.exp(math.log(1.0 - graz100[graz_type]['FLGREM'] - graz100[graz_type]['FDGREM'])/30), 4)
                                excretacarbon = graz100[graz_type]['GFCRET']
                                excretanitrogen = graz100[graz_type]['GRET(1)']
                                urinefraction = 1 - graz100[graz_type]['FECF(1)']
                            except KeyError:
                                print(f'No graz.100 file supplied or grazing type not known -> Skip grazing event at {str(date)[:-9]}')
                                continue
                            graz_start = pd.to_datetime(f'{str(date)[:-9]}')
                            graz_end = graz_start + pd.Timedelta(days=30)
                            ldndc_event = ET.SubElement(top, 'event')
                            ldndc_event.set('type', 'graze')
                            ldndc_event.set('time', f'{str(graz_start)[:-9]} -> {str(graz_end)[:-9]}')
                            ldndc_event_info = ET.SubElement(ldndc_event, 'graze')
                            ldndc_event_info.set('remains_relative', str(remains_relative))
                            ldndc_event_info.set('excretacarbon', str(excretacarbon))
                            ldndc_event_info.set('excretanitrogen', str(excretanitrogen))
                            ldndc_event_info.set('urinefraction', str(urinefraction))
                        else:
                            continue
                count_year += int(line.split()[0])
        tree = ET.ElementTree(top)
        ET.indent(tree)
        tree.write(mana_file_name, xml_declaration=True)
    events_in.close()
    events_out.close()

    print(f'Created file {mana_file_name}')


###Functions below are only used in JRC framework

#Function to create setup file
def create_setup(row, col, setup_file_name): #, site100):
    top = ET.Element('ldndcsetup')
    setup = ET.SubElement(top, 'setup')
    setup.set('id', '0')
    setup.set('name', f'{row}_{col}')
    #Models
    models = ET.SubElement(setup, 'models')
    model = ET.SubElement(models, 'model')
    model.set('id', '_MoBiLE')
    #Mobile
    mobile = ET.SubElement(setup, 'mobile')
    modulelist = ET.SubElement(mobile, 'modulelist')
    #Modulelist
    ids = ['microclimate:canopyecm', 'watercycle:watercycledndc', 'airchemistry:airchemistrydndc', 'physiology:plamox', 'soilchemistry:metrx']
    timemodes = ['subdaily', 'subdaily', 'subdaily', 'subdaily', 'subdaily']

    for id, timemode in zip(ids, timemodes):
        module = ET.SubElement(modulelist, 'module')
        module.set('id', id)
        module.set('timemode', timemode)

    output = ET.SubElement(modulelist, 'module')
    output.set('id', 'output:soilchemistry:daily')
    #To file
    tree = ET.ElementTree(top)
    ET.indent(tree)
    tree.write(setup_file_name, xml_declaration=True)

    print(f'Created file {setup_file_name}')

#Function to create *.ldndc file
def create_ldndc(row, col, ldndc_file_name, start_year, end_year):
    #Get time for schedule
    simulation_time = end_year - start_year
    time = f'{start_year}-01-01/24 -> +{simulation_time}-0-0'
    #LDNDC project
    ldndcproject = ET.Element('ldndcproject')
    ldndcproject.set('PackageMinimumVersionRequired', '1.3')
    ldndcproject.set('XPackageVersionRequired', '1.2')
    #Schedule
    schedule = ET.SubElement(ldndcproject, 'schedule')
    schedule.set('time', time)
    #Input
    input = ET.SubElement(ldndcproject, 'input')
    #Sources
    sources = ET.SubElement(input, 'sources')
    sources.set('sourceprefix', f'{row}_{col}_')

    for ins, f_name in zip(['setup', 'site', 'airchemistry', 'climate', 'event'], ['setup.xml', 'site.xml', 'airchem.txt', 'climate.txt', 'mana.xml']):
        source = ET.SubElement(sources, ins)
        source.set('source', f'{f_name}')

    #Attributes
    attributes = ET.SubElement(input, 'attributes')
    attributes.set('use', '0')
    attributes.set('endless', '0')
    airchemistry = ET.SubElement(attributes, 'airchemistry')
    airchemistry.set('endless', 'yes')
    climate = ET.SubElement(attributes, 'climate')
    climate.set('endless', 'yes')
    #Output
    output = ET.SubElement(ldndcproject, 'output')
    sinks = ET.SubElement(output, 'sinks')
    sinks.set('sinkprefix', f'./{row}_{col}_output/{row}_{col}_')
    #To file
    tree = ET.ElementTree(ldndcproject)
    ET.indent(tree)
    tree.write(f'{ldndc_file_name}', xml_declaration=True)

    print(f'Created file {ldndc_file_name}')


###Function to create *airchemistry.txt file. Needs to have N deposition (dry) as external input
###Deposition of N is assumed to be mg N m^-2 a^-1 (unit in EMEP dataset)
def create_airchem(airchemistry_file_name, start_year, end_year, N_deposition):
    #Defaults
    CO2 = 405

    #Convert deposition to g N m^-2
    total_deposition = N_deposition*0.001
    #Create time vector
    datetime = pd.date_range(start=pd.to_datetime(f'{start_year}-01-01', format='%Y-%m-%d'), end=pd.to_datetime(f'{end_year}-12-31', format='%Y-%m-%d'), freq='d')
    #Create CO2, NH4 and NO3 deposition
    co2 = np.tile(CO2, len(datetime))
    nh4_deposition, no3_deposition = np.tile(total_deposition/2/365, len(datetime)), np.tile(total_deposition/2/365, len(datetime))
    df_out = pd.DataFrame({'*':datetime, 'co2':co2, 'nh4dry':nh4_deposition, 'no3dry':no3_deposition})
    #Write to file
    with open(airchemistry_file_name, 'w') as f:
        f.write('%global\n')
        f.write(f'\ttime = "{datetime[0]}"\n')
        f.write('\n')
        f.write('%airchemistry\n')
        f.write('\tid = 0\n')
        f.write('\n')
        f.write('%data\n')
        df_out.to_csv(f, index=False, header=True, sep='\t')
    
    print(f'Created file {airchemistry_file_name}')

##Conversion of DayCent *.wth to LDNDC *climate.txt
##Number of defined columns have to be specified in the function call (for JRC its 9)
##*args takes the site100 file, which may contain information about the lat, long, elevation
def convert_wth_climate_jrc(wth_file_name, microclimate_file_name, start_year, *args, columns=9):
    #Read DayCent *.wth file
    wth_file = pd.read_csv(wth_file_name, sep='\t', header=None)
    wth_file = wth_file.iloc[:,:columns]
    wth_file.columns = ['day', 'month', 'year', 'doy', 'tmax', 'tmin', 'prec', 'tavg', 'rad'][:columns]
    wth_file['datetime'] = pd.to_datetime([f'{year}-{month}-{day}' for day, month, year in zip(wth_file['day'], wth_file['month'], wth_file['year'])], format='%Y-%m-%d')
    wth_file = wth_file[wth_file['datetime'] > pd.to_datetime(f'{start_year}-01-01', format='%Y-%m-%d')]
    #wth_file = wth_file.dropna(axis='rows', subset=['day'])
    wth_file = wth_file.astype({'day':int, 'month':int, 'year':int})
    wth_file['prec'] = wth_file['prec']/10 #Convert from cm to mm
    wth_file['day'] = [str(d).zfill(2) for d in wth_file['day']]
    wth_file['month'] = [str(d).zfill(2) for d in wth_file['month']]
    #start_time =  f"{wth_file['year'][0]}-{wth_file['month'][0]}-{wth_file['day'][0]}"
    wth_file = wth_file.drop(['day', 'month', 'year', 'doy'], axis='columns')
    wth_file = wth_file.round(2)
    #Only write observations starting in start year

    #Get lat and long from site.100 file
    if len(args) > 0:
        site100 = read_dot100(args[0])
        site100['SITE'].setdefault('SITLAT', -99.99)
        site100['SITE'].setdefault('SITLNG', -99.99)
        site100['SITE'].setdefault('ELEV', -99.99)
        lat = site100['SITE']['SITLAT']
        long = site100['SITE']['SITLNG']
        elev = site100['SITE']['ELEV']
    
    wth_file = wth_file.reset_index(drop=True)

    with open(microclimate_file_name, 'w') as f:
        f.write('%global\n')
        f.write(f'        time = "{start_year}-01-01/1"\n')
        f.write('\n')
        f.write('%climate\n')
        f.write('        id = 0\n')
        f.write('\n')
        if len(args) > 0:
            f.write('%attributes\n')
            f.write(f'        elevation = "{elev}"\n')
            f.write(f'        latitude = "{lat}"\n')
            f.write(f'        longitude = "{long}"\n')
            f.write('\n')         
        f.write('%data\n')
        wth_file.to_csv(f, index=False, header=True, sep='\t')

    print(f'Created file {microclimate_file_name}')