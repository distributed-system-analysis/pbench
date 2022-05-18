#!/usr/bin/env python3 -u
# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the LICENSE file in
# the root directory of this source tree. An additional grant of patent rights
# can be found in the PATENTS file in the same directory.
#
#-------------------------------------------------------------------------
#
# Copyright (c) 2019, NVIDIA CORPORATION. All rights reserved.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import namedtuple
import numpy as np
import sys

import torch

from fairseq import data, options, tasks, tokenizer, utils
from fairseq.sequence_generator import SequenceGenerator
from fairseq.meters import StopwatchMeter

from apply_bpe import BPE


Batch = namedtuple('Batch', 'srcs tokens lengths')
Translation = namedtuple('Translation', 'src_str hypos pos_scores alignments')


def buffered_read(buffer_size):
    buffer = []
    for src_str in sys.stdin:
        buffer.append(src_str.strip())
        if len(buffer) >= buffer_size:
            yield buffer
            buffer = []

    if len(buffer) > 0:
        yield buffer


def make_batches(lines, args, src_dict, max_positions, bpe=None):
    tokens = [
        tokenizer.Tokenizer.tokenize(src_str, src_dict, tokenize=tokenizer.tokenize_en, add_if_not_exist=False, bpe=bpe).long()
        for src_str in lines
    ]
    lengths = np.array([t.numel() for t in tokens])
    itr = data.EpochBatchIterator(
        dataset=data.LanguagePairDataset(tokens, lengths, src_dict),
        max_tokens=args.max_tokens,
        max_sentences=args.max_sentences,
        max_positions=max_positions,
    ).next_epoch_itr(shuffle=False)
    for batch in itr:
        yield Batch(
            srcs=[lines[i] for i in batch['id']],
            tokens=batch['net_input']['src_tokens'],
            lengths=batch['net_input']['src_lengths'],
        ), batch['id']


def main(args):
    if args.buffer_size < 1:
        args.buffer_size = 1
    if args.max_tokens is None and args.max_sentences is None:
        args.max_sentences = 1

    assert not args.sampling or args.nbest == args.beam, \
        '--sampling requires --nbest to be equal to --beam'
    assert not args.max_sentences or args.max_sentences <= args.buffer_size, \
        '--max-sentences/--batch-size cannot be larger than --buffer-size'

    print(args)

    use_cuda = torch.cuda.is_available() and not args.cpu

    # Setup task, e.g., translation
    task = tasks.setup_task(args)

    # Load ensemble
    print('| loading model(s) from {}'.format(args.path))
    model_paths = args.path.split(':')
    models, model_args = utils.load_ensemble_for_inference(model_paths, task, model_arg_overrides=eval(args.model_overrides))

    # Set dictionaries
    src_dict = task.source_dictionary
    tgt_dict = task.target_dictionary

    # Optimize ensemble for generation
    for model in models:
        model.make_generation_fast_(
            beamable_mm_beam_size=None if args.no_beamable_mm else args.beam,
            need_attn=args.print_alignment,
        )
        if args.fp16:
            model.half()

    # Initialize generator
    translator = SequenceGenerator(
        models, tgt_dict, beam_size=args.beam, stop_early=(not args.no_early_stop),
        normalize_scores=(not args.unnormalized), len_penalty=args.lenpen,
        unk_penalty=args.unkpen, sampling=args.sampling, sampling_topk=args.sampling_topk,
        minlen=args.min_len, sampling_temperature=args.sampling_temperature
    )

    if use_cuda:
        translator.cuda()

    # Load BPE codes file
    if args.bpe_codes:
        codes = open(args.bpe_codes, 'r')
        bpe = BPE(codes)
    # Load alignment dictionary for unknown word replacement
    # (None if no unknown word replacement, empty if no path to align dictionary)
    align_dict = utils.load_align_dict(args.replace_unk)

    def make_result(src_str, hypos):
        result = Translation(
            src_str='O\t{}'.format(src_str),
            hypos=[],
            pos_scores=[],
            alignments=[],
        )

        # Process top predictions
        for hypo in hypos[:min(len(hypos), args.nbest)]:
            hypo_tokens, hypo_str, alignment = utils.post_process_prediction(
                hypo_tokens=hypo['tokens'].int().cpu(),
                src_str=src_str,
                alignment=hypo['alignment'].int().cpu() if hypo['alignment'] is not None else None,
                align_dict=align_dict,
                tgt_dict=tgt_dict,
                remove_bpe=args.remove_bpe,
            )
            hypo_str = tokenizer.Tokenizer.detokenize(hypo_str, 'de')
            result.hypos.append('H\t{}\t{}'.format(hypo['score'], hypo_str))
            result.pos_scores.append('P\t{}'.format(
                ' '.join(map(
                    lambda x: '{:.4f}'.format(x),
                    hypo['positional_scores'].tolist(),
                ))
            ))
            result.alignments.append(
                'A\t{}'.format(' '.join(map(lambda x: str(utils.item(x)), alignment)))
                if args.print_alignment else None
            )
        return result

    gen_timer = StopwatchMeter()
    end2end_timer = StopwatchMeter()

    def process_batch(batch):
        tokens = batch.tokens
        lengths = batch.lengths

        if use_cuda:
            tokens = tokens.cuda()
            lengths = lengths.cuda()

        gen_timer.start()
        translations = translator.generate(
            tokens,
            lengths,
            maxlen=int(args.max_len_a * tokens.size(1) + args.max_len_b),
        )
        gen_timer.stop()

        return [make_result(batch.srcs[i], t) for i, t in enumerate(translations)]

    if args.buffer_size > 1:
        print('| Sentence buffer size:', args.buffer_size)
    print('| Type the input sentence and press return:')
    for inputs in buffered_read(args.buffer_size):
        indices = []
        results = []
        end2end_timer.start()
        for batch, batch_indices in make_batches(inputs, args, src_dict, models[0].max_positions(), bpe):
            indices.extend(batch_indices)
            results += process_batch(batch)

        for i in np.argsort(indices):
            result = results[i]
            print(result.src_str)
            for hypo, pos_scores, align in zip(result.hypos, result.pos_scores, result.alignments):
                print(hypo)
                print(pos_scores)
                if align is not None:
                    print(align)

        print('Model latency: {} s'.format(gen_timer.sum))
        gen_timer.reset()
        end2end_timer.stop()
        print('End-to-end translation time: {} s'.format(end2end_timer.sum))
        end2end_timer.reset()


if __name__ == '__main__':
    parser = options.get_generation_parser(interactive=True)
    args = options.parse_args_and_arch(parser)
    main(args)
