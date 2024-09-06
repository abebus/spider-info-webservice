from __future__ import annotations

import json
from typing import TYPE_CHECKING

import scrapy.signals
from scrapy.core.scheduler import BaseScheduler
from scrapy.statscollectors import StatsCollector
from scrapy.utils.engine import get_engine_status
from scrapy.utils.test import TestSpider, get_crawler
from twisted.trial.unittest import TestCase
from twisted.web.client import Agent

from spider_info_webservice import InfoService
from spider_info_webservice.utils import not_default_settings, prepare_for_serialisation

if TYPE_CHECKING:
    from typing import Optional

class MockSlot:
    def __init__(self):
        from scrapy import Request

        self.inprogress = [
            Request(
                url="http://quotes.toscrape.com/page/2/",
                headers={
                    "Accept": [
                        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                    ],
                    "Accept-Language": ["en"],
                    "User-Agent": ["Scrapy/2.11.2 (+https://scrapy.org)"],
                },
                meta={
                    "download_timeout": 180,
                    "download_slot": "quotes.toscrape.com",
                    "download_latency": 0.4519026279449463,
                    "depth": 0,
                },
            ),
            Request(
                url="http://quotes.toscrape.com/page/1/",
                headers={
                    "Accept": [
                        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                    ],
                    "Accept-Language": ["en"],
                    "User-Agent": ["Scrapy/2.11.2 (+https://scrapy.org)"],
                },
                meta={
                    "download_timeout": 180,
                    "download_slot": "quotes.toscrape.com",
                    "download_latency": 0.4561948776245117,
                    "depth": 0,
                },
            ),
        ]


class MockStatsCollector(StatsCollector):
    def __init__(self, crawler):
        super().__init__(crawler)
        self.stats = {"stats": "test"}


class MockScheduler(BaseScheduler):
    def __init__(self):
        self.enqueued = []

    def enqueue_request(self, request) -> bool:
        self.enqueued.append(request)
        return True


