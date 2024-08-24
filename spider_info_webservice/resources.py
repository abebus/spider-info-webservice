from __future__ import annotations

from typing import TYPE_CHECKING
from scrapy.settings import BaseSettings
from scrapy.utils.engine import get_engine_status
from twisted.web import resource

from .utils import (
    convert_bytes_to_str_in_dict,
    settings_to_dict,
    dumps_as_bytes,
    hide_sensitive_data,
    build_single_regexp_for_keys,
)

if TYPE_CHECKING:
    from scrapy.core.engine import ExecutionEngine, Slot
    from scrapy.crawler import Crawler
    from scrapy.statscollectors import StatsCollector
    from twisted.web.http import Request


class Resource(resource.Resource):
    from . import logger


class SlotResource(Resource):
    """Slot resource, returns engine's slot.inprogress request.to_dict()"""

    isLeaf = True

    def __init__(self, slot: Slot):
        super().__init__()
        self.slot = slot

    def render_GET(self, request: Request) -> bytes:
        self.logger.debug(f"GET request received: {request}")
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

    def render_GET(self, request: Request) -> bytes:
        request.setHeader(b"Content-Type", b"application/json")
        response_data = settings_to_dict(self.settings)
        hide_sensitive_data(response_data, self.sensetive_keys)
        return dumps_as_bytes(response_data, default=str)


class EngineStatusResource(Resource):
    """Engine status resource, returns get_engine_status(curr_engine) imported from scrapy.utils.engine"""

    isLeaf = True

    def __init__(self, engine: ExecutionEngine):
        super().__init__()
        self.engine = engine

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

    def render_GET(self, request: Request) -> bytes:
        request.setHeader(b"Content-Type", b"application/json")
        response_data = self.stats.get_stats()
        return dumps_as_bytes(response_data)


class GeneralDataResource(Resource):
    """General data resource, returns the general data of the crawler. (You are currently here)"""

    isLeaf = True
    general_data = {}

    def render_GET(self, request: Request) -> bytes:
        request.setHeader(b"Content-Type", b"application/json")
        return dumps_as_bytes(self.general_data)


class RootResource(Resource):
    """Root resource, only used for the /info/ endpoint, no other uses"""

    def __init__(self, crawler: Crawler, sensetive_keys: list[str] = []):
        super().__init__()

        self.putChild(b"engine", EngineStatusResource(crawler.engine))
        self.putChild(b"stats", StatsResource(crawler.stats))
        self.putChild(b"settings", SettingsResource(crawler.settings, sensetive_keys))
        self.putChild(b"slot", SlotResource(crawler.engine.slot))
        self.g_r = GeneralDataResource()
        self.putChild(b"general", self.g_r)
