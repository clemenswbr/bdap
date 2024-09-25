import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import re
import os
from copy import deepcopy

##Reads a *.100 or similarly structured file into a dictionary structure
def read_dot100(in_file_name):

    in_file = open(in_file_name, 'r')
    in_dict = {}

    lines = in_file.readlines()
    lines = [l.replace('#', '') for l in lines]
    lines = [l.replace('*** ', '') for l in lines]
    lines = [re.sub(' +', ' ', l) for l in lines]
    lines = [l.replace('*', '') for l in lines]
    lines = [l.replace("'", "") for l in lines]
    

    for line in lines:

        if line.split()[0][0].isalpha():

            key = line.split()[0]
            in_dict[key] = {}

        else:
            in_dict[key][line.split()[1]] = float(line.split()[0])

    return in_dict


##Conversion for DayCent soil file (soils.in) to LandscapeDNDC site file (*site.xml)
def convert_dcsoil_ldndcsoil(dcsoil_file_name, ldndcsoil_file_name):

    dc_soil = pd.read_csv(dcsoil_file_name, sep='\t', header=None)

    col_names = ['upper_depth', 'lower_depth', 'bd', 'wcmax', 'wcmin', 'evaporation', 'root_fraction', 'sand', 'clay', 'organic_matter', 'deltamin', 'sks', 'ph']
    dc_soil.columns = col_names

    dc_soil.insert(0, 'depth', value=(dc_soil['lower_depth'] - dc_soil['upper_depth'])*10)
    dc_soil = dc_soil.drop(['upper_depth', 'lower_depth', 'evaporation', 'root_fraction', 'organic_matter', 'deltamin'], axis='columns')

    #Unit conversions
    #Convert wcmax, wcmin cm^3/cm^3 -> dm^3/m^3
    dc_soil['wcmax'] = dc_soil['wcmax']*1000
    dc_soil['wcmin'] = dc_soil['wcmin']*1000 

    #Convert sks cm/sec -> cm/min
    dc_soil['sks'] = dc_soil['sks']*60

    ###
    #Add norg and corg from LUCAS data
    corg = 0.024
    dc_soil['corg'] = corg
    ###

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
def convert_wth_climate(wth_file_name, microclimate_file_name, *args):

    wth_file = pd.read_csv(wth_file_name, sep='\t', header=None)
    wth_file = wth_file.iloc[:,:7] #Only the first 7 columns are predefined
    wth_file.columns = ['day', 'month', 'year', 'doy', 'tmax', 'tmin', 'prec']

    start_time =  f"{wth_file[:1]['year'][0]}-{wth_file[:1]['month'][0]}-{wth_file['day'][0]}"

    wth_file['prec'] = wth_file['prec']/10 #Convert from cm to mm
    wth_file['day'] = [str(d).zfill(2) for d in wth_file['day']]
    wth_file['month'] = [str(d).zfill(2) for d in wth_file['month']]
    wth_file = wth_file[['tmax', 'tmin', 'prec']]

    #Get lat and long from site.100 file
    if len(args) > 0:
        site100 = read_dot100(args[0])

        site100['Site'].setdefault('SITLAT', -99.99)
        site100['Site'].setdefault('SITLNG', -99.99)
        site100['Site'].setdefault('ELEV', -99.99)

        lat = site100['Site']['SITLAT']
        long = site100['Site']['SITLNG']
        elev = site100['Site']['ELEV']

        ###Add elevation from E-obs
    
    ###
    #Average temperature and radiation need to be added from the raw data (Copernicus E-obs)
    ###

    tavg = pd.concat([wth_file['tmax'], wth_file['tmin']], axis=1).agg(np.mean, 1) ###
    wth_file = pd.concat([tavg, wth_file], axis='columns')
    wth_file.columns = ['tavg', 'tmax', 'tmin', 'prec']
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

        f.write(wth_file.to_string(index=False))
    
    print(f'Created file {microclimate_file_name}')

