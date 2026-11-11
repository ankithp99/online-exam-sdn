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
from congestion import counter_rate_bps, congestion_transition


# Configurable traffic thresholds in bits per second.
CONGESTION_THRESHOLD_BPS = int(
    os.getenv("CONGESTION_THRESHOLD_BPS", "100000")
)
CLEAR_THRESHOLD_BPS = int(
    os.getenv("CLEAR_THRESHOLD_BPS", "50000")
)
if CONGESTION_THRESHOLD_BPS < CLEAR_THRESHOLD_BPS:
    raise ValueError(
        "CONGESTION_THRESHOLD_BPS must be >= CLEAR_THRESHOLD_BPS"
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
        dpid = datapath.id

        if ev.state == MAIN_DISPATCHER:
            self.datapaths[dpid] = datapath
            self.logger.info("Switch connected: dpid=%s", dpid)

        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(dpid, None)
            self.previous_stats.pop(dpid, None)
            self.logger.info("Switch disconnected: dpid=%s", dpid)

    def add_flow(
        self,
        datapath,
        priority,
        match,
        actions,
        idle_timeout=60,
    ):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions,
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
        ofp_event.EventOFPSwitchFeatures,
        CONFIG_DISPATCHER,
    )
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        # A switch may retain flows across a controller disconnect. Remove
        # temporary congestion entries on reconnect; monitoring will create
        # them again only after fresh counter samples confirm congestion.
        stale_filter = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            table_id=0,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            priority=CONGESTION_FLOW_PRIORITY,
            match=parser.OFPMatch(eth_type=0x0800, ip_proto=17),
        )
        datapath.send_msg(stale_filter)
        self.congested_ports = {
            item for item in self.congested_ports if item[0] != datapath.id
        }

        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER,
            )
        ]

        # Keep the table-miss rule installed permanently.
        self.add_flow(
            datapath,
            0,
            parser.OFPMatch(),
            actions,
            idle_timeout=0,
        )

        self.logger.info(
            "Installed table-miss rule on switch %s",
            datapath.id,
        )

    def request_port_stats(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        request = parser.OFPPortStatsRequest(
            datapath,
            0,
            ofproto.OFPP_ANY,
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
                        datapath.id,
                        exc,
                    )

            hub.sleep(POLL_INTERVAL)

    @set_ev_cls(
        ofp_event.EventOFPPortStatsReply,
        MAIN_DISPATCHER,
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

            # Filtering is applied to packets arriving on this port, so use
            # the ingress (RX) counter. Summing RX and TX double-counts flows
            # crossing a port and can trigger a drop in the wrong direction.
            total_bytes = stat.rx_bytes
            old = previous.get(port)
            previous[port] = (total_bytes, now)

            # The first sample establishes a baseline.
            if old is None:
                continue

            old_bytes, old_time = old
            rate_bps = counter_rate_bps(old_bytes, old_time, total_bytes, now)
            if rate_bps is None:
                continue
            key = (dpid, port)
            if rate_bps >= 1000:
                self.logger.info(
                    "PORT RATE: dpid=%s port=%s rx=%.0f bps",
                    dpid, port, rate_bps,
                )
            transition = congestion_transition(
                key in self.congested_ports,
                rate_bps,
                CONGESTION_THRESHOLD_BPS,
                CLEAR_THRESHOLD_BPS,
            )
            if transition == "congested":
                self.congested_ports.add(key)
                self.set_udp_filter(datapath, port, enable=True)
                self.logger.warning(
                    "CONGESTION: dpid=%s ingress_port=%s rate=%.0f bps; "
                    "UDP filter enabled", dpid, port, rate_bps,
                )
            elif transition == "clear":
                self.congested_ports.discard(key)
                self.set_udp_filter(
                    datapath, port, enable=False
                )

                self.logger.info(
                    "CONGESTION CLEARED: dpid=%s port=%s "
                    "rate=%.0f bps; UDP filter removed",
                    dpid,
                    port,
                    rate_bps,
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
            # Empty actions mean matching packets are dropped.
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
                command=ofproto.OFPFC_DELETE_STRICT,
                table_id=0,
                out_port=ofproto.OFPP_ANY,
                out_group=ofproto.OFPG_ANY,
                priority=CONGESTION_FLOW_PRIORITY,
                match=match,
            )
            datapath.send_msg(mod)

    @set_ev_cls(
        ofp_event.EventOFPPacketIn,
        MAIN_DISPATCHER,
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

        dpid = datapath.id
        src = eth.src
        dst = eth.dst

        learned = self.mac_to_port.setdefault(dpid, {})
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

            self.logger.info(
                "Installed forwarding rule: %s -> %s via port %s",
                src,
                dst,
                out_port,
            )

        # Include packet data only when the switch did not buffer it.
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
