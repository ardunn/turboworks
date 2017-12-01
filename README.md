![Comparison of Workflows](/docs/rocketsledfw.png "Rocketsled logo")
### An "On-rails" Machine Learning Interface/Black Box Optimizer for FireWorks workflows.

# What is Rocketsled?
Rocketsled is a flexible and easy-to-use automatic machine-learning framework for Fireworks workflows.
### Why would I use it?

Is your computational problem:
* Expensive and/or complex (requiring high performance computing + workflow software?)
* Run in high-throughput (many similar workflows running concurrently?)
* Limited by an allocation of CPU hours?

If you answered yes to these three questions, *keep reading!*

If you have a complex, multi-iteration task to execute across different computers, and you would like to automatically reduce the number of expensive calculations needed
to run your task, Rocketsled is for you. 

### What can it do?
Rocketsled functions as a **black box optimizer** for a sequential optimization loop; it requires no knowledge of a function in order to optimize it. More importantly
though, Rocketsled **retains the workflow management abilties** of FireWorks (provenance, dynamic workflows, duplicate detection and correction, error handling) across **arbitrary computing resources**.
 
Other abilities of Rocketsled include:
* Facilitating feature engineering
* Duplicate prevention with tolerances
* Persistent storage and optimization tracking
* Built-in "out-of-the-box" sklearn optimizers
* Support for custom machine learning packages
* Automatic encoding for categorical optimization
* Tuneable control of training and prediction performance, across many kinds of computer resources 

![Comparison of Workflows](/docs/Comparison.png "Difference between optimized and unoptimized workflows")
*A Rocketsled use case in materials science*

## Requirements
- Python 2 or 3
- NumPy
- SciPy
- Scikit-learn
- FireWorks
- MongoDB

## Installation
~~~~bash
# Download the repository and install
git clone https://github.com/hackingmaterials/rocketsled.git
cd rocketsled
pip install . -r requirements

# Make sure Mongo DB's daemon is running locally!
mongod 

# Now lets run the tests
python setup.py test
~~~~

If you cannot run `mongod` on your local machine, or would like to run tests on a server, modify the launchpad yaml
file `rocketsled/rocketsled/tests_launchpad.yaml` to set the launchpad you'd like to use to run tests. 
**WARNING**: Running tests resets the LaunchPad. Do **NOT** use a production LaunchPad to run tests!


## A Visual Explanation

If you aren't comfortable with Fireworks, please work through the tutorials [here.](https://hackingmaterials.lbl.gov/fireworks/). Rocketsled is implemented as a modular, atomic task (FireTask)
in a FireWorks workflow. It is designed for *inverse optimization tasks with sequential improvement*. For example, a typical workflow without optimization might look like this:

![Workflow without opt](/docs/basic.png "A basic workflow")

Input parameters are given to the first Firework. This begins the worklow, and a useful output result is given. The workflow is repeated as desired.

![Workflow being repeated](/docs/multiple_wf.png "Multiple sequential workflows")
![Workflow being repeated](/docs/multiple_wf.png "Multiple sequential workflows")
![Workflow being repeated](/docs/multiple_wf.png "Multiple sequential workflows")

Randomly selecting the next input parameters is *inefficient*, since we will have to execute many workflows. To reduce the required number of computed workflows, we need to *intelligently* choose new input parameters
with an optimization loop.

This is where Rocketsled comes in handy. Rocketsled is a Firetask (called `OptTask`) which can go in any Firework in the workflow, and which uses `sklearn` regressors to predict the best *input* parameters for the next iteration,
store them in a MongoDB database, and start a new workflow to compute the next output. 

![Rocketsled](/docs/tw.png "Rocketsled workflow")

## How do I use it?

The easiest way to use rocketsled is by reading through an example and modifying it for your own purposes. Most usage cases follow the same format:
1. Define a workflow mapping **x**, your workflow input, to *y*, your workflow output (objective function metric), and a search space of input paramters, **X**. 
2. Add a FireWork containing `OptTask` to the workflow. 
3. Define a workflow creator function, which returns a new version of the above workflow based on an input of **x**. 

Thats it! All other features of rocketsled can be passed as arguments to OptTask. 


