#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Test code for anti-scaling transformer/generator models.
"""

import random
import unittest
from abc import ABC, abstractmethod
from typing import Dict

import numpy as np
import torch

import parlai.utils.testing as testing_utils
from parlai.core.opt import Opt
from parlai.zoo.bart.build import download as download_bart
from parlai.zoo.blender.blender_90M import download as download_blender


class AbstractTestDistillation(ABC, unittest.TestCase):
    """
    Test agents for distilling Transformer generator models.
    """

    BASE_OPT = {
        'allow_missing_init_opts': True,
        'init_model': '',
        'model_file': '',
        'n_encoder_layers': 1,
        'n_decoder_layers': 1,
        'task': 'blended_skill_talk',
    }
    WIDE_DISTILLATION_OPT = {'copy_teacher_weights': True}
    NARROW_DISTILLATION_OPT = {
        'embedding_size': 64,
        'ffn_size': 256,
        'embedding_loss_coeff': 1,
        'self_attn_loss_coeff': 1,
        'enc_dec_attn_loss_coeff': 1,
    }
    DISTILLATION_MODEL_PREFIX = 'projects.anti_scaling.distillation'

    def setUp(self):
        """
        Download models in advance so that their opt files can be used with --init-opt.
        """
        datapath = 'data'
        self._download_model(datapath)

    @abstractmethod
    def _download_model(self, datapath: str):
        """
        Download the model to calculate distillation losses from.
        """

    def _get_model_file(self) -> str:
        """
        Return the model file for this model type.
        """

    def _get_model_opt(self) -> Dict[str, str]:
        """
        Return opt specifically for this model type.
        """
        model_file = self._get_model_file()
        return {
            'dict_file': f'{model_file}.dict',
            'init_opt': f'{model_file}.opt',
            'teacher_model': model_file,
        }

    @abstractmethod
    def _get_agents(self) -> Dict[str, str]:
        """
        Return a dict of strings of agent classes specifically for this model type.

        'wide_distillation' and 'narrow_distillation' keys required.
        """

    def test_distillation_losses(self):
        """
        Check the sum of distillation losses.

        Make sure that the sum of all distillation losses from one pass through the
        student and teacher models is as expected.
        """

        precise_mode = False
        # Turn this on to check the loss terms for TinyBERT-style distillation, which
        # relies upon weights being initialized in a particular way. Won't work on
        # CircleCI machines

        random.seed()
        np.random.seed(0)
        torch.manual_seed(0)

        opts_and_desired_losses = [
            (
                self._get_model_opt(),
                self.WIDE_DISTILLATION_OPT,
                self._get_agents()['wide_distillation'],
                False,
                DESIRED_LOSSES,
            ),
            (
                self._get_model_opt(),
                self.NARROW_DISTILLATION_OPT,
                self._get_agents()['narrow_distillation'],
                True,
                DESIRED_LOSSES,
            ),
        ]
        for (
            model_opt,
            distillation_opt,
            model_name,
            is_tinybert_style,
            desired_losses,
        ) in opts_and_desired_losses:
            opt = {
                **self.BASE_OPT,
                **model_opt,
                **distillation_opt,
                'model': f'{self.DISTILLATION_MODEL_PREFIX}:{model_name}',
                'num_examples': 1,
                'skip_generation': True,
                'hidden_loss_coeff': 1,
                'encoder_loss_coeff': 1,
                'pred_loss_coeff': 1,
                'task_loss_coeff': 1,
            }
            valid, _ = testing_utils.eval_model(Opt(opt), skip_test=True)
            if not is_tinybert_style or precise_mode:
                for loss_name, desired_loss in desired_losses.items():
                    if np.isinf(desired_loss):
                        self.assertTrue(np.isinf(valid[loss_name].value()))
                    else:
                        if abs(valid[loss_name].value() / desired_loss - 1) > 0.01:
                            raise ValueError(
                                f"""\
Error in matching {loss_name} for {model_name}!
Desired value: {desired_loss}
Actual value: {valid[loss_name].value()}"""
                            )


class TestTransformerDistillation(AbstractTestDistillation):
    """
    Test agents for distilling 'transformer/generator' models specifically.
    """

    def _download_model(self, datapath: str):
        download_blender(datapath)

    def _get_model_file(self) -> str:
        return 'data/models/blender/blender_90M/model'  # BlenderBot90M

    def _get_agents(self) -> Dict[str, str]:
        return {
            'wide_distillation': 'DistillTransformerAgent',
            'narrow_distillation': 'DistillNarrowTransformerAgent',
        }


class TestBartDistillation(AbstractTestDistillation):
    """
    Test agents for distilling 'transformer/generator' models specifically.
    """

    def _download_model(self, datapath: str):
        download_bart(datapath)

    def _get_model_file(self) -> str:
        return 'data/models/bart/bart_large/model'

    def _get_agents(self) -> Dict[str, str]:
        return {
            'wide_distillation': 'DistillBartAgent',
            'narrow_distillation': 'DistillNarrowBartAgent',
        }


if __name__ == '__main__':
    unittest.main()
