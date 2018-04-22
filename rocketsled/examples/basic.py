from __future__ import unicode_literals, print_function, unicode_literals

"""
An example of the most basic rocketsled implementation.
This file creates and executes a workflow containing one Firework.

The Firework contains 2 Tasks.
    1. CalculateTask - a task that reads x from the spec and calculates the sum of the vector.
    2. OptTask - a task that stores optimiztion data in the db and optimizes the next guess.
"""

from fireworks.core.rocket_launcher import rapidfire
from fireworks import Workflow, Firework, LaunchPad
from rocketsled import OptTask
from rocketsled.examples.tasks import SumTask


__author__ = "Alexander Dunn"
__version__ = "0.1"
__email__ = "ardunn@lbl.gov"


# a workflow creator function which takes x and returns a workflow based on x
def wf_creator(x):

    spec = {'_x_opt':x}
    X_dim = [(1, 5), (1, 5), (1, 5)]

    # CalculateTask writes _y_opt field to the spec internally.

    firework1 = Firework([SumTask(),
                          OptTask(wf_creator='rocketsled.examples.basic.'
                                             'wf_creator',
                                  dimensions=X_dim,
                                  host='localhost',
                                  port=27017,
                                  name='rsled')],
                          spec=spec)

    return Workflow([firework1])

def run_workflows():
    TESTDB_NAME = 'rsled'
    launchpad = LaunchPad(name=TESTDB_NAME)
    launchpad.reset(password=None, require_password=False)
    launchpad.add_wf(wf_creator([5, 5, 2]))
    rapidfire(launchpad, nlaunches=10, sleep_time=0)

    # tear down database
    # launchpad.connection.drop_database(TESTDB_NAME)

if __name__ == "__main__":
    run_workflows()



