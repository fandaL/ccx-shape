# script for CalculiX shape optimization

# INPUTS

path = "."  # path to the working directory where the initial file is located
#path = "."  # example - in the current working directory
#path = "~/tmp/shape/"  # Linux example
#path = "D:\\tmp\\"  # Windows example

file_name = "sensitivity_analysis.inp"  # initial file name
path_calculix = "d:\\soft\\ccx"

cpu_threads = "all"  # "all" - use all processor threads, N - will use N number of processor threads

max_node_shift = 0.3  # maximal node shift during one iteration in length units

sign = -1  # -1 for minimization
           # 1 for maximization
sensitivity_to_use = "senstre"  # sensitivity used to shift nodes
                                # "prjgrad" - projected gradient (combines other objectives and constraints)
                                # "senmass" - mass
                                # "senstre" - stress
                                # "sendisa" - displacement
                                # "senener" - shape energy
                                # "senfreqN" - frequency number N where N is N-th printed frequency
# move_limit = [[min, max cumulative node shift along normal, {node numbers}], [another set],...]
               # min must be <= 0, max must be >= 0
               # e.g. move_limit = [[0, 5, {1,2,3,4,5,6}]] will constrain shift of the nodes 1,2,3,4,5,6 to be minimally 0 and maximally 5 length units
move_limit = []

iterations_max = 30  # maximum number of design iterations
convergence_tolerance = 0.0001  # stop iteration if change in objectives is below this value, None - not to use it


# FUNCTIONS

import numpy as np
import time
import os
import subprocess
import multiprocessing

# print ongoing messages to the log file
def write_to_log(file_name, msg):
    f_log = open(file_name[:-4] + ".log", "a")
    f_log.write(msg)
    f_log.close()


# read initial file: design node set, node coordinates
def import_inp(file_name):
    nodes = {}  # dict with node positions
    model_definition = True
    read_node = False

    try:
        f = open(file_name, "r")
    except IOError:
        msg = ("Initial file " + file_name + " not found.")
        write_to_log(file_name, "\nERROR: " + msg + "\n")
        raise Exception(msg)

    line = "\n"
    include = ""
    while line != "":
        if include:
            line = f_include.readline()
            if line == "":
                f_include.close()
                include = ""
                line = f.readline()
        else:
            line = f.readline()
        if line.strip() == '':
            continue
        elif line[0] == '*':  # start/end of a reading set
            if line[0:2] == '**':  # comments
                continue
            if line[:8].upper() == "*INCLUDE":
                start = 1 + line.index("=")
                include = line[start:].strip().strip('"')
                f_include = open(include, "r")
                continue
            read_node = False

        # reading nodes
        if (line[:5].upper() == "*NODE") and (model_definition is True):
            read_node = True

        elif read_node is True:
            line_list = line.split(',')
            nn = int(line_list[0])  # node number
            x = float(line_list[1])
            y = float(line_list[2])
            z = float(line_list[3])
            nodes[nn] = np.array([x, y, z])

        elif line[:5].upper() == "*STEP":
            model_definition = False
    f.close()
    return nodes


def read_dat(file_i, write_header):
    objectives = {}
    read_objectives = 0
    fn = 1  # frequency number

    f = open(file_i + ".dat", "r")
    for line in f:
        line_split = line.split()
        if line.replace(" ", "") == "\n":
            read_objectives -= 1
        elif read_objectives == 1:
            if objective_type == "EIGENFREQUENCY":
                objectives[objective_type + str(fn)] = float(line)  # is it eigenfrequency or eigenvalue? See ccx example transition.dat.ref
                fn += 1
            else:
                objectives[objective_type] = float(line)
        elif line[:11] == " OBJECTIVE:":
            objective_type = line_split[1]
            read_objectives = 2
    f.close()

    # write objectives to the log file
    msg = ""
    if write_header is True:
        msg += "Objectives\n"
        msg += "  i"
        for obj in objectives:
            if obj[:3] == "EIG":
                obj_name = "EIGENVALUE" + obj[14:]
                msg += " " + obj_name.rjust(13)
            else:
                msg += " " + obj.rjust(13)
        msg += "\n"
        write_header = False
    msg +=  str(i).rjust(3)
    for obj in objectives:
        msg += " %.7e" % objectives[obj]
    msg += "\n"
    write_to_log(file_name, msg)

    return objectives, write_header


