from fireworks.core.rocket_launcher import launch_rocket
from fireworks import Workflow, Firework, LaunchPad, FireTaskBase, FWAction
from fireworks.utilities.fw_utilities import explicit_serialize
from rocketsled.optimize import OptTask
import random
from pymongo import MongoClient
# from matminer.descriptors.composition_features import get_pymatgen_descriptor
from pymatgen import Element
import pandas as pd
import numpy as np
import pickle
import os

# 20 solar water splitter perovskite candidates in terms of atomic number
good_cands_ls = [(3, 23, 0), (11, 51, 0), (12, 73, 1), (20, 32, 0), (20, 50, 0), (20, 73, 1), (38, 32, 0),
                 (38, 50, 0), (38, 73, 1), (39, 73, 2), (47, 41, 0), (50, 22, 0), (55, 41, 0), (56, 31, 4),
                 (56, 49, 4), (56, 50, 0), (56, 73, 1), (57, 22, 1), (57, 73, 2), (82, 31, 4)]

# 8 oxide shields in terms of atomic number
good_cands_os = [(20, 50, 0), (37, 22, 4), (37, 41, 0), (38, 22, 0), (38, 31, 4), (38, 50, 0), (55, 73, 0),
                 (56, 49, 4)]

# Names (for categorical)
ab_names = ['Li', 'Be', 'B', 'Na', 'Mg', 'Al', 'Si', 'K', 'Ca', 'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu',
            'Zn', 'Ga', 'Ge', 'As', 'Rb', 'Sr', 'Y', 'Zr', 'Nb', 'Mo', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn',
            'Sb', 'Te', 'Cs', 'Ba', 'La', 'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg', 'Tl', 'Pb', 'Bi']
c_names = ['O3', 'O2N', 'ON2', 'N3', 'O2F', 'OFN', 'O2S']

# Atomic
ab_atomic = [Element(name).Z for name in ab_names]
c_atomic = list(range(7))

# Mendeleev number
ab_mend = [int(Element(name).mendeleev_no) for name in ab_names]
# c_mend = [int(np.sum(get_pymatgen_descriptor(anion, 'mendeleev_no'))) for anion in c_names]

# Mendeleev rank
ab_mendrank = [sorted(ab_mend).index(i) for i in ab_mend]
c_mendrank = [4, 3, 2, 1, 6, 5, 0]

# Corrected and relevant perovskite data
perovskites = pd.read_csv('unc.csv')

# dim = [(0, 51), (0, 51), (0, 6)]
dim = [ab_mendrank, ab_mendrank, c_mendrank]

# Defining search space with exclusions
# exclusions = pickle.load(open('excluded_compounds.p', 'rb'))  # in atomic
# gs_ranking = pickle.load(open('goldschmidt_rank.p', 'rb'))  # in atomic
# space_noex = []
# for x in gs_ranking:
#     if x not in exclusions:
#         a_mend = ab_mendrank[ab_atomic.index(x[0])]
#         b_mend = ab_mendrank[ab_atomic.index(x[1])]
#         c_mendi = c_mendrank[c_atomic.index(x[2])]
#         space_noex.append((a_mend, b_mend, c_mendi))
# pickle.dump(space_noex, open('space_gs_mend.p', 'wb'))

space_noex = pickle.load(open('space_gs_mend.p', 'rb'))

rf_params = {"n_estimators": [10, 100],
              "max_features": ["sqrt", "log2", "auto"],
              "bootstrap": [True, False],
              "criterion": ["mse", "mae"]}


def mend_to_name(a_mr, b_mr, c_mr):
    # go from mendeleev rank to name
    a_i = ab_mendrank.index(a_mr)
    b_i = ab_mendrank.index(b_mr)
    c_i = c_mendrank.index(c_mr)
    a = ab_names[a_i]
    b = ab_names[b_i]
    c = c_names[c_i]
    return a, b, c

@explicit_serialize
class EvaluateFitnessTask(FireTaskBase):
    _fw_name = "EvaluateFitnessTask"

    def run_task(self, fw_spec):

        # mendeleev params
        a_mr = fw_spec['A']
        b_mr = fw_spec['B']
        c_mr = fw_spec['C']

        # convert from mendeleev and score compound
        a, b, c = mend_to_name(a_mr, b_mr, c_mr)

        data = perovskites.loc[(perovskites['A'] == a) & (perovskites['B'] == b) & (perovskites['anion'] == c)]
        score = float(data['complex_score'])
        output = {'_y_opt': score}
        return FWAction(update_spec=output)

