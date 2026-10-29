
import os
import time

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import (
    CONFIG_DISPATCHER,
    MAIN_DISPATCHER,
    DEAD_DISPATCHER,
    set_ev_cls,
)
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib import hub
from os_ken.lib.packet import packet, ethernet, ether_types


CONGESTION_THRESHOLD_BPS = int(
    os.getenv("CONGESTION_THRESHOLD_BPS", "100000")
)
CLEAR_THRESHOLD_BPS = int(
    os.getenv("CLEAR_THRESHOLD_BPS", "50000")
)
POLL_INTERVAL = 5
CONGESTION_FLOW_PRIORITY = 20


class OnlineExamController(app_manager.OSKenApp):
    """Learning switch with port monitoring and UDP congestion filtering."""

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        self.previous_stats = {}
        self.congested_ports = set()

        self.logger.info("Online Examination SDN Controller started")
        self.monitor_thread = hub.spawn(self._monitor_ports)

    @set_ev_cls(
        ofp_event.EventOFPStateChange,
        [MAIN_DISPATCHER, DEAD_DISPATCHER],
    )
    def state_change_handler(self, ev):
        datapath = ev.datapath

        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
            self.logger.info("Switch connected: dpid=%s", datapath.id)

        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)
            self.previous_stats.pop(datapath.id, None)
            self.congested_ports = {
                item for item in self.congested_ports
                if item[0] != datapath.id
            }

    def add_flow(
        self, datapath, priority, match, actions, idle_timeout=60
    ):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS, actions
            )
        ]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions,
            idle_timeout=idle_timeout,
        )
        datapath.send_msg(mod)

    @set_ev_cls(
        ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER
    )
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER,
            )
        ]

        # Keep the table-miss rule installed indefinitely.
        self.add_flow(
            datapath,
            0,
            parser.OFPMatch(),
            actions,
            idle_timeout=0,
        )
        self.logger.info(
            "OpenFlow 1.3 initialized for dpid=%s", datapath.id
        )

    def request_port_stats(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        request = parser.OFPPortStatsRequest(
            datapath, 0, ofproto.OFPP_ANY
        )
        datapath.send_msg(request)

    def _monitor_ports(self):
        while True:
            for datapath in list(self.datapaths.values()):
                try:
                    self.request_port_stats(datapath)
                except Exception as exc:
                    self.logger.warning(
                        "Could not request stats from dpid=%s: %s",
                        datapath.id, exc,
                    )

            hub.sleep(POLL_INTERVAL)

    @set_ev_cls(
        ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER
    )
    def port_stats_reply_handler(self, ev):
        datapath = ev.msg.datapath
        dpid = datapath.id
        now = time.monotonic()

        previous = self.previous_stats.setdefault(dpid, {})

        for stat in ev.msg.body:
            port = stat.port_no

            if port >= datapath.ofproto.OFPP_MAX:
                continue

            total_bytes = stat.rx_bytes + stat.tx_bytes
            old = previous.get(port)
            previous[port] = (total_bytes, now)

            if old is None:
                continue

            old_bytes, old_time = old
            elapsed = now - old_time

            if elapsed <= 0 or total_bytes < old_bytes:
                continue

            rate_bps = (total_bytes - old_bytes) * 8 / elapsed
            key = (dpid, port)

            if key not in self.congested_ports:
                if rate_bps >= CONGESTION_THRESHOLD_BPS:
                    self.congested_ports.add(key)
                    self.set_udp_filter(datapath, port, enable=True)

                    self.logger.warning(
                        "CONGESTION: dpid=%s port=%s rate=%.0f bps; "
                        "UDP ingress filter enabled",
                        dpid, port, rate_bps,
                    )

            elif rate_bps < CLEAR_THRESHOLD_BPS:
                self.congested_ports.remove(key)
                self.set_udp_filter(datapath, port, enable=False)

                self.logger.info(
                    "CONGESTION CLEARED: dpid=%s port=%s rate=%.0f bps; "
                    "UDP ingress filter removed",
                    dpid, port, rate_bps,
                )

    def set_udp_filter(self, datapath, port, enable):
        """Drop IPv4 UDP packets arriving on a congested port."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch(
            in_port=port,
            eth_type=0x0800,
            ip_proto=17,
        )

        if enable:
            self.add_flow(
                datapath,
                CONGESTION_FLOW_PRIORITY,
                match,
                [],
                idle_timeout=0,
            )
        else:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                command=ofproto.OFPFC_DELETE,
                table_id=ofproto.OFPTT_ALL,
                out_port=ofproto.OFPP_ANY,
                out_group=ofproto.OFPG_ANY,
                priority=CONGESTION_FLOW_PRIORITY,
                match=match,
            )
            datapath.send_msg(mod)

    @set_ev_cls(
        ofp_event.EventOFPPacketIn, MAIN_DISPATCHER
    )
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth is None or eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        src = eth.src
        dst = eth.dst

        learned = self.mac_to_port.setdefault(datapath.id, {})
        learned[src] = in_port

        out_port = learned.get(dst, ofproto.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(
                in_port=in_port,
                eth_src=src,
                eth_dst=dst,
            )
            self.add_flow(
                datapath,
                10,
                match,
                actions,
            )

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)