def read_frd(file_i):
    f = open(file_i + ".frd", "r")

    read_normals = False
    read_sensitivities = False
    normals = {}
    sensitivities = {}
    eigennumber = 0
    for line in f:
        # block end
        if line[:3] == " -3":
            read_normals = False
            read_sensitivities = False

        # reading normals
        elif line[:9] == " -4  NORM":
            read_normals = True
        elif read_normals is True:
            if line[:3] == " -1":
                nn = int(line[3:13])
                nx = float(line[13:25])
                ny = float(line[25:37])
                nz = float(line[37:49])
                normals[nn] = np.array([nx, ny, nz])

        # reading sensitivities
        elif line[:12] == " -4  SENMASS":
            read_sensitivities = True
            sensitivities["senmass"] = {}
            sensitivity_reading = sensitivities["senmass"]
        elif line[:12] == " -4  SENSTRE":
            read_sensitivities = True
            sensitivities["senstre"] = {}
            sensitivity_reading = sensitivities["senstre"]
        elif line[:12] == " -4  SENFREQ":
            read_sensitivities = True
            eigennumber += 1
            sensitivities["senfreq" + str(eigennumber)] = {}
            sensitivity_reading = sensitivities["senfreq" + str(eigennumber)]
        elif line[:12] == " -4  SENENER":
            read_sensitivities = True
            sensitivities["senener"] = {}
            sensitivity_reading = sensitivities["senener"]
        elif line[:12] == " -4  SENDISA":
            read_sensitivities = True
            sensitivities["sendisa"] = {}
            sensitivity_reading = sensitivities["sendisa"]
        elif line[:12] == " -4  PRJGRAD":  # only projected gradient is used in this version
            read_sensitivities = True
            sensitivities["prjgrad"] = {}
            sensitivity_reading = sensitivities["prjgrad"]

        elif read_sensitivities:
            if line[:3] == " -1":
                nn = int(line[3:13])
                sensitivity_reading[nn] = float(line[25:37])  # reads column of filtered values

    f.close()

    if not sensitivities:  # missing sentitivities
        row = "Sensitivities not found in the frd file."
        msg = ("\nERROR: " + row + "\n")
        write_to_log(file_name, msg)
        assert False, row

    return normals, sensitivities


def write_inp_h(file_i, file_h, boundary_shift):
    fR = open(file_i + ".inp", "r")
    fW = open(file_h + ".inp", "w")
    for line in fR:
        if line[:5].upper() == "*STEP":  # replace steps by one static step
            fW.write("\n")
            fW.write("*INCLUDE,INPUT=" + file_i + ".equ\n")
            fW.write("*BOUNDARY\n")
            for nn in boundary_shift:
                fW.write("{} ,1,1, {:.13e}\n".format(nn, boundary_shift[nn][0]))
                fW.write("{} ,2,2, {:.13e}\n".format(nn, boundary_shift[nn][1]))
                fW.write("{} ,3,3, {:.13e}\n".format(nn, boundary_shift[nn][2]))
            fW.write("*STEP\n")
            fW.write("*STATIC\n")
            fW.write("*NODE FILE\n")
            fW.write("U\n")
            fW.write("*END STEP\n")
            break
        else:
            fW.write(line)
    fR.close()
    fW.close()


def read_frd_h(file_h, nodes):
    f = open(file_h + ".frd", "r")
    read_displacement = False
    for line in f:
        # block end
        if line[:3] == " -3":
            read_displacement = False
        elif line[:9] == " -4  DISP":
            read_displacement = True
        elif read_displacement is True:
            if line[:3] == " -1":
                nn = int(line[3:13])
                dx = float(line[13:25])
                dy = float(line[25:37])
                dz = float(line[37:49])
                nodes[nn] += [dx, dy, dz]
    f.close()
    return nodes


def rewrite_input(file_name, file_i, nodes):
    fR = open(file_name, "r")
    fW = open(file_i + ".inp", "w")
    model_definition = True
    rewrite_node = False
    for line in fR:
        if line[0] == '*':  # start/end of a reading set
            rewrite_node = False
        if (line[:5].upper() == "*NODE") and (model_definition is True):
            rewrite_node = True
        elif line.strip() == '':
            pass
        elif rewrite_node is True:
            line_list = line.split(',')
            nn = int(line_list[0])
            fW.write("{}, {:.13e}, {:.13e}, {:.13e}\n".format(nn, nodes[nn][0], nodes[nn][1], nodes[nn][2]))
            continue
        elif line[:5].upper() == "*STEP":
            model_definition = False

        fW.write(line)  # copy line from original input
    fR.close()
    fW.close()


