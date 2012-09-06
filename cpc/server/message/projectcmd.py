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


import logging
import json
import os
import os.path
import tarfile
import tempfile
from cpc.util.conf.server_conf import ServerConf

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from server_command import ServerCommand

import cpc.dataflow
import cpc.util



log=logging.getLogger('cpc.server.projectcmd')

class SCProjects(ServerCommand):
    """List all projects."""
    def __init__(self):
        ServerCommand.__init__(self, "projects")

    def run(self, serverState, request, response):
        lst=serverState.getProjectList().list()
        response.add(lst)

class SCProjectStart(ServerCommand):
    """Start a new project."""
    def __init__(self):
        ServerCommand.__init__(self, "project-start")

    def run(self, serverState, request, response):
        name=request.getParam('name')
        serverState.getProjectList().add(name)
        response.add("Project %s created"%name)

class SCProjectDelete(ServerCommand):
    """Delete a project."""
    def __init__(self):
        ServerCommand.__init__(self, "project-delete")

    def run(self, serverState, request, response):
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        q=serverState.getCmdQueue()
        delDir=False
        if request.hasParam('delete-dir'):
            delDir=True
        name=prj.getName()
        msg = ""
        if delDir:
            msg = " and its directory %s"%prj.getBasedir()
        q.deleteByProject(prj)
        serverState.getProjectList().delete(prj, delDir)
        response.add("Project %s%s deleted."%(name, msg))

class SCProjectSetDefault(ServerCommand):
    """Set the default project ."""
    def __init__(self):
        ServerCommand.__init__(self, "project-set-default")

    def run(self, serverState, request, response):
        name=request.getParam('name')
        serverState.getProjectList().setDefault(name)
        response.add("Project %s set to default project"%name)

class SCProjectActivate(ServerCommand):
    """Activate all elements in a project."""
    def __init__(self):
        ServerCommand.__init__(self, "project-activate")

    def run(self, serverState, request, response):
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        if request.hasParam('item'):
            item=request.getParam('item')
        else:
            item=""
        prj.activate(item)
        if item == "":
            response.add("All items in project %s activated."%prj.getName())
        else:
            response.add("%s in project %s activated."%(item, prj.getName()))

class SCProjectDeactivate(ServerCommand):
    """De-activate all elements in a project."""
    def __init__(self):
        ServerCommand.__init__(self, "project-deactivate")

    def run(self, serverState, request, response):
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        if request.hasParam('item'):
            item=request.getParam('item')
        else:
            item=""
        prj.deactivate(item)
        if item == "":
            response.add("All items in project %s de-activated."%prj.getName())
        else:
            response.add("%s in project %s de-activated."%(item, prj.getName()))

class SCProjectRerun(ServerCommand):
    """Force a rerun and optionally clear an error in an active instance."""
    def __init__(self):
        ServerCommand.__init__(self, "project-rerun")
    def run(self, serverState, request, response):
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        if request.hasParam('item'):
            item=request.getParam('item')
        else:
            item=""
        if ( request.hasParam('recursive') and 
             int(request.getParam('recursive')) == 1):
            recursive=True
        else:
            recursive=False
        if ( request.hasParam('clear-error') and 
             int(request.getParam('clear-error')) == 1):
            clearError=True
        else:
            clearError=False
        outf=StringIO()
        lst=prj.rerun(item, recursive, clearError, outf)
        response.add(outf.getvalue())

class SCProjectList(ServerCommand):
    """List named items in a project: instances or networks."""
    def __init__(self):
        ServerCommand.__init__(self, "project-list")
    def run(self, serverState, request, response):
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        if request.hasParam('item'):
            item=request.getParam('item')
        else:
            item=""
        lst=prj.getNamedItemList(item)
        response.add(lst)


class SCProjectInfo(ServerCommand):
    """Get project item descriptions."""
    def __init__(self):
        ServerCommand.__init__(self, "project-info")
    def run(self, serverState, request, response):
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        if request.hasParam('item'):
            item=request.getParam('item')
        else:
            item=""
        desc=prj.getNamedDescription(item)
        response.add(desc)

class SCProjectLog(ServerCommand):
    """Get an active instance log."""
    def __init__(self):
        ServerCommand.__init__(self, "project-log")
    def run(self, serverState, request, response):
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        if request.hasParam('item'):
            item=request.getParam('item')
        else:
            item=""
        inst=prj.getNamedInstance(item)
        logf=inst.getLog()
        if logf is None:
            response.add('Instance %s has no log'%item, status="ERROR")
            return
        if not os.path.exists(logf.getFilename()):
            response.add("%s: log empty"%item)
        try:
            fob=open(logf.getFilename(), "r")
        except IOError:
            response.add("Instance %s: can't read log"%item, status="ERROR")
            return
        response.setFile(fob, 'application/text')
       

class SCProjectGraph(ServerCommand):
    """Get network graph."""
    def __init__(self):
        ServerCommand.__init__(self, "project-graph")

    def run(self, serverState, request, response):
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        if request.hasParam('item'):
            item=request.getParam('item')
        else:
            item=""
        lst=prj.getGraph(item)
        response.add(lst)


class SCProjectUpload(ServerCommand):
    """Upload a project file."""
    def __init__(self):
        ServerCommand.__init__(self, "project-upload")
    def run(self, serverState, request, response):
        upfile=request.getFile('upload')
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        prj.importTopLevelFile(upfile, "uploaded file")
        response.add("Read file")


class SCProjectAddInstance(ServerCommand):
    """Add an instance to the top-level active network."""
    def __init__(self):
        ServerCommand.__init__(self, "project-add-instance")
    def run(self, serverState, request, response):
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        name=request.getParam('name')
        functionName=request.getParam('function')
        prj.addInstance(name, functionName)
        response.add("Added instance '%s' of function %s"%
                          (name, functionName))

