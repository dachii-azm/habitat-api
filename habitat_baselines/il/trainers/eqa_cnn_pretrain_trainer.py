#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import time

import numpy as np
import torch
from torch.utils.data import DataLoader

import habitat
from habitat import logger
from habitat_baselines.common.base_il_trainer import BaseILTrainer
from habitat_baselines.common.baseline_registry import baseline_registry
from habitat_baselines.common.tensorboard_utils import TensorboardWriter
from habitat_baselines.il.data.eqa_cnn_pretrain_data import (
    EQACNNPretrainDataset,
)
from habitat_baselines.il.models.models import MultitaskCNN


@baseline_registry.register_trainer(name="eqa-cnn-pretrain")
class EQACNNPretrainTrainer(BaseILTrainer):
    r"""Trainer class for Encoder-Decoder for Feature Extraction
    used in EmbodiedQA (Das et. al.;CVPR 2018)
    Paper: https://embodiedqa.org/paper.pdf.
    """
    supported_tasks = ["EQA-v0"]

    def __init__(self, config=None):
        super().__init__(config)

        self.device = (
            torch.device("cuda", self.config.TORCH_GPU_ID)
            if torch.cuda.is_available()
            else torch.device("cpu")
        )

        assert torch.cuda.is_available(), "Cuda-enabled GPU required"
        torch.cuda.set_device(config.TORCH_GPU_ID)

        if config is not None:
            logger.info(f"config: {config}")

    def train(self) -> None:
        r"""Main method for training Navigation model of EQA.

        Returns:
            None
        """
        config = self.config

        env = habitat.Env(config=config.TASK_CONFIG)

        eqa_cnn_pretrain_dataset = EQACNNPretrainDataset(env, config)

        train_loader = DataLoader(
            eqa_cnn_pretrain_dataset,
            batch_size=config.IL.EQACNNPretrain.batch_size,
            shuffle=True,
        )

        logger.info(
            "[ train_loader has {} samples ]".format(
                len(eqa_cnn_pretrain_dataset)
            )
        )

        #possibility to num_class for vqa is 40
        #default num_classes for eqa_cnn is 41
        model = MultitaskCNN(num_classes=41)
        model.train().to(self.device)

        optim = torch.optim.Adam(
            filter(lambda p: p.requires_grad, model.parameters()),
            lr=float(config.IL.EQACNNPretrain.lr),
        )

        depth_loss = torch.nn.SmoothL1Loss()
        ae_loss = torch.nn.SmoothL1Loss()
        seg_loss = torch.nn.CrossEntropyLoss()

        epoch, t = 1, 0
        with TensorboardWriter(
            config.TENSORBOARD_DIR, flush_secs=self.flush_secs
        ) as writer:
            while epoch <= int(config.IL.EQACNNPretrain.max_epochs):
                start_time = time.time()
                avg_loss = 0.0

                for batch in train_loader:
                    t += 1

                    idx, rgb, depth, seg = batch

                    optim.zero_grad()

                    rgb = rgb.to(self.device)
                    depth = depth.to(self.device)
                    seg = seg.to(self.device)

                    out_seg, out_depth, out_ae = model(rgb)

                    l1 = seg_loss(out_seg, seg.long())
                    l2 = ae_loss(out_ae, rgb)
                    l3 = depth_loss(out_depth, depth)

                    loss = l1 + (10 * l2) + (10 * l3)

                    avg_loss += loss.item()

                    if t % config.LOG_INTERVAL == 0:
                        logger.info(
                            "[ Epoch: {}; iter: {}; loss: {} ]".format(
                                epoch, t, loss.item()
                            )
                        )

                        writer.add_scalar("total_loss", loss, t)
                        writer.add_scalars(
                            "individual_losses",
                            {"seg_loss": l1, "ae_loss": l2, "depth_loss": l3},
                            t,
                        )

                    loss.backward()
                    optim.step()

                end_time = time.time()
                time_taken = "{:.1f}".format((end_time - start_time) / 60)
                avg_loss = avg_loss / len(train_loader)

                logger.info(
                    "[ Epoch {} completed. Time taken: {} minutes. ]".format(
                        epoch, time_taken
                    )
                )
                logger.info("[ Average loss: {:.2f} ]".format(avg_loss))

                print("-----------------------------------------")

                if epoch % config.CHECKPOINT_INTERVAL == 0:
                    self.save_checkpoint(
                        model.state_dict(), "epoch_{}.ckpt".format(epoch)
                    )

                epoch += 1

    def _eval_checkpoint(
        self,
        checkpoint_path: str,
        writer: TensorboardWriter,
        checkpoint_index: int = 0,
    ) -> None:
        r"""Evaluates a single checkpoint.

        Args:
            checkpoint_path: path of checkpoint
            writer: tensorboard writer object for logging to tensorboard
            checkpoint_index: index of cur checkpoint for logging

        Returns:
            None
        """
        config = self.config

        config.defrost()
        config.TASK_CONFIG.DATASET.SPLIT = self.config.EVAL.SPLIT
        config.freeze()

        env = habitat.Env(config=config.TASK_CONFIG)

        eqa_cnn_pretrain_dataset = EQACNNPretrainDataset(
            env, config, mode="val"
        )

        eval_loader = DataLoader(
            eqa_cnn_pretrain_dataset,
            batch_size=config.IL.EQACNNPretrain.batch_size,
            shuffle=False,
        )

        logger.info(
            "[ eval_loader has {} samples ]".format(
                len(eqa_cnn_pretrain_dataset)
            )
        )
        #possibility to num_classes for vqa is 40
        #default num_classes for eqa_cnn is 41
        model = MultitaskCNN(num_classes=41)

        state_dict = torch.load(checkpoint_path)
        model.load_state_dict(state_dict)

        model.to(self.device).eval()

        depth_loss = torch.nn.SmoothL1Loss()
        ae_loss = torch.nn.SmoothL1Loss()
        seg_loss = torch.nn.CrossEntropyLoss()

        np.random.seed(2)
        #default size is (41, 3)
        self.colors = np.random.randint(255, size=(41, 3))

        t = 0
        avg_loss = 0.0
        avg_l1 = 0.0
        avg_l2 = 0.0
        avg_l3 = 0.0

        with torch.no_grad():
            for batch in eval_loader:
                t += 1

                idx, rgb, depth, seg = batch
                rgb = rgb.to(self.device)
                depth = depth.to(self.device)
                seg = seg.to(self.device)

                out_seg, out_depth, out_ae = model(rgb)
                l1 = seg_loss(out_seg, seg.long())
                l2 = ae_loss(out_ae, rgb)
                l3 = depth_loss(out_depth, depth)

                loss = l1 + (10 * l2) + (10 * l3)

                avg_loss += loss.item()
                avg_l1 += l1.item()
                avg_l2 += l2.item()
                avg_l3 += l3.item()

                if t % config.LOG_INTERVAL == 0:
                    logger.info(
                        "[ Iter: {}; loss: {} ]".format(t, loss.item()),
                    )

                if config.EVAL_SAVE_RESULTS:
                    if t % config.EVAL_SAVE_RESULTS_INTERVAL == 0:

                        self._save_eqa_cnn_pretrain_results(
                            checkpoint_index,
                            idx,
                            rgb,
                            out_ae,
                            seg,
                            out_seg,
                            depth,
                            out_depth,
                        )

        avg_loss /= len(eval_loader)
        avg_l1 /= len(eval_loader)
        avg_l2 /= len(eval_loader)
        avg_l3 /= len(eval_loader)

        writer.add_scalar("avg val total loss", avg_loss, checkpoint_index)
        writer.add_scalars(
            "avg val individual_losses",
            {"seg_loss": avg_l1, "ae_loss": avg_l2, "depth_loss": avg_l3},
            checkpoint_index,
        )

        logger.info("[ Average loss: {:.3f} ]".format(avg_loss))
        logger.info("[ Average seg loss: {:.3f} ]".format(avg_l1))
        logger.info("[ Average autoencoder loss: {:.4f} ]".format(avg_l2))
        logger.info("[ Average depthloss: {:.4f} ]".format(avg_l3))
