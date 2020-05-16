# -*- coding: utf-8 -*-

import scikit_tt.data_driven.transform as tdt
import numpy as np
from scipy import linalg
from scikit_tt.tensor_train import TT


def amuset_hosvd(data_matrix, x_indices, y_indices, basis_list, threshold=1e-2, progress=False):
    """
    AMUSEt (AMUSE on tensors) using HOSVD.

    Apply tEDMD to a given data matrix by using AMUSEt with HOSVD. This procedure is a tensor-based
    version of AMUSE using the tensor-train format. For more details, see [1]_.

    Parameters
    ----------
    data_matrix : np.ndarray
        snapshot matrix
    x_indices : np.ndarray or list of np.ndarray
        index sets for snapshot matrix x
    y_indices : np.ndarray or list of np.ndarray
        index sets for snapshot matrix y
    basis_list : list of lists of lambda functions
        list of basis functions in every mode
    threshold : float, optional
        threshold for SVD/HOSVD, default is 1e-2
    progress : boolean, optional
        whether to show progress bar, default is False

    Returns
    -------
    eigenvalues : np.ndarray or list of np.ndarray
        tEDMD eigenvalues
    eigentensors : TT or list of TT
        tEDMD eigentensors in TT format

    References
    ----------
    ..[1] F. Nüske, P. Gelß, S. Klus, C. Clementi. "Tensor-based EDMD for the Koopman analysis of high-dimensional
          systems", arXiv:1908.04741, 2019
    """

    # define quantities
    eigenvalues = []
    eigentensors = []

    # construct transformed data tensor in TT format using direct approach
    psi = tdt.basis_decomposition(data_matrix, basis_list)

    # left-orthonormalization
    psi = psi.ortho_left(threshold=threshold, progress=progress)

    # extract last core
    last_core = psi.cores[-1]

    # convert x_indices and y_indices to lists
    if not isinstance(x_indices, list):
        x_indices = [x_indices]
        y_indices = [y_indices]

    # loop over all index sets
    for i in range(len(x_indices)):
        # compute reduced matrix
        matrix, u, s, v = _reduced_matrix(last_core, x_indices[i], y_indices[i])

        # solve reduced eigenvalue problem
        eigenvalues_reduced, eigenvectors_reduced = np.linalg.eig(matrix)
        idx = (np.abs(eigenvalues_reduced - 1)).argsort()
        eigenvalues_reduced = np.real(eigenvalues_reduced[idx])
        eigenvectors_reduced = np.real(eigenvectors_reduced[:, idx])

        # construct eigentensors
        eigentensors_tmp = psi
        eigentensors_tmp.cores[-1] = u.dot(np.diag(np.reciprocal(s))).dot(eigenvectors_reduced)[:, :, None, None]

        # append results
        eigenvalues.append(eigenvalues_reduced)
        eigentensors.append(eigentensors_tmp)

    # only return lists if more than one set of x-indices/y-indices was given
    if len(x_indices) == 1:
        eigenvalues = eigenvalues[0]
        eigentensors = eigentensors[0]

    return eigenvalues, eigentensors


def amuset_hocur(data_matrix, x_indices, y_indices, basis_list, max_rank=1000, multiplier=2, progress=False):
    """
    AMUSEt (AMUSE on tensors) using HOCUR.

    Apply tEDMD to a given data matrix by using AMUSEt with HOCUR. This procedure is a tensor-based
    version of AMUSE using the tensor-train format. For more details, see [1]_.

    Parameters
    ----------
    data_matrix : np.ndarray
        snapshot matrix
    x_indices : np.ndarray or list of np.ndarray
        index sets for snapshot matrix x
    y_indices : np.ndarray or list of np.ndarray
        index sets for snapshot matrix y
    basis_list : list of lists of lambda functions
        list of basis functions in every mode
    max_rank : int, optional
        maximum ranks for HOSVD as well as HOCUR, default is 1000
    multiplier : int
        multiplier for HOCUR
    progress : boolean, optional
        whether to show progress bar, default is False

    Returns
    -------
    eigenvalues : np.ndarray or list of np.ndarray
        tEDMD eigenvalues
    eigentensors : TT or list of TT
        tEDMD eigentensors in TT format

    References
    ----------
    ..[1] F. Nüske, P. Gelß, S. Klus, C. Clementi. "Tensor-based EDMD for the Koopman analysis of high-dimensional
          systems", arXiv:1908.04741, 2019
    """

    # define quantities
    eigenvalues = []
    eigentensors = []

    # construct transformed data tensor in TT format using HOCUR
    psi = tdt.hocur(data_matrix, basis_list, max_rank, repeats=1, multiplier=multiplier, progress=progress)

    # left-orthonormalization
    psi = psi.ortho_left(progress=progress)

    # extract last core
    last_core = psi.cores[-1]

    # convert x_indices and y_indices to lists
    if not isinstance(x_indices, list):
        x_indices = [x_indices]
        y_indices = [y_indices]

    # loop over all index sets
    for i in range(len(x_indices)):
        # compute reduced matrix
        matrix, u, s, v = _reduced_matrix(last_core, x_indices[i], y_indices[i])

        # solve reduced eigenvalue problem
        eigenvalues_reduced, eigenvectors_reduced = np.linalg.eig(matrix)
        idx = (np.abs(eigenvalues_reduced - 1)).argsort()
        eigenvalues_reduced = np.real(eigenvalues_reduced[idx])
        eigenvectors_reduced = np.real(eigenvectors_reduced[:, idx])

        # construct eigentensors
        eigentensors_tmp = psi
        eigentensors_tmp.cores[-1] = u.dot(np.diag(np.reciprocal(s))).dot(eigenvectors_reduced)[:, :, None, None]

        # append results
        eigenvalues.append(eigenvalues_reduced)
        eigentensors.append(eigentensors_tmp)

    # only return lists if more than one set of x-indices/y-indices was given
    if len(x_indices) == 1:
        eigenvalues = eigenvalues[0]
        eigentensors = eigentensors[0]

    return eigenvalues, eigentensors


def _reduced_matrix(last_core, x_indices, y_indices, threshold=1e-3):
    """
    Compute reduced matrix for AMUSEt.

    Parameters
    ----------
    last_core : np.ndarray
        last TT core of left-orthonormalized psi_z
    x_indices : np.ndarray
        index set for snapshot matrix x
    y_indices : np.ndarray
        index set for snapshot matrix y
    threshold : float, optional
        threshold for SVD, default is 1e-4

    Returns
    -------
    matrix : np.ndarray
        reduced matrix
    u : np.ndarray
        left-orthonormal matrix of the SVD of the last core of psi_x
    s : np.ndarray
        vector of singular values of the SVD of the last core of psi_x
    v : np.ndarray
        right-orthonormal matrix of the SVD of the last core of psi_x
    """

    # extract last cores of psi_x and psi_y
    psi_x_last = np.squeeze(last_core[:, x_indices, :, :])
    psi_y_last = np.squeeze(last_core[:, y_indices, :, :])

    # decompose last core of psi_x
    u, s, v = linalg.svd(psi_x_last, full_matrices=False, overwrite_a=True, check_finite=False, lapack_driver='gesvd')
    indices = np.where(s / s[0] > threshold)[0]
    u = u[:, indices]
    s = s[indices]
    v = v[indices, :]

    # construct reduced matrix
    matrix = v.dot(psi_y_last.T).dot(u).dot(np.diag(np.reciprocal(s)))

    return matrix, u, s, v
