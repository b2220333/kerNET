# -*- coding: utf-8 -*-
# torch 0.3.1

from __future__ import print_function, division

import torch
from torch.autograd import Variable

import backend as K
from layers.kerlinear import kerLinear

# TODO: check GPU compatibility: move data and modules on GPU, see, for example,
# https://github.com/pytorch/pytorch/issues/584
# TODO: using multiple devices, see
# http://pytorch.org/docs/0.3.1/notes/multiprocessing.html and nn.DataParallel
# TODO: numerically check initial grad calculation for the toy example
# TODO: check numerically grad updates for two update modes (update-per-batch
# and accumulate_grad)
# TODO: tests
# TODO: python2 compatibility
# TODO: numerically check feedforward, initial grad calc and grad updates of the
# bp model; run it on some datasets (classification and regression)

torch.manual_seed(1234)

class baseMLKN(torch.nn.Module):
    """
    Model for fast implementations of MLKN. Do not use this base class, use
    subclasses instead.

    A special property of MLKN is that for it to do anything, it always needs
    a reference to its training set, which we call X. You could think of this
    as a set of bases to expand your kernel machine on. And this is why in a lot
    of methods of this class you see the parameter X. It is true that it
    can be highly memory-inefficient to carry this big chunk of data around,
    we may add more functionalities to the class in the future to tackle with
    this issue.
    """
    # TODO: see above documentation
    def __init__(self):
        super(baseMLKN, self).__init__()
        self._layer_counter = 0

    def add_layer(self, layer):
        """
        Add a layer to the model.

        Parameters
        ----------
        layer : a layer instance.
        """
        assert isinstance(layer, torch.nn.Module)
        setattr(self, 'layer'+str(self._layer_counter), layer)
        self._layer_counter += 1
        # layer indexing : layer 0 is closest to input

    def add_loss(self, loss_fn):
        """
        Specify loss function for the last layer. We recommend using
        CrossEntropyLoss (CrossEntropyLoss(output, y), in PyTorch, is
        equivalent to NLLLoss(logsoftmax(output), y), where logsoftmax =
        torch.nn.LogSoftmax(dim=1) for output Tensor of shape
        (n_example, n_class)). Base of the log functions in these operations
        is e.

        Using other loss functions may cause unexpected behaviors since
        we have only tested the model with CrossEntropyLoss.

        Parameters
        ----------
        loss_fn : a torch loss object
        """
        setattr(self, 'output_loss_fn', loss_fn)

    def _forward(self, x, X, upto=None):
        """
        Feedforward upto layer 'upto'. If 'upto' is not passed,
        this works as the standard forward function in PyTorch.

        Parameters
        ----------

        x : Tensor, shape (batch_size, dim)
            Batch.

        X : Tensor, shape (n_example, dim)
            Training set.

        upto (optional) : int
            Index for the layer upto (and including) which we will evaluate
            the model. 0-indexed.

        Returns
        -------
        y : Tensor, shape (batch_size, out_dim)
            Batch output.
        """
        if upto is not None: # cannot use 'if upto' here since it is 0-indexed
        # and layer0 is the first layer
            assert 0<=upto<=self._layer_counter
            counter = upto + 1
        else: counter = self._layer_counter

        y_previous, Y_previous = x, X
        # TODO: because we always need to compute F_i(X) at each layer i, this
        # is a huge overhead
        # feedforward
        for i in range(counter):
            layer = getattr(self, 'layer'+str(i))
            y, Y = layer(y_previous, Y_previous), layer(Y_previous, Y_previous)
            y_previous, Y_previous = y, Y

        return y

    def _forward_volatile(self, x, X, upto=None):
        """
        Feedforward upto layer 'upto' in volatile mode. Use for inference. See
        http://pytorch.org/docs/0.3.1/notes/autograd.html.
        If 'upto' is not passed, this works as the standard forward function
        in PyTorch.

        Parameters
        ----------

        x : Tensor, shape (batch_size, dim)
            Batch. Must be a leaf Variable.

        X : Tensor, shape (n_example, dim)
            Training set.
        upto (optional) : int
            Index for the layer upto (and including) which we will evaluate
            the model. 0-indexed.

        Returns
        -------
        y : Tensor, shape (batch_size, out_dim)
            Batch output.
        """
        x.volatile = True
        return self._forward(x, X, upto)

    def get_repr(self, X_test, X, layer=None, batch_size=None):
        """
        Feed random sample x into the network and get its representation at the
        output of a given layer. This is useful mainly for two reasons. First,
        one might just be curious and want to explore the hidden representation
        of a trained MLKN. Second, to train the last layer as a SVM (or just
        substitute all layers after this one with a SVM), one could
        simply take this hidden representation and use it as a new random sample
        for his/her favorite SVM model.

        Parameters
        ----------
        X_test : Tensor, shape (n1_example, dim)
            Random sample whose representation is of interest.

        X : Tensor, shape (n_example, dim)
            Training set used for fitting the network.

        layer (optional) : int
            Output of this layer is the hidden representation. Layers are
            zero-indexed with the 0th layer being the one closest to the input.
            If this parameter is not passed, evaluate the output of the entire
            network.

        Returns
        -------
        Y_test : Tensor, shape (n1_example, layer_dim)
            Hidden representation of X_test at the given layer.
        """
        # TODO: test
        if not batch_size or batch_size>X_test.shape[0]: batch_size=X_test.shape[0]
        if layer is None: layer=self._layer_counter-1
        else: assert 0<=layer<=self._layer_counter-1

        layer = getattr(self, 'layer'+str(layer))
        out_dim = layer.weight.shape[0] # TODO: strangely, nn.Linear stores
        # weights as [out_dim, in_dim]...or am I making a mistake somewhere

        Y_test = torch.cuda.FloatTensor(X_test.shape[0], out_dim) if \
        X_test.is_cuda else torch.FloatTensor(X_test.shape[0], out_dim)

        i = 0
        for x_test in K.get_batch(X_test, batch_size=batch_size):
            x_test = x_test[0].clone() # NOTE: clone turns x_test into a leaf
            # Variable, which is required to set the volatile flag

            # NOTE: when only one set is sent to get_batch,
            # we need to use x_test[0] because no automatic unpacking has
            # been done by Python
            y_test = self._forward_volatile(x_test, X, upto=layer)

            if x_test.shape[0]<batch_size: # last batch
                Y_test[i*batch_size:] = y_test.data[:]
                break
            Y_test[i*batch_size: (i+1)*batch_size] = y_test.data[:]
            i += 1

        return Variable(Y_test, requires_grad=False)
        # NOTE: this is to make the type of Y_pred consistent with X_test since
        # X_test must be a Variable

    def evaluate(self, X_test, X, batch_size=None):
        """
        Feed X_test into the network and get raw output.

        Parameters
        ----------

        X_test : Tensor, shape (n1_example, dim)
            Set to be evaluated.

        X : Tensor, shape (n_example, dim)
            Training set.

        Returns
        -------
        Y_test : Tensor, shape (n1_example, out_dim)
            Raw output from the network.
        """
        # TODO: test
        return self.get_repr(X_test, X, batch_size=batch_size)

    def fit(self):
        raise NotImplementedError('must be implemented by subclass')

    def save(self):
        pass
        # TODO: wrap native PyTorch support for save