# MAIN PROGRAM
start_time = time.time()
# start of the log file
msg = "\n"
msg += "---------------------------------------------------\n"
msg += ("file_name = %s\n" % file_name)
msg += ("Start at    " + time.ctime() + "\n\n")
write_to_log(file_name, msg)


# set an environmental variable driving number of cpu threads to be used by CalculiX
if cpu_threads == "all":  # use all processor cores
    cpu_threads = multiprocessing.cpu_count()
os.putenv('OMP_NUM_THREADS', str(cpu_threads))

# reading nodes form the initial file
nodes = import_inp(file_name)

file_i = file_name[:-4]
i = 0
write_header = True
cumulative_shift = {}
for lb, ub, ns in move_limit:
    for nn in ns:
        cumulative_shift[nn] = 0
while True:
    # running initial CalculiX analysis
    subprocess.call(os.path.normpath(path_calculix) + " " + file_i, shell=True, cwd=path)

    # read dat: objectives (i.e. goal function and constraint values) and save them to the log
    if i != 0:
        objectives_old = objectives
    [objectives, write_header] = read_dat(file_i, write_header)
    if not objectives:
        msg = "\nObjectives not found in *.frd output. The mesh could be already too distorted."
        print(msg)
        write_to_log(file_name, msg)
        break

    # delete unecessary files
    #os.remove(file_i + ".12d")
    #os.remove(file_i + ".stm")
    #os.remove(file_i + ".sta")
    #os.remove(file_i + ".equ")
    #os.remove(file_i + ".cvg")

    # convergence check
    if i > iterations_max:
        break
    if i != 0 and convergence_tolerance:
        converged = []
        for obj in objectives:
            if abs(objectives[obj] - objectives_old[obj]) > convergence_tolerance:
                converged.append(False)
        if False not in converged:
            print("Objectives change lower than convergence_tolerance")
            break

    # read frd: node normals, sensitivities
    [normals, sensitivities] = read_frd(file_i)

    # define boundary shift
    boundary_shift = {}
    continue2 = False
    for nn in sensitivities[sensitivity_to_use]:
        sens_nn = sensitivities[sensitivity_to_use][nn]
        if sens_nn:
            for lb, ub, ns in move_limit:
                if nn in ns:
                    if sign * sens_nn > 0:  # wants to grow
                        free_shift = ub - cumulative_shift[nn]
                        if max_node_shift <= free_shift:
                            final_shift = max_node_shift
                        else:
                            final_shift = free_shift
                    elif sign * sens_nn < 0:  # wants to reduce
                        free_shift = lb - cumulative_shift[nn]  # < 0
                        if -max_node_shift >= free_shift:
                            final_shift = max_node_shift
                        else:
                            final_shift = free_shift
                    boundary_shift[nn] = normals[nn] * sign * sens_nn * final_shift
                    cumulative_shift[nn] += sign * sens_nn * final_shift
                    continue2 = True
                    break
            if continue2 == True:
                continue2 = False
                continue
            boundary_shift[nn] = normals[nn] * sign * sensitivities[sensitivity_to_use][nn] * max_node_shift

    # write helper linear static analysis with displacement output
    # loaded with boundary shift and with equations generated by CalculiX
    file_h = file_i + "_h"
    write_inp_h(file_i, file_h, boundary_shift)

    # run helper analysis
    subprocess.call(os.path.normpath(path_calculix) + " " + file_h, shell=True, cwd=path)

    # read frd: update node positions by helper displacement
    nodes = read_frd_h(file_h, nodes)
    # delete unecessary files
    os.remove(file_h + ".12d")
    os.remove(file_h + ".sta")
    os.remove(file_h + ".cvg")

    # write new iteration file with shifted nodes from helper analysis
    i += 1
    file_i = os.path.join(path, "file" + str(i).zfill(3))
    rewrite_input(file_name, file_i, nodes)


# print total time
total_time = time.time() - start_time
total_time_h = int(total_time / 3600.0)
total_time_min = int((total_time % 3600) / 60.0)
total_time_s = int(round(total_time % 60))
msg = "\n"
msg += ("Finished at  " + time.ctime() + "\n")
msg += ("Total time   " + str(total_time_h) + " h " + str(total_time_min) + " min " + str(total_time_s) + " s\n")
msg += "\n"
write_to_log(file_name, msg)
print("total time: " + str(total_time_h) + " h " + str(total_time_min) + " min " + str(total_time_s) + " s")
