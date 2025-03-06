import argparse
import glob
import numpy as np


parser = argparse.ArgumentParser()
parser.add_argument('-index', '--index', help='No index found', dest='index', required=True, type=int)
parser.add_argument('-cores', '--cores', help='No cores found', dest='cores', required=True, type=int)
index = parser.parse_args().index
cores = parser.parse_args().cores

ldndc_files = glob.glob('/eos/jeodpp/data/projects/SOIL-NACA/MODEL4/test_ldndc/*.ldndc')
ldndc_files = np.array_split(ldndc_files, cores)[index]

with open(f'/eos/jeodpp/data/projects/SOIL-NACA/MODEL4/test_{index}.txt', 'w') as f:
    for line in ldndc_files:
        f.write(line + '\n')
        f.write('test')

f.close()