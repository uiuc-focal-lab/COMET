import xed
import subprocess
import sys
import tempfile
import os
import networkx as nx
sys.path.append('predicates')
sys.path.append('utils')
sys.path.append('.')
from microArchConfigs import MicroArchConfigs
import numpy as np
import copy
import pred_instructions_dependencies_num_insts
import pred_opcodes_dependencies_num_insts
import instruction
from dependency_types_pools import *
# np.random.seed(42)


class BasicBlock(pred_instructions_dependencies_num_insts.InstructionsDependencies, pred_opcodes_dependencies_num_insts.InstructionsDependencies):
    def __init__(self, code, predicate_type, classifier_func, **kwargs):
        _, asm_file = tempfile.mkstemp()
        _, bin_file = tempfile.mkstemp()
        with open(asm_file, 'w') as f:
            f.write(code)
        try:
            subprocess.run(['as', asm_file, '-o', bin_file])
        except:
            print('here')
            exit(1)
        # os.close(asm_desc)
        self.disas = xed.disasFile(bin_file, chip=MicroArchConfigs['HSW'].XEDName)
        # os.close(bin_desc)
        # for my_asm in self.disas:
        #     print("disas asm:", my_asm['asm'])
        # print(self.disas)
        # exit(0)
        # check for nop opcode in any instruction. if found, then remove the excess operands from the disas['asm'] (don't know of a better way to do it)
        code = code.replace('\t', ' ')

        for i in range(len(self.disas)):  # considering the disas object as it will have all the directives removed
            if self.disas[i]['iclass'].split('_')[0].upper() == 'NOP':
                self.disas[i]['asm'] = self.disas[i]['asm'].split(', ', 1)[0]
                # print("changed: ", self.disas[i]['asm'])
                # exit(0)
            # lone 'ptr' keywords (which are not preceded by 'word' indicating the length of operand) are dangerous as they put the displacement to be 0
            # so we want to remove all the lone 'ptr's
            # for this, we first remove all 'ptr's
            self.disas[i]['asm'] = self.disas[i]['asm'].replace(' ptr ', ' ')
            # then when we find an occurrence of a 'word', we add a 'ptr' after it to maintain the syntax
            self.disas[i]['asm'] = self.disas[i]['asm'].replace('word ', 'word ptr ')
            self.disas[i]['asm'] = self.disas[i]['asm'].replace('byte ', 'byte ptr ')

        #     print(self.disas[i]['asm'])
        # exit(0)

        self.instructions = [instruction.Instruction(x, i) for i, x in enumerate(self.disas)]
        # exit(0)
        self.original_asm = '; '.join(x['asm'] for x in self.disas)
        # print("Original: ", self.original_asm)
        # self.instructions_num_tokens = [len(x.get_tokens()) for x in self.instructions]
        self.all_token_dict = {}
        for i, x in enumerate(self.instructions):
            self.all_token_dict[i] = x.get_tokens()
        self.predicate_type = predicate_type
        self.classifier_fn = classifier_func
        # if self.classifier_fn is None:
        #     self.center = 0
        # else:
        if 'uica_output_type' in kwargs.keys():
            self.center = self.classifier_fn([self.original_asm], output_type=kwargs['uica_output_type'])[0]
        else:
            self.center = self.classifier_fn([self.original_asm])[0]
        self.make_my_dependencies()
        self.token_list = []
        self.positions = []
        if self.predicate_type == 'instruction_dependency_num_insts':  # instruction and dependency together
            self.make_predicates, self.perturb = self.make_predicates_inst_dep_num_insts, self.perturb_inst_dep_num_insts
        elif self.predicate_type == 'opcode_dependency_num_insts':  # instruction and dependency together
            self.make_predicates, self.perturb = self.make_predicates_opc_dep_num_insts, self.perturb_opc_dep_num_insts
        self.make_predicates()

        self.inst_not_to_be_perturbed = []  #[0, 1, 2, 3, 5, 6, 7]  #[0, 1, 2, 3, 5, 6]  #[0, 1, 2, 3, 6, 7]  # hard-coding for now
    
    def get_original_pred(self):
        return self.center
    
    def get_tokens(self):
        return self.token_list, self.positions

    def get_num_perturbations(self):
        # each instruction will have some number of possibilities for it
        # for all perturbations, each instruction will be perturbed independently
        # total num_perturbations = product of num perturbations for all instructions
        num_perturbations = 1  # includes the original code
        for inst in self.instructions:
            num_perturbations *= inst.get_num_perturbations()  # guaranteed to be > 0
        return num_perturbations
        # num_perturbations = []  # includes the original code
        # for inst in self.instructions:
        #     num_perturbations.append(inst.get_num_perturbations()) # guaranteed to be > 0
        # return num_perturbations


    def make_my_dependencies(self):
        # dependency predicates
        # self.data_dependency_graph = nx.DiGraph()
        for i, inst in enumerate(self.instructions):
            inst.make_rw_pools()  # makes the read/write pools of instruction
            # self.data_dependency_graph.add_node(i)

        self.operands_for_data_dependencies = {}
        for i in range(len(self.instructions) - 1):
            for j in range(i+1, len(self.instructions)):
                raw_list = raw(self.instructions[i].get_write_pool(), self.instructions[j].get_read_pool())  # raw() returns list of operands involved in RAW data dependency between i, j
                war_list = war(self.instructions[i].get_read_pool(), self.instructions[j].get_write_pool())
                waw_list = waw(self.instructions[i].get_write_pool(), self.instructions[j].get_write_pool())
                string_raw_list = ['.'.join(sorted(r)) for r in raw_list]
                string_war_list = ['.'.join(sorted(r)) for r in war_list]
                # string_waw_list = ['.'.join(sorted(r)) for r in waw_list]
                # orig_dep_list = copy.deepcopy(raw_list) + copy.deepcopy(war_list) + copy.deepcopy(waw_list)
                # print('raw list:', raw_list)
                # print('war list:', war_list)
                # print('waw list:', waw_list)`
                waw_list = [w for w in waw_list if '.'.join(sorted(w)) not in string_raw_list and '.'.join(sorted(w)) not in string_war_list]
                war_list = [w for w in war_list if '.'.join(sorted(w)) not in string_raw_list]
                dep_dict = {'RAW': raw_list, 'WAR': war_list, 'WAW': waw_list}
                # print(dep_dict)
                # exit(0)
                for dep_type in dep_dict.keys():
                    # print(dep_type)
                    dep_list = []
                    for dep in dep_dict[dep_type]:
                        if dep not in dep_list:
                            dep_list.append(dep)
                    if len(dep_list) > 0:
                        # self.data_dependency_graph.add_edge(i, j, label=dep_type)  # let's see if this works
                        self.operands_for_data_dependencies[(i, j, dep_type)] = dep_list  # this would contain the operands even for dependencies which will be eventually removed. but we won't access them so fine

        # self.data_dependency_graph = nx.transitive_reduction(self.data_dependency_graph)
