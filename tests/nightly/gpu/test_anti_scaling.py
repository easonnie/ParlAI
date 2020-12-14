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
import pytest
import torch
from pytest_regressions.data_regression import DataRegressionFixture

import parlai.utils.testing as testing_utils
from parlai.core.message import Message
from parlai.core.opt import Opt
from parlai.core.teachers import register_teacher, Teacher
from parlai.zoo.bart.build import download as download_bart
from parlai.zoo.blender.blender_90M import download as download_blender


FIXED_MESSAGE_TASK = 'fixed_message'


@register_teacher(FIXED_MESSAGE_TASK)
class FixedMessageTeacher(Teacher):
    """
    Teacher agent that returns one fixed message.
    """

    def __init__(self, opt, shared=None):
        super().__init__(opt, shared)
        self.id = FIXED_MESSAGE_TASK

    def observe(self, observation):
        """
        No need to do anything here.
        """
        _ = observation
        pass

    def act(self):
        """
        Just respond with the sample message for the model agent to respond to.

        There's only one "turn" to this conversation.
        """
        return Message(
            {
                'id': self.id,
                'text': 'This is a test message.',
                'eval_labels': ['(NONE)'],
                'episode_done': True,
            }
        )


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
        'task': FIXED_MESSAGE_TASK,
        'num_examples': 1,
        'skip_generation': True,
        'hidden_loss_coeff': 1,
        'encoder_loss_coeff': 1,
        'pred_loss_coeff': 1,
        'task_loss_coeff': 1,
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

    @pytest.fixture(scope="function")
    def setup(self):
        """
        Download models in advance so that their opt files can be used with --init-opt.
        """

        random.seed()
        np.random.seed(0)
        torch.manual_seed(0)

        datapath = 'data'
        self._download_model(datapath)

        yield 'Setup complete'

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

    def test_wide_distillation_losses(
        self, setup, data_regression: DataRegressionFixture
    ):
        """
        Check losses for a model with "wide" (DistilBART-style) distillation loss terms.
        """
        model_name = self._get_agents()['wide_distillation']
        opt = Opt(
            {
                **self.BASE_OPT,
                **self._get_model_opt(),
                **self.WIDE_DISTILLATION_OPT,
                'model': f'{self.DISTILLATION_MODEL_PREFIX}:{model_name}',
            }
        )
        self._check_losses(opt=opt, data_regression=data_regression)

    def test_narrow_distillation_losses(
        self, setup, data_regression: DataRegressionFixture
    ):
        """
        Check losses for a model with "narrow" (TinyBERT-style) distillation loss terms.
        """

        # precise_mode = False
        # # Turn this on to check the loss terms for TinyBERT-style distillation, which
        # # relies upon weights being initialized in a particular way. Won't work on
        # # CircleCI machines
        # TODO: either reenable or remove

        model_name = self._get_agents()['narrow_distillation']
        opt = Opt(
            {
                **self.BASE_OPT,
                **self._get_model_opt(),
                **self.NARROW_DISTILLATION_OPT,
                'model': f'{self.DISTILLATION_MODEL_PREFIX}:{model_name}',
            }
        )
        self._check_losses(opt=opt, data_regression=data_regression)

    def _check_losses(self, opt: Opt, data_regression: DataRegressionFixture):
        """
        Calculate and check distillation loss terms.

        Given the input opt, run eval and check each of the loss terms to make sure that
        they match what is expected.
        """
        valid, _ = testing_utils.eval_model(opt, skip_test=True)
        losses = {loss_name: metric.value() for loss_name, metric in valid.items()}
        data_regression.check(losses)


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