class MLKN(baseMLKN):
    """
    A general MLKN model that does everything. Trained using backpropagation.
    """
    def add_optimizer(self, optimizer):
        """
        One optimizer for the entire model. But this of course supports those
        fancy per-parameter options from PyTorch.
        """
        assert isinstance(optimizer, torch.optim.Optimizer)
        setattr(self, 'optimizer', optimizer)

    def fit(
        self,
        n_epoch,
        X, Y,
        batch_size=None,
        shuffle=False,
        accumulate_grad=True):
        """
        Parameters
        ----------
        n_epoch : int
            The number of epochs to train the model.

        X : Tensor, shape (n_example, dim)
            Training set.

        Y : Tensor, shape (n_example, 1) or (n_example,)
            Target data.

        batch_size (optional) : int
            If not specified, use full mode.

        shuffle (optional) : bool
            Shuffle the data at each epoch.

        accumulate_grad (optional) : bool
            If True, accumulate gradient from each batch and only update the
            weights after each epoch.
        """
        assert X.shape[0]==Y.shape[0]

        if not batch_size or batch_size>X.shape[0]: batch_size = X.shape[0]
        n_batch = X.shape[0] // batch_size
        last_batch = bool(X.shape[0] % batch_size)

        if len(Y.shape)==2: Y=Y.view(-1,)
        # NOTE: CrossEntropyLoss requires label tensor to be of
        # shape (n)
        # TODO: what about multi-D MSELoss or CrossEntropyLoss?
        if isinstance(self.output_loss_fn, torch.nn.CrossEntropyLoss):
            Y=Y.type(torch.cuda.LongTensor)\
            if Y.is_cuda else Y.type(torch.LongTensor)
            # NOTE: required by CrossEntropyLoss

        elif isinstance(self.output_loss_fn, torch.nn.MSELoss):
            Y=Y.type(torch.cuda.FloatTensor)\
            if Y.is_cuda else Y.type(torch.FloatTensor)
            # NOTE: required by MSELoss

        for param in self.parameters(): param.requires_grad=True # unfreeze
        for _ in range(n_epoch):
            __ = 0
            self.optimizer.zero_grad()
            for x, y in K.get_batch(
                X, Y,
                batch_size=batch_size,
                shuffle=shuffle
                ):
                __ += 1
                output = self._forward(x, X)

                loss = self.output_loss_fn(output, y)
                # NOTE: L2 regulatization
                # is taken care of by setting the weight_decay param in the
                # optimizer, see
                # https://discuss.pytorch.org/t/simple-l2-regularization/139

                print('epoch: {}/{}, batch: {}/{}, loss({}): {:.3f}'.format(
                    _+1, n_epoch, __, n_batch+int(last_batch),
                    self.output_loss_fn.__class__.__name__,
                    loss.data[0]
                    ))

                loss.backward()
                if not accumulate_grad:
                    self.optimizer.step()
                    self.optimizer.zero_grad()

            if accumulate_grad:
                self.optimizer.step()
                self.optimizer.zero_grad()

        print('\n' + '#'*10 + '\n')
        for param in self.parameters(): param.requires_grad=False # freeze
        # the model

