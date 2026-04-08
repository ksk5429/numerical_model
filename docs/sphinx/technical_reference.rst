Technical reference
===================

Mathematical formulation, unit conventions, coordinate systems, and
sign conventions for the Op\ :sup:`3` framework. This is the
authoritative specification for anyone reviewing the code or
reproducing the results in a publication.

.. contents:: Contents
   :local:
   :depth: 2

1. Unit system
--------------

Op\ :sup:`3` uses **strict SI units everywhere in public APIs**:

.. list-table::
   :header-rows: 1

   * - Quantity
     - Unit
     - Symbol
   * - Length
     - metre
     - ``m``
   * - Mass
     - kilogram
     - ``kg``
   * - Time
     - second
     - ``s``
   * - Force
     - newton
     - ``N``
   * - Pressure / stress / shear modulus
     - pascal
     - ``Pa``
   * - Stiffness (translation)
     - newton / metre
     - ``N/m``
   * - Stiffness (rotation)
     - newton-metre / radian
     - ``Nm/rad``
   * - Mass density
     - kilogram / cubic metre
     - ``kg/m^3``
   * - Angle
     - radian
     - ``rad``

The **only exception** is frequency, which is reported in Hz (cycles/s)
in line with published NREL / DNV / IEC tables. Internal OpenSees
eigenvalues are angular frequency squared and are converted via
:math:`f = \sqrt{\lambda}/(2\pi)`.

CSV files carrying geotechnical data use **mixed conventions** inherited
from the OptumGX / SACS export formats:

* ``depth_m`` -- metres (SI)
* ``k_ini_kN_per_m`` -- kilonewtons / metre (multiplied by 1e3 on load)
* ``p_ult_kN_per_m`` -- kilonewtons / metre
* ``D_total_kJ`` -- kilojoules
* ``w_z`` -- dimensionless weight
* ``su`` -- pascal (SI)
* ``phi`` -- degrees (converted to radians internally when needed)

The unit invariance test 2.13 in
:doc:`verification` verifies that the entire pipeline gives
bit-identical frequencies when rebuilt in mm / N / tonne units.

2. Coordinate system
--------------------

Op\ :sup:`3` uses a right-handed Cartesian coordinate system that
matches the OpenFAST v5 / SubDyn convention:

.. code-block:: text

   +z  (upward, from mudline toward hub)
   ^
   |
   +--------> +x  (downwind, nominal wind direction)
   /
  /
 +y  (to the left of the rotor when viewed from behind)

- The **tower base** sits on or above the mudline, typically at
  ``z = TowerBsHt`` read from the OpenFAST ElastoDyn file.
- The **mudline** is at ``z = 0`` for monopiles and at
  ``z = -WaterDepth`` for offshore structures measured from MSL.
- The **hub** is at ``z = TowerHt + Twr2Shft + NacCMzn`` above the
  tower base (v0.3.0+ with the rigid CM offset).
- Tower foreaft bending is in the ``x-z`` plane; side-side is in
  ``y-z``.

3. Degree-of-freedom numbering
------------------------------

OpenSees in 3D with ``-ndf 6`` uses this DOF ordering at every node:

.. code-block:: text

   DOF 1 : translation in x (Ux)     foreaft tower displacement
   DOF 2 : translation in y (Uy)     side-side tower displacement
   DOF 3 : translation in z (Uz)     axial
   DOF 4 : rotation about x (Rx)     tower side-side bending moment
   DOF 5 : rotation about y (Ry)     tower foreaft bending moment
   DOF 6 : rotation about z (Rz)     torsion

The 6x6 head-stiffness matrix ``K`` is indexed in this order:

.. code-block:: text

              Ux    Uy    Uz    Rx    Ry    Rz
         +---------------------------------------
    Ux   | Kxx    0     0     0     K_x_ry  0
    Uy   | 0    Kyy    0    K_y_rx  0       0
    Uz   | 0     0    Kzz    0      0       0
    Rx   | 0   K_y_rx  0   Krxrx    0       0
    Ry   | K_x_ry 0    0     0    Kryry     0
    Rz   | 0     0     0     0      0      Krzrz

The off-diagonal coupling terms ``K[0,4]`` and ``K[1,3]`` are the
lateral-rocking coupling. For a monopile in the Op\ :sup:`3`
convention ``K[0,4] < 0`` and ``K[1,3] > 0``.

4. Foundation modes -- mathematical definitions
------------------------------------------------

