import binascii
import tempfile
import subprocess
import os
import logging
import sys
import argparse
import codecs

START_MARKER = binascii.unhexlify('bb6f000000646790')  #.decode('hex')  # convert hex string to ascii?
END_MARKER = binascii.unhexlify('bbde000000646790')  #.decode('hex')


def read_basic_block(fname1):
    with open(fname1, 'rb') as f:
        code = f.read(-1)
    start_pos = code.index(START_MARKER)
    if start_pos == -1:
        raise ValueError('START MARKER NOT FOUND')

    end_pos = code.index(END_MARKER)
    if end_pos == -1:
        raise ValueError('END MARKER NOT FOUND')

    block_binary = code[start_pos+len(START_MARKER):end_pos]
    return binascii.b2a_hex(block_binary)


def get_hex_of_code(code):
    _, tmp = tempfile.mkstemp()  # used for disassembly
    _, fname = tempfile.mkstemp()
    success = intel_compile(code, tmp, fname)
    # if not success:
    #     success = att_compile(code)
    # if not success:
    #     success, nasm_output = nasm_compile(code, fname)

    if not success:
        if os.path.exists(fname):
            os.unlink(fname)
        raise ValueError(f'Could not assemble code {code}')

    res = read_basic_block(fname)
    # os.unlink(fname)
    return res

def get_hex_of_code_att(code):
    _, tmp = tempfile.mkstemp()  # used for disassembly
    _, fname = tempfile.mkstemp()
    success = att_compile(code, tmp, fname)
    # if not success:
    #     success, as_att_output = att_compile(code, fname)
    # if not success:
    #     success, nasm_output = nasm_compile(code, fname)

    if not success:
        if os.path.exists(fname):
            os.unlink(fname)
        raise ValueError(f'Could not assemble code {code}')  #.\nAssembler outputs:\n\n{}'.format('\n\n'.join([
        #     'as (Intel syntax): {}'.format(as_intel_output[1]),
            # 'as (AT&T syntax): {}'.format(as_att_output[1]),
            # 'nasm: {}'.format(nasm_output[1]),
        # ])))

    res = read_basic_block(fname)
    # os.unlink(fname)
    return res


def intel_compile(code, tmp, fname):

    with open(tmp, 'w+') as f:
        f.write('''
         .text
        .global main
        main:
        .intel_syntax noprefix

        mov ebx, 111
        .byte 0x64, 0x67, 0x90

        {}

        mov ebx, 222
        .byte 0x64, 0x67, 0x90
        '''.format(code))

    p = subprocess.run(['as', tmp, '-o', fname])
    return p.returncode == 0  #, output

def att_compile(code, tmp1, fname1):
    with open(tmp1, 'w+') as f:
        f.write('''
         .text
        .global main
        main:

        movl $111, %ebx
        .byte 0x64, 0x67, 0x90

        {}

        mov $222, %ebx
        .byte 0x64, 0x67, 0x90
        '''.format(code))

#
    #
    #;
    # print(code)
    p = subprocess.run(['as', tmp1, '-o', fname1])
    return p.returncode == 0

    # p = subprocess.Popen(['as', '-o', output], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # c = '''
    #     .text
    #     .global main
    #     main:
    #
    #     movl $111, %ebx
    #     .byte 0x64, 0x67, 0x90
    #
    #     {}
    #
    #     mov $222, %ebx
    #     .byte 0x64, 0x67, 0x90
    # '''.format(code)
    # output = p.communicate(c)
    # p.wait()
    # return p.returncode == 0, output

def nasm_compile(code, output):
    tmp = tempfile.NamedTemporaryFile()
    with open(tmp.name, 'w+') as f:
        f.write('''
	SECTION .text
        global main
        main:

        mov ebx, 111
        db 0x64, 0x67, 0x90

        {}

        mov ebx, 222
        db 0x64, 0x67, 0x90
        '''.format(code))

    p = subprocess.Popen(['nasm', '-o', output, tmp.name], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = p.communicate()
    p.wait()
    tmp.close()
    return p.returncode == 0, output

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("code", type=str)
    args = parser.parse_args()
    code = args.code
    print(get_hex_of_code_att(code))


if __name__ == '__main__':
    main()
