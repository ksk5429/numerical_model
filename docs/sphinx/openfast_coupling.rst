OpenFAST coupling
=================

The Op\ :sup:`3` -> OpenFAST bridge produces SoilDyn-compatible input
files from any Op\ :sup:`3` foundation handle.

SoilDyn export
--------------

.. autofunction:: op3.openfast_coupling.soildyn_export.write_soildyn_input

.. autofunction:: op3.openfast_coupling.soildyn_export.write_soildyn_from_pisa

.. autofunction:: op3.openfast_coupling.soildyn_export.write_soildyn_multipoint

End-to-end example
------------------

.. code-block:: python

   from op3.openfast_coupling.soildyn_export import write_soildyn_from_pisa
   from op3.standards.pisa import SoilState

   profile = [
       SoilState(0.0,  5.0e7, 35, "sand"),
       SoilState(15.0, 1.0e8, 35, "sand"),
       SoilState(36.0, 1.5e8, 36, "sand"),
   ]
   write_soildyn_from_pisa(
       "SiteA-Ref4MW_SoilDyn.dat",
       diameter_m=6.0, embed_length_m=36.0,
       soil_profile=profile,
       location_xyz=(-24.80, 0.0, -45.0),
   )

Then in the OpenFAST .fst:

.. code-block:: text

   1   CompSoil   - Compute soil-structural dynamics (switch) {1=SoilDyn}
   "SiteA-Ref4MW_SoilDyn.dat"   SoilFile

Reference paper
---------------

Bergua, R., Robertson, A., Jonkman, J., & Platt, A. (2021).
"Specification Document for OC6 Phase II: Verification of an
Advanced Soil-Structure Interaction Model for Offshore Wind
Turbines". NREL/TP-5000-79989.
https://doi.org/10.2172/1811648

The OC6 Phase II project is the international validation effort that
delivered the SoilDyn module to OpenFAST. Op\ :sup:`3` should be
benchmarked against the OC6 Phase II datasets for any
publication-grade SSI claims.
