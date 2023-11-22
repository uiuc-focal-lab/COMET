import pandas as pd
import os
import numpy as np
np.random.seed(0)

BASE_FOLDER = 'data/Ithemal_results_seed_1'
tries = 1
df_hsw = pd.read_csv('data/dataset/hsw_w_categories_half.csv')
with open('explanation_test_set1.txt', 'r') as fp:
    block_ids = fp.read().strip().split('\n')
block_ids = np.random.choice(np.array([int(d.split('.txt')[0]) for d in block_ids]), 300)
block_ids = sorted(block_ids)

# get the distribution of the ground truth explanations
num_inst = 0
inst = 0
dep = 0
gt_exps = {}
for id in block_ids:
    gt_exp = df_hsw.iloc[id]['simple_model_exp'][1:-1].split(', ')  # ['num_insts', '0_2_RAW', '1_2_RAW']
    gt_exp = [g[1:-1] for g in gt_exp if g != '']
    gt_exps[id] = gt_exp
    for g in gt_exp:
        if g == 'num_insts':
            num_inst += 1
        elif 'inst_' in g:
            inst += 1
        else:
            dep += 1

total_exp = num_inst + inst + dep
num_inst_prob = num_inst/total_exp
inst_prob = inst/total_exp
dep_prob = dep/total_exp
print('probs:', num_inst_prob, inst_prob, dep_prob)
trial_success = [0]*tries

for id in block_ids:
    with open(os.path.join(BASE_FOLDER, f'{id}.txt')) as fp:
        ithemal_output = fp.read()

    all_predicates_start = ithemal_output.find('All features of basic block to explain with:')
    all_predicates_start = ithemal_output.find(': ', all_predicates_start) + 3
    all_predicates_end = ithemal_output.find(']', all_predicates_start)
    all_predicates = ithemal_output[all_predicates_start:all_predicates_end].split(', ')
    all_predicates = [p[1:-1] for p in all_predicates if 'WAR' not in p and 'WAW' not in p]
    # inst_num_predicates = len(['inst_' in p for p in all_predicates])
    # raw_num_predicates = len(['RAW' in p for p in all_predicates])
    for times in range(tries):
        np.random.seed(times)
        random_exp = []
        for p in all_predicates:
            if 'num_inst' in p:
                if np.random.binomial(1, num_inst_prob) == 1:
                    random_exp.append(p)
            elif 'inst_' in p:
                if np.random.binomial(1, inst_prob) == 1:
                    random_exp.append(p)
            elif 'RAW' in p:
                if np.random.binomial(1, dep_prob) == 1:
                    random_exp.append(p)
        if set(random_exp).issubset(set(gt_exps[id])):
            trial_success[times] += 1

trial_success = np.array([t/len(block_ids) for t in trial_success])
# print(trial_success)
print(np.mean(trial_success))
print(np.std(trial_success))
