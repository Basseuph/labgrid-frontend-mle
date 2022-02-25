"""
Generic RPC functions for labby
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from attr import attrib, attrs

from .labby_error import LabbyError, failed, invalid_parameter, not_found
from .labby_types import Place, PlaceName, PowerState, Resource, ResourceName, SerLabbyError, TargetName, Session
from .labby_util import prepare_place

from autobahn.wamp.exception import ApplicationError


@attrs()
class RPCDesc():
    name: str = attrib()
    endpoint: str = attrib()
    remote_endpoint: str = attrib(default=None)
    info: Optional[str] = attrib(default=None)
    parameter: Optional[List[Tuple[str, str]]] = attrib(default=None)


FUNCTION_INFO = {
    "places": RPCDesc(name="places",
                      endpoint="localhost.places",
                      remote_endpoint="org.labgrid.coordinator.get_places",
                      info="""Takes optional string parameter to filter Places by.
Returns Dictionary of places with registered Resources.""",
                      parameter=[("places", "Place filter string")]),
    "resource": RPCDesc(name="resource",
                        endpoint="localhost.resource",
                        remote_endpoint="org.labgrid.coordinator.get_resources",),
    "power_state": RPCDesc(name="power_state",
                           endpoint="localhost.power_state",
                           )
}


async def fetch(context: Session, attribute: str, endpoint: str, *args, **kwargs) -> Any:
    """
    QoL function to fetch data drom Coordinator and store in attribute member in Session
    """
    assert context is not None
    assert attribute is not None
    assert endpoint is not None

    data: Optional[Dict] = context.__getattribute__(attribute)
    if context.__getattribute__(attribute) is None:
        data: Optional[Dict] = await context.call(endpoint, *args, **kwargs)
        context.__setattr__(attribute, data)
    return data


async def fetch_places(context: Session,
                       place: Optional[PlaceName]) -> Union[Dict, LabbyError]:
    """
    Fetch places from coordinator, update if missing and handle possible errors
    """
    assert context is not None
    data: Optional[Dict] = await fetch(context=context,
                                       attribute="places",
                                       endpoint="org.labgrid.coordinator.get_places")

    if data is None:
        if place is None:
            return not_found("Could not find any places.")
        return not_found(f"Could not find place with name {place}.")
    if place is not None and place not in data.keys():
        return not_found(f"Could not find place with name {place}.")

    return data


async def fetch_resources(context: Session,
                          place: Optional[PlaceName],
                          resource_key: Optional[ResourceName]) -> Union[Dict, LabbyError]:
    """
    Fetch resources from coordinator, update if missing and handle possible errors
    """
    assert context is not None
    data: Optional[Dict] = await fetch(context=context,
                                       attribute="resources",
                                       endpoint="org.labgrid.coordinator.get_resources")
    if data is None:
        if place is None:
            return not_found("Could not find any resources.")
        return not_found(f"No resources found for place {place}.")

    if resource_key is not None:
        ret = {
            place_name: {k: v for k, v in place_res if k == resource_key}
            for place_name, place_res in data.items()
        }

        if not ret:
            return not_found(f"Could not find any resources with key {resource_key}.")
        return ret
    return data


async def fetch_power_state(context: Session, place: Optional[PlaceName]) -> Union[PowerState, LabbyError]:
    """
    Use fetch resource to determine power state, this may update context.resource
    """

    data = await fetch_resources(context=context, place=place, resource_key=None)
    if isinstance(data, LabbyError):
        return data

    power_states = {}
    tmp = {}
    for place_name, resource_data in data.items():
        power = any(
            "avail" in resource_data.keys()
            for _, resource_data in resource_data.items()
        )

        power_states[place_name] = {"power_state": power}
    return power_states


@attrs()
class RPC():
    """
    Wrapper for remote procedure call functions
    """

    endpoint: str = attrib()
    func: Callable = attrib()

    def bind(self, context: Callable, *args, **kwargs):
        """
        Bind RPC to specific context,to be called by the frontend
        """

        return lambda *a, **kw: self.func(context(), *args, *a, **kwargs, **kw)


async def places(context: Session,
                 place: Optional[PlaceName] = None) -> Union[List[Place], SerLabbyError]:
    """
    returns registered places as dict of lists
    """
    context.log.info("Fetching places.")

    data = await fetch_places(context, place)
    if isinstance(data, LabbyError):
        return data.to_json()
    power_states = await fetch_power_state(context=context, place=place)
    if isinstance(power_states, LabbyError):
        return power_states.to_json()

    place_res = []
    for place_name, place_data in data.items():
        if place is not None and place_name != place:
            continue
        exporter = place_data["matches"][0]["exporter"] # ??? (Kevin) what if there are more than one or no matches
        assert exporter is not None
        place_res.append(
            prepare_place(place_data, place_name, exporter,
                          power_states[place_name]['power_state'])
        )
    return place_res


async def resource(context: Session,
                   # TODO (Kevin) REPRESENT TARGET IN API
                   place: Optional[PlaceName] = None,
                   ) -> Union[Resource, SerLabbyError]:
    """
    rpc: returns resources registered for given place
    """
    context.log.info(f"Fetching resources for {place}.")
    resource_data = await fetch_resources(context=context, place=place, resource_key=None)

    if isinstance(resource_data, LabbyError):
        return resource_data.to_json()

    if place is None:
        return resource_data
    if place not in resource_data.keys():
        return not_found(f"Place {place} not found.").to_json()
    return resource_data[place]


async def power_state(context: Session,
                      place: PlaceName,
                      ) -> Union[Resource, SerLabbyError]:
    """
    rpc: return power state for a given place
    """
    # TODO (Kevin) Cache resource updates and get powerstates from there
    if place is None:
        return invalid_parameter("Missing required parameter: place.").to_json()
    power_data = await fetch_power_state(context=context, place=place)

    if isinstance(power_data, LabbyError):
        return power_data.to_json()

    if place not in power_data.keys():
        return not_found(f"Place {place} not found on Coordinator.").to_json()

    return power_data[place]


async def resource_overview(context: Session,
                            place: Optional[PlaceName] = None,
                            ) -> Union[List[Resource], SerLabbyError]:
    """
    rpc: returns list of all resources on target
    """
    context.log.info(f"Fetching resources overview for {place}.")

    targets = await fetch_resources(context=context, place=place, resource_key=None)
    if isinstance(targets, LabbyError):
        return targets.to_json()

    ret = []
    for target, resources in targets.items():
        for res_place, res in resources.items():
            if place is None or place == res_place:
                ret.extend({'name': key, 'target': target,
                            'place': res_place, **values} for key, values in res.items())
    return ret


async def resource_by_name(context: Session,
                           name: ResourceName,  # filter by name
                           ) -> Union[List[Resource], SerLabbyError]:
    """
    rpc: returns list of all resources of given name on target
    """

    if name is None:
        return invalid_parameter("Missing required parameter: name.").to_json()

    resource_data = await fetch_resources(context, place=None, resource_key=None)
    if isinstance(resource_data, LabbyError):
        return resource_data.to_json()

    ret = []
    for target, resources in resource_data.items():
        for place, res in resources.items():
            ret.extend(
                {'name': key, 'target': target, 'place': place, **values}
                for key, values in res.items()
                if name == key
            )

    return ret


async def acquire(context: Session,
                  place: PlaceName) -> Union[Dict, SerLabbyError]:
    """
    rpc for acquiring places
    """
    if place is None:
        return invalid_parameter("Missing required parameter: place.").to_json()
    if place in context.acquired_places:
        return failed(f"Already acquired place {place}.").to_json()

    # , group, resource_key, place)
    context.log.info(f"Acquiring place {place}.")
    try:
        acquire_successful = await context.call("org.labgrid.coordinator.acquire_place", place)
    except ApplicationError as err:
        return failed(f"Got exception while trying to call org.labgrid.coordinator.acquire_place. {err}").to_json()
    if acquire_successful:
        context.acquired_places.append(place)
    return acquire_successful


async def release(context: Session,
                  place: PlaceName) -> Dict:
    """
    rpc for releasing 'acquired' places
    """
    if place is None:
        return invalid_parameter("Missing required parameter: place.").to_json()

    if place not in context.acquired_places:
        return failed(f"Place {place} is not acquired").to_json()
    context.log.info(f"Releasing place {place}.")
    try:
        release_successful = await context.call('org.labgrid.coordinator.release_place', place)
    except ApplicationError as err:
        return failed(f"Got exception while trying to call org.labgrid.coordinator.release_place. {err}").to_json()
    if release_successful:
        context.acquired_places.remove(place)
    return release_successful


async def info(_context=None, func_key: Optional[str] = None) -> Union[List[Dict], SerLabbyError]:
    """
    RPC call for general info for RPC function usage
    """
    if func_key is None:
        return [desc.__dict__ for desc in globals()["FUNCTION_INFO"].values()]
    if func_key not in globals()["FUNCTION_INFO"]:
        return not_found(f"Function {func_key} not found in registry.").to_json()
    return globals()["FUNCTION_INFO"][func_key].__dict__


async def reservations(context: Session) -> Dict:
    reservation_data = await context.call("org.labgrid.coordinator.get_reservations")
    # TODO (Kevin) handle errors
    return reservation_data


async def reset(context: Session, place: PlaceName) -> bool:
    """
    Send a reset request to a place matching a given place name
    Note 
    """
    return False


async def console(context: Session, *args):
    pass


async def video(context: Session, *args):
    pass


async def forward(context: Session, *args):
    return context.call(*args)


async def create_place(context: Session, place: PlaceName) -> bool:
    return False


async def delete_place(context: Session, place: PlaceName) -> bool:
    return False


async def create_resource(context: Session, place: PlaceName, resource: Resource) -> bool:
    return False


async def delete_resource(context: Session, place: PlaceName, resource: ResourceName) -> bool:
    return False
