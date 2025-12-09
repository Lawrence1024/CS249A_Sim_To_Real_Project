import numpy as np

class Sampler:
    '''
    Abstract class for VerifAI-style samplers
    '''
    def __init__(self, domain):
        self.domain = domain
        self.dimension = len(domain)
        
    def getSample(self):
        raise NotImplementedError
    
    def update(self, sample, info, rho):
        raise NotImplementedError
    
class CrossEntropySampler(Sampler):
    '''
    Cross-entropy sampler
    '''
    def __init__(self, domain, alpha, thres, buckets=10, dist=None):
        super().__init__(domain)
        self.alpha = alpha
        self.thres = thres
        self.buckets = {}
        self.dist = {}
        if isinstance(buckets, int):
            for feature in domain.keys():
                self.buckets[feature] = buckets
        else:
            raise NotImplementedError("Only uniform bucket is supported.")
        if dist is None:
            for feature in domain.keys():
                self.dist[feature] = np.ones(int(self.buckets[feature])) / self.buckets[feature]
        else:
            raise NotImplementedError("Custom distribution is not supported.")
            
    def getSample(self):
        bucket_samples = {}
        for feature in self.domain.keys():
            bucket_samples[feature] = np.random.choice(int(self.buckets[feature]), p=self.dist[feature])
        norm_ret = {}
        for feature in self.domain.keys():
            norm_ret[feature] = np.random.uniform(bucket_samples[feature], bucket_samples[feature]+1.)/self.buckets[feature]
        ret = {}
        for feature in self.domain.keys():
            l, h = self.domain[feature].intervals[0]
            ret[feature] = l + (h-l)*norm_ret[feature]
        return ret
    
    def update(self, sample, rho, log=None):
        """
        Args:
            sample: The previous sample
            rho: Positive if any of the rules are violated
        """
        if rho is None or rho <= self.thres:
            return
        for feature in self.domain.keys():
            b = self.sampleToBucket(sample)[feature]
            row = self.dist[feature]
            row *= self.alpha
            row[b] += 1 - self.alpha
        print("Updated dist: ", self.dist)
            
    def sampleToBucket(self, sample):
        norm_sample = {}
        bucket_sample = {}
        for feature in self.domain.keys():
            l, h = self.domain[feature].intervals[0]
            norm_sample[feature] = (sample[feature] - l) / (h - l)
            bucket_sample[feature] = int(norm_sample[feature] * self.buckets[feature])
            if bucket_sample[feature] == self.buckets[feature]: # edge case
                bucket_sample[feature] -= 1
        return bucket_sample
    
    def reset(self):
        """Reset sampler to initial state."""
        for feature in self.domain.keys():
            self.dist[feature] = np.ones(int(self.buckets[feature])) / self.buckets[feature]
    
    def save_state(self, filepath):
        """Save sampler state to file."""
        import pickle
        state = {
            'dist': {k: v.tolist() for k, v in self.dist.items()},
            'buckets': self.buckets,
            'domain': self.domain,
            'alpha': self.alpha,
            'thres': self.thres
        }
        with open(filepath, 'wb') as f:
            pickle.dump(state, f)
    
    @classmethod
    def load_state(cls, filepath):
        """Load sampler state from file."""
        import pickle
        with open(filepath, 'rb') as f:
            state = pickle.load(f)
        
        # Get bucket size from first feature
        first_feature = list(state['buckets'].keys())[0]
        bucket_size = state['buckets'][first_feature]
        
        sampler = cls(
            state['domain'],
            alpha=state['alpha'],
            thres=state['thres'],
            buckets=bucket_size
        )
        sampler.dist = {k: np.array(v) for k, v in state['dist'].items()}
        return sampler
    