Mode A (FIXED)
~~~~~~~~~~~~~~

Pure rigid constraint at the tower base node via ``ops.fix``. No
spring elements, no compliance. Used as the limiting case for Mode B
(``K_diag -> infinity``).

Mode B (STIFFNESS_6X6)
~~~~~~~~~~~~~~~~~~~~~~

A lumped 6x6 elastic relation between forces and displacements at
the tower base:

.. math::

   \begin{bmatrix} F_x \\ F_y \\ F_z \\ M_x \\ M_y \\ M_z \end{bmatrix}
   =
   \mathbf{K}_{6\times 6}
   \begin{bmatrix} u_x \\ u_y \\ u_z \\ \psi_x \\ \psi_y \\ \psi_z \end{bmatrix}

``K`` must be symmetric and positive-definite (enforced by the V&V
test C4). The current Op\ :sup:`3` implementation
uses an OpenSees ``zeroLength`` element with six ``uniaxialMaterial``
"Elastic" instances on the diagonal; full off-diagonal coupling via
``zeroLengthND`` is a v0.4 extension.

Mode C (DISTRIBUTED_BNWF)
~~~~~~~~~~~~~~~~~~~~~~~~~

Distributed Winkler springs along the embedded length of the pile.
At depth :math:`z`, the local reaction is:

.. math::

   p(z, v) = k(z) \cdot v

where ``k(z)`` is read from the spring profile CSV. The head
stiffness is obtained by Winkler integration:

.. math::

   K_{xx} &= \int_0^L k(z)\,dz \\
   K_{x,\psi_y} &= \int_0^L k(z) \cdot z\,dz \\
   K_{\psi_y\psi_y} &= \int_0^L k(z) \cdot z^2\,dz + \int_0^L k_m(z)\,dz

where :math:`k_m(z)` is the distributed moment stiffness (zero if
not provided). Scour relief is applied by multiplying :math:`k(z)`
by :math:`\sqrt{(z-s)/z}` for :math:`z > s` (and zero below).

Mode D (DISSIPATION_WEIGHTED)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The novel Op\ :sup:`3` contribution. The elastic Mode C springs are
multiplied by a dimensionless weighting function:

.. math::

   w(D, D_{\max}, \alpha, \beta) = \beta + (1 - \beta)
   \left(1 - \frac{D}{D_{\max}}\right)^\alpha

where :math:`D(z)` is the cumulative plastic dissipation from an
OptumGX analysis and :math:`D_{\max}` is the layer maximum. The
weighted stiffness is:

.. math::

   k^D_i = k^{\rm el}_i \cdot w(D_i, D_{\max}, \alpha, \beta)

Parameters :math:`\alpha` (default 1.0) and :math:`\beta` (default
0.05) are the only free knobs. See
`docs/MODE_D_DISSIPATION_WEIGHTED.md <https://github.com/ksk5429/numerical_model/blob/main/docs/MODE_D_DISSIPATION_WEIGHTED.md>`_ for the full formulation,
limits, and validation gates.

5. PISA conic shape function
----------------------------

The PISA framework (Burd 2020 / Byrne 2020) represents soil
reactions via a 4-parameter conic curve:

.. math::

   \frac{y}{y_u} = \frac{1 + n(1 - x/x_u) - \sqrt{\left(1 + n(1 - x/x_u)\right)^2 - 4\,n\,\frac{x}{x_u}\,(1-n)}}{2(1-n)}

with four component-specific parameters:

* :math:`k` -- dimensionless initial slope
* :math:`n` -- curvature exponent (0 = bilinear, 1 = elastic-perfectly-plastic)
* :math:`x_u` -- ultimate normalised displacement
* :math:`y_u` -- ultimate normalised reaction

In Op\ :sup:`3` the four parameters are **depth-dependent**
(v0.3.2+):

.. math::

   k(z/D) &= k_1 + k_2 \cdot (z/D) \\
   n(z/D) &= n_1 + n_2 \cdot (z/D) \\
   x_u(z/D) &= x_{u,1} + x_{u,2} \cdot (z/D) \\
   y_u(z/D) &= y_{u,1} + y_{u,2} \cdot (z/D)

For base components the variable is :math:`L/D` (the full pile
slenderness) rather than :math:`z/D`. Coefficients are pinned to the
published calibrations:

* **Sand** -- Burd 2020 Table 5 (``PISA_SAND`` in ``op3/standards/pisa.py``)
* **Clay** -- Byrne 2020 Table 4 second-stage (``PISA_CLAY``)

