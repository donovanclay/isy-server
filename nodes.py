import asyncio
import json
from pprint import pprint

import requests
import logging
import os
import time
from urllib.parse import urlparse

import socketio
from aiohttp import web

from dotenv import load_dotenv
from pyisy import ISY
from pyisy.connection import ISYConnectionError, ISYInvalidAuthError, get_new_client_session
from pyisy.constants import NODE_CHANGED_ACTIONS
from pyisy.logging import enable_logging
from pyisy.nodes import NodeChangedEvent

load_dotenv()

ADDRESS = os.getenv("ADDRESS")
USERNAME = os.getenv("USER_NAME")
PASSWORD = os.getenv("PASSWORD")

print(ADDRESS)
print(USERNAME)
print(PASSWORD)

_LOGGER = logging.getLogger(__name__)


async def main(url, username, password, tls_ver, events, node_servers):
    """Execute connection to ISY and load all system info."""
    _LOGGER.info("Starting PyISY...")
    t_0 = time.time()
    host = urlparse(url)
    if host.scheme == "http":
        https = False
        port = host.port or 80
    elif host.scheme == "https":
        https = True
        port = host.port or 443
    else:
        _LOGGER.error("host value in configuration is invalid.")
        return False

    # Use the helper function to get a new aiohttp.ClientSession.
    websession = get_new_client_session(https, tls_ver)

    # Connect to ISY controller.
    isy = ISY(
        host.hostname,
        port,
        username=username,
        password=password,
        use_https=https,
        tls_ver=tls_ver,
        webroot=host.path,
        websession=websession,
        use_websocket=True,
    )

    try:
        await isy.initialize(node_servers)
    except (ISYInvalidAuthError, ISYConnectionError):
        _LOGGER.error(
            "Failed to connect to the ISY, please adjust settings and try again."
        )
        await isy.shutdown()
        return
    except Exception as err:
        _LOGGER.error("Unknown error occurred: %s", err.args[0])
        await isy.shutdown()
        raise

    # Print a representation of all the Nodes
    # _LOGGER.debug(repr(isy.nodes))
    _LOGGER.info("Total Loading time: %.2fs", time.time() - t_0)

    node_changed_subscriber = None
    system_status_subscriber = None

    def node_changed_handler(event: NodeChangedEvent) -> None:
        """Handle a node changed event sent from Nodes class."""
        (event_desc, _) = NODE_CHANGED_ACTIONS[event.action]
        # _LOGGER.info(
        #     "Subscriber--Node %s Changed: %s %s",
        #     event.address,
        #     event_desc,
        #     event.event_info if event.event_info else "",
        #     )

    def system_status_handler(event: str) -> None:
        """Handle a system status changed event sent ISY class."""
        # _LOGGER.info("System Status Changed: %s", SYSTEM_STATUS.get(event))

    try:
        if events:
            isy.websocket.start()
            node_changed_subscriber = isy.nodes.status_events.subscribe(
                node_changed_handler
            )
            system_status_subscriber = isy.status_events.subscribe(
                system_status_handler
            )

        # -----------------------------------------
        # CLAY HUANG CODE STARTS HERE
        # -----------------------------------------

        r = requests.get("https://raw.githubusercontent.com/donovanclay/isy/master/util.json")

        file_data = r.json()

        nodes = {
            "Exhausts": {},
            "Supplies": {},
            "Humidity Sensors": {},
            "Motion Sensors": {}
        }

        for fan in file_data["exhaust_fans"]:
            name = file_data["exhaust_fans"][fan]["name"]
            cfm = file_data["exhaust_fans"][fan]["cfm"]
            nodes["Exhausts"][name] = [isy.nodes[name].status, cfm]

        for fan in file_data["supplies"]:
            name = file_data["supplies"][fan]["name"]
            cfm = file_data["supplies"][fan]["cfm"]
            nodes["Supplies"][name] = [isy.nodes[str(name)].status, cfm]

        for fan in file_data["honeywell_sens"]:
            nodes["Humidity Sensors"][fan["sens_hum"]] = isy.nodes[fan["sens_hum"]].aux_properties["CLIHUM"].value
            nodes["Motion Sensors"][fan["sens_motion"]] = isy.nodes[fan["sens_motion"]].status

        for node in nodes["Exhausts"]:
            update_server("Exhausts", node, isy.nodes[node].status, nodes["Exhausts"][node][1])

        for node in nodes["Supplies"]:
            update_server("Supplies", node, isy.nodes[node].status, nodes["Supplies"][node][1])

        for node in nodes["Humidity Sensors"]:
            update_server("Humidity Sensors", node, isy.nodes[node].aux_properties["CLIHUM"].value)

        for node in nodes["Motion Sensors"]:
            update_server("Motion Sensors", node, isy.nodes[node].status)

        while True:
            await asyncio.sleep(1)

            for node in nodes["Exhausts"]:
                if nodes["Exhausts"][node] != isy.nodes[node].status:
                    nodes["Exhausts"][node] = isy.nodes[node].status
                    update_server("Exhausts", node, isy.nodes[node].status)

            for node in nodes["Supplies"]:
                if nodes["Supplies"][node] != isy.nodes[node].status:
                    nodes["Supplies"][node] = isy.nodes[node].status
                    update_server("Supplies", node, isy.nodes[node].status)

            for node in nodes["Humidity Sensors"]:
                if nodes["Humidity Sensors"][node] != isy.nodes[node].aux_properties["CLIHUM"].value:
                    nodes["Humidity Sensors"][node] = isy.nodes[node].aux_properties["CLIHUM"].value
                    update_server("Humidity Sensors", node, isy.nodes[node].aux_properties["CLIHUM"].value)

            for node in nodes["Motion Sensors"]:
                if nodes["Motion Sensors"][node] != isy.nodes[node].status:
                    nodes["Motion Sensors"][node] = isy.nodes[node].status
                    update_server("Motion Sensors", node, isy.nodes[node].status)

    except asyncio.CancelledError:
        pass
    finally:
        if node_changed_subscriber:
            node_changed_subscriber.unsubscribe()
        if system_status_subscriber:
            system_status_subscriber.unsubscribe()
        await isy.shutdown()


def update_server(node_type, node, status, cfm=None):
    if cfm is None:
        requests.post("http://localhost:8080/post", json={
            "type": node_type,
            "node": node,
            "status": status
        })
    else:
        requests.post("http://localhost:8080/post", json={
            "type": node_type,
            "node": node,
            "status": status,
            "cfm": cfm
        })


if __name__ == "__main__":

    enable_logging(logging.WARNING)

    _LOGGER.info(
        "ISY URL: %s, username: %s",
        ADDRESS,
        USERNAME,
    )

    try:
        asyncio.run(
            main(
                url=ADDRESS,
                username=USERNAME,
                password=PASSWORD,
                tls_ver=1.1,
                events=True,
                node_servers=False,
            )
        )
    except KeyboardInterrupt:
        _LOGGER.warning("KeyboardInterrupt received. Disconnecting!")
