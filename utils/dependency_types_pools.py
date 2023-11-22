import copy

def raw(write_i, read_j):  # returns raw_list: list of set of operands in given instructions which have a RAW dependency
    # get the write pool of i
    # write_i = self.instructions[i].get_write_pool()  # this is of form: {reg/mem name: [opnd codes for it]}
    # get the read pool of j
    # read_j = self.instructions[j].get_read_pool()
    # intersect the two to get raw_list
    keys_i = set(list(write_i.keys()))
    keys_j = set(list(read_j.keys()))
    common_keys = list(keys_i.intersection(keys_j))
    # encode them in the desired form
    raw_list = []
    for common in common_keys:
        to_add = copy.deepcopy(write_i[common]) + copy.deepcopy(read_j[common])
        to_add = combine_b_i(to_add)
        raw_list.append(to_add)
    return raw_list

def war(read_i, write_j):  # returns war_list: list of set of operands in given instructions which have a WAR dependency
    # get the read pool of i
    # read_i = self.instructions[i].get_read_pool()  # this is of form: {reg/mem name: [opnd codes for it]}
    # get the write pool of j
    # write_j = self.instructions[j].get_write_pool()
    # intersect the two to get raw_list
    keys_i = set(list(read_i.keys()))
    keys_j = set(list(write_j.keys()))
    common_keys = list(keys_i.intersection(keys_j))
    # encode them in the desired form
    war_list = []
    for common in common_keys:
        to_add = copy.deepcopy(read_i[common]) + copy.deepcopy(write_j[common])
        to_add = combine_b_i(to_add)
        war_list.append(to_add)
    return war_list

def waw(write_i, write_j):  # returns waw_list: list of set of operands in given instructions which have a WAW dependency
    # get the write pool of i
    # write_i = self.instructions[i].get_write_pool()  # this is of form: {reg/mem name: [opnd codes for it]}
    # get the write pool of j
    # write_j = self.instructions[j].get_write_pool()
    # intersect the two to get raw_list
    keys_i = set(list(write_i.keys()))
    keys_j = set(list(write_j.keys()))
    common_keys = list(keys_i.intersection(keys_j))
    # encode them in the desired form
    waw_list = []
    for common in common_keys:
        to_add = copy.deepcopy(write_i[common]) + copy.deepcopy(write_j[common])
        to_add = combine_b_i(to_add)
        waw_list.append(to_add)
    return waw_list

def combine_b_i(to_add):
    to_add.sort()  # this would sort a list in alphabetical order
    to_remove = []
    to_include = []
    idx = 0
    while idx < len(to_add):
        op = to_add[idx]
        if idx + 1 < len(to_add) and (op + '_b') == to_add[idx + 1]:
            to_remove.append(to_add[idx+1])
            if idx + 2 < len(to_add) and (op + '_i') == to_add[idx + 2]:
                to_remove.append(to_add[idx+2])
            idx += 3
        elif idx + 1 < len(to_add) and (op + '_i') == to_add[idx + 1]:
            to_remove.append(to_add[idx+1])
            idx += 2
        elif '_b' in op and (idx + 1 < len(to_add) and (op[:-1] + 'i') == to_add[idx + 1]):
            to_remove.append(op)
            to_remove.append(to_add[idx+1])
            to_include.append(op + '_i')
            idx += 2
        else:
            idx += 1
    to_add.extend(to_include)
    to_add = [x for x in to_add if x not in to_remove]
    return to_add


    # if opnd_{i}_{j} in to_add, then neither of opnd_{i}_{j}_b or opnd_{i}_{j}_i should be in to_add
    # elif opnd_{i}_{j}_b and opnd_{i}_{j}_i in to_add then opnd_{i}_{j}_b_i should be there and not the previous ones