### What's the minimum I need to run a workflow with `OptTask`?
Rocketsled is designed to be a "plug and play" framework, meaning "plug in" your workflow and search space. Specifically, you need:


* **Workflow creator function**: takes in a vector of workflow input parameters `x`  and returns a Fireworks workflow based on those parameters, including optimization. Specified with the `wf_creator` arg to `OptTask`. `OptTask` should be located somewhere in the workflow that `wf_creator` returns. 
* **`'_x_opt'` and `'_y_opt'` fields in spec**: the parameters the workflow is run with and the output metric, in the spec of the Firework containing `OptTask`
* **Dimensions of the search space**: A list of the spaces dimensions, where each dimension is defined by`(higher, lower)` form (for  `float`/ `int`)  or `["a", "comprehensive", "list"]` form for categories. Specified with the `dimensions` argument of `OptTask`
* **MongoDB collection to store data**: Each optimization problem should have its own collection. Specify with `host`, `port`, and `name` arguments to `OptTask`,
or with a Launchpad object (via `lpad` arg to `OptTask`). 


## Tutorial: Basic example

The fastest way to get up and running is to do an example. Lets create an optimization loop with one Firework containing two Firetasks, 
`SumTask` and `OptTask`. 

`SumTask` takes a vector `x` and computes its sum. We will have `OptTask` run 10 workflows to minimize  `x` with a predictor based on the `sklearn` `RandomForestRegressor`. 

```python
# rs_examples/example_tasks.py

from fireworks.utilities.fw_utilities import explicit_serialize
from fireworks.core.firework import FireTaskBase
from fireworks import FWAction
import numpy as np

@explicit_serialize
class SumTask(FireTaskBase):
    _fw_name = "SumTask"

    def run_task(self, fw_spec):
        x = fw_spec['_x_opt']
        y = np.sum(x)
        return FWAction(update_spec={'_y_opt': y})
```

The following workflow creator function takes in `x`, and returns a workflow based on `x`. Once we start a workflow created with this function, it will execute the workflow, predict the next best `x`, and then automatically load another workflow onto the Launchpad using the new `x`. 

```python
# rs_examples/test_basic.py

from fireworks.core.rocket_launcher import rapidfire
from fireworks import Workflow, Firework, LaunchPad
from rocketsled.optimize import OptTask
from rs_examples.example_tasks import SumTask

def wf_creator(x):

    spec = {'_x_opt':x}
    X_dim = [(1, 5), (1, 5), (1, 5)]

    # SumTask writes _y_opt field to the spec internally.

    firework1 = Firework([SumTask(),
                          OptTask(wf_creator='rs_examples.test_basic.wf_creator',
                                  dimensions=X_dim,
                                  host='localhost',
                                  port=27017,
                                  name='rocketsled')],
                          spec=spec)

    return Workflow([firework1])
```

`OptTask` must have the `wf_creator` argument specified as a string (similar to `PyTask`). For now we can just specify the MongoDB collection with `host` `port` and `name` as args to `OptTask`, with the collection named `opt_default` by default. The dimensions of the search space are integers from `1-5` in `3` dimensions.

