import argparse
import subprocess
import glob
import numpy as np

ldndc_executable = '/eos/jeodpp/data/projects/SOIL-NACA/MODEL4/LDNDC/ldndc'
ldndc_conf = '/eos/jeodpp/data/projects/SOIL-NACA/MODEL4/ldndc_test.conf'

parser = argparse.ArgumentParser()
parser.add_argument('-index', '--index', help='No index found', dest='index', required=True, type=int)
parser.add_argument('-cores', '--cores', help='No cores found', dest='cores', required=True, type=int)
cores = parser.parse_args().cores
index = parser.parse_args().index if cores > 1 else 0

ldndc_files = glob.glob('/eos/jeodpp/data/projects/SOIL-NACA/MODEL4/test_ldndc/*.ldndc')
ldndc_files = np.array_split(ldndc_files, cores)[index]

for sim in ldndc_files:
    subprocess.run(f'{ldndc_executable} {ldndc_conf} {sim}'.split())

f.close()