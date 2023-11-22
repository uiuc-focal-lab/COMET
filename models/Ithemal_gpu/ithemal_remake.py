# import the required modules
import torch
import torch.nn as nn
import subprocess
import xml.etree.ElementTree as ET
import itertools
import time
import multiprocessing as mp
import sys
sys.path.append('./models/Ithemal_gpu')
from get_hex_gpu import get_hex_of_code
import token2hotidx
import os
_TOKENIZER = os.path.join(os.getenv('COMET_HOME'), 'models/Ithemal_gpu/data_collection/build/bin/tokenizer')  # this is where the tokenizer lives
device = 'cpu' #'cpu' #if torch.cuda.is_available() else 'cpu'

# here is a complete description of the lifecycle of a basic block within Ithemal:
# Ithemal takes as input a basic block assembly code
# This assembly code is converted to its hex form (done)
# hex form -> xml form (done)
# xml form -> token encodings (done)
# token encodings ----embedding_layer----> embedding for each token (done)
# token embeddings ----tokenLSTM----> embedding for instructions
# instruction embeddings ----instLSTM----> embedding for basic block
# embedding for basic block ----Linear----> throughput prediction


# define the model architecture for Ithemal
class Ithemal(nn.Module):
    def __init__(self, model_file):
        super().__init__()

        # 4 layers in the model
        # Embedding layer
        self.final_embeddings = nn.Embedding(628, 256)  #.to(device)
        self.token_rnn = nn.LSTM(input_size=256, hidden_size=256, batch_first=True).to(device)
        self.instr_rnn = nn.LSTM(input_size=256, hidden_size=256, batch_first=True).to(device)
        self.linear = nn.Linear(in_features=256, out_features=1, bias=True).to(device)
        self.load_state_dict(torch.load(model_file, map_location=torch.device('cpu')))  # this file contains all the model weights
        self.eval()  # setting model to eval mode
        self.token_to_hot_idx = token2hotidx.token_to_hot_idx

    def forward(self, input_basic_blocks):  # a list of basic blocks will be passed
        if isinstance(input_basic_blocks, str):
            input_basic_blocks = [input_basic_blocks]  # we accept a list of basic blocks as input

        token_embedding = []
        num_insts = []

        # attempt at multiprocessing! Fails because the transfer of gradient requiring embeddings is problematic
        # pool = mp.Pool(mp.cpu_count()-1)
        # results = pool.starmap_async(self.create_embeddings, [(input_basic_blocks, idx) for idx in range(len(input_basic_blocks))]).get()
        # pool.close()
        # pool.join()
        # results.sort(key=lambda a: a[2])
        #
        # for res in results:
        #     token_embedding.append(res[0])  # my_token_embeddings
        #     num_insts.append(len(res[1]))  # my_token_encodings
        # t1 = time.time()
        for idx in range(len(input_basic_blocks)):
            my_token_embeddings, my_token_encodings, _ = self.create_embeddings(input_basic_blocks, idx)
            token_embedding.append(my_token_embeddings)  # token embedding tensor inside tensor for each instruction; each instruction tensor inside list of instructions in basic block, inside list of basic blocks
            num_insts.append(len(my_token_encodings))  # there are as many encodings as the number of instructions in the basic block
        # print(f'time for creating embeddings for {len(input_basic_blocks)} samples:', time.time()-t1)
        # pass the token_embedding into token_rnn, instr_rnn and linear layers to return throughputs of all the basic blocks
        # flattening the token_embedding list to make a list of tensors for instructions
        # print('token_embedding:', token_embedding)
        # t2 = time.time()
        inst_tensors = list(itertools.chain.from_iterable(token_embedding))
        # print("inst tensors:", inst_tensors)
        inst_tensors_pack = nn.utils.rnn.pack_sequence(inst_tensors, enforce_sorted=False)  # this creates a pack of variable length tensors for instructions
        # print('inst_tensors_pack', inst_tensors_pack)
        _, (token_rnn_output, _) = self.token_rnn(inst_tensors_pack.to(device))  # the h0, c0 default to zero (also there in the original codebase)
        # the token_rnn_output is for each instruction in the batch, each element of hidden_dim size
        # need to stack the outputs for instructions of a basic block
        # print()
        # print('token rnn output:', token_rnn_output)
        # print('token rnn output shape:', token_rnn_output.shape)
        # exit(0)
        token_rnn_output = token_rnn_output.squeeze(0).to('cpu')
        first_inst_num = 0
        bb_tensors = []
        for my_num_insts in num_insts:
            bb_tensors.append(token_rnn_output[first_inst_num:(first_inst_num+my_num_insts)])
            first_inst_num += my_num_insts
        # print(bb_tensors[0])
        bb_tensors_pack = nn.utils.rnn.pack_sequence(bb_tensors, enforce_sorted=False)  # this creates a pack of variable length tensors for basic blocks
        _, (inst_rnn_output, _) = self.instr_rnn(bb_tensors_pack.to(device))  # again h0, c0 default to 0; this is 256 length tensor for each basic block
        # print()
        # print('inst rnn output:', inst_rnn_output)
        # print('inst rnn output shape:', inst_rnn_output.shape)
        # exit(0)
        inst_rnn_output = inst_rnn_output.squeeze(0)
        # passing through linear layer
        tp_tensor = self.linear(inst_rnn_output)  # this will be a tensor of predicted throughput values
        # print(tp_tensor)
        # print(f'time for creating tp for {len(input_basic_blocks)} samples:', time.time()-t2)
        return tp_tensor.flatten().to('cpu').tolist()  # returns a list of throughput predictions

    def create_embeddings(self, input_basic_blocks, idx):
        bb = input_basic_blocks[idx]
        my_hex = self.get_hex_bb(bb)  # this will return the hex of the basic block
        my_xml = self.get_xml_hex(my_hex)  # convert the hex to xml
        my_token_encodings = self.get_tokens_xml(
            my_xml, idx)  # get tokens from xml of basic block; token lists of all instructions are there in a list
        my_token_embeddings = []  # this contains the embeddings of all the tokens in all the instructions of the basic block
        for token_list in my_token_encodings:  # this is going over all the tokens in each instruction
            my_token_embeddings.append(self.final_embeddings(torch.LongTensor(token_list)))  # .to(device)).to('cpu'))
        return my_token_embeddings, my_token_encodings, idx

    # input preprocessing system

    def get_hex_bb(self, bb):
        return get_hex_of_code(bb)

    def get_xml_hex(self, my_hex):
        # print('hex type:', type(my_hex.decode("utf-8")))
        return subprocess.check_output([_TOKENIZER, my_hex, '--token']).decode('ascii')

    def get_tokens_xml(self, my_xml, idx):
        def hot_idxify(elem):
            if elem not in self.token_to_hot_idx:
                raise ValueError(f'Ithemal does not yet support UNK tokens! index: {idx}')
            return self.token_to_hot_idx[elem]

        block_root = ET.fromstring(my_xml)
        raw_instrs = []
        for instr in block_root:
            raw_instr = []
            opcode = int(instr.find('opcode').text)
            raw_instr.extend([opcode, '<SRCS>'])
            for src in instr.find('srcs'):
                if src.find('mem') is not None:
                    raw_instr.append('<MEM>')
                    for mem_op in src.find('mem'):
                        raw_instr.append(int(mem_op.text))
                    raw_instr.append('</MEM>')
                else:
                    raw_instr.append(int(src.text))

            raw_instr.append('<DSTS>')
            for dst in instr.find('dsts'):
                if dst.find('mem') is not None:
                    raw_instr.append('<MEM>')
                    for mem_op in dst.find('mem'):
                        raw_instr.append(int(mem_op.text))
                    raw_instr.append('</MEM>')
                else:
                    raw_instr.append(int(dst.text))

            raw_instr.append('<END>')
            raw_instrs.append(list(map(hot_idxify, raw_instr)))
        return raw_instrs


Ithemal_gpu_model_original = Ithemal(os.path.join(os.getenv('COMET_HOME'), 'models/Ithemal_gpu/my_model'))
