from __future__ import division
from rl.util import *
import config
import time

class Policy(object):

    def __init__(self):
        self.mask = None
        self.qlogger = None
        self.eps_forB = 0
        self.eps_forC = 0

    def _set_agent(self, agent):
        self.agent = agent

    def set_mask(self, mask):
        self.mask = mask

    @property
    def metrics_names(self):
        return []

    @property
    def metrics(self):
        return []

    def select_action(self, **kwargs):
        raise NotImplementedError()

    def get_config(self):
        return {}

    def log_qvalue(self, q_values):

        if self.qlogger is not None:

            if self.mask is not None:
                q_values = q_values - self.mask * 1e20

            self.qlogger.pre_maxq = self.qlogger.cur_maxq

            self.qlogger.cur_maxq = np.max(q_values)

            if self.qlogger.maxq < self.qlogger.cur_maxq:
                self.qlogger.maxq = self.qlogger.cur_maxq

            self.qlogger.mean_maxq.append(self.qlogger.cur_maxq)

class RandomPolicy(Policy):

    def select_action(self, q_values):
        #self.log_qvalue(q_values)
        assert q_values.ndim == 1
        nb_actions = q_values.shape[0]
        action = np.random.random_integers(0, nb_actions - 1)
        return action


class BoltzmannQPolicy(Policy):

    def __init__(self, tau=1.):
        super(BoltzmannQPolicy, self).__init__()
        self.tau = tau

    def select_action(self, q_values):
        #self.log_qvalue(q_values)
        assert q_values.ndim == 1
        nb_actions = q_values.shape[0]
        q_values = q_values.astype('float64')
        q_values /= self.tau
        q_values -= np.max(q_values)
        exp_values = np.exp(q_values)
        sum_exp = np.sum(exp_values)
        assert sum_exp >= 1.0
        probs = exp_values / sum_exp
        action = np.random.choice(range(nb_actions), p=probs)
        return action

    def get_config(self):
        config = super(BoltzmannQPolicy, self).get_config()
        return config


class GreedyQPolicy(Policy):

    def select_action(self, q_values):
        #self.log_qvalue(q_values)
        assert q_values.ndim == 1
        action = np.argmax(q_values)
        return action


class MaskedRandomPolicy(Policy):

    def __init__(self):
        super(MaskedRandomPolicy, self).__init__()
        self.mask = None

    def select_action(self, q_values):
        #self.log_qvalue(q_values)
        assert q_values.ndim == 1
        nb_actions = q_values.shape[0]
        probs = np.ones(nb_actions)
        if self.mask is not None:
            probs -= self.mask
        sum_probs = np.sum(probs)
        assert sum_probs >= 1.0
        probs /= sum_probs
        action = np.random.choice(range(nb_actions), p=probs)
        return action

    def get_config(self):
        config = super(MaskedRandomPolicy, self).get_config()
        return config


class MaskedBoltzmannQPolicy(Policy):

    def __init__(self, tau=1.):
        super(MaskedBoltzmannQPolicy, self).__init__()
        self.minq = 1e20
        self.maxq = -1e20
        self.tau = tau
        self.mask = None

    def select_action(self, q_values):
        #self.log_qvalue(q_values)
        assert q_values.ndim == 1
        nb_actions = q_values.shape[0]
        q_values = q_values.astype('float64')
        if self.mask is not None:
            q_values -= self.mask * 1e20
        q_values /= self.tau
        q_values -= np.max(q_values)
        exp_values = np.exp(q_values)
        sum_exp = np.sum(exp_values)
        assert sum_exp >= 1.0
        probs = exp_values / sum_exp
        action = np.random.choice(range(nb_actions), p=probs)
        return action

    def get_config(self):
        config = super(MaskedBoltzmannQPolicy, self).get_config()
        return config


class MaskedGreedyQPolicy(Policy):

    def __init__(self):
        super(MaskedGreedyQPolicy, self).__init__()
        self.mask = None

    def select_action(self, q_values):
        #self.log_qvalue(q_values)
        assert q_values.ndim == 1
        if self.mask is not None:
            q_values -= self.mask * 1e20
        action = np.argmax(q_values)
        return action


class EpsABPolicy(Policy):

    def __init__(self, policyA, policyB, eps_forB, half_eps_step=0, eps_min=0):
        super(EpsABPolicy, self).__init__()
        self.policyA = policyA
        self.policyB = policyB
        self.eps_forB = eps_forB
        self.eps_min=eps_min
        if half_eps_step==0:
            self.eps_decay_rate_each_step = 1.0
        else:
            self.eps_decay_rate_each_step = np.power(0.5, 1.0/half_eps_step)

    def select_action(self, q_values):
        #self.log_qvalue(q_values)
        assert q_values.ndim == 1
        if np.random.uniform() < self.eps_forB:
            action = self.policyB.select_action(q_values)
        else:
            action = self.policyA.select_action(q_values)
        self.eps_forB *= self.eps_decay_rate_each_step
        self.eps_forB = max(self.eps_min, self.eps_forB)
        return action

    def get_config(self):
        config = super(EpsABPolicy, self).get_config()
        config['policyA'] = self.policyA
        config['policyB'] = self.policyB
        config['eps_forB'] = self.eps_forB
        config['eps_decay_rate_each_step'] = self.eps_decay_rate_each_step
        return config

    def set_mask(self, mask):
        self.mask = mask
        self.policyA.set_mask(self.mask)
        self.policyB.set_mask(self.mask)


