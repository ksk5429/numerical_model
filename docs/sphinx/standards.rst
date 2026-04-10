Industry standards
==================

Op\ :sup:`3` ships calibrated implementations of the major offshore
geotechnical standards. Each is wrapped in a single function that
returns a 6x6 head-stiffness matrix consumable by Mode B
(``STIFFNESS_6X6``) or by the SoilDyn exporter.

.. list-table::
   :header-rows: 1

   * - Standard
     - Module
     - Citation
   * - DNVGL-ST-0126
     - :mod:`op3.standards.dnv_st_0126`
     - DNV (2021), Support structures for wind turbines
   * - ISO 19901-4
     - :mod:`op3.standards.iso_19901_4`
     - ISO (2016), Offshore structures: geotechnical design
   * - API RP 2GEO + Gazetas (1991)
     - :mod:`op3.standards.api_rp_2geo`
     - API (2014); Gazetas, J. Geotech. Eng. 117(9)
   * - Carbon Trust OWA + Houlsby & Byrne (2005)
     - :mod:`op3.standards.owa_bearing`
     - Carbon Trust OWA Bearing Capacity Report
   * - PISA (Burd 2020 / Byrne 2020)
     - :mod:`op3.standards.pisa`
     - Geotechnique 70(11), 1030-1066
   * - HSsmall (Benz 2007 / Schanz 1999)
     - :mod:`op3.standards.hssmall`
     - Hardening Soil with small-strain stiffness

Cyclic degradation
------------------

.. autofunction:: op3.standards.cyclic_degradation.hardin_drnevich
   :no-index:

.. autofunction:: op3.standards.cyclic_degradation.vucetic_dobry_gamma_ref
   :no-index:

.. autofunction:: op3.standards.cyclic_degradation.cyclic_stiffness_6x6
   :no-index:
