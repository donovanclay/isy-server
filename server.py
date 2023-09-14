import asyncio
from pprint import pprint

import socketio
from aiohttp import web
import json

sio = socketio.AsyncServer(cors_allowed_origins=["http://localhost:3000"])

routes = web.RouteTableDef()

app = web.Application()

sio.attach(app)

nodes = {
    "Exhausts": {},
    "Supplies": {},
    "Humidity Sensors": {},
    "Motion Sensors": {}
}


@sio.event
async def connect(sid, environ, auth):
    print('connection established with {}'.format(sid))
    await asyncio.sleep(1)
    # await send_nodes(sid)


@sio.event
def node_changed(sid, data):
    print(data)


@sio.event
def hello(sid, data):
    print("{} and {}".format(sid, data))


@sio.event
def disconnect(sid):
    print('disconnect ', sid)


@routes.get('/')
async def get_handler(request):
    print("get received")
    return web.Response(text=str(json.dumps(nodes, indent=4)))


@routes.post('/post')
# async def post_handler(request):
async def post_handler(request):
    print("post received")
    data = await request.json()
    if data["type"] == "Exhausts" or data["type"] == "Supplies":
        if "cfm" in data:
            nodes[data["type"]][data["node"]] = [data["status"], data["cfm"]]
        else:
            nodes[data["type"]][data["node"]][0] = data["status"]
    else:
        nodes[data["type"]][data["node"]] = data["status"]
    # if "cfm" in data:
    #     await sio.emit("node_changed", [data["type"], data["node"], data["status"], data["cfm"]])
    # else:
    #     await sio.emit("node_changed", [data["type"], data["node"], data["status"]])
    # await sio.emit("node_changed", [data["type"], data["node"], data["status"]])
    return web.Response(text="Hello, world")


app.add_routes(routes)


# app.router.add_post("/post", post_handler)

async def send_nodes(sid):
    print("sending all nodes because connection")
    for node_type in nodes:
        if node_type == "Exhausts" or node_type == "Supplies":
            for node in nodes[node_type]:
                await sio.emit("node_changed", [node_type, node, nodes[node_type][node], nodes[node_type][node][1]], sid)
        else:
            for node in nodes[node_type]:
                await sio.emit("node_changed", [node_type, node, nodes[node_type][node]], sid)


if __name__ == '__main__':
    web.run_app(app)