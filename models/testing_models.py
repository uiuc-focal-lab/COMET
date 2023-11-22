import os
import pandas as pd
import xed
import subprocess
import time
import multiprocessing as mp
import tempfile
import sys
sys.path.append('models/Ithemal_gpu/')
sys.path.append('models/')
sys.path.append('utils')
from microArchConfigs import MicroArchConfigs
from ithemal_remake import *
from uiCA import *
import instrData.HSW_data as archData
from basic_block_for_dep import *


# ithemal_pred_proc = subprocess.Popen()
df_hsw_tp_table = pd.read_csv(os.path.join(os.getenv('COMET_HOME'), 'utils/hsw_tp_table.csv'))
hsw_tp_table_dict = df_hsw_tp_table.set_index('Instruction').T.to_dict('list')

def testing_ithemal_gpu_original(inputs, center=-1, n = 0): # when center is -1, return actual runtime
    if isinstance(inputs, str):
        inputs = [inputs]
    inputs = [('.intel_syntax noprefix; ' + i.strip()) for i in inputs]

    output = Ithemal_gpu_model_original(inputs)

    # print(output)
    if center == -1:
        return output
    # print(center)
    class_pred = [int((round(out/50, 0) > (center/50 - 1)) and (round(out/50, 0) < (center/50 + 1))) for out in output]  #[int((out < center+50.0) and (out > center-50.0)) for out in output]  #  # the current one had <= earlier
    # print("center", center)
    # print(class_pred)
    # print("input: ", inputs[0], "prediction:", class_pred[0])
    # for i in range(len(inputs)):
    #     print("asm:", inputs[i], "labels:", output[i], 'center:', center)
    # print("time for ithemal:", time.time()-t1)
    return class_pred


def testing_uica(inputs, center = -1, n = 0, output_type = 'tp'):
    if isinstance(inputs, str):
        inputs = [inputs]

    pool = mp.Pool(mp.cpu_count()-1)
    t2 = time.time()
    uica_result_func = uica_result
    if output_type == 'bottleneck':
        uica_result_func = uica_result_bottleneck
    results = pool.starmap_async(uica_result_func, [(center, inputs, k) for k in range(len(inputs))]).get()
    pool.close()
    pool.join()
    labels = []
    results.sort(key=lambda a: a[0])
    for res in results:
        labels.append(res[1])
    # print('total time for results:', time.time()-t2)
    # for i in range(len(inputs)):
    #     print("asm:", inputs[i], "labels:", labels[i])
    return labels


def uica_result(center, inputs, n):
    i = inputs[n].strip()
    t1 = time.time()
    _, fname = tempfile.mkstemp()  # for the binary file
    _, fname1 = tempfile.mkstemp()  # for the asm file
    with open(fname1, 'w') as f:
        f.write('.intel_syntax noprefix; ' + i + '\n')
    # my_code = '.intel_syntax noprefix; ' + i + '\n'
    # p = subprocess.Popen(['as', '-o', fname], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(['as', fname1, '-o', fname])

    output = uiCA_pred(fname, arch='HSW', TPonly=True)

    output = float(output.strip())
    class_pred = int((round(2*output, 0) > (2*center - 1)) and (round(2*output, 0) < (2*center + 1)))  # int((output <= center + 1.0) and (output >= center - 1.0))
    if center == -1:
        class_pred = output
    # print('uica inference time 1 sample:', time.time()-t1)
    return n, class_pred


def uica_result_bottleneck(center, inputs, n):
    i = inputs[n].strip()
    _, fname = tempfile.mkstemp()  # for the binary file
    _, fname1 = tempfile.mkstemp()  # for the asm file
    with open(fname1, 'w') as f:
        f.write('.intel_syntax noprefix; ' + i + '\n')
    subprocess.run(['as', fname1, '-o', fname])
    my_output = ''
    # find the word Bottleneck in it and get its value here
    bottleneck_start = my_output.find('Bottleneck')
    bottleneck_start = my_output.find(': ', bottleneck_start) + 2
    bottleneck_end = my_output.find('\n', bottleneck_start)
    output = my_output[bottleneck_start:bottleneck_end].strip().split(', ')
    return n, output



def simple_analytical_model(inputs, center=-1, n = 0, return_explanations=False):
    if isinstance(inputs, str):
        inputs = [inputs]
    inputs = [('.intel_syntax noprefix; ' + i.strip() + '\n') for i in inputs]
    pool = mp.Pool(mp.cpu_count()-1)
    results = pool.starmap_async(simple_analytical_model_helper, [(center, inputs, k, return_explanations) for k in range(len(inputs))]).get()
    pool.close()
    pool.join()
    output = []
    results.sort(key=lambda a: a[1])
    for res in results:
        output.append(res[0])
    return output


def simple_analytical_model_helper(center, inputs, n, return_explanations):
    code = inputs[n]
    # if n%1000 == 0:
    #     print(n)
    _, asm_file = tempfile.mkstemp()
    _, bin_file = tempfile.mkstemp()
    with open(asm_file, 'w') as f:
        f.write(code)

    subprocess.run(['as', asm_file, '-o', bin_file])
    disas = xed.disasFile(bin_file, chip=MicroArchConfigs['HSW'].XEDName)

    # get number of instructions
    num_inst = len(disas)

    # get the tp for each instruction by matching each opcode against the tp table
    inst_canonical_forms = []
    inst_tps = []
    for my_inst_disas in disas:
        for instrData in archData.instrData.get(my_inst_disas['iform'], []):
             if xed.matchXMLAttributes(my_inst_disas, archData.attrData[instrData['attr']]):
                inst_canonical_forms.append(instrData['string'])
                break
        if len(inst_canonical_forms) > 0 and inst_canonical_forms[-1] in hsw_tp_table_dict.keys():
            my_tp = float(hsw_tp_table_dict[inst_canonical_forms[-1]][0])
        else:
            my_tp = 0
        inst_tps.append(my_tp)

    # get the data-dependencies in the bb, only for RAW dependencies consider the sum of the tps of the 2 instructions
    bb_dep = BasicBlockDependencies(code, only_raw=True)
    present_dependencies = bb_dep.get_operands_dependencies().keys()
    dep_tps = []
    dep_names = []
    for (start, end, _) in present_dependencies:
        dep_tps.append(inst_tps[start] + inst_tps[end])
        dep_names.append(f'{start}_{end}_RAW')

    all_candidates = [num_inst/4]
    all_candidates_names = ['num_insts']
    all_candidates.extend(inst_tps)
    all_candidates_names.extend([f'inst_{ins}' for ins in range(len(inst_tps))])
    all_candidates.extend(dep_tps)
    all_candidates_names.extend(dep_names)
    output = max(all_candidates)
    if return_explanations:
        explanation = [all_candidates_names[i] for i, j in enumerate(all_candidates) if j == output]
        return (output, explanation), n
    if center == -1:
        return output, n
    class_pred = int((round(4*output, 0) > (4*center - 1)) and (round(4*output, 0) < (4*center + 1)))
    return class_pred, n