#Function to convert DayCent *.sch/*.evt file to LDNDC *.mana file
def convert_sch_mana(sch_file_name, mana_file_name, omad100_file_name, harv100_file_name, irrig100_file_name, lookup_file_name):

    #Read files
    lookup = pd.read_csv(lookup_file_name, sep='\t')
    omad100 = read_dot100(omad100_file_name) 
    harv100 = read_dot100(harv100_file_name)
    irri100 = read_dot100(irrig100_file_name)

    with open(sch_file_name, 'r') as events_in, open(mana_file_name, 'wb') as events_out:

        in_lines = events_in.readlines()
        in_lines = [re.sub(' +', ' ', l) for l in in_lines]
        in_lines = [l.lstrip(' ') for l in in_lines]

        in_block_lines = []
        block_last_years = []
        block_start_years = []
        start = 0

        for line in in_lines:

            if line.startswith('#'):
                in_lines.remove(line)

            if len(line) == 0:
                in_lines.remove(line)

        for i, line in enumerate(in_lines):

            if 'Option' in line:
                in_lines = in_lines[i:]

        for i, line in enumerate(in_lines):
            if 'Output starting year' in line:
                block_start_years.append(int(line.split()[0]))

            if 'Last year' in line:
                block_last_years.append(int(line.split()[0]))

            elif '-999 -999 X' in line:
                in_block_lines.append(in_lines[start:i])
                start = i + 1

        top = ET.Element('event')

        for i, block in enumerate(in_block_lines):

            block_last_year = block_last_years[i]
            count_year = block_start_years[i]

            while count_year < block_last_year:

                for line in block:

                    if len(line.split()) <= 1:
                        continue

                    elif '.wth' in line:
                        continue
                    
                    elif line.split()[1].isalpha():
                        continue

                    else:
                        event = line.split()[2]

                        try:
                            block_year = int(line.split()[0])
                        except:
                            continue

                        doy = int(line.split()[1])
                        evt_year = count_year + block_year - 1

                        date = pd.to_datetime(pd.to_datetime(f'{evt_year}-01-01') + pd.Timedelta(days=doy-1))

                        if event == 'FERT':
                            try:
                                f_amount = float(line.split()[3].split('N')[0][1:])*10000*0.001
                            
                            except:
                                f_amount = -99.99

                            f_type = 'nh4no3'

                            ### For inhibitors
                            if 'I' in line.split()[3] or 'SU' in line.split()[3]:
                                f_type = 'ni'
                            ###

                            ldndc_event = ET.SubElement(top, 'event')
                            ldndc_event.set('type', 'fertilize')
                            ldndc_event.set('time', str(date)[:-9])

                            ldndc_event_info = ET.SubElement(ldndc_event, 'fertilize')
                            ldndc_event_info.set('amount', str(f_amount))
                            ldndc_event_info.set('type', f_type)

                        elif event == 'CROP':
                            crop = line.split()[3]
                            ldndc_crop = lookup[lookup['dc_crop'] == crop]['ldndc_crop'].iloc[0]
                            ldndc_initbiom = '10' ###where to get initialbiomass from

                        elif event == 'PLTM':
                            ldndc_event = ET.SubElement(top, 'event')
                            ldndc_event.set('type', 'plant')
                            ldndc_event.set('time', str(date)[:-9])

                            ldndc_event_info = ET.SubElement(ldndc_event, 'plant')
                            ldndc_event_info.set('type', ldndc_crop)
                            ldndc_event_info.set('name', ldndc_crop)
                            
                            ldndc_event_subinfo = ET.SubElement(ldndc_event_info, 'crop')
                            ldndc_event_subinfo.set('initialbiomass', ldndc_initbiom)

                        elif event == 'OMAD':
                            ldndc_event = ET.SubElement(top, 'event')
                            ldndc_event.set('type', 'manure')
                            ldndc_event.set('time', str(date)[:-9])

                            ldndc_event_info = ET.SubElement(ldndc_event, 'manure')
                            ldndc_event_info.set('type', 'farmyard')

                            type = line.split()[3]
                            c = omad100[type]['ASTGC']
                            c = c/1000 * 10000 #Convert g C m^2 -> kg C ha^2
                            cn = omad100[type]['ASTREC(1)']
                            
                            ldndc_event_info.set('c', str(c))
                            ldndc_event_info.set('cn', str(cn))

                        elif event == 'HARV':
                            #Get remains
                            type = line.split()[3]
                            residue = float(harv100[type]['RMVSTR'])
                            fraction_residue = float(harv100[type]['REMWSD'])
                            remains = (1-residue) * fraction_residue
                                        
                            ldndc_event = ET.SubElement(top, 'event')
                            ldndc_event.set('type', 'harvest')
                            ldndc_event.set('time', str(date)[:-9])

                            ldndc_event_info = ET.SubElement(ldndc_event, 'harvest')
                            ldndc_event_info.set('type', ldndc_crop)
                            ldndc_event_info.set('name', ldndc_crop)
                            ldndc_event_info.set('remains', str(1-remains))

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

                        elif event == 'IRRI':
                                i_type = line.split()[3]
                                
                                if irri100[i_type]['AUIRRI'] == 2.0:
                                    i_amount = irri100[i_type]['IRRAUT'] * 10

                                elif irri100[i_type]['AUIRRI'] == 0.0:
                                    i_amount = irri100[i_type]['IRRAMT'] * 10

                                else:
                                    i_amount = -99.99

                                ldndc_event = ET.SubElement(top, 'event')
                                ldndc_event.set('type', 'irrigate')
                                ldndc_event.set('time', str(date)[:-9])

                                ldndc_event_info = ET.SubElement(ldndc_event, 'irrigate')
                                ldndc_event_info.set('amount', str(i_amount))

                        elif event == 'CULT':

                            if line.split()[3] == 'HERB':
                                continue

                            else:
                                cult_depth = 0.2

                                ldndc_event = ET.SubElement(top, 'event')
                                ldndc_event.set('type', 'till')
                                ldndc_event.set('time', str(date)[:-9])

                                ldndc_event_info = ET.SubElement(ldndc_event, 'till')
                                ldndc_event_info.set('depth', str(cult_depth))
                        
                        else:
                            continue
                
                count_year += int(line.split()[0])

        tree = ET.ElementTree(top)
        ET.indent(tree)
        tree.write(mana_file_name, xml_declaration=True)

    events_in.close()
    events_out.close()

    print(f'Created file {mana_file_name}')

