import sys
# add anchor to path
sys.path.append('./anchor')
import argparse
import anchor_text
sys.path.append('utils')
import settings
sys.path.append('models')
from testing_models import *


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("code", type=str)
    parser.add_argument("predicate_type", type=str)
    parser.add_argument("testing_model", type=str)
    parser.add_argument("precision_threshold", type=float)
    parser.add_argument("my_seed", type=int, default=1)
    parser.add_argument('-use_stoke', action='store_true')
    args = parser.parse_args()

    settings.init(args.my_seed)
    code_text = args.code
    # code_text = "movl 0x8(%r12), %eax; leaq (%r14,%rax,8), %rbp; cmpq %rdx, %r14"
    print("The code to explain is:\n{}".format(code_text))

    if args.testing_model == 'ithemal':
        my_model = testing_ithemal_gpu_original
        print("Testing Ithemal")
    elif args.testing_model == 'uica':
        my_model = testing_uica
        print("Testing uiCA")
    elif args.testing_model == 'crude':
        my_model = simple_analytical_model
        print("Testing simple analytical baseline")
    else:
        raise("model type not recognized!")

  # TODO: check if the ithemal container is running

    explainer = anchor_text.AnchorText(None, ['far', 'close'], use_unk_distribution=False)  # 0: far; 1: close (to original input)
    pred = 'close'
    pred_num = my_model(code_text)
    print("Code:\n"+code_text)
    print('Prediction: %s' % pred_num[0]) #TODO: normalize the prediction; Ithemal has prediction scaled by 100
    alternative = 'far'
    if args.predicate_type == 'token':
        thresh = 0.9  # just so it has more predicates for higher precision
    else:  # args.predicate_type == 'instruction':
        thresh = 0.95

    exps = explainer.explain_instance(code_text, my_model, args.predicate_type, threshold=args.precision_threshold, use_stoke=args.use_stoke, perturbation_probability=0.5) #0.82)  # FIXME: changing just for now to see the effect
    for exp_type, exp in exps.items():
        print('='*100)
        # print("Predicate type: ", exp_type)
        print('Explanation feature set: %s' % (' AND '.join(exp.names())))
        print('Precision: %.2f' % exp.precision())
        print('Coverage: %.2f' % exp.coverage())
        print('='*100)
        # print('Examples where anchor applies and model predicts %s:' % pred)
        # print()
        # print('\n\n'.join([x[0] for x in exp.examples(only_same_prediction=True)]))
        # print('='*100)
        # print()
        # print('Examples where anchor applies and model predicts %s:' % alternative)
        # print()
        # print('\n\n'.join([x[0] for x in exp.examples(partial_index=None, only_different_prediction=True)]))
        # # making partial index none, coz we want to add the samples which have anchor satisfied but are predicted low
        # # partial index is indicative of till which anchor index to show the samples
        # print('='*100)


if __name__ == '__main__':
    main()
