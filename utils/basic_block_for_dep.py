import subprocess
import sys
import networkx as nx
import copy
import tempfile
sys.path.append('../')
import xed
from microArchConfigs import MicroArchConfigs
import instruction
from dependency_types_pools import *


class BasicBlockDependencies:
    def __init__(self, code, only_raw=False):
        _, fname = tempfile.mkstemp()
        _, fname1 = tempfile.mkstemp()
        with open(fname, 'w') as f:
            f.write('.intel_syntax noprefix; '+code+'\n')
        # print('here')
        try:
            subprocess.run(['as', fname, '-o', fname1])
        except:
            print('bb dep')
            exit(1)
        self.disas = xed.disasFile(fname1, chip=MicroArchConfigs['HSW'].XEDName)

        for i in range(len(self.disas)):  # considering the disas object as it will have all the directives removed
            if self.disas[i]['iclass'] == 'NOP':
                self.disas[i]['asm'] = self.disas[i]['asm'].split(', ', 1)[0]
            # below lone ptr problem doesn't really matter here, as it just has to compute the dependencies
            # putting below code just for consistency with my notion of the disas asm
            # lone 'ptr' keywords (which are not preceded by 'word' indicating the length of operand) are dangerous as they put the displacement to be 0
            # so we want to remove all the lone 'ptr's
            # for this, we first remove all 'ptr's
            self.disas[i]['asm'] = self.disas[i]['asm'].replace(' ptr ', ' ')
            # then when we find an occurrence of a 'word', we add a 'ptr' after it to maintain the syntax
            self.disas[i]['asm'] = self.disas[i]['asm'].replace('word ', 'word ptr ')
            self.disas[i]['asm'] = self.disas[i]['asm'].replace('byte ', 'byte ptr ')
        self.instructions = [instruction.Instruction(x, i) for i, x in enumerate(self.disas)]
        self.operands_for_data_dependencies = {}
        self.make_predicates_dep(only_raw)

    def make_predicates_dep(self, only_raw):  # this has forward edges retained, with no differentiation between the data dependencies
        for i, inst in enumerate(self.instructions):
            inst.make_rw_pools()  # makes the read/write pools of instruction

        for i in range(len(self.instructions) - 1):
            for j in range(i+1, len(self.instructions)):
                raw_list = raw(self.instructions[i].get_write_pool(), self.instructions[j].get_read_pool())  # raw() returns list of operands involved in RAW data dependency between i, j
                dep_dict = {'RAW': raw_list}
                if not only_raw:
                    war_list = war(self.instructions[i].get_read_pool(), self.instructions[j].get_write_pool())
                    waw_list = waw(self.instructions[i].get_write_pool(), self.instructions[j].get_write_pool())
                    string_raw_list = ['.'.join(sorted(r)) for r in raw_list]
                    string_war_list = ['.'.join(sorted(r)) for r in war_list]
                    waw_list = [w for w in waw_list if '.'.join(sorted(w)) not in string_raw_list and '.'.join(sorted(w)) not in string_war_list]
                    war_list = [w for w in war_list if '.'.join(sorted(w)) not in string_raw_list]
                    dep_dict['WAR'] = war_list
                    dep_dict['WAW'] = waw_list
                for dep_type in dep_dict.keys():
                    dep_list = []
                    for dep in dep_dict[dep_type]:
                        if dep not in dep_list:
                            dep_list.append(dep)
                    if len(dep_list) > 0:
                        self.operands_for_data_dependencies[(i, j, dep_type)] = dep_list  # this would contain the operands even for dependencies which will be eventually removed. but we won't access them so fine

    def get_operands_dependencies(self):
        return self.operands_for_data_dependencies
