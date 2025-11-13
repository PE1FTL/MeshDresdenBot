import uuid
from datetime import datetime

from config import Config
from mesh import Mesh
from nodedata import NodeData
from status import Status
from utilities import get_datestamp, format_seconds, calculate_distance


# Generate a short UUID by truncating
def short_uuid():
    return str(uuid.uuid4())[:8]


class Message:
    def __init__(self, interface, packet):
        self.interface = interface
        self.packet = packet
        self.status = Status()
        self.app2type = {
            'TEXT_MESSAGE_APP': 'Text',
            'TELEMETRY_APP': 'Telemetry',
            'POSITION_APP': 'Position',
            'NODEINFO_APP': 'NodeInfo'
        }
        self.formatted_date = get_datestamp()
        self.fromId = None
        self.toId = None
        self.application = None
        self.hops = -1
        self.fromName = ''
        self.decoded = {}

    def handle_message(self):
        if 'rxTime' in self.packet:
            self.formatted_date = datetime.fromtimestamp(self.packet['rxTime']).strftime("%Y-%m-%d %H:%M:%S")

        self.fromId = f'!{self.packet.get('from'):08x}'
        self.toId = f'!{self.packet.get('to'):08x}'
        if self.toId == '!ffffffff':
            self.toId = '^all'

        self.decoded = self.packet.get('decoded', {})
        self.application = self.decoded.get('portnum', None)
        if self.application is None:
            if self.packet.get('encrypted', None):
                self.application = 'ENCRYPTED_MSG'
            else:
                self.application = 'UNKNOWN_APP'

        if 'hopLimit' in self.packet and 'hopStart' in self.packet:
            self.hops = self.packet.get('hopStart') - self.packet.get('hopLimit')
        elif 'hopStart' in self.packet:
            self.hops = self.packet.get('hopStart')

        self.log_packet_to_file()

        # we get a lot of TELEMETRY_APP packets from ourselves that aren't transmitted, just sent back to the local computer
        if self.packet['from'] == Mesh().node.localNode.nodeNum and self.application == 'TELEMETRY_APP':
            return

        self.increment_count()

        # Process the packet
        self.handle_packet()

    def log_packet_to_file(self):
        # Write packet to packetlog.txt
        with open('packetlog.txt', 'a') as f:
            f.write(self.formatted_date + ':' + str(self.packet).replace('\n', '\\n') + '\n')

    def handle_packet(self):
        # print(f'{self.application}: {self.fromId} → {self.toId}', flush=True)
        if self.fromId is not None:
            self.fromName = self.fromId
            node = NodeData().lookup_by_id(self.fromId)
            if node is not None:
                self.fromName = f"{self.fromId} {node['user.longName']}"

            if self.application == 'NODEINFO_APP':
                self.handle_nodeinfo()

            elif self.application == 'POSITION_APP':
                self.handle_position()

            elif self.application == 'TELEMETRY_APP':
                self.handle_telemetry()

            elif self.application == 'TEXT_MESSAGE_APP':
                self.handle_text()

            elif self.application == 'ENCRYPTED_MSG':
                self.handle_text()

            elif self.application == 'TRACEROUTE_APP':
                self.handle_traceroute()

            else:
                self.handle_other()

    def add_node_to_ui(self, message_type, node_info_string):
        id = 'id' + short_uuid()
        name = self.fromName.split(' ')

        self.status.add_pkt(
            self.formatted_date,
            ' '.join(name[1:]),
            self.hops,
            self.packet.get('rxRssi', ''),
            message_type,
            node_info_string,
            self.fromId
        )

    def handle_other(self):
        self.add_node_to_ui('-', self.application)

    def handle_traceroute(self):
        route_to = []
        route = [int(self.packet['toId'][1:], 16)]
        if 'route' in self.packet['decoded']['traceroute']:
            for r in self.packet['decoded']['traceroute']['route']:
                route.append(r)
        route.append(int(self.packet['fromId'][1:], 16))

        self.hops = -2
        for hop in route:
            self.hops += 1
            node_id = f'!{int(hop):08x}'
            hop_node = NodeData().lookup_by_id(node_id)
            if hop_node and hop_node.get('user.longName'):
                node_id = hop_node.get('user.longName')
            route_to.append(node_id)

        self.add_node_to_ui('TR', f'Routing: {'→'.join(route_to)}')

    def handle_text(self):
        data = self.flatten_packet()

        if 'channel' not in data:
            if self.toId != '^all':
                data['channel'] = 'DM'
            else:
                data['channel'] = "Pri"

        if self.application == 'TEXT_MESSAGE_APP':
            text = data['text']
        else:
            text = '*** ENCRYPTED TEXT ***'

# === PING-PONG BOT: BROADCAST AUF CHANNEL 2 (sec) ===
        if self.application == 'TEXT_MESSAGE_APP' and self.packet.get('channel', 0) == 1:
            text = data['text'].strip().lower()
            command = text.split()[0] if text else ""
            args = text[len(command):].strip() if text else ""

            # Vermeide Selbst-Antwort
            if self.packet['from'] == Mesh().node.localNode.nodeNum:
                pass  # Ignoriere eigene Nachrichten
            else:
                response = None

                if command == '#ping':
                    response = self.bot_generate_ping()
                elif command == '#test':
                    response = self.bot_generate_test()
                elif command == '#nodes':
                    response = self.bot_generate_nodes()
                elif command == '#info':
                    response = self.bot_generate_info()
                elif command == '#self':
                    response = self.bot_generate_self()

                if response:
                    try:
                        self.interface.sendText(
                            text=response,
                            channelIndex=1
                        )
                        print(f"[BOT] Antwort auf {command}: {response.split()[0]}...")
                    except Exception as e:
                        print(f"[BOT] Sendefehler: {e}")
    