To start the optimization, we run the code below, and we use the point `[5, 5, 2]` as our initial guess.
```python
# rocketsled_examples/test_basic.py

if __name__ == "__main__":
    TESTDB_NAME = 'rocketsled'
    launchpad = LaunchPad(name=TESTDB_NAME)
    launchpad.reset(password=None, require_password=False)
    launchpad.add_wf(wf_creator([5, 5, 2]))
    rapidfire(launchpad, nlaunches=10, sleep_time=0)
```
We only need to add the workflow created with the workflow creator to the Launchpad one time. Once the first workflow is finished, `wf_creator` is called, and a new workflow is automatically added onto the Launchpad. This is why we can add only one workflow to the Launchpad but launch 10 times.
The output of `$python test_basic.py` is:
```bash
2017-11-02 17:35:14,658 INFO Performing db tune-up
2017-11-02 17:35:14,663 INFO LaunchPad was RESET.
2017-11-02 17:35:14,665 INFO Added a workflow. id_map: {-1: 1}
2017-11-02 17:35:14,670 INFO Created new dir /Users/ardunn/alex/lbl/projects/rocketsled/code/rocketsled/rs_examples/launcher_2017-11-03-00-35-14-670099
2017-11-02 17:35:14,670 INFO Launching Rocket
2017-11-02 17:35:19,691 INFO RUNNING fw_id: 1 in directory: /Users/ardunn/alex/lbl/projects/rocketsled/code/rocketsled/rs_examples/launcher_2017-11-03-00-35-14-670099
2017-11-02 17:35:19,705 INFO Task started: {{rs_examples.example_tasks.SumTask}}.
2017-11-02 17:35:19,705 INFO Task completed: {{rs_examples.example_tasks.SumTask}} 
2017-11-02 17:35:19,708 INFO Task started: {{rocketsled.optimize.OptTask}}.
2017-11-02 17:35:19,782 INFO Task completed: {{rocketsled.optimize.OptTask}} 
2017-11-02 17:35:19,792 INFO Rocket finished
...
2017-11-02 17:35:20,539 INFO RUNNING fw_id: 10 in directory: /Users/ardunn/alex/lbl/projects/rocketsled/code/rocketsled/rs_examples/launcher_2017-11-03-00-35-20-530832
2017-11-02 17:35:20,547 INFO Task started: {{rs_examples.example_tasks.SumTask}}.
2017-11-02 17:35:20,547 INFO Task completed: {{rs_examples.example_tasks.SumTask}} 
2017-11-02 17:35:20,549 INFO Task started: {{rocketsled.optimize.OptTask}}.
2017-11-02 17:35:20,608 INFO Task completed: {{rocketsled.optimize.OptTask}} 
2017-11-02 17:35:20,621 INFO Rocket finished
```
Congratulations! We ran our first `OptTask` optimization loop. Now lets take a look at our optimization data we stored in our database.
```bash
$ mongo
> use rocketsled
> db.opt_default.find()
```
Looking through the query results, the following fields are used during the optimization:
* `'x'` indicates the guesses for which expensive workflows have already been run. This array contains the `A`, `B`, and `C` guesses. 
* `'x_new'` indicates the predicted best next guess using the available information at that time.
* `'index'` indicates the iteration number (i.e., the number of times the workflow has been run)

The documents containing `lock`, `queue`, and `reserved` are used for duplicate checking for concurrent optimization loops. 

*Have a look at the other test files in `rs_examples` to look at examples of using more advanced features.*

## Advanced features of `OptTask`

Most of what `OptTask` can do is specified through arguments to `OptTask`. See `test_extras.py` for an example of many of the advanced features. 
Examples of several different (basic) usage scenarios are provided in the `examples` directory.

### Specify `wf_creator` (required)
The workflow creator accepts `x` (the vector of input params) and returns the workflow that will be run in the optimization loop. It should be specified as a `string` in the format: 

`wf_creator='my_package.my_module.my_wf_creator'`

Or alternatively:

`wf_creator='/path/to/my_module.my_wf_creator'`

**In your workflow creator, remember to include `_x_opt` and `_y_opt` keys in the spec for the Firework containing `OptTask`!**

### Pass arguments to `wf_creator`
Add args and kwargs as arguments to `wf_creator` alongside `x` with
* `wf_creator_args`: a list of positional arguments
* `wf_creator_kwargs`: a dict of keyword arguments

For example:
```python
    wf_creator_args=[2, 12],
    wf_creator_kwargs={'rerun': False} 
```

### Specify `dimensions` (required)
The dimensions argument defines the workflow input parameter space that the predictor will search. `dimensions` must be a list of individual dimensions:

* For integer and float dimensions, use `(lower, higher)` format
* For categorical dimensions, use a comprehensive list/tuple of all possible choices (e.g., `['red', 'green', 'blue']`)

For example:

`dimensions=[(1, 100), (12.0, 99.99), ['red', 'green', 'blue']]`


### Specify a `space` and limit input parameter combinations
In certain scenarios, not every single combination of input parameters defined by `dimensions` is a viable guess for `x`.
In these scenarios, we might increase the efficiency of optimization by limiting the search space to a discontinuous set of possible `x` vectors. Use `space` to define the absolute path of a pickle file containing a list 
of all available `x`. For example:

`space='\path\to\my_space.p'`

The `space` should be defined as a comprehensive list of `x` vectors, for example:

`space=[[1, 19, 12.78], [4, 20, 19.11], ... [8, 18, 2019.83]]`


### Choose a `predictor` (builtin, custom)
`OptTask` can use one of eight `sklearn` regressors to make predictions for the next best `x` guess:

* `RandomForestRegressor` (default)
* `LinearRegression`
* `AdaBoostRegressor`
* `BaggingRegressor`
* `GradientBoostingRegressor`
* `GaussianProcessRegressor`
* `MLPRegressor`
* `SVR`

Pass any of these as a string to `OptTask` to use. For example, 
`predictor='SVR'`. 

It is also able to use custom predictor functions.
The predictor must be able to predict a new `x` vector (the input parameters for the workflow) from the information the previous workflows have run. `OptTask` provides the following:
* A list of previous input vectors (a list of `x` from previous workflows, `X`)
* A list of previous output metrics (a list of `y` scalars from previous workflows, `Y`)
* A list of possible new `x` to choose from. The custom predictor can return one of these `x` vectors **or** any `x` vector fitting inside the problem dimensions.

Specify `predictor` with the same string format as `wf_creator`, for example:

`predictor='my_package.my_module.my_wf_creator'`

Or alternatively:

`predictor='/path/to/my_module.my_wf_creator'`

### Pass arguments to predictor

Pass arguments to both builtin and custom predictors with:
* `predictor_args`: a list of positional arguments
* `predictor_kwargs`: a dict of keyword arguments


`predictor_args` and `predictor_kwargs` can be passed to `OptTask` as args. For example:
```python
    predictor_args=['huber', 0.2, 500],
    predictor_kwargs={'max_depth': 2, 'criterion': 'mae'} 
```

### Utilities for custom predictors

If your custom predictor is not able to handle categorical data, pass

`encode_categorical=True`

To `OptTask` to automatically One-hot encode categorical data. The custom predictor will recieve only numerical data, and `OptTask` will reencode the predictor guess to start the next workflow.

Duplicate `x` vectors can cause workflows to be needlessly repeated.
`OptTask` built in predictors will not suggest duplicate guesses; however, if your custom predictor is prone to suggest duplicates, 
set `OptTask`'s argument 

`duplicate_check=True`

To automatically suggest random guesses when the custom predictor suggests duplicates. 
The random guesses are guaranteed to be unique and not duplicates. By default, there is no duplicate check.

You can also assign duplicate tolerances with `tolerances`. Tolerances work with both integers and floats. For categorical dimensions, enter the tolerance as `None`.
Let's run through a quick example. Lets say you are searching a space with `dimensions=[(1, 100), ["red", "blue"], and (2.0, 20.0)]`, and you would like to exclude duplicates where the first and second dimensions are the same as an existing guess and the third dimension is wthin 1e-6 of an existing guess. Then use:

`tolerances=[0, None, 1e-6]`

### Optimize hyperparameters automatically

Rocketsled provides the ability for automatic hyperparameter optimization when using builtin optimizers. It uses the 
`sklearn` `RandomizedSearchCV` and `GridSearchCV` tools. Enable randomized hyperparameter optimzation for *n* iterations
with 

```python
hyper_opt=n
```

Where *n* is the number of CV searches `RandomizedSearchCV` performs, and is any integer greater than 1. To use
exhaustive hyperparameter search with `GridSearchCV`, set *n* equal to 1. 

While OptTask comes with its own default grids for each built-in optimizer, you can define your own by passing the 
`param_grid` argument to OptTask. The `param_grid` must be a `sklearn`-style parameter dictionary, for example:
```python
param_grid={'criterion': ['mse', 'mae'], 
            'n_estimators':[1, 10, 100], 
            'max_features': ['auto', 'sqrt', 'log2']}
```


### Store optimization data in a database

The optimization db can be specified with one of the following options:

