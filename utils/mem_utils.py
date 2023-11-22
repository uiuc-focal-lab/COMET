import re

def decompose_mem_str(mem):
    base = index = None
    displacement = 0
    scale = 1
    for c in re.split(r'\+|-', re.search(r'\[(.*)\]', mem).group(1)):
        if '0x' in c:
            displacement = int(c, 0)
            if '-0x' in mem:
                displacement = -displacement
        elif '*' in c:
            index, scale = c.split('*')
            scale = int(scale)
            index = index.upper()
        else:
            base = c.upper()
    return base, index, scale, displacement

def combine_mem(base, index, scale, displacement):
    mem_str = base
    if base == None:
        mem_str = ''
    if index != None:
        mem_str += ('+'+index+'*'+str(scale))
    displacement = hex(displacement)
    # if displacement != '0x0':  # there is no harm in keeping even 0x0 displacement in the memory
    if '-0x' in displacement:
        mem_str += ('-'+displacement[1:])
    else:
        mem_str += ('+'+displacement)
    mem_str = '[' + mem_str + ']'

    return mem_str
