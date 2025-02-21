import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import re
import os


##Reads a *.100 (or similarly structured) file into a nested dictionary
##Other conversion functions require this structure
##Is called by *.wth conversion
def read_dot100(in_file_name):
    in_file = open(in_file_name, 'r')
    lines = in_file.readlines()
    lines = [l.replace('#', '') for l in lines]
    lines = [l.replace('*** ', '') for l in lines]
    lines = [re.sub(' +', ' ', l) for l in lines]
    lines = [l.replace('*', '') for l in lines]
    lines = [l.replace("'", "") for l in lines]
    in_dict = {}
    
    for line in lines:
        if line.split()[0][0].isalpha():
            key = line.split()[0]
            in_dict[key] = {}
        else:
            in_dict[key][line.split()[1]] = float(line.split()[0])

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
def convert_wth_climate(wth_file_name, microclimate_file_name, *args, columns=7):
    #Read DayCent *.wth file
    wth_file = pd.read_csv(wth_file_name, sep='\t', header=None)
    wth_file = wth_file.iloc[:,:columns]
    wth_file.columns = ['day', 'month', 'year', 'doy', 'tmax', 'tmin', 'prec', 'rad', 'rel_humidity', 'wind'][:columns]
    wth_file = wth_file.drop(['rel_humidity'], axis='columns', errors='ignore')
    wth_file['rad'] = wth_file['rad'] * 0.485 #Convert from Langley/d to W*m^-2
    wth_file['wind'] = round(wth_file['wind'] * 1.609344, 4) #Convert from miles/hour to km/hour
    #wth_file.columns = ['day', 'month', 'year', 'doy', 'tmax', 'tmin', 'prec', 'tavg', 'rad'][:columns]
    #wth_file = wth_file.dropna(axis='rows', subset=['day'])
    wth_file = wth_file.astype({'day':int, 'month':int, 'year':int})
    wth_file['prec'] = wth_file['prec']/10 #Convert from cm to mm
    wth_file['day'] = [str(d).zfill(2) for d in wth_file['day']]
    wth_file['month'] = [str(d).zfill(2) for d in wth_file['month']]
    start_time =  f"{wth_file['year'][0]}-{wth_file['month'][0]}-{wth_file['day'][0]}"
    wth_file = wth_file.drop(['day', 'month', 'year', 'doy'], axis='columns')
    wth_file = wth_file.round(2)

    #Get lat and long from site.100 file
    if len(args) > 0:
        site100 = read_dot100(args[0])
        site100['Site'].setdefault('SITLAT', -99.99)
        site100['Site'].setdefault('SITLNG', -99.99)
        site100['Site'].setdefault('ELEV', -99.99)
        lat = site100['Site']['SITLAT']
        long = site100['Site']['SITLNG']
        elev = site100['Site']['ELEV']
    
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


#Function to convert DayCent *.sch/*.evt file to LDNDC *.mana file
#kwargs are start_year and end_year; writes events in mana file only in range(start_year, end_year + 1)
def convert_evt_mana(sch_file_name, mana_file_name, omad100, harv100, irri100, lookup, start_year, end_year):
    #Defaults
    fert_type = 'nh4' #Type of fertilizer in FERT event
    manure_type = 'slurry' #Type of manure to be applied
    till_depth = 0.2 #Tillage depth
    ldndc_initbiom = 100 #Initial biomass (not crop specific)
    ni_amount = 4.0 #NI amount for nitrification inhibitors
    do_harvest = False #Changes to True, once a crop is planted, prevents harvest when there is no crop

    with open(sch_file_name, 'r') as events_in, open(mana_file_name, 'wb') as events_out:
        in_lines = events_in.readlines()
        #Clean and homogenize lines; Make list of blocks
        in_block_lines = []
        block_last_years = []
        block_start_years = []
        start = 0
        for i, line in enumerate(in_lines):
            line = re.sub(' +', ' ').lstrip(' ')
            if any([len(line) < 1, line.split()[0].isalpha(), line.split()[1].isalpha(),
                    len(line.split()) < 3, line.startswith('#')]):
                continue
            elif 'Option' in line:
                in_lines = in_lines[i:]
            elif 'Output starting year' in line:
                block_start_years.append(int(line.split()[0]))
            elif 'Last year' in line:
                block_last_years.append(int(line.split()[0]))
            elif '-999 -999 X' in line:
                in_block_lines.append(in_lines[start:i])
                start = i + 1

        top = ET.Element('event')
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
                                f_amount = float(line.split()[3].split('N')[0][1:])*10000*0.001 #Conversion from g * m^-2 to kg * ha^-1
                            except:
                                f_amount = -99.99
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
                            crop = line.split()[3]
                            try:
                                ldndc_crop = lookup[lookup['dc_crop'] == crop]['ldndc_crop'].iloc[0]
                            except:
                                print('CROP NOT IN LOOKUP \n') #Throw error and print crop, when it does not exist in lookup
                                print(line)
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
                            ldndc_event_subinfo = ET.SubElement(ldndc_event_info, 'crop')
                            ldndc_event_subinfo.set('initialbiomass', str(ldndc_initbiom))
                            do_harvest = True
                        #Organic matter input (manure)
                        elif event == 'OMAD':
                            ldndc_event = ET.SubElement(top, 'event')
                            ldndc_event.set('type', 'manure')
                            ldndc_event.set('time', str(date)[:-9])
                            ldndc_event_info = ET.SubElement(ldndc_event, 'manure')
                            ldndc_event_info.set('type', manure_type)
                            type = line.split()[3]
                            c = omad100[type]['ASTGC']
                            c = c/1000 * 10000 #Convert g C m^2 -> kg C ha^2
                            cn = omad100[type]['ASTREC(1)']
                            ldndc_event_info.set('c', str(c))
                            ldndc_event_info.set('cn', str(cn))
                        #Harvest event
                        elif event == 'HARV':
                            if do_harvest: 
                                type = line.split()[3]
                                residue = float(harv100[type]['RMVSTR'])
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
                            if line.split()[3][-2] == 'L':
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
                                irri_type = line.split()[3]

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
                            if line.split()[3] == 'HERB':
                                continue
                            else:
                                ldndc_event = ET.SubElement(top, 'event')
                                ldndc_event.set('type', 'till')
                                ldndc_event.set('time', str(date)[:-9])
                                ldndc_event_info = ET.SubElement(ldndc_event, 'till')
                                ldndc_event_info.set('depth', str(till_depth))
                        else:
                            continue
                count_year += int(line.split()[0])
        tree = ET.ElementTree(top)
        ET.indent(tree)
        tree.write(mana_file_name, xml_declaration=True)
    events_in.close()
    events_out.close()

    print(f'Created file {mana_file_name}')


