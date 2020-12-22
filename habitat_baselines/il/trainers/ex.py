import os
import time

import torch
from torch.utils.data import DataLoader

import habitat
from habitat import logger
from habitat_baselines.common.base_il_trainer import BaseILTrainer
from habitat_baselines.common.baseline_registry import baseline_registry
from habitat_baselines.common.tensorboard_utils import TensorboardWriter
from habitat_baselines.il.data.data import EQADataset
from habitat_baselines.il.metrics import VqaMetric
from habitat_baselines.il.models.models import VqaLstmCnnAttentionModel
from habitat_baselines.config.default import get_config


exp_config = "habitat_baselines/config/eqa/il_vqa.yaml"

config = get_config(exp_config)
device = (
            torch.device("cuda", config.TORCH_GPU_ID)
            if torch.cuda.is_available()
            else torch.device("cpu")
)


env = habitat.Env(config=config.TASK_CONFIG)

vqa_dataset = EQADataset(
    env,
    config,
    device,
    input_type="vqa",
    num_frames=config.IL.VQA.num_frames,
)

train_loader = DataLoader(
    vqa_dataset, batch_size=config.IL.VQA.batch_size, shuffle=True
)


#for batch in train_loader:
#    idx, questions, answers, frame_queue = batch
#    questions = questions.to(device)
#    print(questions)
