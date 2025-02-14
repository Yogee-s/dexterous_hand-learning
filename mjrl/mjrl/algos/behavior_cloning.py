import logging

import numpy as np
import time as timer
import torch
from torch.autograd import Variable
from tqdm import tqdm

from mjrl.utils.logger import DataLog

logging.disable(logging.CRITICAL)


class BC:
    def __init__(self, expert_paths,
                 policy,
                 epochs=5,
                 batch_size=64,
                 lr=1e-3,
                 optimizer=None):

        self.policy = policy
        self.expert_paths = expert_paths
        self.epochs = epochs
        self.mb_size = batch_size
        self.logger = DataLog()


        #################################################################
        #################################################################
        #################################################################
        # Finger with 18DOF
        # obs_indexes = [0, 1, 2, 3, 4, 5, 9, 10, 13, 14, 17, 18, 22, 23, 25, 26, 28, 29,30,31,32,33,34,35,36,37,38]
        # act_indexes = [0, 1, 2, 3, 4, 5, 9, 10, 13, 14, 17, 18, 22, 23, 25, 26, 28, 29]

        # Finger with 12DOF
        obs_indexes = [0, 1, 2, 3, 4, 5, 9, 13, 17, 22, 26, 28,30,31,32,33,34,35,36,37,38]
        act_indexes = [0, 1, 2, 3, 4, 5, 9, 13, 17, 22, 26, 28]
        # get transformations
        observations = np.concatenate([path["observations"][:, obs_indexes] for path in expert_paths])
        actions = np.concatenate([path["actions"][:, act_indexes] for path in expert_paths])
        in_shift, in_scale = np.mean(observations, axis=0), np.std(observations, axis=0)
        out_shift, out_scale = np.mean(actions, axis=0), np.std(actions, axis=0)
        #################################################################
        #################################################################
        #################################################################
        # # get transformations
        # observations = np.concatenate([path["observations"] for path in expert_paths])
        # actions = np.concatenate([path["actions"] for path in expert_paths])
        # in_shift, in_scale = np.mean(observations, axis=0), np.std(observations, axis=0)
        # out_shift, out_scale = np.mean(actions, axis=0), np.std(actions, axis=0)

        # set scalings in the target policy
        self.policy.model.set_transformations(in_shift, in_scale, out_shift, out_scale)
        self.policy.old_model.set_transformations(in_shift, in_scale, out_shift, out_scale)

        # set the variance of gaussian policy based on out_scale
        params = self.policy.get_param_values()
        params[-self.policy.m:] = np.log(out_scale + 1e-12)
        self.policy.set_param_values(params)

        # construct optimizer
        self.optimizer = torch.optim.Adam(self.policy.model.parameters(), lr=lr) if optimizer is None else optimizer

        # loss criterion is MSE for maximum likelihood estimation
        self.loss_function = torch.nn.MSELoss()

    def loss(self, obs, act):
        obs_var = Variable(torch.from_numpy(obs).float(), requires_grad=False)
        act_var = Variable(torch.from_numpy(act).float(), requires_grad=False)
        act_hat = self.policy.model(obs_var)
        return self.loss_function(act_hat, act_var.detach())

    def train(self):
        #################################################################
        #################################################################
        #################################################################
        # Finger with 18DOF
        # obs_indexes = [0, 1, 2, 3, 4, 5, 9, 10, 13, 14, 17, 18, 22, 23, 25, 26, 28, 29,30,31,32,33,34,35,36,37,38]
        # act_indexes = [0, 1, 2, 3, 4, 5, 9, 10, 13, 14, 17, 18, 22, 23, 25, 26, 28, 29]

        # Finger with 12DOF
        obs_indexes = [0, 1, 2, 3, 4, 5, 9, 13, 17, 22, 26, 28,30,31,32,33,34,35,36,37,38]
        act_indexes = [0, 1, 2, 3, 4, 5, 9, 13, 17, 22, 26, 28]

        observations = np.concatenate([path["observations"][:, obs_indexes] for path in self.expert_paths])
        actions = np.concatenate([path["actions"][:, act_indexes] for path in self.expert_paths])
        #################################################################
        #################################################################
        #################################################################
        # observations = np.concatenate([path["observations"] for path in self.expert_paths])
        # actions = np.concatenate([path["actions"] for path in self.expert_paths])
        ts = timer.time()
        num_samples = observations.shape[0]
        for ep in tqdm(range(self.epochs)):
            self.logger.log_kv('epoch', ep)
            loss_val = self.loss(observations, actions).data.numpy().ravel()[0]
            self.logger.log_kv('loss', loss_val)
            self.logger.log_kv('time', (timer.time() - ts))
            for mb in range(int(num_samples / self.mb_size)):
                rand_idx = np.random.choice(num_samples, size=self.mb_size)
                obs = observations[rand_idx]
                act = actions[rand_idx]
                self.optimizer.zero_grad()
                loss = self.loss(obs, act)
                loss.backward()
                self.optimizer.step()
        params_after_opt = self.policy.get_param_values()
        self.policy.set_param_values(params_after_opt, set_new=True, set_old=True)
        self.logger.log_kv('epoch', self.epochs)
        loss_val = self.loss(observations, actions).data.numpy().ravel()[0]
        self.logger.log_kv('loss', loss_val)
        self.logger.log_kv('time', (timer.time() - ts))