1. With `host`, `port`, and `name` arguments to `OptTask`, for example:
```
    host='localhost;
    port=27017
    name='my_db'
```

2. With a LaunchPad object in the `lpad` argument, for example: `lpad=LaunchPad()`

3. By setting `_add_launchpad_and_fw_id` to `True` in the fw spec. 

4. Specify `LAUNCHPAD_LOC` in the fw config file for `LaunchPad.auto_load()`

Specify the collection the optimization data should be stored in with `opt_label`, for example `opt_label='my_opt'`.
**Each optimization should have its own collection.**

For password-protected databases, SSL security protocols, or other mongo specs,  use the `db_extras` argument to define
a dict containing all arguments for a `MongoClient` connection. For example:
```
    db_extras={'username': 'myuser', 
               'password': 'mypassword', 
               'maxPoolSize': 10}
```

### Fetch, store, and optimize with extra features (`z`)
In addition to the unique vector that identifies a point in the search space, `x`, we may want to use extra features (a vector `z`)
to improve the performance of our optimization. For instance, a useful `z` feature for optimization may be a linear combination of `x` features.

To use `z` features, specify a function which accepts `x` (the workflow input parameters) and returns `z`, the extra features, as 
`OptTask`'s `get_z`argument. For example:

```python
# This function returns two extra features which may be used 
# to make better predictions

    def my_get_z(x):
        return [x[0] * 2, x[2] ** 3]
```
Specify the location of this function with the argument to `OptTask`:

`get_z='my_package.my_module.my_get_z'`

Alternatively,

`get_z='\path\to\my_module.my_get_z`


### Pass arguments to `get_z`
Add args and kwargs as arguments to `get_z` alongside `x` with
* `get_z_args`: a list of positional arguments
* `get_z_kwargs`: a dict of keyword arguments

For example:
```python
    get_z_args=['extrapolated', 2],
    get_z_kwargs={'bilinear': False} 
```

### Prevent `z` vectors from being calculated more than once with `persistent_z`
If calculating all z vectors is not computationally trivial, we can calculate each `z` only once and store the result for `OptTask` use.

Specify the argument of `OptTask` as the filename where the `z` should be stored. For example:

`persistent_z='/path/to/my_persistent_z.p`

`OptTask` will automatically create and read from this file on each iteration and will not recalculate `z`. 


### Control predictor performance
`OptTask` allows for control of predictor performance using

* `n_search_points`: The number of points to be searched in the search space when choosing the next best point. The default is 1000 points.
Increase the number of search points to increase optimization efficiency.
* `n_train_points`: The number of already explored points to be chosen for training. Default is `None`, meaning
            all available points will be used for training. Reduce the number of points to decrease training times.
* `random_interval`: Suggests a random guess every `n` guesses instead of using the predictor suggestion. For
            instance, `random_interval=10` has `OptTask` randomly guess every 1/10 predictions, and uses the predictor the 
            other 9/10 times. Setting `random_interval` to an `int` greater than 1 may increase exploration. Default is 
            `None`, meaning no random guesses. 
            
For example,

```python
    n_search_points=100000,
    n_train_points=50000,
    random_interval=100
```

### Choose a maximum instead of a minimum
By default, `OptTask` will suggest input parameters `x` that minimize the output metric `y`. To maximize the output metric instead, use

`max=True`

As an argument to `OptTask`. 

### Submit and optimize jobs in batches with `batch_size`
Rocketsled supports batch job submission and optimization. For example, you may want to run 10 workflows, optimize the
next 10 best guesses, and submit another 10 workflows. To do this, use

`batch_size=10`

As an argument to `OptTask`. `OptTask` will wait until all jobs in single batch are finished computing before predicting 
the next best guesses and submitting another batch. The workflow scheme for a batch optimization is shown below:

![Batch Optimization](/docs/batch.png)

To start a batch-style optimization loop, submit your first batch manually, where each batch item is an optimization 
loop continaing `OptTask`. `OptTask` will automatically handle the rest!

If you are confused on using `batch_size` and batch optimization, check out the example `test_batch.py`, which is 
identical to `test_basic.py` except that it submits and optimizes jobs in batches of `5`. 




  