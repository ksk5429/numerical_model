Decision Layer
==============

Op^3 includes a Bayesian decision layer that combines multiple
sensor channels into a single scour diagnosis and recommends the
maintenance action that minimises expected cost.

Three-step procedure
--------------------

1. **Translate** each sensor reading into a probability distribution
   over scour depth using a calibrated observation model.
2. **Combine** the individual distributions by multiplying the
   likelihoods and normalising (Bayes' theorem).
3. **Select** the maintenance action that minimises expected cost
   under the combined posterior.

The implementation lives in ``op3.uq.sequential_bayesian``.

Sensor channels
---------------

Three channels are supported:

- **Frequency channel** (accelerometer): broad likelihood, slow
  sensitivity to scour
- **Capacity channel** (strain gauge): narrow likelihood, fast
  sensitivity to scour
- **Statistical channel** (anomaly detector): binary step function,
  confirms persistent change

Value of information
--------------------

The VoI analysis answers: "if I install one more sensor, which one
changes the maintenance decision most often?"

.. code-block:: python

    from op3.uq.sequential_bayesian import SequentialBayesianTracker

    tracker = SequentialBayesianTracker()
    tracker.update(freq_ratio=0.994, capacity_ratio=0.99, anomaly=False)
    tracker.update(freq_ratio=0.985, capacity_ratio=0.92, anomaly=True)
    print(tracker.summary())

Sequential updating
-------------------

The ``SequentialBayesianTracker`` propagates the posterior from each
epoch to the next. Over time, the posterior tightens as evidence
accumulates, and the recommended action escalates if the degradation
trend persists.