class MLKNGreedy(baseMLKN):
    """
    Base model for a greedy MLKN. Do not use this class, use subclass instead.
    """
    # TODO: this model uses kerLinear or nn.Linear (build thickLinear to make
    # kernel-neural hybrid simpler (note: no kernel should be closer to input
    # than neural)) layers only and all layers
    # should be trained as RBFNs. Users should be encouraged to use the
    # layerwise functionality of this model. Build another model that allows
    # passing in sklearn.SVM objects in order to train the last layer as a SVM
    def __init__(self):
        super(MLKNGreedy, self).__init__()
        self._optimizer_counter = 0

    def add_optimizer(self, optimizer):
        """
        Configure layerwise training. One needs to designate an optimizer for
        each layer. The ordering for optimizers follows that of the layers.
        User can pass any iterable to the non-optional 'params' parameter
        of the optimizer object and this will be later overwritten by this
        function.
        """
        assert isinstance(optimizer, torch.optim.Optimizer)
        setattr(self, 'optimizer'+str(self._optimizer_counter), optimizer)
        self._optimizer_counter += 1
        # optimizer indexing : optimizer 0 is the optimizer for layer 0

    def _compile(self):
        """
        Compile the model.
        """
        assert self._optimizer_counter==self._layer_counter
        # assign each optimizer to its layer ###################################
        for i in range(self._optimizer_counter):
            layer = getattr(self, 'layer'+str(i))
            optimizer = getattr(self, 'optimizer'+str(i))
            optimizer.param_groups[0]['params'] = list(layer.parameters())

        for param in self.parameters(): param.requires_grad=False # freeze all
        # layers

    def _fit_rep_learners(
        self,
        n_epoch,
        X, Y,
        n_group,
        batch_size=None,
        shuffle=False,
        accumulate_grad=True):
        """
        Fit the representation learning layers, i.e., all layers but the last.
        """

        assert len(Y.shape) <= 2
        # NOTE: this model only supports hard class labels
        assert X.shape[0]==Y.shape[0]

        if not batch_size or batch_size>X.shape[0]: batch_size = X.shape[0]
        n_batch = X.shape[0] // batch_size
        last_batch = bool(X.shape[0] % batch_size)

        # train the representation-learning layers #############################
        if len(Y.shape)==1: Y=Y.view(-1, 1)
        # NOTE: ideal_gram() requires label tensor to be of shape
        # (n, 1)
        loss_fn = torch.nn.CosineSimilarity() # NOTE: equivalent to alignment
        for i in range(self._layer_counter-1):
            optimizer = getattr(self, 'optimizer'+str(i))
            next_layer = getattr(self, 'layer'+str(i+1))
            layer = getattr(self, 'layer'+str(i))

            assert isinstance(next_layer, kerLinear)
            # NOTE:
            # torch.nn.Linear cannot pass this. We do this check because each
            # layer uses the kernel function from the next layer to calculate
            # loss but nn.Linear does not have a kernel so it cannot be the
            # next layer for any layer

            for param in layer.parameters(): param.requires_grad=True # unfreeze

            for _ in range(n_epoch[i]):
                __ = 0
                optimizer.zero_grad()
                for x, y in K.get_batch(
                    X, Y,
                    batch_size=batch_size,
                    shuffle=shuffle
                    ):
                    __ += 1
                    # get ideal gram matrix ####################################
                    ideal_gram = K.ideal_gram(y, y, n_group)
                    ideal_gram=ideal_gram.type(torch.cuda.FloatTensor)\
                    if ideal_gram.is_cuda else ideal_gram.type(torch.FloatTensor)
                    # NOTE: required by CosineSimilarity

                    # get output ###############################################
                    output = self._forward(x, X, upto=i)
                    # output.register_hook(print)
                    # print('output', output) # NOTE: layer0 initial feedforward
                    # passed

                    gram = K.kerMap(
                        output,
                        output,
                        next_layer.sigma
                        )
                    # print(gram) # NOTE: initial feedforward passed
                    # gram.register_hook(print) # NOTE: (for torch_backend.alignment)
                    # gradient here is inconsistent using the alignment loss from
                    # torch_backend: hand-calculated_grad*n_example =
                    # pytorch_grad

                    # compute loss and optimizer takes a step###################
                    loss = -loss_fn(gram.view(1, -1), ideal_gram.view(1, -1))
                    # NOTE: negative alignment
                    # NOTE: L2 regulatization
                    # is taken care of by setting the weight_decay param in the
                    # optimizer, see
                    # https://discuss.pytorch.org/t/simple-l2-regularization/139

                    print('epoch: {}/{}, batch: {}/{}, loss({}): {:.3f}'.format(
                        _+1, n_epoch[i], __, n_batch+int(last_batch),
                        'Alignment',
                        -loss.data[0]
                        ))

                    loss.backward()
                    # train the layer
                    if not accumulate_grad:
                        optimizer.step()
                        optimizer.zero_grad()

                    #########
                    # check gradient
                    # print('weight', layer.weight)
                    # print('gradient', layer.weight.grad.data)
                    #########

                if accumulate_grad:
                    optimizer.step()
                    optimizer.zero_grad()

            print('\n' + '#'*10 + '\n')
            for param in layer.parameters(): param.requires_grad=False # freeze
            # this layer again

    def _fit_output(
        self,
        n_epoch,
        X, Y,
        batch_size=None,
        shuffle=False,
        accumulate_grad=True
        ):
        """
        Fit the last layer.
        """

        assert len(Y.shape) <= 2 # NOTE: this model only supports hard class labels
        assert X.shape[0]==Y.shape[0]

        if not batch_size or batch_size>X.shape[0]: batch_size = X.shape[0]
        n_batch = X.shape[0] // batch_size
        last_batch = bool(X.shape[0] % batch_size)


        # train the last layer as a RBFN classifier ############################
        i = self._layer_counter-1
        optimizer = getattr(self, 'optimizer'+str(i))
        layer = getattr(self, 'layer'+str(i))

        if len(Y.shape)==2: Y=Y.view(-1,)
        # NOTE: CrossEntropyLoss (and probably also MSELoss) requires label
        # tensor to be of shape (n)

        # TODO: what about multi-D MSELoss or CrossEntropyLoss?

        if isinstance(self.output_loss_fn, torch.nn.CrossEntropyLoss):
            Y=Y.type(torch.cuda.LongTensor)\
            if Y.is_cuda else Y.type(torch.LongTensor)
            # NOTE: required by CrossEntropyLoss

        elif isinstance(self.output_loss_fn, torch.nn.MSELoss):
            Y=Y.type(torch.cuda.FloatTensor)\
            if Y.is_cuda else Y.type(torch.FloatTensor)
            # NOTE: required by MSELoss


        for param in layer.parameters(): param.requires_grad=True # unfreeze
        for _ in range(n_epoch[i]):
            __ = 0
            optimizer.zero_grad()
            for x, y in K.get_batch(
                X, Y,
                batch_size=batch_size,
                shuffle=shuffle
                ):
                __ += 1
                # compute loss
                output = self._forward(x, X, upto=i)
                # print(output) # NOTE: layer1 initial feedforward passed

                loss = self.output_loss_fn(output, y)
                # print(loss) # NOTE: initial feedforward passed
                # NOTE: L2 regulatization
                # is taken care of by setting the weight_decay param in the
                # optimizer, see
                # https://discuss.pytorch.org/t/simple-l2-regularization/139

                print('epoch: {}/{}, batch: {}/{}, loss({}): {:.3f}'.format(
                    _+1, n_epoch[i], __, n_batch+int(last_batch),
                    self.output_loss_fn.__class__.__name__,
                    loss.data[0]
                    ))

                loss.backward()
                # train the layer
                if not accumulate_grad:
                    optimizer.step()
                    optimizer.zero_grad()

                #########
                # define crossentropy loss to test gradient
                # loss = output_prob.mul(K.one_hot(y.unsqueeze(dim=1), n_class)).sum()/2
                # NOTE: this calculation results in the same gradient as that
                # calculated by autograd using CrossEntropyLoss as loss_fn

                # check gradient
                # print('weight', layer.weight)
                # print('gradient', layer.weight.grad.data)
                # print('bias gradient', layer.bias.grad.data)
                #########
            if accumulate_grad:
                optimizer.step()
                optimizer.zero_grad()

        print('\n' + '#'*10 + '\n')
        for param in layer.parameters(): param.requires_grad=False # freeze
        # this layer again