class SCProjectConnect(ServerCommand):
    """Add a connection to the top-level active network."""
    def __init__(self):
        ServerCommand.__init__(self, "project-connect")
    def run(self, serverState, request, response):
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        src=request.getParam('source')
        dst=request.getParam('destination')
        outf=StringIO()
        prj.scheduleConnect(src, dst, outf)
        response.add(outf.getvalue())

class SCProjectImport(ServerCommand):
    """Import a module (file/lib) to the project."""
    def __init__(self):
        ServerCommand.__init__(self, "project-import")
    def run(self, serverState, request, response):
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        module=request.getParam('module')
        prj.importName(module)
        response.add("Imported module %s"%(module))

class SCProjectGet(ServerCommand):
    """Get an i/o item in a project."""
    def __init__(self):
        ServerCommand.__init__(self, "project-get")

    def run(self, serverState, request, response):
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        itemname=request.getParam('item')
        if not request.hasParam("getFile"):
            ret=dict()
            ret["name"]=itemname
            try:
                val=prj.getNamedValue(itemname)
                if val is not None:
                    ret["value"]=val.getDesc()
                else:
                    ret["value"]="not found"    
            except cpc.dataflow.ApplicationError as e:
                ret["value"]="not found"    
            response.add(ret)
        else:
            try:
                val=prj.getNamedValue(itemname)
                if (val is not None and 
                    val.getType().isSubtype(cpc.dataflow.fileType)):
                    if val.fileValue is not None:
                        fname=val.fileValue.getAbsoluteName()
                    else:
                        fname=val.value
                    if fname is None:
                        response.add('Item %s not set'%itemname)
                        return
                    fob=open(fname, 'r')
                    #response.add('%s'%itemname)
                    response.setFile(fob, 'application/text')
                else:
                    response.add('Item %s not a file'%itemname, status="ERROR")
            except cpc.dataflow.ApplicationError as e:
                response.add('Item %s not found'%itemname, status="ERROR")


class SCProjectSave(ServerCommand):
    def __init__(self):
        ServerCommand.__init__(self, "project-save")

    def run(self, serverState, request, response):

        if request.hasParam('project'):
            project=request.getParam('project')
            try:
                tff = serverState.saveProject(project)
                response.setFile(tff,'application/x-tar')
            except Exception as e:
                response.add(e.message,status="ERROR")
        else:
            response.add("No project specified for save",status="ERROR")


class SCProjectLoad(ServerCommand):
    def __init__(self):
        ServerCommand.__init__(self, "project-load")

    def run(self, serverState, request, response):
        if(request.haveFile("projectFile")):
            projectName = request.getParam("project")
            projectBundle=request.getFile('projectFile')

            try:

                serverState.getProjectList().add(projectName)
                extractPath = "%s/%s"%(ServerConf().getRunDir(),projectName)
                tar = tarfile.open(fileobj=projectBundle,mode="r")
                tar.extractall(path=extractPath)
                tar.close()
                serverState.readProjectState(projectName)

            except:
                response.add("No project file provided",status="ERROR")
                return

            response.add("Project restored as %s"%projectName)
        else:
            response.add("No project file provided",status="ERROR")



class SCProjectSet(ServerCommand):
    """Set an i/o item in a project."""
    def __init__(self):
        ServerCommand.__init__(self, "project-set")

    def run(self, serverState, request, response):
        upfile=None
        filename=None
        if request.haveFile('upload'):
            upfile=request.getFile('upload')
            filename=os.path.basename(request.getParam('filename'))
        setval=request.getParam('value')
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        itemname=request.getParam('item')
        try:
            outf=StringIO()
            if upfile is None:
                prj.scheduleSet(itemname, setval, outf)
            else:
                # write out the file 
                dir=prj.getNewInputSubDir()
                os.mkdir(dir)
                setval=os.path.join(dir, filename)
                #if not tp.isSubtype(cpc.dataflow.fileType):
                #    raise cpc.util.CpcError("%s does not expect a file"%
                #                            itemname)
                #outValue=cpc.dataflow.FileValue(setval)
                outFile=open(setval, "w")
                outFile.write(upfile.read())
                outFile.close()
                prj.scheduleSet(itemname, setval, outf, cpc.dataflow.fileType,
                                printName=filename)
            response.add(outf.getvalue())
        except cpc.dataflow.ApplicationError as e:
            response.add("Item not found: %s"%(str(e)))

class SCProjectTransact(ServerCommand):
    """Start a transaction to be able to commit several project-set commands 
       in a project."""
    def __init__(self):
        ServerCommand.__init__(self, "project-transact")

    def run(self, serverState, request, response):
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        outf=StringIO()
        prj.beginTransaction(outf)
        response.add(outf.getvalue())

class SCProjectCommit(ServerCommand):
    """Commit several project-set commands in a project."""
    def __init__(self):
        ServerCommand.__init__(self, "project-commit")

    def run(self, serverState, request, response):
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        outf=StringIO()
        prj.commit(outf)
        response.add(outf.getvalue())

class SCProjectRollback(ServerCommand):
    """Cancel several project-set commands in a project."""
    def __init__(self):
        ServerCommand.__init__(self, "project-rollback")

    def run(self, serverState, request, response):
        if request.hasParam('project'):
            prj=serverState.getProjectList().get(request.getParam('project'))
        else:
            prj=serverState.getProjectList().getDefault()
        outf=StringIO()
        prj.rollback(outf)
        response.add(outf.getvalue())


