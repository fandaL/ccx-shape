# ccx-shape
Simple shape optimization script which generates nodal shifting according to sensitivities calculated by CalculiX FE solver.

## Options

Variable 'sensitivity_to_use' defines which sensitivity type will be read from the CalculiX output file and used to shift nodes. Variable 'max_node_shift' defines maximal shifting distance per iteration. When this value is large, elements becomes soon too distorted so that CalculiX does not print sensitivities to the frd file and iterations stop sooner then is defined by 'iterations_max'.

## Principle

For optimization you need to define CalculiX input file with *DESIGN VARIABLES and a SENSITIVITY step. See original CalculiX documentation chapter 'Simple example problems - Optimization of a simply supported beam' 
and check original test example opt1.inp or other examples which calculate sensitivities (e.g. beam_sens_freq_coord1.inp, beam_sens_stress_coord1.inp, sensitivity_I.inp).

The ccx-shape script basically:

1) starts CalculiX to analyse original input file,

2) reads sensitivities and normals from the frd file and uses selected sensitivity to shift the design nodes in normal direction,

3) original input file is copied with the shifted design nodes and used for linear static analysis analysed by CalculiX,

4) results from this analysis define shifting of all nodes which are used to modify new copy of the original input file.

5) New iteration starts from point 1 but with modified input file until iterations_max is reached or CalculiX fails (due to distorted elements).

Objectives are successively printed to the log file.

## Example

In the example folder there is an input file for stress minimization of the part consisting of 3D elements with boundary conditions for plane strain and symmetry (one quarter) with 100 MPa tensile load on the shorter side.

![preprocessing.png](https://github.com/fandaL/ccx-shape/blob/master/example1/preprocessing.png)

![initial_analysis_vonMises.png](https://github.com/fandaL/ccx-shape/blob/master/example1/initial_analysis_vonMises.png)

Figure with result mesh below is for optimization settings 'max_node_shift = 0.3' and 'sign = -1' and 'sensitivity_to_use = "senstre"' and 'iterations_max = 30'

![last_analysis_vonMises.png](https://github.com/fandaL/ccx-shape/blob/master/example1/last_analysis_vonMises.png)
