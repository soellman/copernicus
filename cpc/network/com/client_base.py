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


import httplib
import socket
import logging
import cpc.util.log
import client_connection
from cpc.util import CpcError
'''
Created on Mar 10, 2011

@author: iman
'''
log=logging.getLogger('cpc.network.com.client_base')

class ClientError(CpcError):
    def __init__(self, exc):
        self.str=exc.__str__()

class ClientBase(object):
    '''
    classdocs
    '''


    def __init__(self,host,port,conf):
        """Connect to a server opening a connection
           a privatekey and an keychain is needed if a https connection
           is established
        """        
        self.host = host
        self.port = port
        self.conf = conf
                

    def putRequest(self, req, use_verified_https=True):
        self.connect(use_verified_https)
        try:
            ret=self.conn.sendRequest(req,"PUT")
        except httplib.HTTPException as e:
            raise ClientError(e)
        except socket.error as e:
            raise ClientError(e)
        return ret

    def postRequest(self, req, use_verified_https=True):
        self.connect(use_verified_https)
        try:
            ret=self.conn.sendRequest(req)
        except httplib.HTTPException as e:
            raise ClientError(e)
        except socket.error as e:
            raise ClientError(e)
        return ret

    def closeClient(self):
        self.conn.conn.close()

    #FIXME private method
    def connect(self, use_verified_https=True):
        try:
            if use_verified_https:
                log.log(cpc.util.log.TRACE,"Connecting using verified HTTPS")
                self.conn=client_connection.VerifiedClientConnection(self.conf)
            else:
                log.log(cpc.util.log.TRACE,"Connecting using unverified HTTPS")
                self.conn=client_connection.UnverifiedClientConnection(
                            self.conf)
            self.conn.connect(self.host,self.port)
        except httplib.HTTPException as e:
            raise ClientError(e)
        except socket.error as e:
            raise ClientError(e)
