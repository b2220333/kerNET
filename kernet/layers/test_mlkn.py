# -*- coding: utf-8 -*-
# torch 0.3.1

import torch
from torch.autograd import Variable
import torch_backend as K # TODO: relative import
from mlkn import MLKNClassifier
from kerlinear import kerLinear
from sklearn.datasets import load_iris, load_breast_cancer, load_digits
from sklearn.preprocessing import Normalizer, StandardScaler
import numpy as np

torch.manual_seed(1234)

if __name__=='__main__':

    # x, y = load_breast_cancer(return_X_y=True)
    # x, y = load_digits(return_X_y=True)
    x, y = load_iris(return_X_y=True)
    # x = np.load("sonar.npy")
    # y = np.load("sonar_labels.npy")
    # x = np.load("diabetes.npy")
    # y = np.load("diabetes_labels.npy")
    # x = np.load("heart.npy")
    # y = np.load("heart_labels.npy")
    # x = np.load("liver.npy")
    # y = np.load("liver_labels.npy")
    # x = np.load("australian.npy")
    # y = np.load("australian_labels.npy")
    # x = np.load("splice.npy")
    # y = np.load("splice_labels.npy")
    # x = np.load("iono.npy")
    # y = np.load("iono_labels.npy")
    # x = np.load("german.npy")
    # y = np.load("german_labels.npy")
    # x = np.load("banana.npy")
    # y = np.load("banana_labels.npy")
    # x = np.load("ringnorm.npy")
    # y = np.load("ringnorm_labels.npy")
    # x = np.load("waveform.npy")
    # y = np.load("waveform_labels.npy")
    # x = np.load("thyroid.npy")
    # y = np.load("thyroid_labels.npy")
    # x = np.load("titanic.npy")
    # y = np.load("titanic_labels.npy")
    # x = np.load("fsolar.npy")
    # y = np.load("fsolar_labels.npy")

    normalizer = StandardScaler()
    x = normalizer.fit_transform(x)
    n_class = np.amax(y) + 1

    dtype = torch.FloatTensor
    if torch.cuda.is_available():
        dtype = torch.cuda.FloatTensor

    X = Variable(torch.from_numpy(x).type(dtype), requires_grad=False)
    y = Variable(torch.from_numpy(y).type(dtype), requires_grad=False)
    new_index = torch.randperm(X.shape[0])
    X, y = X[new_index], y[new_index].view(-1, 1)

    """
    index = int(np.ceil(x.shape[0] * .5))
    x_train = X[:index]
    y_train = y[:index]
    x_test = X[index:]
    y_test = y[index:]
    """

    # x = Variable(torch.FloatTensor([[0, 7], [1, 2]]).type(dtype), requires_grad=False)
    # X = Variable(torch.FloatTensor([[1, 2], [3, 4]]).type(dtype), requires_grad=False)
    # y = Variable(torch.FloatTensor([[1], [1]]).type(dtype), requires_grad=False)

    mlkn = MLKNClassifier()
    mlkn.add_layer(kerLinear(ker_dim=X.shape[0], out_dim=15, sigma=5, bias=True))
    mlkn.add_layer(kerLinear(ker_dim=X.shape[0], out_dim=3, sigma=.5, bias=True))

    mlkn.add_optimizer(torch.optim.SGD(params=mlkn.parameters(), lr=1e-4))
    mlkn.add_optimizer(torch.optim.SGD(params=mlkn.parameters(), lr=1e-4))

    mlkn.fit(n_epoch=(100, 100), batch_size=50, x=X, X=X, reg_coef=.1, y=y, n_class=int(n_class))