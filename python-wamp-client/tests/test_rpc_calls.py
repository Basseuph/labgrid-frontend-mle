"""
Test all available remote procedure calls
"""
# TODO(Kevin) convert into unit test, requires launcher/launchoptions for router and must start RPC provider

import asyncio
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner
from random import choice
class Component(ApplicationSession):
    """
    Application component that calls procedures which
    produce complex results and showing how to access those.
    """

    def onConnect(self):
        self.log.info(
            f"Connected to Coordinator, joining realm '{self.config.realm}'")
        self.join(self.config.realm)

    async def onJoin(self, details):
        res = await self.call(u"wamp.registration.list")
        print(res)
        procs = []
        for proc in res['exact']:
            p = await self.call(u"wamp.registration.get", proc)
            print(p)
            procs.append(p)

        print("Polling places from router")
        res = await self.call(u"localhost.places")
        print(f"Received places: {res}")

        print("Polling power state for place")
        power_state = await self.call(u"localhost.power_state", choice(res)["name"])
        print(f"Received places: {power_state}")

        print("Polling specific place")
        res = await self.call(u"localhost.places", choice(res)["name"])
        print(f"Received places: {res}")

        place = res[0]['name']
        print(f"Polling resource from {place}")
        res = await self.call(u'localhost.resource', place)
        print(f"Received resources: {res}")

        print("Polling ALL resource")
        res = await self.call(u'localhost.resource')
        print(f"Received resources: {res}")

        temp = list(choice(list(res.values())).keys())
        name = choice(list(temp))
        print(f"Polling resource by name {name}")
        res = await self.call('localhost.resource_by_name', name)
        print(f"Received resources: {res}")

        print("Polling all resources by name")
        res = await self.call('localhost.resource_by_name')
        print(f"Received resources: {res}")

        place = choice(list(res.keys()))
        print(f"Polling resource overview by place {place}")
        res = await self.call('localhost.resource_overview', place)
        print(f"Received resources: {res}")

        print("Polling all resources by name")
        res = await self.call('localhost.resource_overview')
        print(f"Received resources: {res}")

        self.leave()


    def onDisconnect(self):
        asyncio.get_event_loop().stop()


if __name__ == '__main__':
    url = "ws://localhost:8083/ws"
    realm = "frontend"
    runner = ApplicationRunner(url, realm)
    runner.run(Component)
