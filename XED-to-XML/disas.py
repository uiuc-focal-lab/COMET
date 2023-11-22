#!/usr/bin/env python3

import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict

import xed

# Disassembles a binary and finds for each instruction the corresponding entry in the XML file.
# With the -iacaMarkers option, only the parts of the code that are between the IACA markers are considered.
def main():
   parser = argparse.ArgumentParser(description='Disassembler')
   parser.add_argument('xmlfile', help='XML file')
   parser.add_argument('filename', help='File to be disassembled')
   parser.add_argument('-iacaMarkers', help='Use IACA markers', action='store_true')
   args = parser.parse_args()

   disas = xed.disasFile(args.filename, useIACAMarkers=args.iacaMarkers)

   root = ET.parse(args.xmlfile)

   iformToXML = defaultdict(list)
   for XMLInstr in root.iter('instruction'):
      iformToXML[XMLInstr.attrib['iform']].append(XMLInstr)

   for instrD in disas:
      matchingEntries = [XMLInstr.attrib['string'] for XMLInstr in iformToXML[instrD['iform']] if xed.matchXMLAttributes(instrD, XMLInstr.attrib)]
      if not matchingEntries:
         print('No XML entry found for ' + str(instrD))
      elif len(matchingEntries) > 1:
         print('Multiple XML entries found for ' + str(instrD) + ': ' + str(matchingEntries))
      else:
         print(str(instrD) + ': ' + matchingEntries[0])

if __name__ == "__main__":
    main()
