"""
Implement principle-component-analysis tools.

.. include common links, assuming primary doc root is up one directory
.. include:: ../links.rst
"""
from IPython import embed

import numpy as np

from matplotlib import pyplot as plt

from sklearn.decomposition import PCA

from pypeit import msgs
from pypeit import utils
from pypeit.core import fitting
from IPython import embed

def pca_decomposition(vectors, npca=None, pca_explained_var=99.0, mean=None):
    r"""
    Perform principle-component analysis (PCA) for a set of 1D vectors.

    The vectors are first passed to an unconstrained PCA to determine
    the growth curve of the accounted variance as a function of the
    PCA component. If specifying a number of PCA components to use
    (see `npca`), this yields the percentage of the variance
    accounted for in the analysis. If instead specifying the target
    variance percentage (see `pca_explained_var`), this is used to
    determine the number of PCA components to use in the final
    analysis.

    .. note::

        This is a fully generalized convenience function for a
        specific use of `sklearn.decomposition.PCA`_. When used
        within PypeIt, the vectors to decompose (see, e.g.,
        :class:`pypeit.edgetrace.EdgeTracePCA`) typically have the
        length of the spectral axis. This means that, within PypeIt,
        arrays are typically transposed when passed to this function.

    Args:
        vectors (`numpy.ndarray`_):
            A 2D array with vectors to analyze with shape
            :math:`(N_{\rm vec}, N_{\rm pix})`. All vectors must be
            the same length and cannot be masked.
        npca (:obj:`bool`, optional):
            The number of PCA components to keep, which must be less
            than :math:`N_{\rm vec}`. If `npca==nvec`, no PCA
            compression occurs. If None, `npca` is automatically
            determined by calculating the minimum number of
            components required to explain a given percentage of
            variance in the data. (see `pca_explained_var`).
        pca_explained_var (:obj:`float`, optional):
            The percentage (i.e., not the fraction) of the variance
            in the data accounted for by the PCA used to truncate the
            number of PCA coefficients to keep (see `npca`). Ignored
            if `npca` is provided directly.
        mean (`numpy.ndarray`_, optional):
            The mean value of each vector to subtract from the data
            before performing the PCA. If None, this is determined
            directly from the data. Shape must be :math:`N_{\rm
            vec}`.

    Returns:
        Returns four `numpy.ndarray`_ objects:
            - The coefficients of each PCA component, `coeffs`. Shape
              is :math:`(N_{\rm vec},N_{\rm comp})`.
            - The PCA component vectors, `components`. Shape is
              :math:`(N_{\rm comp},N_{\rm pix})`.
            - The mean offset of each PCA for each pixel, `pca_mean`.
              Shape is :math:`(N_{\rm pix},)`.
            - The mean offset applied to each vector before the PCA,
              `vec_mean`. Shape is :math:`(N_{\rm vec},)`.

        To reconstruct the PCA representation of the input vectors, compute::

            np.dot(coeffs, components) + pca_mean[None,:] + vec_mean[:,None]

    """
    # Check input
    if vectors.ndim != 2:
        raise ValueError('Input trace data must be a 2D array')
    nvec = vectors.shape[0]
    if nvec < 2:
        raise ValueError('There must be at least 2 vectors for the PCA analysis.')

    # Take out the mean value of each vector
    if mean is None:
        mean = np.mean(vectors, axis=1)
    vec_pca = vectors - mean[:,None]

    # Perform unconstrained PCA of the vectors
    pca = PCA()
    pca.fit(vec_pca)

    # Compute the cumulative distribution of the variance explained by the PCA components.
    # TODO: Why round to 6 decimals?  Why work in percentages?
    var_growth = np.cumsum(np.round(pca.explained_variance_ratio_, decimals=6) * 100)
    # Number of components for a full decomposition
    npca_tot = var_growth.size

    msgs.info('The unconstrained PCA yields {0} components.'.format(npca_tot))
    if npca is None:
        # Assign the number of components to use based on the variance
        # percentage
        if pca_explained_var is None:
            raise ValueError('Must provide percentage explained variance.')
        npca = int(np.ceil(np.interp(pca_explained_var, var_growth, np.arange(npca_tot)+1))) \
                    if var_growth[0] < pca_explained_var else 1
    elif npca_tot < npca:
        raise ValueError('Too few vectors for a PCA of the requested dimensionality.  '
                         'The full (uncompressing) PCA has {0} component(s)'.format(npca_tot)
                         + ', which is less than the requested {0} component(s).'.format(npca)
                         + '  Lower the number of requested PCA component(s) or turn off the PCA.')

    msgs.info('PCA will include {0} component(s), '.format(npca)
              + 'containing {0:.3f}% of the total variance.'.format(var_growth[npca-1]))

    # Determine the PCA coefficients with the revised number of
    # components, and return the results
    pca = PCA(n_components=npca)
    pca_coeffs = pca.fit_transform(vec_pca)
    return pca_coeffs, pca.components_, pca.mean_, mean


