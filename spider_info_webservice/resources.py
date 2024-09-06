from __future__ import annotations

from typing import TYPE_CHECKING
from functools import wraps

from scrapy.settings import BaseSettings
from scrapy.utils.engine import get_engine_status
from scrapy.utils.misc import load_object
from twisted.web import resource

from .utils import (
    build_single_regexp_for_keys,
    convert_bytes_to_str_in_dict,
    dumps_as_bytes,
    hide_sensitive_data,
    not_default_settings,
    prepare_for_serialisation,
)

if TYPE_CHECKING:
    from typing import Any, Iterable

    from scrapy.core.engine import ExecutionEngine, Slot
    from scrapy.crawler import Crawler
    from scrapy.statscollectors import StatsCollector
    from twisted.web.http import Request


class Resource(resource.Resource):
    from . import logger


def add_debug_logging_to_render(f):
    from . import logger

    @wraps(f)
    def wrapper(self, request: Request):
        logger.debug(
            f"GET request received from {request.getClientIP()}: {request} with headers: {request.getAllHeaders()}"
        )
        res = f(self, request)
        logger.debug(f"Response: {res}")
        return res

    return wrapper

class SlotResource(Resource):
    """Slot resource, returns engine's slot.inprogress request.to_dict()"""

    isLeaf = True

    def __init__(self, slot: Slot):
        super().__init__()
        self.slot = slot

    @add_debug_logging_to_render
    def render_GET(self, request: Request) -> bytes:
        request.setHeader(b"Content-Type", b"application/json")
        response_data = {
            "in_progress_requests": [
                convert_bytes_to_str_in_dict(request.to_dict())
                for request in self.slot.inprogress
            ]
        }
        return dumps_as_bytes(
            response_data, default=lambda x: x.decode() if isinstance(x, bytes) else x
        )


class SettingsResource(Resource):
    """Settings resource, returns crawler.settings"""

    isLeaf = True

    def __init__(self, settings: BaseSettings, sensetive_keys: list[str]):
        super().__init__()
        self.settings = settings
        self.sensetive_keys = build_single_regexp_for_keys(sensetive_keys)

    @add_debug_logging_to_render
    def render_GET(self, request: Request) -> bytes:
        request.setHeader(b"Content-Type", b"application/json")
        if request.args.get(b"all", [b"false"])[0] == b"true":
            response_data = prepare_for_serialisation(self.settings)
        else:
            response_data = prepare_for_serialisation(
                dict(not_default_settings(self.settings))
            )
        hide_sensitive_data(response_data, self.sensetive_keys)
        return dumps_as_bytes(response_data)


class EngineStatusResource(Resource):
    """Engine status resource, returns get_engine_status(curr_engine) imported from scrapy.utils.engine"""

    isLeaf = True

    def __init__(self, engine: ExecutionEngine):
        super().__init__()
        self.engine = engine

    @add_debug_logging_to_render
    def render_GET(self, request: Request) -> bytes:
        request.setHeader(b"Content-Type", b"application/json")
        engine_status_report = get_engine_status(self.engine)
        response_data = {key: value for key, value in engine_status_report}
        return dumps_as_bytes(response_data)


class StatsResource(Resource):
    """Stats resource, returns crawler.stats.get_stats()"""

    isLeaf = True

    def __init__(self, stats: StatsCollector):
        super().__init__()
        self.stats = stats
    
    @add_debug_logging_to_render
    def render_GET(self, request: Request) -> bytes:
        request.setHeader(b"Content-Type", b"application/json")
        response_data = self.stats.get_stats()
        return dumps_as_bytes(response_data)


class GeneralDataResource(Resource):
    """General data resource, returns the general data of the crawler. (You are currently here)"""

    isLeaf = True
    general_data = {}

    
    @add_debug_logging_to_render
    def render_GET(self, request: Request) -> bytes:
        request.setHeader(b"Content-Type", b"application/json")
        response_data = self.general_data
        return dumps_as_bytes(response_data)


class RootResource(Resource):
    """Root resource, only used for the /info/ endpoint, no other uses"""

    def __init__(
        self, crawler: Crawler, childs: list = [dict], child_prefix: str = "child_"
    ):
        super().__init__()

        self.logger.debug(
            f"Creating RootResource for crawler {crawler} with childs: {childs}"
        )
        NOTSET = object()
        for child in childs:
            _class = load_object(child["class"])
            args = child.get("args", NOTSET)
            kwargs = child.get("kwargs", NOTSET)
            if args is NOTSET and kwargs is NOTSET:
                inst = _class()
            elif args is not NOTSET and kwargs is NOTSET:
                inst = _class(*child["args"])
            elif kwargs is not NOTSET and args is NOTSET:
                inst = _class(**child["kwargs"])
            elif kwargs is not NOTSET and args is not NOTSET:
                inst = _class(*child["args"], **child["kwargs"])
            else:
                self.logger.error("???")
                continue

            self.putChild(child["name"], inst)
            setattr(self, child_prefix + child["name"].decode(), inst)
