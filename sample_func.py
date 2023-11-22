import time

import pandas as pd

from basic_block import *
import multiprocessing as mp
import sys
sys.path.append('utils')
import settings

def exp_normalize(x):
    b = x.max()
    y = np.exp(x - b)
    return y / y.sum()


def get_sample_fn(code, classifier_fn, predicate_type, prob, onepass=False, use_proba=False, use_stoke=False):
    # true_label = classifier_fn([code])[0]
    true_label = 1  # always within the eps ball
    bb = BasicBlock(code, predicate_type, classifier_fn)
    center = bb.get_original_pred()
    token_list, positions = bb.get_tokens()
    # df_samples = pd.DataFrame(columns=['asm', 'data', 'label', 'center', 'present'])
    # df_samples.to_csv('data/scratch/samples.csv', index=False)
    # sample_fn

    def sample_fn(present, num_samples, compute_labels=True, usebert=False):
        # print(f'sampling a batch of {num_samples}')
        present_inst_tokens = {}  # this is just called present_inst_token. can take various forms
        for p in present:
            if positions[p] in present_inst_tokens:
                present_inst_tokens[positions[p]].append(token_list[p])
            else:
                present_inst_tokens[positions[p]] = [token_list[p]]

        data = []
        raw_data = []
        labels = []

        def custom_callback(diff, raw, lab):
            data.append(diff)
            raw_data.append(raw)
            labels.append(lab)
        # t1 = time.time()
        settings.seed += 1
        # print()
        # exit(0)
        t1 = time.time()
        # print("started a pool for size: ", num_samples)
        pool = mp.Pool(mp.cpu_count()-1)
        results = pool.starmap_async(bb.perturb, [(present_inst_tokens, prob, n, use_stoke) for n in range(num_samples)]).get()
        pool.close()
        pool.join()
        results.sort(key=lambda a: a[2])
        # print(f"Perturbation time for {num_samples} samples:", time.time()-t1)
        for res in results:
            data.append(res[0])
            raw_data.append(res[1])
        # print("data: ", data)
        # print("raw_data", raw_data)
        # print("labels: ", labels)
        # print("time taken: ", time.time()-t1)
        # exit(0)
        if compute_labels:  # here because the label computation will do the check if Ithemal can work on that input
            # print(raw_data)
            labels = classifier_fn(raw_data, center)
        labels = np.array(labels)
        raw_data = np.array(raw_data).reshape(-1, 1)

        data = np.array(data, dtype=int)
        return raw_data, data, labels
    # perturb each token of each instruction
    return token_list, positions, true_label, sample_fn