#Function to create setup file
def create_setup(run_number, out_file_name): #, site100):

    top = ET.Element('ldndcsetup')

    setup = ET.SubElement(top, 'setup')
    setup.set('id', '0')
    setup.set('name', f'{run_number}')

    #Location
    # site100 = read_dot100(site100)

    # lat = site100['SITLAT']
    # long = site100['SITLONG']

    # location = ET.SubElement(setup, 'location')
    # location.set('latitude', lat)
    # location.set('longitude', long)

    #Models
    models = ET.SubElement(setup, 'models')
    model = ET.SubElement(models, 'model')
    model.set('id', '_MoBiLE')

    #Mobile
    mobile = ET.SubElement(setup, 'mobile')
    modulelist = ET.SubElement(mobile, 'modulelist')

    #Modulelist
    ids = ['microclimate:canopyecm', 'watercycle:watercycledndc', 'airchemistry:airchemistrydndc', 'physiology:arabledndc', 'soilchemistry:metrx']
    timemodes = ['subdaily', 'subdaily', 'subdaily', 'subdaily', 'subdaily']

    for id, timemode in zip(ids, timemodes):

        module = ET.SubElement(modulelist, 'module')
        module.set('id', id)
        module.set('timemode', timemode)

    output = ET.SubElement(modulelist, 'module')
    output.set('id', 'output:soilchemistry:yearly')

    #To file
    tree = ET.ElementTree(top)
    ET.indent(tree)
    tree.write(out_file_name, xml_declaration=True)

    print(f'Created file {out_file_name}')

#Function to create *.ldndc file
def create_ldndc(run_number, out_file_name, mana_file_name):

    #Get time for schedule
    mana_file = ET.parse(mana_file_name)
    start = mana_file.findall('event')[0].attrib['time'] 
    end = mana_file.findall('event')[-1].attrib['time']

    timespan = int(end[:4]) - int(start[:4])
    time = f'{start[:4]}-01-01/24 -> +{timespan}-0-0'
    
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
    sources.set('sourceprefix', f'{run_number}_')

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
    sinks.set('sinkprefix', f'./{run_number}_output/{run_number}_')

    #To file
    tree = ET.ElementTree(ldndcproject)
    ET.indent(tree)
    tree.write(out_file_name, xml_declaration=True)

    print(f'Created file {out_file_name}')

###Function to copy generic airchemistry file (taken from Gebesse site) to local site
###This needs to be changed to the actual airchemistry once it is available
def create_airchem(run_number):

    os.system(f'cp generic_airchem.txt ./test/{run_number}_airchem.txt')
    print(f'Created file OUT/DAYC/test/{run_number}_airchem.txt')