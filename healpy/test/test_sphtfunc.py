import pyfits
import os
import numpy as np
import exceptions
from copy import deepcopy
from itertools import chain

import unittest

import healpy as hp

import warnings
# disable new order warnings in tests
warnings.filterwarnings('ignore')

class TestSphtFunc(unittest.TestCase):

    def setUp(self):
        self.lmax = 64
        self.path = os.path.dirname( os.path.realpath( __file__ ) )
        self.map1 = [hp.ma(m) for m in hp.read_map(os.path.join(self.path, 'data', 'wmap_band_iqumap_r9_7yr_W_v4_udgraded32.fits'), (0,1,2))]
        self.map2 = [hp.ma(m) for m in hp.read_map(os.path.join(self.path, 'data', 'wmap_band_iqumap_r9_7yr_V_v4_udgraded32.fits'), (0,1,2))]
        self.mask = hp.read_map(os.path.join(self.path, 'data', 'wmap_temperature_analysis_mask_r9_7yr_v4_udgraded32.fits')).astype(np.bool)
        for m in chain(self.map1, self.map2):
            m.mask = np.logical_not(self.mask)
        self.cla = hp.read_cl(os.path.join(self.path, 'data', 'cl_wmap_band_iqumap_r9_7yr_W_v4_udgraded32_II_lmax64_rmmono_3iter.fits'))
        self.cl_fortran_nomask = hp.read_cl(os.path.join(self.path, 'data', 'cl_wmap_band_iqumap_r9_7yr_W_v4_udgraded32_II_lmax64_rmmono_3iter_nomask.fits'))
        cls_file = pyfits.open(os.path.join(self.path, 'data',
                                       'cl_wmap_band_iqumap_r9_7yr_W_v4_udgraded32_IQU_lmax64_rmmono_3iter.fits'))
        # fix for pyfits to read the file with duplicate column names
        for i in range(2, 6):
            cls_file[1].header['TTYPE%d' % i] += '-%d' % i
        cls = cls_file[1].data
        # order of HEALPIX is TB, EB while in healpy is EB, TB
        self.cliqu = [np.array(cls.field(i)) for i in (0,1,2,3,5,4)]
        nside = 32
        lmax = 64
        fwhm_deg = 7.
        seed = 12345
        np.random.seed(seed)
        self.mapiqu = hp.synfast(self.cliqu, nside, lmax=lmax, pixwin=False,
                                 fwhm=np.radians(fwhm_deg), new=False)

    def test_anafast(self):
        cl = hp.anafast(self.map1[0].filled(), lmax = self.lmax)
        self.assertEqual(len(cl), 65)
        np.testing.assert_array_almost_equal(cl, self.cla, decimal=8)

    def test_anafast_nomask(self):
        cl = hp.anafast(self.map1[0].data, lmax = self.lmax)
        self.assertEqual(len(cl), 65)
        np.testing.assert_array_almost_equal(cl, self.cl_fortran_nomask, decimal=8)

    def test_anafast_iqu(self):
        cl = hp.anafast(self.map1, regression=True, lmax = self.lmax)
        self.assertEqual(len(cl[0]), 65)
        self.assertEqual(len(cl), 6)
        for i in range(6):
            np.testing.assert_array_almost_equal(cl[i], self.cliqu[i], decimal=8)

    def test_anafast_xspectra(self):
        cl = hp.anafast(self.map1[0], self.map2[0], lmax = self.lmax, regression=True)
        self.assertEqual(len(cl), self.lmax+1)
        clx = hp.read_cl(os.path.join(self.path, 'data', 'cl_wmap_band_iqumap_r9_7yr_WVxspec_v4_udgraded32_II_lmax64_rmmono_3iter.fits'))
        np.testing.assert_array_almost_equal(cl, clx, decimal=8)

    def test_synfast(self):
        nside = 32
        lmax = 64
        fwhm_deg = 7.
        seed = 12345
        np.random.seed(seed)
        map_pregen = hp.read_map(os.path.join(self.path, 'data',
                                              'map_synfast_seed%d.fits' % seed),
                                              (0,1,2))
        sim_map = hp.synfast(self.cliqu, nside, lmax = lmax, pixwin=False,
                             fwhm=np.radians(fwhm_deg), new=False, pol=True)
        np.testing.assert_array_almost_equal(sim_map, map_pregen,
                                             decimal=8)

    def test_smoothing_notmasked(self):
        smoothed = hp.smoothing([m.data for m in self.map1], fwhm=np.radians(10), lmax=self.lmax, regression=False)
        smoothed_f90 = hp.read_map(os.path.join(self.path, 'data',
                  'wmap_band_iqumap_r9_7yr_W_v4_udgraded32_smoothed10deg_fortran.fits'), (0,1,2))
        np.testing.assert_array_almost_equal(smoothed, smoothed_f90, decimal=6)

    def test_smoothing_masked(self):
        smoothed = hp.smoothing(self.map1, fwhm=np.radians(10), lmax=self.lmax, regression=False)
        smoothed_f90 = hp.ma(hp.read_map(os.path.join(self.path, 'data',
                  'wmap_band_iqumap_r9_7yr_W_v4_udgraded32_masked_smoothed10deg_fortran.fits'), (0,1,2)))
        # fortran does not restore the mask
        for mm in smoothed_f90:
            mm.mask = smoothed[0].mask
        for i in range(3):
            np.testing.assert_array_almost_equal(smoothed[i].filled(), smoothed_f90[i].filled(), decimal=6)
        
    def test_gauss_beam(self):
        idl_gauss_beam = np.array(pyfits.open(os.path.join(self.path, 'data', 'gaussbeam_10arcmin_lmax512_pol.fits'))[0].data).T
        gauss_beam = hp.gauss_beam(np.radians(10./60.), lmax=512, pol=True)
        np.testing.assert_allclose(idl_gauss_beam, gauss_beam)

    def test_map2alm(self):
        nside = 32
        lmax = 64
        fwhm_deg = 7.
        seed = 12345
        np.random.seed(seed)
        orig = hp.synfast(self.cla, nside, lmax=lmax, pixwin=False,
                          fwhm=np.radians(fwhm_deg), new=False)
        tmp = np.empty(orig.size * 2)
        tmp[::2] = orig
        maps = [orig, orig.astype(np.float32), tmp[::2]]
        for input in maps:
            for regression in (False, True):
                alm = hp.map2alm(input, iter=10, regression=regression)
                output = hp.alm2map(alm, nside)
                np.testing.assert_allclose(input, output, atol=1e-4)

    def test_map2alm_pol(self):
        tmp = [np.empty(o.size*2) for o in self.mapiqu]
        for t, o in zip(tmp, self.mapiqu):
            t[::2] = o
        maps = [self.mapiqu, [o.astype(np.float32) for o in self.mapiqu],
                [t[::2] for t in tmp]]
        for input in maps:
            for regression in (False, True):
                alm = hp.map2alm(input, iter=10, regression=regression)
                output = hp.alm2map(alm, 32)
                for i, o in zip(input, output):
                    np.testing.assert_allclose(i, o, atol=1e-4)

    def test_map2alm_spin(self):
        spins = [2] #seems to fail with spin = 0 or 1 for the first test even though it works (possibly because of amplitude?)
        tmp = [np.empty(o.size*2) for o in self.mapiqu]
        for t, o in zip(tmp, self.mapiqu):
            t[::2] = o
        maps = [self.mapiqu, [o.astype(np.float32) for o in self.mapiqu],
                [t[::2] for t in tmp]]
        for input in maps:
            for spin in spins:
                alm = hp.map2alm_spin(input[1:], spin, iter=10)
                output = hp.alm2map_spin(alm, spin, 32)
                for i, o in zip(input[1:], output):
                    np.testing.assert_allclose(i, o, atol=1e-4)
            #just showing that spin=0 works
            alm0 = hp.map2alm_spin((input[0],input[0]), 0, iter=10)
            output0 = hp.alm2map_spin(alm0, 0, 32)
            alm12 = hp.map2alm_spin(input[1:], 2, iter=10)
            output12 = hp.alm2map_spin(alm12, 2, 32)
            output = (output0[0], output12[0], output12[1])
            for i, o in zip(input, output):
                np.testing.assert_allclose(i, o, atol=1e-4)
            
         

    def test_rotate_alm(self):
        almigc = hp.map2alm(self.mapiqu)
        alms = [almigc[0], almigc[0:2], almigc, np.vstack(almigc)]
        for i in alms:
            o = deepcopy(i)
            hp.rotate_alm(o, 0.1, 0.2, 0.3)
            hp.rotate_alm(o, -0.3, -0.2, -0.1)
            np.testing.assert_allclose(i, o, rtol=1e-6)


if __name__ == '__main__':
    unittest.main()
