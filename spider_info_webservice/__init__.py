from __future__ import annotations

__version__ = "0.0.2"

import logging
from typing import TYPE_CHECKING
import scrapy
import scrapy.signals
from scrapy.exceptions import NotConfigured
from scrapy.utils.defer import maybe_deferred_to_future

from .utils import get_child_resources, create_port, get_project_name_from_config

if TYPE_CHECKING:
    from scrapy.crawler import Crawler
    from twisted.web import resource
    from .resources import RootResource
    from twisted.internet.tcp import Port

logger = logging.getLogger(__name__)


class InfoService:
    def __init__(self, crawler: Crawler):
        crawler.signals.connect(self._start, signal=scrapy.signals.engine_started)
        crawler.signals.connect(
            self.default_start_callback, signal=scrapy.signals.engine_started
        )
        crawler.signals.connect(self._stop, signal=scrapy.signals.engine_stopped)
        crawler.signals.connect(
            self.default_stop_callback, signal=scrapy.signals.engine_stopped
        )

        self.portrange = crawler.settings.get("STATS_SERVER_PORTRANGE", (6024, 8000))
        self.host = crawler.settings.get("STATS_SERVER_HOST", "127.0.0.1")
        self.settings_sensetive_keys = crawler.settings.get(
            "INFO_SERVICE_SENSITIVE_KEYS",
            [r"^INFO_SERVICE_USERS$", r".*_PASS(?:WORD)?$", r".*_USER(?:NAME)?$"],
        )
        self.users = crawler.settings.get("INFO_SERVICE_USERS", {"scrapy": b"scrapy"})
        self.general_data = {}
        self.port: Port | None = None
        self.crawler: Crawler = crawler

    def _start(self):
        try:
            r: resource.Resource
            root_resource: RootResource
            r, root_resource, self.port = create_port(
                users=self.users,
                host=self.host,
                portrange=self.portrange,
                crawler=self.crawler,
                sensetive_keys=self.settings_sensetive_keys,
            )
            logger.info(
                f"Service started on {self.port.getHost().host}:{self.port.getHost().port}"
            )
        except OSError:
            raise NotConfigured(
                f"Failed to start service in portrange {self.portrange}"
            )

        import os
        from scrapy.utils.versions import scrapy_components_versions

        self.general_data.update(
            {
                "pid": os.getpid(),
                "project_name": get_project_name_from_config(),
                "bot_name": self.crawler.settings.get("BOT_NAME"),
                "spider_name": self.crawler.spider.name,
                "info_service_host": self.port.getHost().host,
                "info_service_port": self.port.getHost().port,
                "base_versions": {
                    "Scrapy": scrapy.__version__,
                    **{name: version for name, version in scrapy_components_versions()},
                },
                "available_resources": get_child_resources(r),
            }
        )
        root_resource.g_r.general_data = self.general_data

    async def _stop(self):
        await maybe_deferred_to_future(self.port.stopListening())

    @classmethod
    def from_crawler(cls, crawler: Crawler):
        ext = cls(crawler)
        return ext

    def default_start_callback(self):
        info_report_url = self.crawler.settings.get("INFO_REPORT_URL")
        if not info_report_url:
            return

        import urllib.request
        import json

        data = json.dumps(self.general_data).encode("utf-8")
        req = urllib.request.Request(
            info_report_url, data=data, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req)

    def default_stop_callback(self):
        pass
