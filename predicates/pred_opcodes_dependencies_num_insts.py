import copy
import sys
import numpy as np
sys.path.append('../utils')
import mem_utils
from basic_block_for_dep import *
import settings
import matplotlib.pyplot as plt
import networkx as nx


class InstructionsDependencies:

    def make_predicates_opc_dep_num_insts(self):  # this has forward edges removed, with no differentiation between the data dependencies
        # instruction predicates
        for i in range(len(self.instructions)):
            self.token_list.append(f'inst_{i}')
            self.positions.append(i)

        # plt.savefig('figures/data_dependencies/0.png')
        # exit(0)
        for (i, j, my_label) in self.operands_for_data_dependencies.keys():
            self.positions.append((i, j, my_label))
            self.token_list.append(f'{i}_{j}_{my_label}')

        self.token_list.append('num_insts')
        self.positions.append('num_insts')

    def perturb_opc_dep_num_insts(self, present_tokens, p, n, use_stoke=False):
        '''
        this can either remove or let a dependency stay.
        it doesn't create a new type of dependency between two instructions, unless that gets created without intention
        Instruction tokens are included in this type of predicates
        opcodes can be changed in this type of perturbation, unless they are required to stay constant for instructions which are not to be perturbed
        '''
        # map the present data dependencies to the operands that must be present in the basic block
        # present_tokens: a dict indicating the position of the token that must be preserved (actually it should be present_predicates)
        np.random.seed((settings.seed*(n+1)*100) % 1000000001)  # set the random seed for the selection of the opnd pool to preserve for the data dependency
        present_inst_tokens = {}  # this will only be used to preserve the dependency type predicates; for instruction preservation, we will simply not call perturb for that instruction
        data = [0]*len(self.token_list)
        for i in range(len(self.instructions)):
            present_inst_tokens[i] = []

        # separate out the present_tokens for instructions and dependencies
        # the keys of present_tokens indicate the instruction numbers of present instructions and the instruction numbers of instructions in a dependency separated by '_' for present dependency
        present_pred_inst = [x for x in present_tokens.keys() if type(x) is int]  # these are instructions which must be present in this perturbation
        present_pred_dep = [x for x in present_tokens.keys() if type(x) is tuple]  # these are the dependencies which must be present in the perturbation (these predicates have tuples indicating their positions)
        present_pred_num_inst = [x for x in present_tokens.keys() if x == 'num_insts']  # this is the predicate for number of instructions in bb
        # for instructions that must be present, perturb function will not be called for them


        for (i, j, label) in present_pred_dep:
            opnd_structured_list = self.operands_for_data_dependencies[(i, j, label)]  # contains operands of insts i, j which are involved in this dependency
            # we will require just one of these operand pools to be preserved for preserving the data dependency
            # the operand pool to be preserved will be picked at random from the opnd_structured_list

            pool_num = np.random.choice(np.arange(len(opnd_structured_list)))  # randomly selecting an index of the opnd_structured_list
            # only the elements of the opnd_list need to be preserved. Rest can be changed randomly
            opnd_list = [x for x in opnd_structured_list[pool_num]]
            present_inst_tokens[i].extend([x for x in opnd_list if x.startswith(f'opnd_{i}')])  # operands of instruction i in the data dependency
            present_inst_tokens[j].extend([x for x in opnd_list if x.startswith(f'opnd_{j}')])  # operands of instruction j in the data dependency
            data[self.token_list.index(f'{i}_{j}_{label}')] = 1

            # the opcodes of the instructions involved in a fixed data dependency must not be changed (if they are changed then the read-write pools and the dependencies come to the danger of being lost)
            present_inst_tokens[i].append(f'opc_{i}')
            present_inst_tokens[j].append(f'opc_{j}')

        # other dependencies will be preserved with some probability
        # needs to be done here, as it can't be done inside individual instructions, where instructions only can be preserved with some probability
        for (i, j, my_label) in self.operands_for_data_dependencies.keys():
            if np.random.uniform(0, 1) > 0.9 and (i, j, my_label) not in present_pred_dep:
                # this dependency has to be preserved
                # the dependency will be preserved by keeping one pool of operands intact
                opnd_structured_list = self.operands_for_data_dependencies[(i, j, my_label)]
                pool_num = np.random.choice(np.arange(len(opnd_structured_list)))  # randomly selecting an index of the opnd_structured_list
                # only the elements of the opnd_list need to be preserved. Rest can be changed randomly
                opnd_list = [x for x in opnd_structured_list[pool_num]]
                if i not in present_inst_tokens.keys():
                    present_inst_tokens[i] = []
                if j not in present_inst_tokens.keys():
                    present_inst_tokens[j] = []
                present_inst_tokens[i].extend([x for x in opnd_list if x.startswith(f'opnd_{i}')])  # operands of instruction i in the data dependency
                present_inst_tokens[j].extend([x for x in opnd_list if x.startswith(f'opnd_{j}')])  # operands of instruction j in the data dependency
                present_inst_tokens[i].append(f'opc_{i}')  # opcodes of a fixed data dependency must also not change
                present_inst_tokens[j].append(f'opc_{j}')
                data[self.token_list.index(f'{i}_{j}_{my_label}')] = 1

        # perturb the basic block, while keeping the present tokens constant
        my_seed = n
        my_seed += 10000
        perturbed_asm_insts = []
        inst_map = {}
        new_inst_id = 0
        do_delete = True
        if len(present_pred_num_inst) > 0:  # need to preserve number of instructions
            do_delete = False
        data[self.token_list.index('num_insts')] = 1
        for i, inst in enumerate(self.instructions):
            present_tokens_my_inst = present_inst_tokens[i]
            if i in present_pred_inst:  # if this instruction must be present: only its opcode should remain unchanged
                data[self.token_list.index(f'inst_{i}')] = 1  # updating the predicate change 'data' object as well here
                present_tokens_my_inst.append(f'opc_{i}')
            perturbed_inst, changes = inst.perturb(present_tokens_my_inst, p, n=(my_seed*(i+1)) % 10001, use_stoke=use_stoke, do_delete=do_delete)
            # don't need to bother setting the data values for data-dependencies deleted with deleted instructions, as default is 0
            if perturbed_inst != '':  # not deleted instruction
                inst_map[i] = new_inst_id
                new_inst_id += 1
            if perturbed_inst == '':
                data[self.token_list.index('num_insts')] = 0
            my_inst_changes = 1
            if changes[0] == 0:  # opcode changed
                my_inst_changes = 0
            data[self.token_list.index(f'inst_{i}')] = my_inst_changes  # updating the instruction predicate 'data' entry
            perturbed_asm_insts.append(perturbed_inst)
        perturbed_asm_insts = [ins for ins in perturbed_asm_insts if ins != '']
        if perturbed_asm_insts == []:  # all instructions got blank
            perturbed_asm = 'nop'
        else:
            perturbed_asm = '; '.join(perturbed_asm_insts)
        # print("Perturbed asm: ", perturbed_asm)

        # recreate the read-write pools for the perturbed asm code
        # make a basic_block_for_dependency object out of the perturbed asm code
        perturbed_bb = BasicBlockDependencies(perturbed_asm)
        present_dependencies = perturbed_bb.get_operands_dependencies().keys()
        # use the operands_for_data_dependency dict to check if the data dependencies in this block are there or not
        # map the present tokens back to a diff data object which indicates whether a data dependency changed or not
        for (i, j, my_label) in self.operands_for_data_dependencies.keys():
            if (i, j, my_label) in present_tokens.keys():
                continue  # this data dependency was preserved, so no need to check it (data object is already having this information)
            if i in inst_map.keys() and j in inst_map.keys():
                data_index = self.token_list.index(f'{i}_{j}_{my_label}')
                data[data_index] = int((inst_map[i], inst_map[j], my_label) in present_dependencies)  # checks if the dependency is present in the perturbed asm

        # for (i, j) in self.data_dependency_graph.edges():
        #     if (i, j) in present_tokens.keys():
        #         continue  # this data dependency was preserved, so no need to check it
        #     changes_i = all_changes[i]
        #     changes_j = all_changes[j]
        #     data_index = self.token_list.index(f'{i}_{j}')
        #     data[data_index] = 0  # assuming change happened
        #     # go over all the lists in the edge's attributes
        #     # print(self.data_dependency_graph[i][j])
        #     # if even one data dependency pool has some preservation, then data dependency is assumed to be preserved according to current design
        #     for cur_opnds in self.operands_for_data_dependencies[(i, j)]:
        #         #print('opnds:', self.operands_for_data_dependencies[(i, j)])
        #         # cur_opnds is a pool of operands associated with a particular common operand in the data dependency
        #         cur_opnds_i = [x for x in cur_opnds if x.startswith(f'opnd_{i}')]
        #         cur_opnds_j = [x for x in cur_opnds if x.startswith(f'opnd_{j}')]
        #         num_changes_i = 0
        #         num_changes_j = 0
        #         for opndi in cur_opnds_i:
        #             opnd_no = int(opndi.split('_')[2])
        #             if changes_i[1 + opnd_no] == 0:  # change happened to this operand
        #                 num_changes_i += 1
        #         for opndj in cur_opnds_j:
        #             opnd_no = int(opndj.split('_')[2])
        #             if changes_j[1 + opnd_no] == 0:
        #                 num_changes_j += 1
        #         # check: this is implementing data dependency maintenance, even when one edge exists between two instructions
        #         # if the operands in no instruction change, then the data dependency is preserved
        #         if (num_changes_i + num_changes_j) == 0:
        #             data[data_index] = 1
        #             break
        #         # if the operands of one instruction don't change, but some of those of the other instruction change, then too the dependency is preserved
        #         if (num_changes_i == 0 and num_changes_j < len(cur_opnds_j)) or (num_changes_j == 0 and num_changes_i < len(cur_opnds_i)):
        #             data[data_index] = 1
        #             break
        #         # if the operands of one instruction don't change, but all of the other instruction change, then the data dependency is gone
        #         if (num_changes_i == 0 and num_changes_j == len(cur_opnds_j)) or (num_changes_j == 0 and num_changes_i == len(cur_opnds_i)):
        #             continue
        #         # if some operands change in both instructions, then the checking for data dependency needs to be done
        #         # if one operand from both instructions matches up then
        #         else:
        #             def get_operand(opnd_list, opnd):
        #                 opnd_no = int(opnd.split('_')[2])
        #                 my_opnd = opnd_list[opnd_no]
        #                 if '_b' in opnd:  # this is requesting for the base of a memory operand
        #                     base, _, _, _ = mem_utils.decompose_mem_str(my_opnd)
        #                     return base
        #                 if '_i' in opnd:  # this is requesting for the index of a memory operand (when _b_i, then both have to be same, it is captured in the above)
        #                     _, index1, _, _ = mem_utils.decompose_mem_str(my_opnd)
        #                     return index1
        #                 return my_opnd  # return the entire operand
        #
        #             def check_equality():  # this function checks if the operands are equal
        #                 # atleast two elements should be there in cur_opnds
        #                 assert len(cur_opnds) > 1
        #                 all_opnds = {i: perturbed_asm_insts[i].split(' ', 1)[1].split(', '), j: perturbed_asm_insts[j].split(' ', 1)[1].split(', ')}  # this is fine to do, as if the instructions will not have operands then they can't be in the data dependency
        #                 # these operands correspond to one type of dependency wrt one register/memory
        #                 # so we will check if in this pool of operands (cur_opnds) there are any two operands each in different instructions which are same (even after the perturbation)
        #                 # basically, we will compute the intersection in the opnds pool of both the instructions and check if that is non-empty
        #
        #                 opnds_inst_i = []
        #                 for my_idx_i in range(len(cur_opnds_i)):
        #                     opnds_inst_i.append(get_operand(all_opnds[i], cur_opnds_i[my_idx_i]))
        #                 opnds_inst_j = []
        #                 for my_idx_j in range(len(cur_opnds_j)):
        #                     opnds_inst_j.append(get_operand(all_opnds[j], cur_opnds_j[my_idx_j]))
        #
        #                 return bool(set(opnds_inst_i) & set(opnds_inst_j))  # this returns if the intersection of the two lists is non-empty
        #                 # common = get_operand(all_opnds[int(cur_opnds[0].split('_')[1])], cur_opnds[0])
        #                 # for my_idx in range(1, len(cur_opnds)):
        #                 #     this_opnd = get_operand(all_opnds[int(cur_opnds[my_idx].split('_')[1])], cur_opnds[my_idx])
        #                 #     if this_opnd != common:
        #                 #         return False
        #                 # return True
        #
        #             if check_equality():  # this function checks if the operands are equal
        #                 data[data_index] = 1
        #                 # print('equality after perturbation')
        #                 # print(f'num_changes {i}:', num_changes_i, f'changes {i}:', changes_i)
        #                 # print(f'num_changes {j}:', num_changes_j, f'changes {j}:', changes_j)
        #                 break
        #             # print("all matched after perturbation:", perturbed_asm, cur_opnds)
        #
        #     # This is a different type of thinking where the data dependency weakening is also considered a change in the dependency
        #             # # if some operands are changed: then data dependency is weakened or removed (changed in short)
        #             # elif num_changes < len(cur_opnds):
        #             #     data[data_index] = 0
        #             #     break
        #         # if all operands are changed: check if the data dependency is preserved by checking actual values of the operands in the perturbed asm
        #
        #     # opnd_list = self.data_dependency_graph[i][j]['operands']
        #     # opnd_list_i = [x for x in opnd_list if x.startswith(f'opnd_{i}')]  # operands of i involved in the data dependency
        #     # opnd_list_j = [x for x in opnd_list if x.startswith(f'opnd_{j}')]  # operands of j involved in the data dependency
        #     # changes_i = all_changes[i]
        #     # changes_j = all_changes[j]
        #     # data_index = self.token_list.index(f'{i}_{j}')
        #     # data[data_index] = 1  # assuming no change happened
        #     # for opndi in opnd_list_i:
        #     #     opnd_no = int(opndi.split('_')[2])  # number of the operand to check
        #     #     if changes_i[1 + opnd_no] == 1:  # no change happened; even if change happened (in other parts of a memory operand), the requested parts were not changed
        #     #         continue
        #     #     else:  # some change happened
        #     #         # if self.instructions[i].get_opnd(opnd_no) == self.instructions[j].get_opnd(opnd_no):
        #     #         #     continue  # the operand changed similarly in both instructions
        #     #         data[data_index] = 0
        #     #         break  # this for loop must be ended now as data dependency has undergone a change
        #     # if data[data_index]:  # if no change has been detected yet
        #     #     for opndj in opnd_list_j:
        #     #         opnd_no = int(opndj.split('_')[2])  # number of the operand to check
        #     #         if changes_j[1 + opnd_no] == 1:  # no change happened; even if change happened (in other parts of a memory operand), the requested parts were not changed
        #     #             continue
        #     #         else:  # some change happened
        #     #             data[data_index] = 0
        #     #             break  # this for loop must be ended now as data dependency has undergone a change
        # print('perturbed asm:', perturbed_asm)
        # print('data:', data)
        return data, perturbed_asm, n
