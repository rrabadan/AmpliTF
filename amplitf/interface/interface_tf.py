# Copyright 2017 CERN for the benefit of the LHCb collaboration
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

import tensorflow as tf
import numpy as np
import itertools
import sys

_fptype = tf.float64
_ctype = tf.complex128
_args = None
_nll = None
_float_pars = None

function = tf.function(autograph=False, experimental_relax_shapes=True)
#function = tf.function(autograph=False)
generator_function = tf.function(autograph=False)
#def function(f) : return f

def set_single_precision():
    global _fptype, _ctype
    _fptype = tf.float32
    _ctype = tf.complex64


def set_double_precision():
    global _fptype, _ctype
    _fptype = tf.float64
    _ctype = tf.complex128


def fptype():
    global _fptype
    return _fptype


def ctype():
    global _ctype
    return _ctype


_interface_dict = {
  "sum" : "tf.add_n",
  "abs" : "tf.abs",
  "max" : "tf.maximum",
  "min" : "tf.minimum",
  #"complex" : "tf.complex",
  "conjugate" : "tf.conj",
  "real" : "tf.real",
  "imaginary" : "tf.imag",
  "sqrt": "tf.sqrt",
  "exp" : "tf.exp",
  "log" : "tf.math.log",
  "sin" : "tf.sin",
  "cos" : "tf.cos",
  "tan" : "tf.tan",
  "asin" : "tf.asin",
  "acos" : "tf.acos",
  "atan" : "tf.atan",
  "atan2" : "tf.atan2",
  "tanh" : "tf.tanh",
  "pow" : "tf.pow",
  "zeros" : "tf.zeros_like",
  "ones" : "tf.ones_like",
  "cross" : "tf.linalg.cross", 
  "reduce_max" : "tf.reduce_max", 
  "reduce_sum" : "tf.reduce_sum", 
  "reduce_mean" : "tf.reduce_mean", 
#  "stack" :  "tf.stack", 
#  "concat" : "tf.concat", 
  "where" :  "tf.where", 
  "equal" :  "tf.equal", 
  "logical_and" : "tf.logical_and", 
  "greater" : "tf.greater", 
  "less" :    "tf.less", 
}

m = sys.modules[__name__]
for k,v in _interface_dict.items() : 
  fun = exec(f"""
def {k}(*args) : 
  return {v}(*args)
  """)
  m.__dict__[k] = locals()[f"{k}"]

def complex(re, im) : 
    return tf.complex(re, im)

def cast_complex(re):
    """ Cast a real number to complex """
    return tf.cast(re, dtype=ctype())

def cast_real(re):
    """ Cast a number to real """
    return tf.cast(re, dtype=fptype())

def const(c):
    """ Declare constant """
    return tf.constant(c, dtype=fptype())

def bool_const(c):
    """ Declare constant """
    return tf.constant(c, dtype=bool)

def invariant(c):
    """ Declare invariant """
    return tf.constant([c], dtype=fptype())

def concat(x, axis = 0) : 
    return tf.concat(x, axis = axis)

def stack(x, axis = 0) : 
    return tf.stack(x, axis = axis)

def pi():
    return const(np.pi)

def interpolate(t, c):
    """
      Multilinear interpolation on a rectangular grid of arbitrary number of dimensions
        t : TF tensor representing the grid (of rank N)
        c : Tensor of coordinates for which the interpolation is performed
        return: 1D tensor of interpolated values
    """
    rank = len(t.get_shape())
    ind = tf.cast(tf.floor(c), tf.int32)
    t2 = tf.pad(t, rank*[[1, 1]], 'SYMMETRIC')
    wts = []
    for vertex in itertools.product([0, 1], repeat=rank):
        ind2 = ind + tf.constant(vertex, dtype=tf.int32)
        weight = tf.reduce_prod(
            1. - tf.abs(c - tf.cast(ind2, dtype=fptype())), 1)
        wt = tf.gather_nd(t2, ind2+1)
        wts += [weight*wt]
    interp = tf.reduce_sum(tf.stack(wts), 0)
    return interp

def set_seed(seed):
    """
      Set random seed for numpy
    """
    tf.random.set_seed(seed)

def variable(x, shape, dtype) : 
    return tf.Variable(x, shape, dtype)

def random_uniform(shape, minval, maxval) : 
    return tf.random.uniform(shape, minval, maxval, dtype = fptype())

from tensorflow.python.ops.resource_variable_ops import ResourceVariable

class FitParameter :

    def __init__(self, name, init_value, lower_limit, upper_limit, step_size = 1e-6) :
        self.var = ResourceVariable(init_value, shape = (), name = name, dtype = fptype(), trainable = True)
        self.init_value = init_value
        self.name = name
        self.step_size = step_size
        self.lower_limit = lower_limit
        self.upper_limit = upper_limit
        self.prev_value = None
        self.fixed = False
        self.error = 0.
        self.positive_error = 0.
        self.negative_error = 0.
        self.fitted_value = init_value

    def update(self, value) : 
        if value != self.prev_value : 
            self.var.assign(value)
            self.prev_value = value

    def __call__(self) : 
        return self.var

    def fix(self):
        self.fixed = True

    def float(self):
        self.fixed = False

    def setFixed(self, fixed):
        self.fixed = fixed

    def floating(self):
        """
          Return True if the parameter is floating and step size>0
        """
        return self.step_size > 0 and not self.fixed

    def numpy(self) : 
        return var.numpy()

def create_gradient(nll, args, float_pars) : 
    global _args, _nll, _float_pars
    _args = args
    _nll = nll
    _float_pars = float_pars
    return True

def gradient(par) :
    global _args, _nll, _float_pars
    for i,p in enumerate(_float_pars) : p.update(par[i])
    kwargs = { p.name : p() for p in _float_pars }
    float_vars = [ i() for i in _float_pars ]
    gradient.n += 1
    with tf.GradientTape() as gt : 
        gt.watch( float_vars )
        nll_val = _nll(*_args, kwargs)
    g = gt.gradient(nll_val, float_vars, unconnected_gradients=tf.UnconnectedGradients.ZERO)
    g_val = [ i.numpy() for i in g ]
    return g_val