##Functions below are only used in JRC framework
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


###Function to copy generic airchemistry file (taken from Gebesee site) to local site
###Needs to be changed to the actual airchemistry once it is available
def create_airchem(site_100_file_name, airchemistry_file_name, wth_file_name):
    #Defaults
    CO2 = 405

    #Get combined deposition from *site.100
    try:
        site_100_file = read_dot100(site_100_file_name)
        total_deposition = site_100_file['External']['EPNFA(2)']/1000 #Convert from mg/m2 to g/m2
    except:
        total_deposition = -99.99

    #Read *.wth file and create datetime 
    wth_file = pd.read_csv(wth_file_name, sep='\t', header=None)
    wth_file = wth_file.iloc[:,:3] 
    wth_file.columns = ['day', 'month', 'year', 'doy', 'tmax', 'tmin', 'prec', 'tavg', 'rad'][:3]
    wth_file = wth_file.dropna(axis='rows', subset=['day'])
    wth_file = wth_file.astype({'day':int, 'month':int, 'year':int})
    wth_file['day'] = [str(d).zfill(2) for d in wth_file['day']]
    wth_file['month'] = [str(d).zfill(2) for d in wth_file['month']]
    datetime = [f"{wth_file.iloc[i]['year']}-{wth_file.iloc[i]['month']}-{wth_file.iloc[i]['day']}" for i in range(len(wth_file))]
    #Create CO2 NH4 and NO3 deposition
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
def convert_wth_climate_jrc(wth_file_name, microclimate_file_name, *args, columns=9):
    #Read DayCent *.wth file
    wth_file = pd.read_csv(wth_file_name, sep='\t', header=None)
    wth_file = wth_file.iloc[:,:columns]
    wth_file.columns = ['day', 'month', 'year', 'doy', 'tmax', 'tmin', 'prec', 'tavg', 'rad'][:columns]
    #wth_file = wth_file.dropna(axis='rows', subset=['day'])
    wth_file = wth_file.astype({'day':int, 'month':int, 'year':int})
    wth_file['prec'] = wth_file['prec']/10 #Convert from cm to mm
    wth_file['day'] = [str(d).zfill(2) for d in wth_file['day']]
    wth_file['month'] = [str(d).zfill(2) for d in wth_file['month']]
    start_time =  f"{wth_file['year'][0]}-{wth_file['month'][0]}-{wth_file['day'][0]}"
    wth_file = wth_file.drop(['day', 'month', 'year', 'doy'], axis='columns')
    wth_file = wth_file.round(2)

    #Get lat and long from site.100 file
    if len(args) > 0:
        site100 = read_dot100(args[0])
        site100['Site'].setdefault('SITLAT', -99.99)
        site100['Site'].setdefault('SITLNG', -99.99)
        site100['Site'].setdefault('ELEV', -99.99)
        lat = site100['Site']['SITLAT']
        long = site100['Site']['SITLNG']
        elev = site100['Site']['ELEV']
    
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