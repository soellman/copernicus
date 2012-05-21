# This file is part of Copernicus
# http://www.copernicus-computing.org/
# 
# Copyright (C) 2011, Sander Pronk, Iman Pouya, Erik Lindahl, and others.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published 
# by the Free Software Foundation
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


import sys
import os
import re
import os.path
import shutil
import glob
import stat
import subprocess
import logging
import time


log=logging.getLogger('cpc.lib.mdrun')


from cpc.dataflow import Value
from cpc.dataflow import FileValue
from cpc.dataflow import IntValue
from cpc.dataflow import FloatValue
from cpc.dataflow import Resources
import cpc.server.command
import cpc.util

import tune


class GromacsError(cpc.util.CpcError):
    pass

def extractConf(tprFile, confFile):
    """Extract a configuration to confFile from tprFile."""
    cmdlist=['editconf', '-f', tprFile, '-o', confFile]
    proc=subprocess.Popen(cmdlist, 
                          stdin=None,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          cwd=os.path.split(confFile)[0])
    proc.communicate(None)
    if proc.returncode != 0:
        raise GromacsError("Error running editconf: %s"%
                           (open(stdoutfn,'r').read()))




def procSettings(inp, outMdpDir):
    """Process settings into a new mdp file, or return the old mdp file if
       there are no additional settings."""
    mdpfile=inp.getInput('mdp')
    if ( inp.hasInput('settings') and len(inp.getInput('settings'))>0 ):
        repl=dict()
        #if inp.hasInput('gen_vel'):
        #    gen_vel=inp.getInput('gen_vel')
        #    if gen_vel == 0:
        #        genvelst='no'
        #    else:
        #        genvelst='yes'
        #    repl['gen_vel'] = genvelst
        if inp.hasInput('settings'):
            settings=inp.getInput('settings')
            for setting in settings:
                if ("name" in setting.value) and ("value" in setting.value):
                    val = setting.value["value"].value
                    repl[setting.value["name"].value] = val
        # now set the gen_vel option
        outMdpName=os.path.join(outMdpDir, "grompp.mdp")
        outf=open(outMdpName, "w")
        inf=open(mdpfile, "r")
        for line in inf:
            sp=line.split('=')
            if len(sp) == 2:
                key=sp[0].strip().replace('-', '_').lower()
                if key in repl:
                    outf.write('%s = %s\n'%(key, str(repl[key])))
                    del repl[key]
                else:
                    outf.write(line)
        # and write our remaining options 
        for key, value in repl.iteritems():
            outf.write('%s = %s\n'%(key, str(value)))
        outf.close()
        return outMdpName
    else:
        return mdpfile

def grompp_multi(inp):
    if inp.testing():
    # if there are no inputs, we're testing wheter the command can run
        cpc.util.plugin.testCommand("grompp -version")
        return

    #simple case first
    #for each mdp file
    arr_mdp = inp.getInput("mdp")
#    arr_top = inp.getInput("top")
#    arr_conf = inp.getInput("conf")
#    pers=cpc.dataflow.Persistence(os.path.join(inp.persistentDir,
#        "persistent.dat"))
    out=inp.getFunctionOutput()
    for i in range(len(arr_mdp)):

        out.addInstance("grompp_%d"%i, "grompp")
        out.addConnection("self:ext_in.mdp[%d]"%i, "grompp_%d:in.mdp"%i)
        out.addConnection("self:ext_in.top[%d]"%i, "grompp_%d:in.top"%i)
        out.addConnection("self:ext_in.conf[%d]"%i, "grompp_%d:in.conf"%i)

        out.addConnection("grompp_%d:out.tpr"%i, "self:ext_out.result[%d].tpr"%i)
        out.addConnection("grompp_%d:out.stdout"%i, "self:ext_out.result[%d].stdout"%i)

#connect mdp top and conf to this grompp instance!

    return out
     #pers.write()

