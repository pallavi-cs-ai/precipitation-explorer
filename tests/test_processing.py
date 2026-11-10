import importlib.util
from pathlib import Path
import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('explore', Path(__file__).parents[1] / 'scripts/explore.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_units():
    np.testing.assert_allclose(m.to_mm(np.array([.001, .01]), 'm'), [1, 10])
    np.testing.assert_allclose(m.to_mm(np.array([1., 10.]), 'kg m**-2'), [1, 10])
    with pytest.raises(ValueError):
        m.to_mm(np.array([1.]), 'unknown')


def test_interval_and_reset_detection():
    np.testing.assert_allclose(m.interval(np.array([2., 3.]), np.array([5., 3.]), 0), [3, 0])
    with pytest.raises(ValueError):
        m.interval(np.array([10.]), np.array([1.]), .001)
    np.testing.assert_allclose(m.interval(np.array([1.]), np.array([.9999]), .001), [0])
