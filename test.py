import json
import requests


r = requests.get("https://raw.githubusercontent.com/donovanclay/isy/master/util.json")

data = r.json()

nodes = dict()

for fan in data["exhaust_fans"]:
    # print(data["exhaust_fans"][fan]["name"])
    nodes[data["exhaust_fans"][fan]["name"]] = 0

for fan in data["supplies"]:
    nodes[data["supplies"][fan]["name"]] = 0

for fan in data["honeywell_sens"]:
    nodes[fan["sens_hum"]] = 0
    nodes[fan["sens_motion"]] = 0


for node in nodes:
    print(node)
# print(nodes)