def wf_creator(x, predictor, get_z, lpad, space, persistent_z, chemical_rules=False):
    spec = {'A': x[0], 'B': x[1], 'C': x[2], '_x_opt': x}

    firework = Firework([EvaluateFitnessTask(),
                        OptTask(wf_creator='rs_examples.test_perovskites.wf_creator',
                                dimensions=dim,
                                lpad=lpad,
                                get_z=get_z,
                                predictor=predictor,
                                duplicate_check=True,
                                wf_creator_args=[predictor, get_z, lpad, space, persistent_z],
                                wf_creator_kwargs={'chemical_rules': chemical_rules},
                                # get_z_kwargs = {'chemical_rules': chemical_rules},
                                max=True,
                                space=space if chemical_rules else None,
                                persistent_z=persistent_z,
                                opt_label='test_perovskites',
                                n_search_points=20000,
                                n_train_points=20000,
                                hyper_opt=1,
                                param_grid=rf_params)],
                        spec=spec)
    return Workflow([firework])

def get_z(x, chemical_rules=False):
    # descriptors = ['X', 'average_ionic_radius']
    # a, b, c = mend_to_name(x[0], x[1], x[2])
    # name = a + b + c
    # conglomerate = [get_pymatgen_descriptor(name, d) for d in descriptors]
    # means = [np.mean(k) for k in conglomerate]
    # stds = [np.std(k) for k in conglomerate]
    # ranges = [np.ptp(k) for k in conglomerate]
    # z = means + stds + ranges
    # # z = []
    #
    # for d in descriptors[:1]:
    #     ab_attrs = [getattr(Element(el), d) for el in (a, b)]
    #     c_attrs = get_pymatgen_descriptor(c, d)
    #
    #     for attrs_set in [ab_attrs, c_attrs]:
    #         z.append(np.mean(attrs_set))
    #         z.append(np.ptp(attrs_set))
    #         z.append(np.std(attrs_set))
    #
    # z += [Element(a).max_oxidation_state, Element(a).min_oxidation_state]
    # z += [Element(b).max_oxidation_state, Element(b).min_oxidation_state]
    #
    # # Chemical rules
    # rx = np.mean(get_pymatgen_descriptor(c, 'average_ionic_radius'))
    # ra = Element(a).average_ionic_radius
    # rb = Element(b).average_ionic_radius
    # gs_dev = abs(1 - (ra + rx)/(2 ** 0.5 * (rb + rx)))
    # if chemical_rules:
    #     z.append(gs_dev)
    #
    # return z
    return []

if __name__ =="__main__":
    TESTDB_NAME = 'perovskites'
    predictor = 'RandomForestRegressor'
    # get_z = 'rs_examples.test_perovskites.get_z'
    get_z = None
    n_cands = 20
    n_runs = 3
    filename = 'perovskites_{}_{}_{}cands_{}runs.p'.format(predictor, TESTDB_NAME, n_cands, n_runs)

    Y = []
    for i in range(n_runs):
        rundb = TESTDB_NAME + "_{}".format(i)

        conn = MongoClient('localhost', 27017)
        db = getattr(conn, rundb)
        collection = db.test_perovskites
        filedir = os.path.dirname(os.path.realpath(__file__))

        launchpad = LaunchPad(name=rundb)
        launchpad.reset(password=None, require_password=False)
        launchpad.add_wf(wf_creator(random.choice(space_noex), predictor, get_z, launchpad,
                                    filedir + '/space_gs_mend.p',
                                    None,
                                    # filedir + '/persistent_z.p',
                                    chemical_rules=False))

        y = []
        cands = 0
        while cands != n_cands:
            launch_rocket(launchpad)
            cands = collection.find({'y':30.0}).count()
            y.append(cands)

        pickle.dump(y, open(filename + "_{}".format(i), 'w'))

        Y.append(y)
        launchpad.connection.drop_database(TESTDB_NAME)

    pickle.dump(Y, open(filename, 'w'))