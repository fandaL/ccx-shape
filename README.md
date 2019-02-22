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
