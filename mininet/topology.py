#!/usr/bin/env python3

from mininet.topo import Topo


class OnlineExamTopo(Topo):
    """
    Topology for the Online Examination Network.

    h1: Examination server
    h2: Student client 1
    h3: Student client 2
    s1: SDN-controlled switch
    """

    def build(self):
        # Create the examination server and student hosts
        server = self.addHost("h1", ip="10.0.0.1/24")
        student1 = self.addHost("h2", ip="10.0.0.2/24")
        student2 = self.addHost("h3", ip="10.0.0.3/24")

        # Create the virtual network switch
        switch = self.addSwitch("s1")

        # Connect all hosts to the switch
        self.addLink(server, switch)
        self.addLink(student1, switch)
        self.addLink(student2, switch)


topos = {
    "onlineexam": lambda: OnlineExamTopo()
}