class EpsABCPolicy(Policy):
    def __init__(self, policyA, policyB, policyC, eps_forB, eps_forC, half_eps_step=0, eps_min=0):
        super(EpsABCPolicy, self).__init__()
        self.policyA = policyA
        self.policyB = policyB
        self.policyC = policyC
        self.eps_forB = eps_forB
        self.eps_forC = eps_forC
        self.eps_min = eps_min
        if half_eps_step == 0:
            self.eps_decay_rate_each_step = 1.0
        else:
            self.eps_decay_rate_each_step = np.power(0.5, 1.0 / half_eps_step)

    def select_action(self, q_values):
        #self.log_qvalue(q_values)
        assert q_values.ndim == 1
        rand = np.random.uniform()
        if rand < self.eps_forC:
            action = self.policyC.select_action(q_values)
        elif rand < self.eps_forC + self.eps_forB:
            action = self.policyB.select_action(q_values)
        else:
            action = self.policyA.select_action(q_values)
        self.eps_forB *= self.eps_decay_rate_each_step
        self.eps_forC *= self.eps_decay_rate_each_step
        self.eps_forB = max(self.eps_min, self.eps_forB)
        self.eps_forC = max(self.eps_min, self.eps_forC)
        return action

    def get_config(self):
        config = super(EpsABCPolicy, self).get_config()
        config['policyA'] = self.policyA
        config['policyB'] = self.policyB
        config['policyC'] = self.policyC
        config['eps_forB'] = self.eps_forB
        config['eps_decay_rate_each_step'] = self.eps_decay_rate_each_step
        return config

    def set_mask(self, mask):
        self.mask = mask
        self.policyA.set_mask(self.mask)
        self.policyB.set_mask(self.mask)
        self.policyC.set_mask(self.mask)


class EpsGreedyQPolicy(Policy):
    def __init__(self, eps=.1,end_eps=0.1, steps=200000):
        super(EpsGreedyQPolicy, self).__init__()
        self.eps = eps
        self.end_eps = end_eps
        self.steps = steps

    def select_action(self, q_values):
        if self.eps > self.end_eps:
            self.eps -= (self.eps-self.end_eps)/self.steps

        if q_values.ndim == 1:
            nb_actions = q_values.shape[0]

            if np.random.uniform() < self.eps:
                action = np.random.random_integers(0, nb_actions - 1)
            else:
                action = np.argmax(q_values)
            return action
        elif q_values.ndim == 2:
            nb_actions = q_values.shape[1]
            actions = []
            for q_value in q_values:
                if np.random.uniform() < self.eps:
                    action = np.random.random_integers(0, nb_actions - 1)
                else:
                    action = np.argmax(q_value)
                actions.append(action)
            return actions

    def get_config(self):
        config = super(EpsGreedyQPolicy, self).get_config()
        config['eps'] = self.eps
        return config


class GreedyQPolicy2D(Policy):
    def select_action(self, q_values):
        if q_values.ndim == 1:
            action = np.argmax(q_values)
            return action
        elif q_values.ndim == 2:
            actions = []
            # print "------------------"
            # print q_values
            for q_value in q_values:
                action = np.argmax(q_value)
                actions.append(action)
            # print actions
            return actions

class MultiDisPolicy(Policy):
    def select_action(self, q_values):
        # print "distribution", q_values
        while np.sum(q_values) > 1 - 1e-8:
            q_values /= (1 + 1e-5)
        # choice = np.random.multinomial(1, masked_q, size=1).tolist()[0].index(1)
        choice = np.random.choice(range(len(q_values)), p=q_values)
        # print choice, q_values[choice], np.argmax(q_values), np.max(q_values)
        if max(q_values) > 0.2:
            print "max p:", max(q_values), np.argmax(q_values)
        return choice

class MultiDisPolicy2D(Policy):
    def select_action(self, q_values):
        # print "distribution", q_values
        choices = []
        for i in range(config.nb_exchange):
            while np.sum(q_values[i]) > 1 - 1e-8:
                q_values[i] /= (1 + 1e-5)
            # choice = np.random.multinomial(1, masked_q, size=1).tolist()[0].index(1)
            choice = np.random.choice(range(len(q_values[i])), p=q_values[i])
            choices.append(choice)
            # print choice, q_values[choice], np.argmax(q_values), np.max(q_values)
            if max(q_values[i]) > 0.5:
                print "max p:", i, max(q_values[i]), np.argmax(q_values[i])
        # print q_values[0][:6]
        return choices


class MaskedMultiDisPolicy(Policy):
    def select_action(self, q_values):
        # print "distribution", q_values
        masked_q = q_values * self.mask
        masked_q = masked_q/np.sum(masked_q)
        if not np.isfinite(q_values).all() or not np.isfinite(masked_q).all():
            # print "got warning"
            # print "q:", q_values
            # print q_values.dtype
            # print self.mask
            # print "sum:", np.sum(masked_q)
            # print "mask_q1:", masked_q
            # print "mask_q2:", masked_q1
            for i in range(len(q_values)):
                if self.mask[i] == 1:
                    masked_q[i] = 1.0
                    # print '0?',i, q_values[i]
                else:
                    masked_q[i] = 0
            # print masked_q
            # assert 0
            masked_q = masked_q / np.sum(masked_q)

        # while np.sum(masked_q) > 1 - 1e-8:
        #     masked_q /= (1 + 1e-5)
        # choice = np.random.multinomial(1, masked_q, size=1).tolist()[0].index(1)
        choice = np.random.choice(range(config.Hole_num), p=masked_q)
        # print choice, q_values[choice], np.argmax(q_values), np.max(q_values)
        if max(q_values) > 0.8:
            print "max p:", max(q_values), np.argmax(q_values)
        # print q_values
        return choice