def mdrun_multi(inp):
    if inp.testing():
    # if there are no inputs, we're testing wheter the command can run
        cpc.util.plugin.testCommand("trjcat -version")
        cpc.util.plugin.testCommand("eneconv -version")
        cpc.util.plugin.testCommand("gmxdump -version")
        return

    arr_tpr = inp.getInput("tpr")
    out = inp.getFunctionOutput()
    for i in range(len(arr_tpr)):
        out.addInstance("mdrun_%d"%i,"mdrun")
        out.addConnection("self:ext_in.tpr[%d]"%i,"mdrun_%d:in.tpr"%i)
        out.addConnection("self:ext_in.priority[%d]"%i,"mdrun_%d:in.priority"%i)
        out.addConnection("self:ext_in.cmdline_options[%d]"%i,"mdrun_%d:in.cmdline_options"%i)

        out.addConnection("mdrun_%d:out.conf"%i,"self:ext_out.result[%d].conf"%i)
        out.addConnection("mdrun_%d:out.stderr"%i,"self:ext_out.result[%d].stderr"%i)
        out.addConnection("mdrun_%d:out.stdout"%i,"self:ext_out.result[%d].stdout"%i)
        out.addConnection("mdrun_%d:out.xtc"%i,"self:ext_out.result[%d].xtc"%i)
        out.addConnection("mdrun_%d:out.trr"%i,"self:ext_out.result[%d].trr"%i)
        out.addConnection("mdrun_%d:out.edr"%i,"self:ext_out.result[%d].edr"%i)

    return out




def grompp(inp):
    if inp.testing(): 
        # if there are no inputs, we're testing wheter the command can run
        cpc.util.plugin.testCommand("grompp -version")
        return 
    #outfname=os.path.join(inp.outputDir, "grompp.mdp")
    mdpfile=procSettings(inp, inp.outputDir)
    # copy the topology and include files 
    topfile=os.path.join(inp.outputDir, 'topol.top')
    shutil.copy(inp.getInput('top'), topfile)
    incl=inp.getInput('include')
    if incl is not None and len(incl)>0:
        for i in range(len(incl)):
            filename=inp.getInput('include[%d]'%i)
            if filename is not None:
                # same name, but in one directory.
                nname=os.path.join(inp.outputDir, os.path.split(filename)[1])
                shutil.copy(filename, nname)
    # and execute grompp
    cmdlist=[ "grompp", "-f", mdpfile,
              "-quiet",
              "-c", inp.getInput('conf'),
              "-p", 'topol.top', # we made sure it's there
              "-o", "topol.tpr" ]
    if inp.hasInput('ndx'):
        cmdlist.append('-n')
        cmdlist.append(inp.getInput('ndx'))
    # TODO: symlink all the auxiliary files into the run dir
    stdoutfn=os.path.join(inp.outputDir, "stdout")
    stdoutf=open(stdoutfn,"w")
    stdoutf.write("%s\n"%time.strftime("%a, %d %b %Y %H:%M:%S"))
    stdoutf.write("%f\n"%time.time())
    #stdoutf=open(os.path.join(inp.outputDir, "stderr"),"w")
    proc=subprocess.Popen(cmdlist, 
                          stdin=None,
                          stdout=stdoutf,
                          stderr=subprocess.STDOUT,
                          cwd=inp.outputDir)
    proc.communicate(None)
    stdoutf.close()
    if proc.returncode != 0:
        raise GromacsError("Error running grompp: %s"%
                           (open(stdoutfn,'r').read()))
    fo=inp.getFunctionOutput()
    fo.setOut('stdout', FileValue(stdoutfn))
    fo.setOut('tpr', FileValue(os.path.join(inp.outputDir, "topol.tpr")))
    return fo

