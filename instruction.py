import sys
import time

sys.path.append('utils')
import perturbation_utils
import mem_utils
import x64_lib
import instrData.HSW_data as archData
import json
import copy
import numpy as np
import xed
import re
import settings
from lock_supporting_opcodes import *
import tempfile
import subprocess
from my_get_hex import get_hex_of_code, get_hex_of_code_att
# np.random.seed(42)

class Instruction:
    def __init__(self, disas_obj, num):
        self.disas = copy.deepcopy(disas_obj)
        self.inst_num = num
        # keeping these as the default values, just in case the XML match attributes does not work out
        self.operands_canon = ''
        self.operands_list_canon = []
        for instrData in archData.instrData.get(self.disas['iform'], []):
             if xed.matchXMLAttributes(self.disas, archData.attrData[instrData['attr']]):
                 # print(instrData['string'])
                 if ' (' not in instrData['string']:  # empty operand
                     self.operands_canon = ''
                     self.operands_list_canon = []
                 else:
                     self.operands_canon = instrData['string'][instrData['string'].find(' (')+2:instrData['string'].find(')')]
                     self.operands_list_canon = self.operands_canon.split(', ')
                 self.canonical_form = instrData['string']
                 break

        self.opcode = self.disas['iclass'].split('_')[0].upper()
        self.is_lock = (self.disas['asm'].split(' ')[0] == 'lock')  # is this a lock instruction or not
        if self.is_lock:
            self.disas['asm'] = self.disas['asm'].split(' ', 1)[1]  # removing the lock prefix from the asm for clarity

        with open('utils/operand_dict.py', 'r') as f:
            operand_dict = json.load(f)
        self.opcode_perturbation_choices = []
        if self.operands_canon in operand_dict.keys():  # some opcodes have unrecognized type of operands such as 'nop'
            self.opcode_perturbation_choices = copy.deepcopy(operand_dict[self.operands_canon])
        self.opcode_perturbation_choices = list(set([x.split('_', 1)[0] for x in self.opcode_perturbation_choices]))
        # print(self.disas['iclass'].upper())
        # print(self.opcode_perturbation_choices)
        if self.opcode in self.opcode_perturbation_choices:
            self.opcode_perturbation_choices.remove(self.opcode)
        if self.is_lock:  # restricting opcode perturbation choices to opcodes which can take a lock prefix
            self.opcode_perturbation_choices = [x for x in self.opcode_perturbation_choices if x in lock_opcodes]
        self.opcode_perturbation_choices.sort()
        try:
            self.operands = self.disas['asm'].strip().split(' ', 1)[1].split(', ')  # actual operands
        except:
            self.operands = []  # probably no operands are there, so assigned an empty list here
        # print("for asm:", self.disas['asm'], 'operands are:', self.operands)
        self.opnds_not_to_be_modified = np.zeros((len(self.operands)))
        for my_idx, my_opnd in enumerate(self.operands):
            if my_opnd.upper() in self.operands_list_canon:
                self.opnds_not_to_be_modified[my_idx] = 1
        self.perturber = perturbation_utils.AsmPerturber()
        self.read_pool = {}  # these will be populated in self.make_rw_pools()
        self.write_pool = {}
        self.all_regs = []
        self.make_tokens()

    def get_original_asm(self):
        original_my_asm = self.disas['asm']
        if self.is_lock:
            original_my_asm = 'lock ' + original_my_asm
        return original_my_asm

    def make_tokens(self):  # sends list of all the tokens of the instruction. Choose the ones you need; 'lock' if present, is not a token for now
        self.token_list = [f'opc_{self.inst_num}']
        for i in range(len(self.operands)):
            self.token_list.append(f'opnd_{self.inst_num}_{i}')  # starts with 0
            # need to put the base and index of memory operands as tokens as well
            # check if this is a memory operand
            opnd = self.operands[i]
            if '[' in opnd:  # this is a memory operand
                # decompose the memory operand and check and add the base and index
                base, index1, _, _ = mem_utils.decompose_mem_str(opnd)
                if base is not None:
                    self.token_list.append(f'opnd_{self.inst_num}_{i}_b')
                if index1 is not None:
                    self.token_list.append(f'opnd_{self.inst_num}_{i}_i')

    def get_tokens(self):
        return self.token_list

    def get_operand(self, opnd):  # returns opnd indicated in operand template
        # get operand number:
        opnd_no = int(opnd.split('_')[2])
        my_opnd = self.operands[opnd_no]
        if '_b' in opnd:  # this is requesting for the base of a memory operand
            base, _, _, _ = mem_utils.decompose_mem_str(my_opnd)
            return base
        if '_i' in opnd:  # this is requesting for the index of a memory operand (when _b_i, then both have to be same, it is captured in the above)
            _, index1, _, _ = mem_utils.decompose_mem_str(my_opnd)
            return index1
        return my_opnd  # return the entire operand

    def get_num_perturbations(self):
        # opcode will have number of perturbations = len(opcode perturbation choices)
        # each operand will have some number of perturbation choices
        # exclude immediate perturbation choices and they will be just too many and falsely blow up the number of perturbations
        num_perturbations = 1  # original instruction is also a perturbation
        num_perturbations *= (len(self.opcode_perturbation_choices)+1)
        # now for all the operands
        for i, opnd in enumerate(self.operands):
            if self.opnds_not_to_be_modified[i] == 1:  # this operand must not be changed; so no perturbation for it
                continue
            if '[' in opnd:  # means a memory opnd
                # if the instruction is lea, then memory perturbations come only with lea opcode and with all others, memory is blank

                if self.opcode == 'LEA':
                    num_perturbations /= (len(self.opcode_perturbation_choices)+1)  # remove the effect of multiplying
                    num_perturbations *= (1*self.perturber.num_perturb_memory_choices(opnd) + len(self.opcode_perturbation_choices)*1)
                else:
                    num_perturbations *= self.perturber.num_perturb_memory_choices(opnd)
            elif '0x' in opnd:  # checking for immediates; we don't want to include the perturbations for immediates
                continue
            else:  # must be a register
                num_perturbations *= self.perturber.num_perturb_register_choices(opnd, exclude_self=False)
        return num_perturbations
        # num_perturbations = []  # original instruction is also a perturbation
        # num_perturbations.append(len(self.opcode_perturbation_choices)+1)
        # # now for all the operands
        # for i, opnd in enumerate(self.operands):
        #     if self.opnds_not_to_be_modified[i] == 1:  # this operand must not be changed; so no perturbation for it
        #         continue
        #     if '[' in opnd:  # means a memory opnd
        #         # if the instruction is lea, then memory perturbations come only with lea opcode and with all others, memory is blank
        #
        #         if self.opcode == 'LEA':
        #             num_perturbations.remove(len(self.opcode_perturbation_choices)+1)  # remove the effect of multiplying
        #             num_perturbations.append([1*self.perturber.num_perturb_memory_choices(opnd), len(self.opcode_perturbation_choices)*1])
        #         else:
        #             num_perturbations.append(self.perturber.num_perturb_memory_choices(opnd))
        #     elif '0x' in opnd:  # checking for immediates; we don't want to include the perturbations for immediates
        #         continue
        #     else:  # must be a register
        #         num_perturbations.append(self.perturber.num_perturb_register_choices(opnd, exclude_self=False))
        # return num_perturbations

    def perturb(self, present_tokens, p, n, use_stoke=False, do_delete=True):
        my_seed = (settings.seed*n*1001) % 1000000001
        np.random.seed(my_seed)
        # print(my_seed, n)
        is_lea = (self.opcode == 'LEA')
        data = np.zeros((len(self.token_list)))  # indicates that all the tokens changed
        # # adding the nop instructions for perturbation

        if len(present_tokens) == 0 and np.random.uniform(0, 1) > 0.66 and do_delete:  # if no token needs to be present, can delete the entire instruction
            return '', data
        # else:

        if np.random.uniform(0, 1) > 0.5:  # don't perturb instruction with 50% probability
            original_my_asm = self.disas['asm']
            if self.is_lock:
                original_my_asm = 'lock ' + original_my_asm
            return original_my_asm, np.ones((len(self.token_list)))



        new_opcode = self.opcode
        if f'opc_{self.inst_num}' not in present_tokens:  # can perturb opcode
            if np.random.uniform(0, 1) > 0.5 and len(self.opcode_perturbation_choices) > 0:  # perturb with 0.5 probability if there are any options available
                new_opcode = np.random.choice(self.opcode_perturbation_choices)
                # new_opcode = new_opcode.split('_', 1)[0]
                # if new_opcode == self.disas['iclass']:
                #     data[0] = 1
            else:
                data[0] = 1
        else:
            data[0] = 1
        data_index = 1  # use this to index the data object, as we are not going by the order of the operands in the data object; starts with 1, as opcode is at index 0
        new_opnds = copy.deepcopy(self.operands)
        for i, opnd in enumerate(self.operands):
            memopnd = False
            if '[' in opnd:
                memopnd = True
                base, index1, scale, disp = mem_utils.decompose_mem_str(new_opnds[i])  # precomputing this for utility
            # if any(item.startswith(f'opnd_{self.inst_num}_{i}') for item in present_tokens):  # some components of memory should stay constant
            #     data[data_index] = 1
            #     # for memory operand where some component stays constant, we can keep that entry in data as 1, just to indicate that the things to keep constant are still constant
            #     # only one of the following is allowed to exist in present_tokens; these can only be for memory
            #     if f'opnd_{self.inst_num}_{i}_b' in present_tokens:
            #         new_opnds[i] = self.perturber.perturb_memory(opnd, base_change=False, n=np.random.randint(2**32-1))
            #     elif f'opnd_{self.inst_num}_{i}_i' in present_tokens:
            #         new_opnds[i] = self.perturber.perturb_memory(opnd, index_change=False, n=np.random.randint(2**32-1))
            #     elif f'opnd_{self.inst_num}_{i}_b_i' in present_tokens:
            #         new_opnds[i] = self.perturber.perturb_memory(opnd, base_change=False, index_change=False, n=np.random.randint(2**32-1))
            #     # but it will still stay a memory operand here, so the only opcode that could replace LEA is itself
            #     if is_lea and ('[' in opnd):  # this is lea and memory operand or some component of it has to stay constant
            #         new_opcode = 'LEA'
            #         data[0] = 1
            #     continue

            if f'opnd_{self.inst_num}_{i}' in present_tokens:
                data[data_index] = 1
                if memopnd:  # this is a memory opnd which is to be kept constant, then base, index should also be constant
                    if base is not None:
                        data_index += 1
                        data[data_index] = 1  # base is constant
                    if index1 is not None:
                        data_index += 1
                        data[data_index] = 1  # index is constant
                    if is_lea:
                        new_opcode = 'LEA'
                        data[0] = 1
                data_index += 1
                continue

            if self.opnds_not_to_be_modified[i] == 1:  # this operand must not be changed; generally a register (not memory)
                data[data_index] = 1
                data_index += 1
                continue
            if np.random.uniform(0, 1) > 0.5:  # perturb for sure
                if memopnd:  # means a memory opnd
                    base_change = (f'opnd_{self.inst_num}_{i}_b' not in present_tokens) and (f'opnd_{self.inst_num}_{i}_b_i' not in present_tokens)
                    index_change = (f'opnd_{self.inst_num}_{i}_i' not in present_tokens) and (f'opnd_{self.inst_num}_{i}_b_i' not in present_tokens)
                    if is_lea and new_opcode != 'LEA':
                        if any(item.startswith(f'opnd_{self.inst_num}_{i}_') for item in present_tokens):  # this is to check if either of base/index are to be kept constant
                            # in this case, we can't delete the memory, so we have to keep the opcode as LEA and negate its change
                            new_opcode = 'LEA'
                            data[0] = 1
                            # but we can change perturb parts of memory which are not required to be constant
                            new_opnds[i] = self.perturber.perturb_memory(opnd, base_change=base_change, index_change=index_change, n=np.random.randint(2**32-1))
                            new_base, new_index, _, _ = mem_utils.decompose_mem_str(new_opnds[i])
                            data[data_index] = 0  # this memory is changed
                            if base is not None:
                                data_index += 1
                                data[data_index] = int(new_base == base)  # if base should be present (no change), then data object's value should be 1
                            if index1 is not None:
                                data_index += 1
                                data[data_index] = int(new_index == index1)
                        else:
                            new_opnds[i] = ''  # this also signifies a change to the operand; memory operand, its base, index all changed
                            if base is not None:
                                data_index += 1  # as we need to skip out updating the base of this memory operand (as they are changed)
                            if index1 is not None:
                                data_index += 1
                    else:
                        new_opnds[i] = self.perturber.perturb_memory(opnd, base_change=base_change, index_change=index_change, n=np.random.randint(2**32-1))
                        # check if the base and index were changed or not
                        new_base, new_index, _, _ = mem_utils.decompose_mem_str(new_opnds[i])
                        # memory operand underwent a change overall
                        if base is not None:
                            data_index += 1
                            data[data_index] = int(new_base == base)  # no change happened to base
                        if index1 is not None:
                            data_index += 1
                            data[data_index] = int(new_index == index1)
                elif '0x' in opnd:  # checking for immediates
                    new_opnds[i] = opnd  #self.perturber.perturb_immediate(opnd, n=np.random.randint(2**32-1))
                else:  # must be a register
                    new_opnds[i] = self.perturber.perturb_register(opnd, n=np.random.randint(2**32-1))
                    if new_opnds[i] == opnd:  # just a safe-guard
                        data[data_index] = 1
            else:
                data[data_index] = 1  # this is 1 when no perturbation happened
                if memopnd:  # this is memory operand
                    if base is not None:
                        data_index += 1
                        data[data_index] = 1  # the base remains constant
                    if index1 is not None:
                        data_index += 1
                        data[data_index] = 1  # the index remains constant
                    if is_lea:
                        new_opcode = 'LEA'
                        data[0] = 1
            data_index += 1  # incrementing for next operand
        if '' in new_opnds:
            new_opnds.remove('')
        perturbed_asm = new_opcode + ' ' + ', '.join(new_opnds)
        if self.is_lock:
            perturbed_asm = 'lock ' + perturbed_asm  # adding lock prefix to the perturbed asm
        # print('instruction perturbed asm:', perturbed_asm, 'data:', data)
        # print('data for instruction perturbed asm:', data)
        return perturbed_asm, data

    def get_read_pool(self):
        return self.read_pool

    def get_write_pool(self):
        return self.write_pool

    def make_rw_pools(self):
        rw = self.disas['rw']  # this is the set of all the operands which were read/written
        # go over all the operands. Match them with regOperands or memOperands depending on their types
        taken_names = []
        for idx, opnd in enumerate(self.operands):
            if '[' in opnd:  # this is a memory type operand. Try to match it with memOperands
                # print("memory operand")
                base, index, scale, displacement = mem_utils.decompose_mem_str(opnd)
                own_mem = {'scale': scale, 'disp': displacement}
                if base is not None:
                    own_mem['base'] = base
                if index is not None:
                    own_mem['index'] = index
                my_name = ''
                # print("own mem: ", own_mem)
                for name, mem in self.disas['memOperands'].items():
                    if mem == own_mem:
                        if name in taken_names:  # this is probably a repeat case
                            continue
                        my_name = name
                        taken_names.append(my_name)
                        break

                if base is not None:
                    base = x64_lib.getCanonicalReg(base)
                    if base in self.read_pool:
                        self.read_pool[base].append(f'opnd_{self.inst_num}_{idx}_b')
                    else:
                        self.read_pool[base] = [f'opnd_{self.inst_num}_{idx}_b']
                if index is not None:
                    index = x64_lib.getCanonicalReg(index)
                    if index in self.read_pool:
                        self.read_pool[index].append(f'opnd_{self.inst_num}_{idx}_i')
                    else:
                        self.read_pool[index] = [f'opnd_{self.inst_num}_{idx}_i']
                combined_opnd = mem_utils.combine_mem(base, index, scale, displacement)
                if 'R' in rw[my_name]:
                    if combined_opnd in self.read_pool:
                        self.read_pool[combined_opnd].append(f'opnd_{self.inst_num}_{idx}')
                    else:
                        self.read_pool[combined_opnd] = [f'opnd_{self.inst_num}_{idx}']
                if 'W' in rw[my_name]:
                    if combined_opnd in self.write_pool:
                        self.write_pool[combined_opnd].append(f'opnd_{self.inst_num}_{idx}')
                    else:
                        self.write_pool[combined_opnd] = [f'opnd_{self.inst_num}_{idx}']
            elif '0x' in opnd:  # this is an immediate operand. Not in any pools
                continue
            else:  # this would be a register
                opnd = opnd.upper()
                if opnd == 'ST':  # adding rudimentary FP support
                    opnd = 'ST(0)'
                my_name = ''
                for name, reg in self.disas['regOperands'].items():
                    if reg == opnd:
                        if name in taken_names:  # this is probably a repeat case
                            continue
                        my_name = name
                        taken_names.append(my_name)
                        break
                opnd = x64_lib.getCanonicalReg(opnd)
                if 'R' in rw[my_name]:
                    if opnd in self.read_pool:
                        self.read_pool[opnd].append(f'opnd_{self.inst_num}_{idx}')
                    else:
                        self.read_pool[opnd] = [f'opnd_{self.inst_num}_{idx}']
                if 'W' in rw[my_name]:
                    if opnd in self.write_pool:
                        self.write_pool[opnd].append(f'opnd_{self.inst_num}_{idx}')
                    else:
                        self.write_pool[opnd] = [f'opnd_{self.inst_num}_{idx}']
        # print("Instruction:", self.disas['asm'])
        # print("Read pool:", self.read_pool)
        # print("Write pool:", self.write_pool)

        # return form: {reg/mem name: [opnd codes for it]}

    def make_all_regs(self):
        for my_idx, opnd in enumerate(self.operands):
            if '[' in opnd:
                #print("memory came:", opnd)
                base, index, _, _ = mem_utils.decompose_mem_str(opnd)
                if base is not None:
                    self.all_regs.append(x64_lib.getCanonicalReg(base))
                if index is not None:
                    self.all_regs.append(x64_lib.getCanonicalReg(index))
            elif '0x' in opnd:  # immediate
                continue
            else:  # this is a register
                op = opnd.upper()
                self.all_regs.append(x64_lib.getCanonicalReg(op))
        self.all_regs = list(set(self.all_regs))
        self.all_regs.sort()
        print(self.all_regs)

    def get_all_regs(self):
        return self.all_regs


    def change_all_regs(self, perturbed_regs, n):
        #print("Perturbed regs", perturbed_regs)
        # exit(0)
        new_opnds = copy.deepcopy(self.operands)
        for i, opnd in enumerate(self.operands):
            if '[' in opnd:  # means a memory opnd
                new_opnds[i] = self.perturber.perturb_memory(opnd, target_regs=perturbed_regs, n=(n+1)*(i+1))
            elif '0x' in opnd:  # checking for immediates
                new_opnds[i] = self.perturber.perturb_immediate(opnd, n=(n+1)*(i+1))
            else:  # must be a register
                opnd = opnd.upper()
                new_opnds[i] = self.perturber.perturb_register(opnd, target=perturbed_regs[x64_lib.getCanonicalReg(opnd)], n=(n+1)*(i+1))
        # if len(new_opnds) == 0:
        # print(self.disas['iclass'] == None)
        # print(self.disas['iclass'], new_opnds)
        perturbed_asm = self.opcode + ' ' + ', '.join(new_opnds)
        if self.is_lock:
            perturbed_asm = 'lock ' + perturbed_asm  # adding lock prefix to the perturbed asm
        return perturbed_asm