def fit_pca_coefficients(coeff, order, ivar=None, weights=None, function='legendre', lower=3.0,
                         upper=3.0, maxrej=1, maxiter=25, coo=None, minx=None, maxx=None, 
                         debug=False):
    r"""
    Fit a parameterized function to a set of PCA coefficients,
    primarily for the purpose of predicting coefficients at
    intermediate locations.

    The coefficients of each PCA component are fit by a low-order
    polynomial, where the abscissa is set by the `coo` argument (see
    :func:`pypeit.fitting.robust_fit`).

    .. note::
        This is a general function, not really specific to the PCA;
        and is really just a wrapper for
        :func:`pypeit.fitting.robust_fit`.

    Args:
        coeff (`numpy.ndarray`_):
            PCA component coefficients. If the PCA decomposition used
            :math:`N_{\rm comp}` components for :math:`N_{\rm vec}`
            vectors, the shape of this array must be :math:`(N_{\rm
            vec}, N_{\rm comp})`. The array can be 1D with shape
            :math:`(N_{\rm vec},)` if there was only one PCA
            component.
        order (:obj:`int`, `numpy.ndarray`_):
            The order, :math:`o`, of the function used to fit the PCA
            coefficients. Can be a single number for all PCA
            components, or an array with an order specific to each
            component. If the latter, the shape must be
            :math:`(N_{\rm comp},)`.
        ivar (`numpy.ndarray`_, optional):
            Inverse variance in the PCA coefficients to use during
            the fit; see the `invvar` parameter of
            :func:`pypeit.fitting.robust_fit`. If None, fit is
            not error weighted. If a vector with shape :math:`(N_{\rm
            vec},)`, the same error will be assumed for all PCA
            components (i.e., `ivar` will be expanded to match the
            shape of `coeff`). If a 2D array, the shape must match
            `coeff`.
        weights (`numpy.ndarray`_, optional):
            Weights to apply to the PCA coefficients during the fit;
            see the `weights` parameter of
            :func:`pypeit.fitting.robust_fit`. If None, the
            weights are uniform. If a vector with shape
            :math:`(N_{\rm vec},)`, the same weights will be assumed
            for all PCA components (i.e., `weights` will be expanded
            to match the shape of `coeff`). If a 2D array, the shape
            must match `coeff`.
        function (:obj:`str`, optional):
            Type of function used to fit the data.
        lower (:obj:`float`, optional):
            Number of standard deviations used for rejecting data
            **below** the mean residual. If None, no rejection is
            performed. See :func:`fitting.robust_fit`.
        upper (:obj:`float`, optional):
            Number of standard deviations used for rejecting data
            **above** the mean residual. If None, no rejection is
            performed. See :func:`fitting.robust_fit`.
        maxrej (:obj:`int`, optional):
            Maximum number of points to reject during fit iterations.
            See :func:`fitting.robust_fit`.
        maxiter (:obj:`int`, optional):
            Maximum number of rejection iterations allows. To force
            no rejection iterations, set to 0.
        coo (`numpy.ndarray`_, optional):
            Floating-point array with the independent coordinates to
            use when fitting the PCA coefficients. If None, simply
            uses a running number. Shape must be :math:`(N_{\rm
            vec},)`.
        minx, maxx (:obj:`float`, optional):
            Minimum and maximum values used to rescale the
            independent axis data. If None, the minimum and maximum
            values of `coo` are used. See
            :func:`fitting.robust_fit`.
        debug (:obj:`bool`, optional):
            Show plots useful for debugging.

    Returns:
        Returns five objects:
            - A boolean `numpy.ndarray`_ masking data (`coeff`) that
              were rejected during the polynomial fitting. Shape is the
              same as the input `coeff`.
            - A `list` of `numpy.ndarray`_ objects (or a single
              `numpy.ndarray`_), one per PCA component where the length
              of the 1D array is the number of coefficients fit to the
              PCA-component coefficients. The number of function
              coefficients is typically :math:`N_{\rm coeff} = o+1`.
            - The minimum
            - and maximum coordinate values used to rescale
              the abscissa during the fitting.
            - A `list` of `:class:pypeit.core.fitting.PypeItFit` objects
    """
    # Check the input
    #   - Get the shape of the input data to fit
    _coeff = np.asarray(coeff)
    if _coeff.ndim == 1:
        _coeff = np.expand_dims(_coeff, 1)
    if _coeff.ndim != 2:
        raise ValueError('Array with coefficiencts cannot be more than 2D')
    nvec, npca = _coeff.shape
    #   - Check the inverse variance
    _ivar = None if ivar is None else np.atleast_2d(ivar)
    if _ivar is not None and _ivar.shape != _coeff.shape:
        raise ValueError('Inverse variance array does not match input coefficients.')
    #   - Check the weights
    _weights = np.ones(_coeff.shape, dtype=float) if weights is None else np.asarray(weights)
    if _weights.ndim == 1:
        _weights = np.tile(_weights, (_coeff.shape[1],1)).T
    if _weights.shape != _coeff.shape:
        raise ValueError('Weights array does not match input coefficients.')
    #   - Set the abscissa of the data if not provided and check its
    #   shape
    if coo is None:
        coo = np.arange(nvec, dtype=float)
    if coo.size != nvec:
        raise ValueError('Vector coordinates have incorrect shape.')
    #   - Check the order of the functions to fit
    _order = np.atleast_1d(order)
    if _order.size == 1:
        _order = np.full(npca, order, dtype=int)
    if _order.size != npca:
        raise ValueError('Function order must be a single number or one number per PCA component.')
    #   - Force the values of minx and maxx if they're not provided directly
    if minx is None:
        minx = np.amin(coo)
    if maxx is None:
        maxx = np.amax(coo)

    # Instantiate the output
    coeff_used = np.ones(_coeff.shape, dtype=bool)
    fit_coeff = [None]*npca

    # TODO: This fitting is fast. Maybe we should determine the best
    #  order for each PCA component, up to some maximum, by comparing
    #  reduction in chi-square vs added number of parameters?

    # Fit the coefficients of each PCA component so that they can be
    # interpolated to other coordinates.

    inmask = np.ones_like(coo, dtype=bool)
    pypeitFits = []
    for i in range(npca):
        pypeitFit = fitting.robust_fit(coo, _coeff[:,i], _order[i], in_gpm=inmask,
                                           invvar=None if _ivar is None else _ivar[:,i],
                                           weights=_weights[:,i], function=function,
                                           maxiter=maxiter, lower=lower, upper=upper,
                                           maxrej=maxrej, sticky=False, use_mad=_ivar is None,
                                           minx=minx, maxx=maxx)
        coeff_used[:,i], fit_coeff[i] = pypeitFit.gpm, pypeitFit.fitc
        pypeitFits.append(pypeitFit)
        if debug:
            # Visually check the fits
            xvec = np.linspace(np.amin(coo), np.amax(coo), num=100)
            rejected = np.invert(coeff_used[:,i]) & inmask
            plt.scatter(coo[inmask], _coeff[inmask,i], marker='.', color='k', s=100,
                        facecolor='none', label='pca coeff')
            plt.scatter(coo[np.invert(inmask)], _coeff[np.invert(inmask),i], marker='.',
                        color='orange', s=100, facecolor='none',
                        label='pca coeff, masked from previous')
            if np.any(rejected):
                plt.scatter(coo[rejected], _coeff[rejected,i], marker='x', color='C3', s=80, 
                            label='robust_polyfit_djs rejected')
            plt.plot(xvec, pypeitFit.eval(xvec),
                     linestyle='--', color='C0',
                     label='Polynomial fit of order={0}'.format(_order[i]))
            plt.xlabel('Trace Coordinate', fontsize=14)
            plt.ylabel('PCA Coefficient', fontsize=14)
            plt.title('PCA Fit for Dimension #{0}/{1}'.format(i+1, npca))
            plt.legend()
            plt.show()

        inmask=coeff_used[:,i]
    # Return arrays that match the shape of the input data
    if coeff.ndim == 1:
        return np.invert(coeff_used)[0], fit_coeff[0], minx, maxx
    return np.logical_not(coeff_used), fit_coeff, minx, maxx, pypeitFits


