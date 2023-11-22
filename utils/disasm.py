#!/usr/bin/env python

import sys
import subprocess

def disassemble(hex, output_intel_syntax):
  args = []
  for i in range(0, len(hex), 2):
    byte = hex[i:i+2]
    args.append('0x'+byte)

  syntax_id = 1 if output_intel_syntax else 0
  
  cmd = 'echo %s | llvm-mc -disassemble -output-asm-variant=%d' % (' '.join(args), syntax_id)
  stdout = subprocess.check_output(cmd, shell=True)
  return stdout.decode('utf8')

if __name__ == '__main__':
  import argparse

  argparser = argparse.ArgumentParser(description='Disassemble hex encoding of machine code into assembly.')
  argparser.add_argument('hex', help='hex encoding of the basic block you want to disassemble')
  argparser.add_argument('--output-intel-syntax', action='store_true')

  args = argparser.parse_args()

  print(disassemble(args.hex, output_intel_syntax=args.output_intel_syntax))