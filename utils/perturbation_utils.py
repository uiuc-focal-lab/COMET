import numpy as np
import copy
from x64_lib import *
import mem_utils
import time
import settings


class AsmPerturber:
    def __init__(self):
        pass
    
    def perturb_immediate(self, imm, n, exclude_self = True):
        np.random.seed((settings.seed*(n+1)*102)%1000000001)

        my_input = imm
        if isinstance(imm, str):
            my_input = int(imm, 0)
        possibilities = list(range(-60, 60))
        if exclude_self and my_input in possibilities:
            possibilities.remove(my_input)
        new_imm = np.random.choice(possibilities)
        output = new_imm
        if isinstance(imm, str):
            output = hex(new_imm)
        return output
    
    def perturb_memory(self, mem, n, base_change = True, index_change = True, target_regs = None):
        np.random.seed((settings.seed*(n+1)*103)%1000000001)
        base, index, scale, displacement = mem_utils.decompose_mem_str(mem)
                
        changes_list = ['b', 'i', 'd', 's']
        if not base_change:
            changes_list.remove('b')
        if not index_change:
            changes_list.remove('i')
        must_change = np.random.choice(changes_list)
        
        def perturb_scale(scale, exclude_self = True):
            possibilities = [1, 2, 4, 8]
            if exclude_self and scale in possibilities:
                possibilities.remove(scale)
            return np.random.choice(possibilities)
        
        displacement = self.perturb_immediate(displacement, exclude_self=(must_change == 'd'), n=np.random.randint(2**32-1))
        scale = perturb_scale(scale, exclude_self=(must_change == 's'))
        if base_change:
            if target_regs is not None and base in target_regs.keys():
                base = self.perturb_register(base, exclude_self=(must_change == 'b'), target=target_regs[base], n=np.random.randint(2**32-1))
            else:
                base = self.perturb_register(base, exclude_self=(must_change == 'b'), n=np.random.randint(2**32-1))
        if index_change:
            if target_regs is not None and index in target_regs.keys():
                index = self.perturb_register(index, exclude_self=(must_change == 'i'), target=target_regs[index], is_index=True, n=np.random.randint(2**32-1))
            else:
                index = self.perturb_register(index, exclude_self=(must_change == 'i'), is_index=True, n=np.random.randint(2**32-1))
        
        mem_str = mem_utils.combine_mem(base, index, scale, displacement)
        
        return re.sub(r'\[(.*)\]', mem_str, mem)
    
        
    
    def perturb_register(self, reg, n, exclude_self = True, is_index = False, target = None):
        np.random.seed((settings.seed*(n+1)*104)%1000000001)
        if reg == None:
            return reg
        reg = reg.upper()
        my_pool = []
        reg_size = getRegSize(reg)
        if reg_size == -1:
            if reg in STATUSFLAGS_noAF:
                my_pool = copy.deepcopy(STATUSFLAGS_noAF)
                if exclude_self and reg in my_pool:
                    my_pool.remove(reg)
            elif reg in STATUSFLAGS:
                my_pool = copy.deepcopy(STATUSFLAGS)
                if exclude_self and reg in my_pool:
                    my_pool.remove(reg)
            else:
                print(f'invalid register type {reg}, cannot perturb')
                return reg
        else:
            if target is not None:
                if is_index and 'SP' in target:
                    return reg
                result = regToSize(getCanonicalReg(target), reg_size)
                if result == None:
                    print(target, getCanonicalReg(target), reg_size)
                #exit(0)
                if result == 'ESP':
                    return reg
                else:
                    return result
            canon_form = getCanonicalReg(reg)
            if canon_form in r64_pool:
                my_pool = copy.deepcopy(r64_pool)
                if exclude_self and canon_form in my_pool:
                    my_pool.remove(canon_form)
            elif canon_form in xmm_pool:
                my_pool = copy.deepcopy(xmm_pool)
                if exclude_self and canon_form in my_pool:
                    my_pool.remove(canon_form)
            else:
                # print(r64_pool)
                # print(xmm_pool)
                return reg
        my_pool = list(my_pool)
        my_pool.sort()
        # if is_index or reg_size == 32:  # index can't be stack pointer; ESP is unsupported by Ithemal
        my_pool = [x for x in my_pool if 'SP' not in x]  # removing stack pointer register as it is unsupported token for ithemal
        new_reg = np.random.choice(my_pool)
        if reg_size == -1:
            return new_reg
        # here come the gprs and xmms
        if reg_size <= 64:  # gprs
            new_reg = regToSize(new_reg, reg_size)
        else: # xmms
            if reg_size == 256:  # there are no zmms currently supported by ithemal. so not in this perturbation model as well
                temp_reg = list(new_reg)
                temp_reg[0] = 'Y'
                new_reg = ''.join(temp_reg)
        return new_reg


    def num_perturb_register_choices(self, reg, exclude_self = True):
        if reg == None:
            return 1
        reg = reg.upper()
        reg_size = getRegSize(reg)
        if reg_size == -1:
            if reg in STATUSFLAGS_noAF:
                my_pool = copy.deepcopy(STATUSFLAGS_noAF)
                if exclude_self and reg in my_pool:
                    my_pool.remove(reg)
            elif reg in STATUSFLAGS:
                my_pool = copy.deepcopy(STATUSFLAGS)
                if exclude_self and reg in my_pool:
                    my_pool.remove(reg)
            else:
                print(f'invalid register type {reg}, cannot perturb')
                return 1
        else:
            canon_form = getCanonicalReg(reg)
            if canon_form in r64_pool:
                my_pool = copy.deepcopy(r64_pool)
                if exclude_self and canon_form in my_pool:
                    my_pool.remove(canon_form)
            elif canon_form in xmm_pool:
                my_pool = copy.deepcopy(xmm_pool)
                if exclude_self and canon_form in my_pool:
                    my_pool.remove(canon_form)
            else:
                return 1
        my_pool = list(my_pool)
        my_pool.sort()
        my_pool = [x for x in my_pool if 'SP' not in x]  # removing stack pointer register as it is unsupported token for ithemal
        return len(my_pool)


    def num_perturb_memory_choices(self, mem):  # this has to compute a number, so both base and index would be changed
        num_perturbations = 1
        base, index, scale, displacement = mem_utils.decompose_mem_str(mem)

        def num_perturb_scale_choices(scale, exclude_self = True):
            possibilities = [1, 2, 4, 8]
            if exclude_self and scale in possibilities:
                possibilities.remove(scale)
            return len(possibilities)

        num_perturbations *= self.num_perturb_register_choices(base, exclude_self=False)
        if index is not None:
            num_perturbations *= self.num_perturb_register_choices(index, exclude_self=False)
            num_perturbations *= num_perturb_scale_choices(scale, exclude_self=False)

        return num_perturbations