def pca_predict(x, pypeitFits, pca_components, pca_mean, mean):
    r"""
    Use a model of the PCA coefficients to predict vectors at the
    specified coordinates.

    Args:
        x (:obj:`float`, `numpy.ndarray`_):
            One or more trace coordinates at which to sample the PCA
            coefficients and produce the PCA model. As used within
            PypeIt, this is typically the spatial pixel coordinate or
            echelle order number.
        pypeitFits (:obj:`list`):
            List of :class:`pypeit.fitting.PypeItFit` objects
        pca_mean (`numpy.ndarray`_):
            The mean offset of the PCA decomposotion for each pixel.
            Shape is :math:`(N_{\rm pix},)`.
        mean (:obj:`float`, `numpy.ndarray`_):
            The mean offset of each trace coordinate to use for the
            PCA prediction. This is typically identical to `x`, and
            its shape must match `x`.
        minx, maxx (:obj:`float`, optional):
            Minimum and maximum values used to rescale the
            independent axis data. See
            :func:`utils.robust_polyfit_djs`.
        function (:obj:`str`, optional):
            The functional used to fit the PCA coefficients.
    
    Returns:
        `numpy.ndarray`_: PCA constructed vectors, one per position
        `x`. Shape is either :math:`(N_{\rm pix},)` or :math:`(N_{\rm
        x},N_{\rm pix})`, depending on the input shape/type of `x`.
    """
    _x = np.atleast_1d(x)
    _mean = np.atleast_1d(mean)
    if _x.ndim != 1:
        raise ValueError('Coordinates for predicted vectors must be no more than 1D.')
    if _mean.shape != _x.shape:
        raise ValueError('Input mean must match the shape of the input prediction coordinates.')
    # Calculate the coefficients using the best fitting function
    npca = pca_components.shape[0]
    c = np.zeros((_x.size, npca), dtype=float)
    for i in range(npca):
        c[:,i] = pypeitFits[i].eval(_x)
    # Calculate the predicted vectors and return them
    vectors = np.dot(c, pca_components) + pca_mean[None,:] + _mean[:,None]
    return vectors if isinstance(x, np.ndarray) else vectors[0,:]


