import subprocess
import pandas as pd
import sys
import os
import numpy as np
import argparse
sys.path.append('utils/')
import settings

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('cost_model', type=str)
    parser.add_argument("precision_threshold", type=float, default=0.7)
    parser.add_argument('my_seed', type=int, default=0)
    args = parser.parse_args()
    settings.init(args.my_seed)
    np.random.seed(settings.seed)

    BASE_FOLDER = f'data/{args.cost_model}_results_seed_{args.my_seed}'
    if not os.path.exists(BASE_FOLDER):
        os.makedirs(BASE_FOLDER)

    blocks = pd.read_csv('data/dataset/explanation_test_set.csv')

    for i in range(blocks.shape[0]):
        code = blocks.iloc[i]['asm']
        insts = code.splitlines()
        if '.text' in insts[0]:  # remove the .text directive from the code
            insts = insts[1:]

        # remove comments from the code
        for ins in range(len(insts)):
            hash_pos = insts[ins].find('#')
            if hash_pos == -1:  # not here!
                continue
            insts[ins] = insts[ins][:hash_pos]

        insts = [x for x in insts if x != '']

        code = '; '.join(insts)
        code = code.replace('\t', ' ')

        try:
            print("Trying block", i)
            print("code:", code)
            my_output = subprocess.check_output(['python3', 'bb_explain.py', '.intel_syntax noprefix; '+code+'\n', 'opcode_dependency_num_insts', args.cost_model, str(args.precision_threshold), str(args.my_seed)], universal_newlines=True)
            with open(f'{BASE_FOLDER}/{i}.txt', 'w') as f:
                f.write(my_output)
            print(f'explained block {i} for {args.cost_model}')
        except Exception as err:
            print("exception for block", i)
            print(err)
            continue


if __name__ == '__main__':
    main()
