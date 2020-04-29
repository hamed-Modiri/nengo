import numpy as np
import pytest

import nengo
from nengo.builder.neurons import SimNeurons
from nengo.exceptions import BuildError


@pytest.mark.parametrize(
    "SpikingType",
    (nengo.RegularSpiking, nengo.PoissonSpiking, nengo.StochasticSpiking),
)
def test_spiking_builders(SpikingType):
    # use a base type with its own state(s), to make sure those states get built
    base_type = nengo.AdaptiveLIFRate()

    neuron_type = SpikingType(base_type)

    with nengo.Network() as net:
        neurons = nengo.Ensemble(10, 1, neuron_type=neuron_type).neurons

    with nengo.Simulator(net) as sim:
        ops = [op for op in sim.model.operators if isinstance(op, SimNeurons)]
        assert len(ops) == 1

        adaptation = sim.model.sig[neurons]["adaptation"]
        assert sum(adaptation is sig for sig in ops[0].states.values()) == 1


def test_state_build_errors():
    class MyNeuronType(nengo.SpikingRectifiedLinear):
        def __init__(self, error_mode=0):
            super().__init__()
            self.error_mode = error_mode

        def make_neuron_state(self, phases, dt, dtype=None):
            if self.error_mode == 0:  # no error
                return {"voltage": phases}
            elif self.error_mode == 1:  # too short
                return {"voltage": phases[:-1]}
            elif self.error_mode == 2:  # 2-D
                return {"voltage": phases[:, None] * np.ones(3)}
            elif self.error_mode == 3:  # not array-like
                return {"voltage": lambda: 3}
            elif self.error_mode == 4:  # overlaps with existing signal
                return {"in": phases}

    def test_type(error_mode=0):
        with nengo.Network() as net:
            nengo.Ensemble(2, 1, neuron_type=MyNeuronType(error_mode=error_mode))

        with nengo.Simulator(net, progress_bar=False):
            pass

    test_type(0)

    with pytest.raises(BuildError, match="State init array must be 0-D, or 1-D of"):
        test_type(1)

    with pytest.raises(BuildError, match="State init array must be 0-D, or 1-D of"):
        test_type(2)

    with pytest.raises(BuildError, match="State init must be a distribution or array"):
        test_type(3)

    with pytest.raises(BuildError, match="State name .* overlaps with existing signal"):
        test_type(4)

    # --- `get_neuron_states`: the following errors should not be possible because the
    # `initial_phase` parameter should check this
    with nengo.Network() as net:
        ens = nengo.Ensemble(2, 1)

    # hack to set ensemble state to too long 1-D array
    nengo.Ensemble.initial_phase.data[ens] = np.array([0.1, 0.2, 0.3])
    with pytest.raises(BuildError, match="`initial_phase` array must be 0-D, or 1-D"):
        with nengo.Simulator(net, progress_bar=False):
            pass

    # hack to set ensemble state to 2-D array
    nengo.Ensemble.initial_phase.data[ens] = np.array([[0.1, 0.2]])
    with pytest.raises(BuildError, match="`initial_phase` array must be 0-D, or 1-D"):
        with nengo.Simulator(net, progress_bar=False):
            pass