# === UI: Nachricht anzeigen ===
        self.status.add_msg(data['received'], data['fromName'], data['toName'], data['channel'], text, self.fromId)

        self.add_node_to_ui('Text', text[:32])

    def handle_telemetry(self):
        telemetry = self.decoded.get('telemetry', {})
        metrics = telemetry.get('deviceMetrics', {})
        if metrics.get('uptimeSeconds'):
            self.add_node_to_ui('🕑', f'{format_seconds(metrics.get("uptimeSeconds", 0))} uptime')
        elif telemetry.get('temperature'):
            self.add_node_to_ui('🌡', f'{telemetry.get("temperature", "?")}°C')
        else:
            self.handle_other()

    def increment_count(self):
        # Increment the count for the app type
        if self.application in self.app2type:
            self.status.add_count(self.app2type[self.application])
        else:
            self.status.add_count('Other')

    def handle_nodeinfo(self):
        user = self.decoded.get('user', {})
        hw = user.get('hwModel', '?')
        role = user.get('role', '?')
        if role == '?':
            role = ''
        else:
            role = 'as ' + role
        self.add_node_to_ui('ⓘ', f'{hw} {role}')

    def handle_position(self):
        position = self.decoded.get('position', {})
        node_lat = position.get("latitude", None)
        node_long = position.get("longitude", None)
        config = Config()
        my_lat = config.get('location.latitude', None)
        my_long = config.get('location.longitude', None)

        distance = ''
        if all([node_lat, node_long, my_lat, my_long]):
            km = calculate_distance((float(node_lat), float(node_long)), (float(my_lat), float(my_long)))
            distance = f' {int(km)}km'

        self.add_node_to_ui('<img src="static/position.png" width=24>',
                            f'({position.get("latitude", 0):7.4f}, {position.get("longitude", 0):7.4f}, {position.get('altitude', '?')}m) {distance}')

    def flatten_packet(self):
        packet_data = [
            ['from', ['fromId']],
            ['to', ['toId']],
            ['app', ['decoded', 'portnum']],
            ['channel', ['channel']],
            ['text', ['decoded', 'text']],
            ['telemetry', ['decoded', 'telemetry']],
            ['position', ['decoded', 'position']]
        ]

        data = {}
        for pd in packet_data:
            d = self.packet
            keyname = []
            for k in pd[1]:
                keyname.append(k)
                d = d.get(k)
                if d is None:
                    break

            if d is not None:
                data[pd[0]] = str(d)

        data['fromName'] = self.fromId
        data['toName'] = self.toId

        node = NodeData().lookup_by_id(self.fromId)
        if node is not None:
            data['fromName'] = node['user.longName']

        node = NodeData().lookup_by_id(self.toId)
        if node is not None:
            data['toName'] = node['user.longName']

        if 'rxTime' in self.packet:
            dt = datetime.fromtimestamp(self.packet['rxTime'])
        else:
            dt = datetime.now()

        data['received'] = dt.strftime('%Y-%m-%d %H:%M:%S')

        return data

# === BOT UNTERROUTINEN ===
    def bot_generate_ping(self):
        """Erweiterte Pong-Antwort mit UTC-Zeit und Node-ID"""
        from datetime import datetime
        import pytz
        now = datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
        local_node = Mesh().node.localNode
        node_id = f"!{local_node.nodeNum:08x}"
        return f"pong {now} | Node: {node_id}"

    def bot_generate_test(self):
        """Testantwort mit Echo und System-Check"""
        from datetime import datetime
        import pytz
        now = datetime.now(pytz.UTC).strftime('%H:%M:%S')
        return f"Test OK | {now} | MeshDDBot v1.0"

    def bot_generate_nodes(self):
        """Liste aller bekannter Nodes mit Name und ID"""
        nodes = NodeData().get_nodes()
        if not nodes:
            return "Keine Nodes bekannt."
        
        lines = [f"{len(nodes)} Nodes:"]
        for node in sorted(nodes, key=lambda x: x['user']['longName']):
            name = node['user']['longName']
            node_id = f"!{node['num']:08x}"
            lines.append(f"  • {name} ({node_id})")
        return "\n".join(lines[:10])  # Max 10 Zeilen

    def bot_generate_info(self):
        """Netzwerk- und Bot-Info"""
        from datetime import datetime
        import pytz
        now = datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
        local = Mesh().node.localNode
        uptime = format_seconds(local.uptimeSeconds) if hasattr(local, 'uptimeSeconds') else "unbek."
        return f"MeshDDBot Info:\nZeit: {now}\nUptime: {uptime}\nKanal: sec (2)"

    def bot_generate_self(self):
        """Info über den eigenen Node"""
        local = Mesh().node.localNode
        node_id = f"!{local.nodeNum:08x}"
        hw = local.hwModel if hasattr(local, 'hwModel') else "unbek."
        role = local.role if hasattr(local, 'role') else "unbek."
        battery = local.deviceMetrics.batteryLevel if hasattr(local, 'deviceMetrics') and local.deviceMetrics.batteryLevel else "unbek."
        return f"Self:\nID: {node_id}\nHW: {hw}\nRole: {role}\nBat: {battery}%"