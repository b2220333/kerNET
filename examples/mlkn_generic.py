# -*- coding: utf-8 -*-
# torch 0.3.1

from __future__ import division, print_function

import numpy as np
import torch
from torch.autograd import Variable
from sklearn.datasets import load_iris, load_breast_cancer, load_digits, \
load_boston
from sklearn.preprocessing import StandardScaler, MinMaxScaler

import sys
sys.path.append('../kernet')
import backend as K
from models.mlkn import MLKN
from layers.kerlinear import kerLinear

torch.manual_seed(1234)

if __name__=='__main__':
    """
    This example shows how a generic MLKN works. The MLKN implemented here
    inherits only the general architecture from https://arxiv.org/abs/1802.03774
    but not the greedy training method. Thus, it is applicable to any general
    learning problem including classification, regression, etc.
    """
    # x, y = load_breast_cancer(return_X_y=True)
    # x, y = load_digits(return_X_y=True)
    # x, y = load_iris(return_X_y=True)
    x, y = load_boston(return_X_y=True)

    # for other Multiple Kernel Learning benchmarks used in the paper, you could
    # do:
    # x = np.load('../kernet/datasets/mkl/name_of_dataset.npy')
    # y = np.load('../kernet/datasets/mkl/name_of_dataset_labels.npy')
    # note that for some of the datasets, the results reported are only on a
    # subset of the data with size given in Table 1. This is to keep consistency
    # with the original paper that reported most of the results.
    # A random subset is chosen at each one of the 20 runs.

    # standardize features to zero-mean and unit-variance
    standard = StandardScaler()
    x = standard.fit_transform(x)

    # 0-1 normalization for y, comment this out for classification

    y = y.reshape(-1, 1)
    minmax = MinMaxScaler()
    y = minmax.fit_transform(y)


    # comment this out for regression
    """
    n_class = int(np.amax(y) + 1)
    """

    dtype = torch.FloatTensor
    if torch.cuda.is_available():
        dtype = torch.cuda.FloatTensor
    X = Variable(torch.from_numpy(x).type(dtype), requires_grad=False)
    Y = Variable(torch.from_numpy(y).type(dtype), requires_grad=False)

    # randomly permute data
    new_index = torch.randperm(X.shape[0])
    X, Y = X[new_index], Y[new_index]

    # split data evenly into training and test
    index = len(X)//2
    x_train, y_train = X[:index], Y[:index]
    x_test, y_test = X[index:], Y[index:]

    mlkn = MLKN()
    # add layers to the model, see layers/kerlinear for details on kerLinear
    mlkn.add_layer(
        kerLinear(ker_dim=x_train.shape[0], out_dim=15, sigma=5, bias=True)
        )
    # comment out for regression
    """
    mlkn.add_layer(
        kerLinear(ker_dim=x_train.shape[0], out_dim=n_class, sigma=.1, bias=True)
        )
    """
    # comment out for classification
    mlkn.add_layer(
        kerLinear(ker_dim=x_train.shape[0], out_dim=y_train.shape[1], sigma=.1, bias=True)
        )
    # add optimizer for each layer, this works with any torch.optim.Optimizer
    # note that this model is trained with the proposed layerwise training
    # method by default
    mlkn.add_optimizer(
        torch.optim.Adam(params=mlkn.parameters(), lr=1e-3, weight_decay=0.1)
        )
    # specify loss function for the output layer, this works with any
    # PyTorch loss function but it is recommended that you use CrossEntropyLoss
    # mlkn.add_loss(torch.nn.CrossEntropyLoss()) # comment out for regression
    mlkn.add_loss(torch.nn.MSELoss()) # comment out for classification
    # fit the model
    mlkn.fit(
        n_epoch=30,
        batch_size=30,
        shuffle=True,
        X=x_train,
        Y=y_train,
        accumulate_grad=True
        )
    # make a prediction on the test set and print error
    y_raw = mlkn.evaluate(X_test=x_test, X=x_train, batch_size=15)

    # comment out for regression
    """
    _, y_pred = torch.max(y_raw, dim=1)
    y_pred = y_pred.type_as(y_test)
    err = (y_pred!=y_test).sum().type(torch.FloatTensor).div_(y_test.shape[0])
    print('error rate: {:.2f}%'.format(err.data[0] * 100))
    """

    # comment out for classification

    mse = torch.nn.MSELoss()
    print('mse: {:.4f}'.format(mse(y_raw, y_test).data[0]))
    y_raw_np = y_raw.data.numpy()
    y_test_np = y_test.data.numpy()

    y_raw_np = minmax.inverse_transform(y_raw_np)
    y_test_np = minmax.inverse_transform(y_test_np)
    mse = sum((y_raw_np - y_test_np)**2) / len(y_test_np)
    print('mse(original scale): {:.4f}'.format(mse[0]))
