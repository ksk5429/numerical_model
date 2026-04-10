Visualization Gallery
=====================

Op\ :sup:`3` generates publication-quality figures across all three
pipeline stages using **opsvis** (OpenSeesPy), **PyVista** (OptumGX),
and **matplotlib/welib** (OpenFAST). All figures are reproducible::

   make viz   # generates all 23 figures

.. contents:: On this page
   :local:
   :depth: 1


Tier 1: Defense Slides
----------------------

**VHM Failure Envelope with Scour Degradation**

.. image:: ../../validation/figures/tier1/tier1_vhm_envelope.png
   :width: 100%
   :alt: V-H failure envelope shrinking with scour depth

Three panels showing: (a) V-H interaction envelopes at 5 scour depths
with design load marker, (b) vertical and horizontal capacity retention
vs S/D, (c) radial factor of safety trajectory from 1.89 to 1.29.

|

**Cross-Pipeline Composite (The Thesis in One Figure)**

.. image:: ../../validation/figures/tier1/tier1_cross_pipeline.png
   :width: 100%
   :alt: Three-panel composite: OptumGX springs, OpenSeesPy mode shape, OpenFAST time series

(a) OptumGX-derived foundation spring profile with bucket sketch,
(b) OpenSeesPy first mode shape at f\ :sub:`1` = 0.275 Hz (Mode B),
(c) OpenFAST aeroelastic response (generator power + blade root moment).

|

**Scour Progression Sweep**

.. image:: ../../validation/figures/tier1/tier1_scour_sweep.png
   :width: 100%
   :alt: Four-panel mode shapes at increasing scour depths

Mode shape evolution at S/D = 0, 0.1, 0.3, 0.5. Frequency drops from
0.316 to 0.309 Hz (-2.1%). Factor of safety transitions from green
(1.89) through orange to red (1.29).

|

**Mode C vs Mode D Dissipation Comparison**

.. image:: ../../validation/figures/tier1/tier1_mode_cd_comparison.png
   :width: 100%
   :alt: Mode C elastic vs Mode D dissipation-weighted stiffness profiles

(a) Stiffness profile overlay with w(z) weighting function inset.
Mode D reduces stiffness by up to 84% at the skirt tip where plastic
dissipation concentrates.
(b) Calibration curve: f\ :sub:`1` vs dissipation exponent alpha, with
field-measured frequency (0.244 Hz) as the target.


Tier 2: Journal Paper Figures
-----------------------------

**Geotechnical Foundation Profile**

.. image:: ../../validation/figures/tier2/tier2_foundation_profile.png
   :width: 100%
   :alt: Four-panel foundation cross-section with depth profiles

Publication-standard geotechnical figure: (a) bucket cross-section with
soil layer shading, (b) undrained shear strength s\ :sub:`u`\ (z),
(c) initial stiffness k(z) as smooth depth curve, (d) ultimate
resistance p\ :sub:`ult`\ (z).

|

**Rainflow Fatigue Damage Matrix**

.. image:: ../../validation/figures/tier2/tier2_rainflow_heatmap.png
   :width: 100%
   :alt: 2D rainflow damage matrix heatmap

(a) 2D heatmap of fatigue damage contribution (range vs mean) weighted
by Miner's rule (m = 4), (b) cycle range histogram with DEL markers at
m = 3, 4, 10.

|

**Campbell Diagram**

.. image:: ../../validation/figures/tier2/tier2_campbell.png
   :width: 100%
   :alt: Campbell diagram with rotor harmonics and mode frequencies

Rotor harmonics (1P, 3P, 6P, 9P) vs tower mode frequencies. The 3P
crossing at 5.5 rpm near the operational cut-in speed is highlighted.
The SSI effect (blue band) shifts f\ :sub:`1` from 0.316 to 0.275 Hz.

|

**Moment-Rotation Backbone with Published References**

.. image:: ../../validation/figures/tier2/tier2_moment_rotation.png
   :width: 100%
   :alt: Moment-rotation curves with cross-validation overlay

(a) Op\ :sup:`3` Mode C moment-rotation from pushover analysis.
(b) Cross-validation: DJ Kim 2014 centrifuge (red), Houlsby 2005 field
(green), Barari 2021 Plaxis 3D (blue dashed), Op\ :sup:`3` analytical
M\ :sub:`y` = 92.4 MNm at 0.6 deg (black star).


Tier 3: Interactive Dashboard
-----------------------------

**Interactive 3D Foundation Model**

The interactive model is available as a standalone HTML file:
`tier3_interactive_3d.html <../../validation/figures/tier3/tier3_interactive_3d.html>`_.
Rotate, zoom, and click any spring node to inspect k(z) and
p\ :sub:`ult`\ (z) values.

|

**Bayesian Digital Twin: Sensor Overlay**

.. image:: ../../validation/figures/tier3/tier3_sensor_overlay.png
   :width: 100%
   :alt: Field monitoring frequency tracking with Bayesian posterior

(a) 32-month OMA frequency tracking: raw scatter (gray), filtered
(blue, 70.1% scatter reduction), Op\ :sup:`3` prediction band (red).
(b) Bayesian posterior scour distribution with decision zones:
CONTINUE MONITORING / INSPECT / REMEDIATE.


Pipeline-Stage Figures
----------------------

**OptumGX: Contact Pressure at Collapse**

.. image:: ../../validation/figures/optumgx_pressure.png
   :width: 60%
   :alt: 3D contact pressure on bucket surface

|

**OptumGX: Plastic Dissipation (Collapse Mechanism)**

.. image:: ../../validation/figures/optumgx_collapse.png
   :width: 60%
   :alt: 3D plastic dissipation field

|

**OptumGX: Spring Profile**

.. image:: ../../validation/figures/optumgx_spring_profile.png
   :width: 80%
   :alt: k(z) and p_ult(z) bar chart

|

**OpenSeesPy: Model Geometry**

.. image:: ../../validation/figures/op3_model.png
   :width: 50%
   :alt: 3D stick model

|

**OpenSeesPy: Mode Shapes**

.. image:: ../../validation/figures/op3_mode_1.png
   :width: 40%
   :alt: First mode shape

.. image:: ../../validation/figures/op3_mode_3.png
   :width: 40%
   :alt: Third mode shape

|

**OpenFAST: PSD with 1P/3P Markers**

.. image:: ../../validation/figures/openfast_psd.png
   :width: 80%
   :alt: Power spectral density with rotor harmonics

|

**OpenFAST: Damage-Equivalent Loads**

.. image:: ../../validation/figures/openfast_del.png
   :width: 70%
   :alt: DEL bar chart
