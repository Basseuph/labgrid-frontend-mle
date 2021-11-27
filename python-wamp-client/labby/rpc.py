"""
Generic RPC functions for labby
"""

from typing import List, Dict, Union, Optional

import labby.labby_error as le


async def places(
        context) -> List[str]:
    """
    returns registered places as dict of lists
    """
    context.log.info("Fetching places.")
    targets = await context.call("org.labgrid.coordinator.get_places")
    # first level is target
    return list(targets.keys())


async def resource(context,
                   place: Optional[str] = None,
                   # TODO (Kevin) REPRESENT TARGET IN API
                   target: Union[str, int, None] = None,
                   ) -> Dict:
    """
    rpc: returns resources registered for given place
    """
    context.log.info(f"Fetching resources for {target}.{place}.")
    targets = await context.call("org.labgrid.coordinator.get_resources")

    def resource_for_place():
        if place is None:
            return {"resources": targets[target]}
        else:
            if not place in targets[target].keys():
                return le.not_found(f"Place {place} not found on Target").to_json()
            return {"resources": targets[target][place]}

    if isinstance(target, str):
        if not target in targets:
            err_str = f"Target {target} not found on Coordinator"
            context.log.warn(err_str)
            return le.not_found(err_str).to_json()
        return resource_for_place()

    elif isinstance(target, int):
        if target >= len(targets):
            err_str = f"Target {target} not found on Coordinator"
            context.log.warn(err_str)
            return le.not_found(err_str).to_json()
        return resource_for_place()

    return {"resources": targets}
