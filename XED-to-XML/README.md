# XED to XML converter

The goal of this project is to create a machine-readable XML representation of the x86 instruction set that makes it easy to automatically generate assembler code for all instruction variants.
A particular use case for this is the automatic generation of microbenchmarks for measuring the performance of x86 instructions (see [uops.info](http://uops.info/)).

We currently only consider instruction variants that can be used in 64-bit mode and that use an effective address size of 64 bits.
The assembler code is intended to be used with the GNU assembler, using the [".intel_syntax noprefix" directive](http://www.sourceware.org/binutils/docs-2.12/as.info/i386-Syntax.html).
However, it should be relatively straightforward to adapt it to other assemblers.

## "Instruction variants" vs. XED iforms

We consider a definition of "instruction variant" that is more fine-grained than XED's iforms.
For example, we consider versions of an instruction that use 32-bit and 64-bit general-purpose registers (i.e., that use a different effective operand size) to be different "instruction variants"; however, both versions have the same XED iform.

The combination of an *XED iform* and the *agen*, *bcast*, *eosz*, *high8*, *immzero*, *mask*, *rep*, *rm*, *sae*, and *zeroing* attributes uniquely identifies an "instruction variant".


## Generating assembler code for all instruction variants

xmlToAssembler.py is a short Python script that shows how the instructions.xml file can be used to generate assembler code for all instruction variants.

## (Re)generating instructions.xml

```shell
git clone https://github.com/andreas-abel/XED-to-XML.git XED-to-XML
git clone https://github.com/intelxed/mbuild.git mbuild
cd XED-to-XML
./mfile.py
```

This would, for example, be necessary if the configuration files in datafiles/ were modified/updated.

## uops.info

At [uops.info](http://uops.info/), you can find a version of the instructions.xml file that is extended with latency, throughput, and port usage data for all generations of Intel's Core architecture.
