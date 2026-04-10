Report Generator
================

Op^3 can produce a DOCX and PDF report from any project state.

Generating a report
-------------------

.. code-block:: python

    from op3_viz.project import load
    from op3_viz.report import build_report

    proj = load("sample_projects/gunsan_ref4mw.op3proj")
    produced = build_report(proj, output_dir="reports/")
    print(produced)

The report includes:

- Project metadata (name, Op^3 version, creation date)
- Turbine and foundation configuration
- Soil profile parameters
- Analysis settings (eigenvalue modes, damping, pushover target)
- DLC configuration (wind speeds, simulation time)
- Conformance summary placeholder
- Provenance footer (Op^3 version, Zenodo DOI, Git commit hash)

Requirements
------------

The report generator uses Quarto as the rendering engine. Quarto
must be installed and on the system PATH. If Quarto is not available,
the generator produces the intermediate ``.qmd`` file only.

Customisation
-------------

The report template is a Quarto Markdown document embedded in
``op3_viz/report.py``. To customise the layout, modify the
``REPORT_QMD_TEMPLATE`` string in that file. The template uses
standard Quarto YAML front-matter for title, author, and format
settings.
