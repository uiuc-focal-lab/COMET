#!/usr/bin/env python3

import xml.etree.ElementTree as ET
from collections import defaultdict
from operator import itemgetter

def main():
   root = ET.parse('instructions.xml')

   attributes = ['iform', 'agen', 'bcast', 'eosz', 'high8', 'immzero', 'mask', 'rep', 'rm', 'sae', 'zeroing']
   allIformCombinations = [itemgetter(*attributes)(defaultdict(lambda: 0, instrNode.attrib)) for instrNode in root.iter('instruction')]

   assert(len(allIformCombinations) == len(set(allIformCombinations)))

if __name__ == "__main__":
    main()