def mdrun(inp):
    if inp.testing(): 
        # if there are no inputs, we're testing wheter the command can run
        cpc.util.plugin.testCommand("trjcat -version")
        cpc.util.plugin.testCommand("eneconv -version")
        cpc.util.plugin.testCommand("gmxdump -version")
        return 
    persDir=inp.getPersistentDir()
    outDir=inp.getOutputDir()
    fo=inp.getFunctionOutput()
    rsrc=Resources(inp.getInputValue("resources"))
    rsrcFilename=os.path.join(persDir, 'rsrc.dat')
    # check whether we need to reinit
    if inp.cmd is None and inp.getInputValue('tpr').isUpdated():
        # there was no previous command. 
        # purge the persistent directory, by moving the confout files to a
        # backup directory
        log.debug("Initializing mdrun")
        confout=glob.glob(os.path.join(persDir, "run_???"))
        if len(confout)>0:
            backupDir=os.path.join(persDir, "backup")
            try:
                os.mkdir(backupDir)    
            except:
                pass
            for conf in confout:
                try:
                    os.rename(conf, os.path.join(backupDir, 
                                                 os.path.split(conf)[-1]))
                except:
                    pass
        if rsrc.max.get('cores') is None:
            confFile=os.path.join(persDir, 'conf.gro')
            extractConf(inp.getInput('tpr'), confFile)
            tune.tune(rsrc, confFile, inp.getInput('tpr'), persDir)
    else:
        if rsrc.max.get('cores') is None:
            rsrc.load(rsrcFilename)
    # try to find out whether the run has already finished
    confout=glob.glob(os.path.join(persDir, "run_???", "confout.part*.gro"))
    if len(confout) > 0:
        log.debug("Extracting data")
        # confout exists. we're finished. Concatenate all the runs if
        # we need to, but first create the output dict
        #outputs=dict()
        # Concatenate stuff
        confoutPath=os.path.join(outDir, "confout.gro")
        shutil.copy(confout[0], confoutPath ) 
        #outputs['conf'] = Value(confoutPath, 
        #                        inp.function.getOutput('conf').getType())
        fo.setOut('conf', FileValue(confoutPath))
        # fix the xtc files
        xtcso = sorted(glob.glob(os.path.join(persDir, "run_???", 
                                              "traj.part*.xtc")))
        # cull empty files and duplicate trajectory names
        xtcs=[]
        xtcbase=[]
        for file in xtcso:
            st=os.stat(file)
            base=os.path.split(file)[1]
            if st.st_size>0:
                if base not in xtcbase:
                    xtcs.append(file)
                    xtcbase.append(base) 
                else:
                    # there already was a file with this name. Overwrite
                    # it because mdrun wasn't aware of it when writing.
                    ind=xtcbase.index(base)
                    xtcs[ind]=file

        # concatenate them
        xtcoutname=os.path.join(outDir, "traj.xtc")
        if len(xtcs) > 0:
            cmd=["trjcat", "-f"]
            cmd.extend(xtcs)
            cmd.extend(["-o", xtcoutname])
            stdo=open(os.path.join(persDir,"trjcat_xtc.out"),"w")
            sp=subprocess.Popen(cmd, stdout=stdo,
                                stderr=subprocess.STDOUT)
            sp.communicate(None)
            stdo.close()
            #outputs['xtc'] = Value(xtcoutname, 
            #                       inp.function.getOutput('xtc').getType())
            fo.setOut('xtc', FileValue(xtcoutname))
        # do the trrs
        trrso = sorted(glob.glob(os.path.join(persDir, "run_???", 
                                              "traj.part*.trr")))
        # cull empty files and duplicate trajectory names
        trrs=[]
        trrbase=[]
        for file in trrso:
            st=os.stat(file)
            base=os.path.split(file)[1]
            if st.st_size>0:
                if base not in trrbase:
                    trrs.append(file)
                    trrbase.append(base) 
                else:
                    # there already was a file with this name. Overwrite
                    # it because mdrun wasn't aware of it when writing.
                    ind=trrbase.index(base)
                    trrs[ind]=file
        # concatenate them
        trroutname=os.path.join(outDir, "traj.trr")
        if len(trrs) > 0:
            cmd=["trjcat", "-f"]
            cmd.extend(trrs)
            cmd.extend(["-o", trroutname])
            stdo=open(os.path.join(persDir,"trjcat_trr.out"),"w")
            sp=subprocess.Popen(cmd, stdout=stdo,
                                stderr=subprocess.STDOUT)
            sp.communicate(None)
            stdo.close()
            #outputs['trr'] = Value(trroutname, 
            #                       inp.function.getOutput('trr').getType())
            fo.setOut('trr', FileValue(trroutname))
        # and the edrs
        edrso = glob.glob(os.path.join(persDir, "run_???", "ener.part*.edr"))
        # cull empty files and duplicate trajectory names
        edrs=[]
        edrbase=[]
        for file in edrso:
            st=os.stat(file)
            base=os.path.split(file)[1]
            if st.st_size>0:
                if base not in edrbase:
                    edrs.append(file)
                    edrbase.append(base) 
                else:
                    # there already was a file with this name. Overwrite
                    # it because mdrun wasn't aware of it when writing.
                    ind=edrbase.index(base)
                    edrs[ind]=file
        edroutname=os.path.join(outDir, "ener.edr")
        # concatenate them
        if len(edrs) > 0:
            cmd=["eneconv", "-f"]
            cmd.extend(edrs)
            cmd.extend(["-o", edroutname])
            stdo=open(os.path.join(persDir,"eneconv.out"),"w")
            sp=subprocess.Popen(cmd, stdout=stdo,
                                stderr=subprocess.STDOUT)
            sp.communicate(None)
            stdo.close()
            #outputs['edr'] = Value(edroutname, 
            #                       inp.function.getOutput('edr').getType())
            fo.setOut('edr', FileValue(edroutname))
        # do the stdout
        stdouto = glob.glob(os.path.join(persDir, "run_???", "stdout"))
        stdoutname=os.path.join(outDir, "stdout")
        outf=open(stdoutname,"w")
        for infile in stdouto:
            inf=open(infile, "r")
            outf.write(inf.read())
            inf.close()
        outf.write("%s\n"%time.strftime("%a, %d %b %Y %H:%M:%S"))
        outf.write("%f\n"%time.time())
        outf.close()
        #outputs['stdout'] = Value(stdoutname, 
        #                          inp.function.getOutput('trr').getType())
        fo.setOut('stdout', FileValue(stdoutname))
        # do the stderr
        stderro = glob.glob(os.path.join(persDir, "run_???", "stderr"))
        stderrname=os.path.join(outDir, "stderr")
        outf=open(stderrname,"w")
        for infile in stderro:
            inf=open(infile, "r")
            outf.write(inf.read())
            inf.close()
        outf.close()
        
        fo.setOut('stderr', FileValue(stderrname))
        log.debug("Returning without command.")
        log.debug("fo.cmds=%s"%str(fo.cmds))
        return fo
    else:
        # we're not finished. Find the last run directory and checkpoint
        lastrundir=None
        lastcpt=None
        lastfound=True
        prevtraj=[]
        i=0
        while lastfound:
            i+=1
            currundir=os.path.join(persDir, "run_%03d"%i)
            lastfound=False
            try:
                st=os.stat(currundir)
                if st.st_mode & stat.S_IFDIR:
                    lastfound=True
                    lastrundir=currundir
                    cpt=os.path.join(lastrundir, "state.cpt")
                    if os.path.exists(cpt):
                        # and check the size
                        st=os.stat(cpt)
                        if st.st_size>0: 
                            lastcpt=cpt
                    # now check if this has produced trajectories
                    xtc = glob.glob(os.path.join(lastrundir, "traj.part*.xtc"))
                    trr = glob.glob(os.path.join(lastrundir, "traj.part*.trr"))
                    edr = glob.glob(os.path.join(persDir, "ener.part*.trr"))
                    if len(xtc) == 0 and len(trr)==0 and len(edr)==0:
                        prevtraj.append(False)
                    else:
                        prevtraj.append(True)
            except OSError:
                pass
        # now check whether the last 4 iterations produced trajectories
        if len(prevtraj) > 4:
            ret=False
            for j in range(4):
                ret=ret or prevtraj[-j-1]
            if not ret:
                stde=os.path.join(lastrundir, "stderr")
                if os.path.exists(stde):
                    stdef=open(stde, 'r')
                    # TODO fix unicode
                    errmsg=unicode(stdef.read(), errors='ignore')
                    stdef.close()
                raise GromacsError("Error running mdrun. No trajectories: %s"%
                                   errmsg)
        # Make a new directory with the continuation of this run
        newdirname=currundir #"run_%03d"%(i+1)
        try:
            os.mkdir(newdirname)
        except OSError:
            pass
        tpr=inp.getInput('tpr')
        src=os.path.join(inp.getBaseDir(), tpr)
        dst=os.path.join(newdirname,"topol.tpr")
        if inp.getInput('cmdline_options') is not None:
            cmdlineOpts=shutil.split(inp.getInput('cmdline_options'))
        else:
            cmdlineOpts=[]
        if inp.getInput('priority') is not None:
            prio=inp.getInput('priority')
        else:
            prio=0
        # now add to the priority if this run has already been started
        if lastcpt is not None:
            shutil.copy(lastcpt, os.path.join(newdirname,"state.cpt"))
            # now check how far along the run is by inspecting the
            # step number we're at.
            cmd=['gmxdump', '-cp', lastcpt ]
            sp=subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
            stepline=re.compile('step = .*')
            for line in sp.stdout:
                if stepline.match(line):
                    stepnr=int(line.split()[2])
                    break
            sp.stdout.close()
            #sp.communicate()
            # and get the total step number
            cmd=['gmxdump', '-s', tpr ]
            sp=subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
            stepline=re.compile('[ ]*nsteps.*')
            for line in sp.stdout:
                if stepline.match(line):
                    nsteps=int(line.split()[2])
                    break
            sp.stdout.close()
            #sp.communicate()
            # now the priority ranges from 1 to 4, depending on how
            # far along the simulation is.
            prio += 1+int(3*(float(stepnr)/float(nsteps)))
            log.debug("Setting new priority to %d because it's in progress"%
                      prio)
        shutil.copy(src,dst)
        # we can always add state.cpt, even if it doesn't exist.
        args=["-quiet", "-s", "topol.tpr", "-noappend", "-cpi", "state.cpt",
               "-rcon", "0.7"  ]
        args.extend(cmdlineOpts)
        if lastcpt is not None:
            shutil.copy(lastcpt, os.path.join(newdirname,"state.cpt"))
        cmd=cpc.server.command.Command(newdirname, "gromacs/mdrun",args,
                                 minVersion=cpc.server.command.Version("4.5"),
                                 addPriority=prio)
        if inp.hasInput("resources") and inp.getInput("resources") is not None:
            log.debug("resources is %s"%(inp.getInput("resources")))
            #rsrc=Resources(inp.getInputValue("resources"))
            rsrc.updateCmd(cmd)
        log.debug("Adding command")
        fo.addCommand(cmd)
        if inp.getInputValue('tpr').isUpdated():
            fo.cancelPrevCommands()
    # and save for further invocations
    rsrc.save(rsrcFilename)
    return fo

