# Volatility
# Copyright (C) 2007-2013 Volatility Foundation
#
# This file is part of Volatility.
#
# Volatility is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.  You may not use, modify or
# distribute this program under any other version of the GNU General
# Public License.
#
# Volatility is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Volatility.  If not, see <http://www.gnu.org/licenses/>.
#

"""
@author:       Andrew Case
@license:      GNU General Public License 2.0
@contact:      atcuno@gmail.com
@organization: 
"""

import volatility.plugins.linux.common as linux_common
import volatility.plugins.linux.ifconfig as linux_ifconfig
import volatility.plugins.linux.lsof as linux_lsof
import volatility.debug as debug
import volatility.obj as obj

class linux_list_promisc(linux_common.AbstractLinuxCommand):
    """List applications with promiscuous sockets"""

    def __init__(self, config, *args, **kwargs):
        self.fd_cache = {}
        linux_common.AbstractLinuxCommand.__init__(self, config, *args, **kwargs)

    def _SOCK_INODE(self, sk):
        backsize = self.profile.get_obj_size("socket")
        addr = sk + backsize

        return obj.Object('inode', offset = addr, vm = self.addr_space) 

    def _walk_net_spaces(self):
        offset = self.addr_space.profile.get_obj_offset("sock_common", "skc_node")
        
        nslist_addr = self.addr_space.profile.get_symbol("net_namespace_list")
        nethead = obj.Object("list_head", offset = nslist_addr, vm = self.addr_space)
            
        for net in nethead.list_of_type("net", "list"):
            node = net.packet.sklist.first.dereference().v()
            
            sk = obj.Object("sock", offset = node - offset, vm = self.addr_space)

            while sk.is_valid():
                inode = self._SOCK_INODE(sk.sk_socket)

                ino = inode

                yield ino

                sk = obj.Object("sock", offset = sk.sk_node.next - offset, vm = self.addr_space)

    def _fill_cache(self):
        for (task, filp, fd) in linux_lsof.linux_lsof(self._config).calculate():
            filepath = linux_common.get_path(task, filp)
            if type(filepath) == str and filepath.find("socket:[") != -1:
                to_add = filp.dentry.d_inode.i_ino
                self.fd_cache[to_add] = [task, filp, fd, filepath]
                 
    def _find_proc_for_inode(self, inode):
        if self.fd_cache == {}:
            self._fill_cache()

        if inode.i_ino in self.fd_cache:
            (task, filp, fd, filepath) = self.fd_cache[inode.i_ino]
        else:
            debug.error("ERROR: Unable to find inode %d in cache!" % inode.i_ino)

        return (task, fd, inode.i_ino)

    def calculate(self):
        linux_common.set_plugin_members(self)

        sym_addr = self.addr_space.profile.get_symbol("packet_sklist") 

        # old kernels before namespaces
        if sym_addr:
            print "oldddddddddd"
        else:
            for inode in self._walk_net_spaces():
                yield self._find_proc_for_inode(inode)
            
    def render_text(self, outfd, data):

        self.table_header(outfd, [("Process", "16"),
                                  ("PID", "6"),
                                  ("File Descriptor", "5"),
                                  ("Inode", "18"),
                                 ])

        for (task, fd, inum) in data:
            self.table_row(outfd, task.comm, task.pid, fd, inum)