class MultiArmedBanditSampler(Sampler):
    '''
    Multi-armed bandit sampler
    '''
    def __init__(self, domain, alpha, thres, buckets=10, dist=None, exploration_ratio=2.0):
        super().__init__(domain)
        self.alpha = alpha
        self.thres = thres
        self.buckets = {}
        self.dist = {}
        if isinstance(buckets, int):
            for feature in domain.keys():
                self.buckets[feature] = buckets
        else:
            raise NotImplementedError("Only uniform bucket is supported.")
        if dist is None:
            for feature in domain.keys():
                self.dist[feature] = np.ones(int(self.buckets[feature])) / self.buckets[feature]
        else:
            raise NotImplementedError("Custom distribution is not supported.")
        self.counts = {}
        for feature in domain.keys():
            self.counts[feature] = np.ones(int(self.buckets[feature]))
        self.errors = {}
        for feature in domain.keys():
            self.errors[feature] = np.zeros(int(self.buckets[feature]))
        self.t = 1
        self.exploration_ratio = exploration_ratio
        
    def getSample(self):
        proportions = {}
        for feature in self.domain.keys():
            proportions[feature] = self.errors[feature] / self.counts[feature]
        ucb = {}
        for feature in self.domain.keys():
            ucb[feature] = proportions[feature] + np.sqrt(self.exploration_ratio * np.log(self.t) / self.counts[feature])
        bucket_samples = {}
        for feature in self.domain.keys():
            max_ucb = np.max(ucb[feature])
            candidates = np.where(ucb[feature] == max_ucb)[0]
            bucket_samples[feature] = np.random.choice(candidates)
        norm_ret = {}
        for feature in self.domain.keys():
            norm_ret[feature] = np.random.uniform(bucket_samples[feature], bucket_samples[feature]+1.)/self.buckets[feature]
        ret = {}
        for feature in self.domain.keys():
            l, h = self.domain[feature].intervals[0]
            ret[feature] = l + (h-l)*norm_ret[feature]
        return ret
    
    def update(self, sample, error_value, log=None):
        """
        Args:
            sample: The previous sample
            error_value: The **normalized** error value computed from the rulebook
        """
        self.t += 1
        for feature in self.domain.keys():
            b = self.sampleToBucket(sample)[feature]
            self.counts[feature][b] += 1
            self.errors[feature][b] += error_value
        if log is not None:
            ucb = {}
            for feature in self.domain.keys():
                ucb[feature] = self.errors[feature] / self.counts[feature] + np.sqrt(self.exploration_ratio * np.log(self.t) / self.counts[feature])
            log.info("Updated UCB: " + str(ucb))
    
    def sampleToBucket(self, sample):
        norm_sample = {}
        bucket_sample = {}
        for feature in self.domain.keys():
            l, h = self.domain[feature].intervals[0]
            norm_sample[feature] = (sample[feature] - l) / (h - l)
            bucket_sample[feature] = int(norm_sample[feature] * self.buckets[feature])
            if bucket_sample[feature] == self.buckets[feature]: # edge case
                bucket_sample[feature] -= 1
        return bucket_sample
    
    def reset(self):
        """Reset sampler to initial state."""
        for feature in self.domain.keys():
            self.counts[feature] = np.ones(int(self.buckets[feature]))
            self.errors[feature] = np.zeros(int(self.buckets[feature]))
        self.t = 1
    
    def save_state(self, filepath):
        """Save sampler state to file."""
        import pickle
        state = {
            'counts': {k: v.tolist() for k, v in self.counts.items()},
            'errors': {k: v.tolist() for k, v in self.errors.items()},
            'buckets': self.buckets,
            'domain': self.domain,
            'alpha': self.alpha,
            'thres': self.thres,
            't': self.t,
            'exploration_ratio': self.exploration_ratio
        }
        with open(filepath, 'wb') as f:
            pickle.dump(state, f)
    
    @classmethod
    def load_state(cls, filepath):
        """Load sampler state from file."""
        import pickle
        with open(filepath, 'rb') as f:
            state = pickle.load(f)
        
        # Get bucket size from first feature
        first_feature = list(state['buckets'].keys())[0]
        bucket_size = state['buckets'][first_feature]
        
        sampler = cls(
            state['domain'],
            alpha=state['alpha'],
            thres=state['thres'],
            buckets=bucket_size,
            exploration_ratio=state['exploration_ratio']
        )
        sampler.counts = {k: np.array(v) for k, v in state['counts'].items()}
        sampler.errors = {k: np.array(v) for k, v in state['errors'].items()}
        sampler.t = state['t']
        return sampler
    