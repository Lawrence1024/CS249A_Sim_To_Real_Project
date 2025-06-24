## **Installation**

To interface with Isaac Sim, follow these steps:

1. Follow the instructions [here](https://docs.isaacsim.omniverse.nvidia.com/4.5.0/installation/install_python.html) to install Isaac Sim Python packages into your Scenic Python Virtual Environment.

2. To test that everything is working, try the following:
```python
import scenic
from scenic.simulators.isaacsim import IsaacSimSimulator
scenario = scenic.scenarioFromFile("Scenic/examples/isaacsim/create3/create3.scenic", 
                                   model='scenic.simulators.isaacsim.model')
scene, _ = scenario.generate()
simulator = IsaacSimSimulator()
simulation = simulator.simulate(scene, maxSteps=1000)
```

## **Known Issues**

1. There seems to be a slight mismatch between the location of objects placed in Scenic and those placed in Isaac Sim. This causes problems with the Scenic mutate statement, as differences in positions will cause well-defined Scenic programs to create Isaac Sim programs with intersecting 3D meshes. To see this, try the vacuum example with `mutate couch, coffee_table` (and default standard deviations).

2. Sometimes, repairing a complex converted mesh will not result in a reasonable volume. One example of this is the Jetbot robot.

3. Some robots, like Franka, require setup after being added to the simulator. Maybe the Scenic hook `startDynamicSimulation` can be used (see [here](https://docs.scenic-lang.org/en/latest/reference/classes.html#objects))?

## **Assets**

A local copy of Isaac Sim assets can be obtained [here](https://docs.isaacsim.omniverse.nvidia.com/4.5.0/installation/download.html#isaac-sim-latest-release). To convert assets from USD to glTF, the `usd_to_mesh.py` script can be used under utils. Example usage for a folder of assets looks like:

`python ./utils/usd_to_mesh.py --folders /path/to/assets --environments warehouse.usd`

In this example, we convert a folder of usd assets to glTF, and we specify that one of the assets in the folder is an environment. For each environment file, a JSON info file will generated. The generated files will be located at `/path/to/assets_converted`. Important note: USD environment files must be flattened by the user before they are converted (the process involves moving Prims, which requires a flattened usd file).