class MLKNClassifier(MLKNGreedy):
    """
    MLKN classifier dedicated for layerwise training using method proposed
    in https://arxiv.org/abs/1802.03774. This feature can be tedious to
    implement in standard PyTorch since a lot of details need to be taken care
    of so we build it for your convenience.

    If one wants a MLKN classifier trained with standard backpropagation,
    use MLKN instead, the setup for training would be much simpler for
    MLKN and many more loss functions are supported.
    """
    def __init__(self):
        super(MLKNClassifier, self).__init__()

    def predict(self, X_test, X, batch_size=None):
        """
        Get predictions from the classifier.

        Parameters
        ----------

        X_test : Tensor, shape (n1_example, dim)
            Test set.

        X : Tensor, shape (n_example, dim)
            Training set.

        Returns
        -------
        Y_pred : Tensor, shape (n1_example,)
            Predicted labels.
        """
        if not batch_size or batch_size>X_test.shape[0]: batch_size=X_test.shape[0]
        Y_raw = self.evaluate(X_test, X, batch_size=batch_size)
        _, Y_pred = torch.max(Y_raw, dim=1)

        return Y_pred

    def get_error(self, y_pred, y):
        """
        Compute prediction error rate.

        Parameters
        ----------

        y_pred : Tensor, shape (batch_size,)
            Predicted labels.

        y : Tensor, shape (batch_size,)
            True labels.

        Returns
        -------
        err : scalar (or wrapped in a Variable, if one of y or y_pred is)
            Error rate.
        """
        assert y_pred.shape==y.shape
        y_pred = y_pred.type_as(y)
        err = (y_pred!=y).sum().type(torch.FloatTensor).div_(y.shape[0])
        return err

    def fit(
        self,
        n_epoch,
        X, Y,
        n_class,
        batch_size=None,
        shuffle=False,
        accumulate_grad=True):
        """
        Parameters
        ----------
        n_epoch : tuple
            The number of epochs for each layer. If the length of the tuple is
            greater than the number of the layers, use n_epoch[:n_layer].
            Even if there is only one layer, this parameter must be a tuple (
            may be of of a scalar, e.g., (1,)).

        X : Tensor, shape (n_example, dim)
            Training set.

        Y : Variable of shape (n_example, 1) or (n_example,)
            Categorical labels for the set.

        n_class : int

        batch_size (optional) : int
            If not specified, use full mode.

        shuffle (optional) : bool
            Shuffle the data at each epoch.

        accumulate_grad (optional) : bool
            If True, accumulate gradient from each batch and only update the
            weights after each epoch.
        """
        assert len(n_epoch) >= self._layer_counter
        self._compile()
        self._fit_rep_learners(
            n_epoch,
            X, Y,
            n_class,
            batch_size=batch_size,
            shuffle=shuffle,
            accumulate_grad=accumulate_grad
            )
        print('Representation-learning layers trained.')

        self._fit_output(
            n_epoch,
            X, Y,
            batch_size=batch_size,
            shuffle=shuffle,
            accumulate_grad=accumulate_grad
            )
        print('Classifier trained.')

if __name__=='__main__':
    pass