The normalisations (Byrne 2020 Table 1) are:

.. math::

   \bar{p} &= \frac{p}{\sigma'_v \cdot D}     &\bar{v} &= \frac{v \cdot G}{D \cdot \sigma'_v} \\
   \bar{m} &= \frac{m}{\sigma'_v \cdot D^2}   &\bar{\psi} &= \frac{\psi \cdot G}{\sigma'_v} \\
   \bar{H_B} &= \frac{H_B}{\sigma'_v \cdot D^2} &\bar{M_B} &= \frac{M_B}{\sigma'_v \cdot D^3}

For sand, :math:`\sigma'_v` is the effective vertical stress
(approximated as :math:`\gamma'_{\rm eff} \cdot z` with a default
:math:`\gamma' = 10 \text{ kN/m}^3`). For clay the normalising
pressure is the undrained shear strength :math:`s_u`.

6. Effective head stiffness under eccentric load
------------------------------------------------

The McAdam 2020 / Byrne 2020 field-test ``k_Hinit`` metric is the
secant slope of H vs ground-level displacement with the load applied
at height :math:`h` above the seabed. For the 2x2 (x, ry) block of
K, the ground-level displacement is:

.. math::

   u_x &= \frac{K_{ryry} - h K_{x,ry}}{\det} H \\
   \det &= K_{xx} K_{ryry} - K_{x,ry}^2

so the effective head stiffness is:

.. math::

   k_{H,\rm init} = \frac{\det}{K_{ryry} - h \cdot K_{x,ry}}

This is implemented in
:func:`op3.standards.pisa.effective_head_stiffness` and is the
correct comparator to the published field-test k_Hinit values.

7. Hardin-Drnevich modulus reduction
------------------------------------

Cyclic soil degradation follows the modified hyperbolic:

.. math::

   \frac{G}{G_{\max}} = \frac{1}{1 + (\gamma / \gamma_{\rm ref})^a}

with curvature exponent :math:`a = 1` (default) or :math:`a = 0.92`
(Darendeli 2001). At :math:`\gamma = \gamma_{\rm ref}` the ratio is
exactly 0.5 by definition.

Reference strain is plasticity-index-dependent via Vucetic & Dobry
(1991):

.. math::

   \gamma_{\rm ref}(PI = 0)     &\approx 1 \times 10^{-4}  \\
   \gamma_{\rm ref}(PI = 200)   &\approx 5 \times 10^{-3}

with linear-in-log interpolation between the knots digitised from
Figure 5 of the paper.

8. Tower bending frequency formulas (analytical references)
------------------------------------------------------------

Op\ :sup:`3` is verified against Euler-Bernoulli closed-form cantilever
results.

Cantilever without tip mass
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

   f_n = \frac{\beta_n^2}{2\pi L^2} \sqrt{\frac{EI}{m_L}}

with :math:`\beta_1 L = 1.87510` for the first mode,
:math:`\beta_2 L = 4.69409` for the second, etc. ``m_L`` is the
mass per unit length.

Cantilever with tip mass (Rayleigh)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

   f_1 = \frac{1}{2\pi} \sqrt{\frac{3 EI}{L^3 (M_{\rm tip} + 0.2235\, m_L L)}}

from Blevins (1979) Table 8-1. The 0.2235 coefficient is the
Rayleigh modal-mass fraction for the first mode of a uniform
cantilever.

Static tip deflection
~~~~~~~~~~~~~~~~~~~~~

.. math::

   \delta = \frac{P L^3}{3 EI}

used in the V&V test C for a bit-exact comparison.

9. RNA mass and inertia convention
----------------------------------

The rotor-nacelle assembly (RNA) is placed at a rigid offset from
the tower top via ``ops.rigidLink("beam", ...)``:

.. math::

   \text{offset} = (N_{CM,xn}, 0, \text{Twr2Shft} + N_{CM,zn})

read from the OpenFAST ElastoDyn file. The rigid CM node carries:

* Translational mass :math:`m_{RNA} = m_{\rm hub} + m_{\rm nac} + n_{\rm blades} \cdot m_{\rm blade}`
* Roll inertia (x-axis) :math:`\approx (I_{\rm hub} + I_{\rm nac,yaw})/2`
* Pitch inertia (y-axis) :math:`= I_{\rm hub}`
* Yaw inertia (z-axis) :math:`= I_{\rm nac,yaw}`

10. Hermite polynomial chaos
----------------------------

