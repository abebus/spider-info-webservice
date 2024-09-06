from __future__ import annotations

import logging
import warnings
from typing import TYPE_CHECKING

import scrapy
import scrapy.signals
from scrapy.exceptions import NotConfigured
from scrapy.utils.defer import maybe_deferred_to_future

from .utils import create, get_child_resources, get_project_name_from_config

if TYPE_CHECKING:
    from typing import Any

    from scrapy.crawler import Crawler
    from twisted.internet.tcp import Port
    from twisted.web import resource

    from .resources import RootResource

logger = logging.getLogger(__name__)


class InfoService:
    def __init__(self, crawler: Crawler):
        crawler.signals.connect(self._start, signal=scrapy.signals.spider_opened)
        crawler.signals.connect(
            self.default_start_callback, signal=scrapy.signals.spider_opened
        )
        crawler.signals.connect(self._stop, signal=scrapy.signals.engine_stopped)
        crawler.signals.connect(
            self.default_stop_callback, signal=scrapy.signals.engine_stopped
        )

        portrange_deprecated = crawler.settings.get("STATS_SERVER_PORTRANGE")
        if portrange_deprecated:
            warnings.warn(
                "STATS_SERVER_PORTRANGE is deprecated in 0.0.3. Use INFO_SERVICE_PORTRANGE instead.",
                DeprecationWarning,
            )
        host_deprecated = crawler.settings.get("STATS_SERVER_HOST")
        if host_deprecated:
            warnings.warn(
                "STATS_SERVER_HOST is deprecated in 0.0.3. Use INFO_SERVICE_HOST instead.",
                DeprecationWarning,
            )

        self.portrange = portrange_deprecated or crawler.settings.get(
            "INFO_SERVICE_PORTRANGE", (6024, 8000)
        )
        self.host = host_deprecated or crawler.settings.get(
            "INFO_SERVICE_HOST", "127.0.0.1"
        )
        self.settings_sensetive_keys = crawler.settings.get(
            "INFO_SERVICE_SENSITIVE_KEYS",
            [r"^INFO_SERVICE_USERS$", r".*_PASS(?:WORD)?$", r".*_USER(?:NAME)?$"],
        )
        self.users = crawler.settings.get("INFO_SERVICE_USERS", {"scrapy": b"scrapy"})
        self.general_data = {}
        self.port: Port | None = None
        self.crawler: Crawler = crawler

        self.resources_child_prefix = self.crawler.settings.get(
            "INFO_SERVICE_RESOURCES_CHILD_PREFIX", "child_"
        )

        info_report_url_deprecated = self.crawler.settings.get("INFO_REPORT_URL")
        if info_report_url_deprecated:
            warnings.warn(
                "INFO_REPORT_URL is deprecated in 0.0.3. Use INFO_SERVICE_REPORT_URL instead.",
                DeprecationWarning,
            )
        self.info_report_url = info_report_url_deprecated or self.crawler.settings.get(
            "INFO_SERVICE_REPORT_URL",
        )
        self.resources: list[dict[str, Any]] | None = None

    def prep_resources(self):
        self.resources = self.crawler.settings.get(
            "INFO_SERVICE_RESOURCES",
            [
                {
                    "name": b"engine",
                    "class": "spider_info_webservice.resources.EngineStatusResource",
                    "args": [self.crawler.engine],
                },
                {
                    "name": b"slot",
                    "class": "spider_info_webservice.resources.SlotResource",
                    "args": [self.crawler.engine.slot],
                },
                {
                    "name": b"settings",
                    "class": "spider_info_webservice.resources.SettingsResource",
                    "args": [self.crawler.settings, self.settings_sensetive_keys],
                },
                {
                    "name": b"stats",
                    "class": "spider_info_webservice.resources.StatsResource",
                    "args": [self.crawler.stats],
                },
                {
                    "name": b"general",
                    "class": "spider_info_webservice.resources.GeneralDataResource",
                },
            ],
        )

    def _start(self):
        self.prep_resources()
        try:
            r: resource.Resource
            root_resource: RootResource
            r, root_resource, self.port = create(
                users=self.users,
                host=self.host,
                portrange=self.portrange,
                crawler=self.crawler,
                resources=self.resources,
                resources_child_prefix=self.resources_child_prefix,
            )
            logger.info(
                f"Service started on {self.port.getHost().host}:{self.port.getHost().port}"
            )
        except OSError:
            raise NotConfigured(
                f"Failed to start service in portrange {self.portrange}"
            )
        except Exception as e:
            raise NotConfigured(f"Failed to start service: {e}")

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
        getattr(
            root_resource, self.resources_child_prefix + "general"
        ).general_data = self.general_data

    async def _stop(self):
        if d := self.port.stopListening():
            await maybe_deferred_to_future(d)

    @classmethod
    def from_crawler(cls, crawler: Crawler):
        ext = cls(crawler)
        return ext

    async def default_start_callback(self):
        if not self.info_report_url:
            return

        def send_report():
            import json
            import urllib.request

            data = json.dumps(self.general_data).encode("utf-8")
            req = urllib.request.Request(
                self.info_report_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req)

        from twisted.internet.threads import deferToThread

        await maybe_deferred_to_future(deferToThread(send_report))

    def default_stop_callback(self):
        pass
