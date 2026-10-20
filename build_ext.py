"""Build the C++ Hayashi-Yoshida core in place:  python build_ext.py build_ext --inplace   (needs pybind11 and a C++17
compiler; build.ps1 does it with MSVC on Windows).  Without it d1basis.leadlag runs the same estimator in Python."""
import sys

from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

# no fused multiply-add: the compiled sums must round exactly as numpy's do
FP = ["/fp:precise"] if sys.platform == "win32" else ["-ffp-contract=off"]

setup(name="d1basis-ext", ext_modules=[Pybind11Extension("d1basis._hy", ["cpp/hy.cpp"], cxx_std=17, extra_compile_args=FP)], cmdclass={"build_ext": build_ext}, zip_safe=False)
