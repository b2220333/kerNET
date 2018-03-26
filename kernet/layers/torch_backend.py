# -*- coding: utf-8 -*-
# torch 0.3.1

import torch
import numpy as np

def gaussianKer(x, y, sigma):
    """
    Gaussian kernel: k(x, y) = exp(-||x-y||_2^2 / (2 * sigma^2)).
    Arguments must be matrices or 1darrays. 1darrays will be converted to
    matrices. While the last dimension of its two
    arguments must be identical, this function supports broadcasting in the
    first dimension. Can be used to calculate Gram matrix.

    Parameters
    ----------

    x : Tensor, shape (n1_example, dim)

    y : Tensor, shape (n2_example, dim)

    sigma : scalar

    Returns
    -------

    gram : Tensor, shape (n1_example, n2_example)
        Technically not a Gram matrix when x!=y, only using this name for
        convenience.
    """
    if len(x.shape)==1: x.unsqueeze_(0)
    if len(y.shape)==1: y.unsqueeze_(0)
    assert len(x.shape)==2 and len(y.shape)==2 and x.shape[1]==y.shape[1]
    # TODO: if len(x.shape)>=2 but only two dimensions are nontrivial, should
    # allow computation after squeezing into 2darray
    # TODO: support ndarrays where n>2, e.g., RGB images may have shape
    # (n_example, 3_channels, channel_dim). shape of return should
    # always be (n1_example, n2_example), need to be careful with broadcasting
    # and which dimensions to sum out in this part:
    # y.sub(x.unsqueeze(1)).pow(2).sum(dim=-1)

    gram = y.sub(x.unsqueeze(1)).pow(2).sum(dim=-1).mul(-1./(2*sigma**2)).exp()
    return gram


def kerMap(x, X, sigma):
    """
    For all x_ \in x, computes the image of x_ under the mapping:
        f: f(x_) -> (k(x_1, x_), k(x_2, x_), ..., k(x_n, x_)),
    where k is a kernel function and X = {x_1, x_2, ..., x_n}.
    Currently only supports Gaussian kernel:
    k(x, y) = exp(-||x-y||_2^2 / (2 * sigma^2)).
    Can be used to calculate Gram matrix.

    Parameters
    ----------

    x : Tensor, shape (batch_size, dim)

    X : Tensor, shape (n_example, dim)

    sigma : scalar

    Returns
    -------

    x_image : Tensor, shape (batch_size, n_example)
    """
    x_image = gaussianKer(x, X, sigma)

    return x_image

if __name__=='__main__':
    x = torch.FloatTensor([[1, 2]])
    X = torch.FloatTensor([[1, 2], [3, 4], [5, 6]])
    y = kerMap(x, X, sigma=1)
    print(y)

def ideal_gram(y):
    # TODO: to be checked for multi-class, check if one-hot transform applied to x and y separately
    # produces the same codebook, i.e., is class 1 transformed into 001 in both x, y
    # or is it transformed into 001 in x but 010 in y
    """
    Get the "perfect" Gram matrix for classification using labels only: two
    items with the same label have entry 1 in the Gram matrix and everywhere
    else is 0. Using such a Gram matrix, the dataset can always be perfectly
    classified. This is slightly more general than the similar concept introduced
    in <on kernel-target alignment>, in there, they substitute 0 with -1.

    :type y: tf n*0 vector
    :type noisy: Boolean
    :type c: float, coef controling the magnitude of the noise added
    :rtype: tf n*n matrix
    """
    ideal_gram = tf.matmul(tf.one_hot(x, depth=n_classes), tf.transpose(
    tf.one_hot(y, depth=n_classes)))
    return ideal

def alignment(gram, true_gram):
    """
    Get kernel alignment as a cost function. Input must be 2*2 matrices. So
    works best with multi_k=False/one Gram at each layer.
    Raises an error if one of the two matrices only has 0 entries.
    Compatible with batch training.

    :type K: tf 2*2 matrix
    :type perfect_K: tf 2*2 matrix
    :rtype: tf scalar
    """
    K = tf.cast(K, tf.float32)
    perfect_K = tf.cast(perfect_K, tf.float32)

    alignment = tf.reduce_sum(K * perfect_K) / \
    tf.sqrt(tf.reduce_sum(K * K) * tf.reduce_sum(perfect_K * perfect_K))
    return alignment