def tune_fn(inp):
    if inp.testing():
        # if there are no inputs, we're testing wheter the command can run
        #cpc.util.plugin.testCommand("grompp -version")
        #cpc.util.plugin.testCommand("mdrun -version")
        return
    fo=inp.getFunctionOutput()
    persDir=inp.getPersistentDir()
    mdpfile=procSettings(inp, inp.outputDir)
    # copy the topology and include files 
    topfile=os.path.join(inp.outputDir, 'topol.top')
    shutil.copy(inp.getInput('top'), topfile)
    incl=inp.getInput('include')
    if incl is not None and len(incl)>0:
        for i in range(len(incl)):
            filename=inp.getInput('include[%d]'%i)
            if filename is not None:
                # same name, but in one directory.
                nname=os.path.join(inp.outputDir, os.path.split(filename)[1])
                shutil.copy(filename, nname)
    # and execute grompp
    cmdlist=[ "grompp", "-f", mdpfile,
              "-quiet",
              "-c", inp.getInput('conf'),
              "-p", 'topol.top', # we made sure it's there
              "-o", "topol.tpr" ]
    if inp.hasInput('ndx'):
        cmdlist.append('-n')
        cmdlist.append(inp.getInput('ndx'))
    proc=subprocess.Popen(cmdlist, 
                          stdin=None,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          cwd=inp.outputDir)
    (stdo, stde) = proc.communicate(None)
    if proc.returncode != 0:
        raise GromacsError("Error running grompp: %s, %s"%
                           (stdo, stde))
    rsrc=Resources()
    tune.tune(rsrc, inp.getInput('conf'), 
              os.path.join(inp.outputDir, 'topol.tpr'), persDir)
    fo.setOut('mdp', FileValue(mdpfile))
    fo.setOut('resources', rsrc.setOutputValue())
    return fo