class TestInfoService(TestCase):
    async def setUp(self) -> None:
        import logging
        logging.basicConfig(level=logging.DEBUG)
        spider = TestSpider()
        self.crawler = get_crawler(
            spider.__class__,
            {
                "INFO_SERVICE_USERS": {
                    "scrapy": b"scrapy",
                    "test": b"test",
                    "test2": b"test2",
                },
                "VERY_SENSETIVE_INFO": "test",
                "SENSETIVE_INFO_1": "test",
                "SENSETIVE_INFO_2": "test",
                "SENSETIVE_INFO_3": "test",
                "INFO_SERVICE_SENSITIVE_KEYS": [r"^.*SENSETIVE_INFO.*$"],
                "TELNETCONSOLE_ENABLED": False,
                "DOWNLOAD_HANDLERS_BASE": {},
                "DOWNLOADER_MIDDLEWARES_BASE": {},
                "EXTENSIONS_BASE": {},
                "SPIDER_CONTRACTS_BASE": {},
                "SPIDER_MIDDLEWARES_BASE": {},
                "FEED_EXPORTERS_BASE": {},
                "FEED_STORAGES_BASE": {}
            },
        )
        self.crawler.spider = spider
        self.crawler.stats = MockStatsCollector(self.crawler)
        self.scheduler = MockScheduler()
        engine = self.crawler._create_engine()
        engine.slot = MockSlot()
        self.ext = InfoService.from_crawler(self.crawler)
        self.crawler.engine = engine
        self.ext.crawler = self.crawler

        self.crawler.engine.start()
        await self.crawler.signals.send_catch_log_deferred(scrapy.signals.spider_opened)

    async def _req(self, to: str, user: bytes, passwd: bytes, params: Optional[dict] = None):
        from base64 import b64encode

        from twisted.internet import reactor
        from twisted.web.client import readBody
        from twisted.web.http_headers import Headers

        authorization = b64encode(user + b":" + passwd)
        url = f"http://{self.ext.host}:{self.ext.port.getHost().port}/info/{to}"
        if params:
            import urllib.parse

            url += "/?" + urllib.parse.urlencode(params)
        agent = Agent(reactor)
        resp = await agent.request(
            b"GET",
            url.encode(),
            Headers({b"authorization": [b"Basic " + authorization]}),
        )
        content = await readBody(resp)
        try:
            return json.loads(content.decode())
        except json.JSONDecodeError:
            return content

    async def tearDown(self) -> None:
        from twisted.internet import reactor

        if d := self.ext.port.stopListening():
            await d

        if self.crawler.engine.running:
            await self.crawler.engine.stop()
        await self.ext._stop()
        for call in reactor.getDelayedCalls():
            call.cancel()
        reactor.stop()

    async def test_default_callback(self):
        from twisted.internet import reactor
        from twisted.internet.endpoints import serverFromString
        from twisted.web.http import Request
        from twisted.web.resource import Resource
        from twisted.web.server import Site

        def render(req: Request):
            general = json.loads(req.content.read().decode())
            self.assertEqual(general, self.ext.general_data)
            return b"OK"

        r = Resource()
        r.putChild(b"test", r)
        r.render = render
        site = Site(r)
        site.isLeaf = True
        site.render = render
        endpoint = serverFromString(reactor, "tcp:0:interface=127.0.0.1")
        port = await endpoint.listen(site)
        self.addCleanup(port.stopListening)

        self.ext.info_report_url = f"http://127.0.0.1:{port.getHost().port}/test"
        import urllib.error

        try:
            await self.ext.default_start_callback()
        except (
            urllib.error.HTTPError,
            urllib.error.HTTPError,
            urllib.error.ContentTooShortError,
        ):
            self.fail()

    async def test_sensitive_keys(self):
        import re

        settings = await self._req("settings", b"scrapy", b"scrapy")
        for k, v in settings.items():
            if re.match(r"^.*SENSETIVE_INFO.*$", k):
                self.assertEqual(v, "******")
            else:
                self.assertNotEqual(v, "******")

    async def test_all_settings(self):
        import re

        settings = await self._req("settings", b"scrapy", b"scrapy", {"all": "true"})
        for k, v in prepare_for_serialisation(self.crawler.settings).items():
            if re.match(r"^.*SENSETIVE_INFO.*$", k):
                self.assertEqual(settings[k], "******")
            else:
                self.assertEqual(settings[k], v)

    async def test_not_default_settings(self):
        import re

        settings = await self._req("settings", b"scrapy", b"scrapy", {"all": "false"})
        for k, v in prepare_for_serialisation(
            dict(not_default_settings(self.crawler.settings))
        ).items():
            if re.match(r"^.*SENSETIVE_INFO.*$", k):
                self.assertEqual(settings[k], "******")
            else:
                self.assertEqual(settings[k], v)

    async def test_general_data(self):
        general = await self._req("general", b"scrapy", b"scrapy")
        self.assertEqual(general, self.ext.general_data)

    async def test_stats(self):
        stats_from_ext = await self._req("stats", b"scrapy", b"scrapy")
        stats = self.crawler.stats.get_stats()
        for k in stats:
            if "log_count" in k:
                stats[k] = 0
                stats_from_ext[k] = 0
        self.assertEqual(stats, stats_from_ext)

    async def test_slot(self):
        slot = await self._req("slot", b"scrapy", b"scrapy")
        self.assertEqual(
            slot,
            {
                "in_progress_requests": [
                    prepare_for_serialisation(elem.to_dict())
                    for elem in self.crawler.engine.slot.inprogress
                ]
            },
        )

    async def test_engine(self):
        engine_status_from_ext = await self._req("engine", b"scrapy", b"scrapy")
        engine_status = dict(get_engine_status(self.crawler.engine))
        engine_status.pop("time()-engine.start_time")  # it will be different anyway
        engine_status_from_ext.pop("time()-engine.start_time")
        self.assertEqual(engine_status_from_ext, engine_status)

    def test_start(self):
        self.assertIsNotNone(self.ext.port)

    async def test_stop(self):
        await self.ext._stop()
        assert self.ext.port.disconnected == 1