The Op\ :sup:`3` PCE uses probabilist Hermite polynomials
:math:`He_k(\xi)` orthogonal under the standard normal density
:math:`\phi(\xi) = (2\pi)^{-1/2} e^{-\xi^2/2}`:

.. math::

   \mathbb{E}[He_i(\xi) He_j(\xi)] = \delta_{ij} \cdot i!

A 1D PCE of order p is the expansion:

.. math::

   f(\xi) \approx \sum_{k=0}^{p} c_k He_k(\xi)

with pseudo-spectral projection coefficients:

.. math::

   c_k = \frac{1}{k!} \int_{-\infty}^{\infty} f(\xi) He_k(\xi) \phi(\xi)\,d\xi
   \approx \frac{1}{k!} \sum_i w_i f(\xi_i) He_k(\xi_i)

where :math:`(\xi_i, w_i)` are Gauss-Hermite quadrature nodes and
weights. **Critical implementation detail**: ``numpy.polynomial.hermite_e.hermegauss``
returns weights for :math:`\int f(x) e^{-x^2/2} dx`, missing the
:math:`1/\sqrt{2\pi}` standard-normal density factor. Op\ :sup:`3`
divides the weights by :math:`\sqrt{2\pi}` internally -- see the
comment in ``op3/uq/pce.py``.

Mean and variance from the coefficients (closed form, no resampling):

.. math::

   \mathbb{E}[f] = c_0 \qquad
   \text{Var}[f] = \sum_{k=1}^{p} k! \cdot c_k^2

Sobol indices (2D):

.. math::

   S_1 = V_1 / V, \quad S_2 = V_2 / V, \quad S_{12} = V_{12}/V

where :math:`V_i = \sum_{k_i \geq 1, k_j = 0} i! j! c_{ij}^2`.

11. Grid Bayesian calibration
-----------------------------

For a scalar calibration parameter :math:`\theta` with forward model
:math:`g(\theta)` and measured observable :math:`y_{\rm meas}`, the
posterior is:

.. math::

   p(\theta | y) \propto p(y | \theta) \cdot p(\theta)

with Gaussian likelihood:

.. math::

   p(y | \theta) = \frac{1}{\sigma \sqrt{2\pi}}
   \exp\left(-\frac{(y_{\rm meas} - g(\theta))^2}{2\sigma^2}\right)

Op\ :sup:`3` evaluates :math:`g(\theta)` on a user-supplied grid,
multiplies by the prior, normalises via trapezoidal integration, and
reports posterior mean, std, and quantiles. The grid approach is
preferred over MCMC for the 1D problems Op\ :sup:`3` needs because
the posterior is uni-modal and 200-500 points are sufficient for
sub-percent accuracy with no tuning.

12. Key references
------------------

.. list-table::
   :header-rows: 1

   * - Topic
     - Citation
   * - PISA sand
     - Burd et al. (2020), *Geotechnique* 70(11), 1048-1066
   * - PISA clay
     - Byrne et al. (2020), *Geotechnique* 70(11), 1030-1047
   * - Dunkirk field tests
     - McAdam et al. (2020), *Geotechnique* 70(11), 986-998
   * - Ground characterisation
     - Zdravkovic et al. (2020), *Geotechnique* 70(11), 945-962
   * - OC6 Phase II
     - Bergua et al. (2021), NREL/TP-5000-79989
   * - NREL 5 MW
     - Jonkman et al. (2009), NREL/TP-500-38060
   * - OC3 monopile
     - Jonkman & Musial (2010), NREL/TP-500-47535
   * - IEA 15 MW
     - Gaertner et al. (2020), NREL/TP-5000-75698
   * - Hardin-Drnevich
     - Hardin & Drnevich (1972), *J. Soil Mech. Found. Div.* 98(7)
   * - Vucetic-Dobry
     - Vucetic & Dobry (1991), *J. Geotech. Eng.* 117(1)
   * - Houlsby-Byrne caisson
     - Houlsby & Byrne (2005), *Proc. ICE Geotech. Eng.* 158(2/3)
   * - Hermite PCE
     - Xiu & Karniadakis (2002), *SIAM J. Sci. Comput.* 24(2)
   * - Rayleigh cantilever
     - Blevins (1979), *Formulas for Natural Frequency*, Table 8-1
   * - Phoon-Kulhawy COVs
     - Phoon & Kulhawy (1999), *Can. Geotech. J.* 36(4)

See ``paper/paper.bib`` for the full BibTeX entries.
