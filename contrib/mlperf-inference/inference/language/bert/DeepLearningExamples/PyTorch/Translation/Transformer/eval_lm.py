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

import numpy as np
import torch

from fairseq import data, options, progress_bar, tasks, utils
from fairseq.meters import StopwatchMeter, TimeMeter
from fairseq.sequence_scorer import SequenceScorer


def main(args):
    assert args.path is not None, '--path required for evaluation!'

    args.tokens_per_sample = getattr(args, 'tokens_per_sample', 1024)
    print(args)

    use_cuda = torch.cuda.is_available() and not args.cpu

    # Load dataset splits
    task = tasks.setup_task(args)
    task.load_dataset(args.gen_subset)
    print('| {} {} {} examples'.format(args.data, args.gen_subset, len(task.dataset(args.gen_subset))))

    # Load ensemble
    print('| loading model(s) from {}'.format(args.path))
    models, _ = utils.load_ensemble_for_inference(args.path.split(':'), task)

    # Optimize ensemble for generation and set the source and dest dicts on the model (required by scorer)
    for model in models:
        model.make_generation_fast_()
        if args.fp16:
            model.half()

    assert len(models) > 0

    itr = data.EpochBatchIterator(
        dataset=task.dataset(args.gen_subset),
        max_tokens=args.max_tokens or 36000,
        max_sentences=args.max_sentences,
        max_positions=models[0].max_positions(),
        num_shards=args.num_shards,
        shard_id=args.shard_id,
        ignore_invalid_inputs=True,
    ).next_epoch_itr(shuffle=False)

    gen_timer = StopwatchMeter()
    scorer = SequenceScorer(models, task.target_dictionary)
    if use_cuda:
        scorer.cuda()

    score_sum = 0.
    count = 0

    if args.remove_bpe is not None:
        bpe_cont = args.remove_bpe.rstrip()
        bpe_toks = set(i for i in range(len(task.dictionary)) if task.dictionary[i].endswith(bpe_cont))
        bpe_len = len(bpe_cont)
    else:
        bpe_toks = None
        bpe_len = 0

    with progress_bar.build_progress_bar(args, itr) as t:
        results = scorer.score_batched_itr(t, cuda=use_cuda, timer=gen_timer)
        wps_meter = TimeMeter()
        for _, src_tokens, __, hypos in results:
            for hypo in hypos:
                pos_scores = hypo['positional_scores']

                skipped_toks = 0
                if bpe_toks is not None:
                    for i in range(len(hypo['tokens']) - 1):
                        if hypo['tokens'][i].item() in bpe_toks:
                            skipped_toks += 1
                            pos_scores[i + 1] += pos_scores[i]
                            pos_scores[i] = 0

                inf_scores = pos_scores.eq(float('inf')) | pos_scores.eq(float('-inf'))
                if inf_scores.any():
                    print('| Skipping tokens with inf scores:',
                          task.target_dictionary.string(hypo['tokens'][inf_scores.nonzero()]))
                    pos_scores = pos_scores[(~inf_scores).nonzero()]
                score_sum += pos_scores.sum()
                count += pos_scores.numel() - skipped_toks

                if args.output_word_probs:
                    w = ''
                    word_prob = []
                    for i in range(len(hypo['tokens'])):
                        w_ind = hypo['tokens'][i].item()
                        w += task.dictionary[w_ind]
                        if bpe_toks is not None and w_ind in bpe_toks:
                            w = w[:-bpe_len]
                        else:
                            word_prob.append((w, pos_scores[i].item()))
                            w = ''
                    print('\t'.join('{} [{:2f}]'.format(x[0], x[1]) for x in word_prob))

            wps_meter.update(src_tokens.size(0))
            t.log({'wps': round(wps_meter.avg)})

    avg_nll_loss = -score_sum / count
    print('| Evaluated {} tokens in {:.1f}s ({:.2f} tokens/s)'.format(gen_timer.n, gen_timer.sum, 1. / gen_timer.avg))
    print('| Loss: {:.4f}, Perplexity: {:.2f}'.format(avg_nll_loss, np.exp(avg_nll_loss)))


if __name__ == '__main__':
    parser = options.get_eval_lm_parser()
    args = options.parse_args_and_arch(parser)
    main(args)
