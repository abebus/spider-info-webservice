# spider-info-webservice

[![Tests](https://github.com/abebus/spider-info-webservice/actions/workflows/tests.yml/badge.svg)](https://github.com/abebus/spider-info-webservice/actions/workflows/tests.yml) [![Downloads](https://static.pepy.tech/badge/spider-info-webservice)](https://pepy.tech/project/spider-info-webservice)

Scrapy extension for monitoring your spiders. 

How to access it, if I have million spiders on one machine? Easy! This extension have `default_start_callback`, that sends request to your `INFO_SERVICE_REPORT_URL` with its own unique URL for each spider.

Inspired by Scrapy's built-in Telnet console extension and deprecated `scrapy-jsonrpc` (https://github.com/scrapy-plugins/scrapy-jsonrpc) and also presented in Scrapy 0.24 WebService built-in extension (https://docs.scrapy.org/en/0.24/topics/webservice.html).

Every time I used Telnet, it all came down to calling several methods to show information, so I made this extension, which conveniently serves basic information about spider via HTTP.

## Installation
```
pip install spider-info-webservice
```

or

```
pip install git+https://github.com/abebus/spider-info-webservice
```


### Dependencies

Scrapy >= 2.6

Python from 3.8 to 3.12

## Usage

Add `spider_info_webservice.InfoService` to EXTENSIONS in `settings.py` 

```python
EXTENSIONS = {
    "spider_info_webservice.InfoService": 500
}
```

All done! Now you can access to endpoints via your favourite cli http request tool or browser.

### Extension settings

`INFO_SERVICE_PORTRANGE`: defaults to `(6024, 8000)`.

`INFO_SERVICE_HOST`: defaults to `"127.0.0.1"`.

`INFO_SERVICE_USERS`: defaults to `{"scrapy": b"scrapy"}`. Dictionary of type `dict[str, bytes]` containing key-value pairs like `username: password`, used for basic HTTP auth.

`INFO_SERVICE_REPORT_URL`: optional. Extension will send a request to a given url with json containing general info about running spider and `host:port` of this service. 

`INFO_SERVICE_SENSITIVE_KEYS`: optional. Defaults to `[r"^INFO_SERVICE_USERS$", r".*_PASS(?:WORD)?$", r".*_USER(?:NAME)?$"]`. List of strings, that will compile to regex. They will try to match all keys in `settings` (recursively) and if key is matched, replace value with asterisks.

`INFO_SERVICE_RESOURCES_CHILD_PREFIX`: optional. Prefix for accesing child resources from extension.

`INFO_SERVICE_RESOURCES`: optional. List of resources dicts like: 
```python
{
  "name": b"name_of_resource",
  "class": "path.to.ResourseClass",
  "args": [args, that, resource, needs] # optional
  "kwargs": {"kwargs": for_resource} # optional
}
```
All resources are being initialised at `scrapy.signals.spider_opened` signal in `prep_resources` method. If you want to modify available resources, redefine this list at `settings.py`. For more control over `args` and `kwargs` that you could pass to resource, redefine this setting at `spider_opened` method in your `Spider` class or derive from this extension and override `prep_resources` method.


### Endpoints

`info/general`: General info.

Example response: 

```json
{
  "pid": 1605,
  "project_name": "quotes_scraper/name_from_scrapy.cfg",
  "bot_name": "quotes_scraper/name_from_settings",
  "spider_name": "quote-spider",
  "info_service_host": "127.0.0.1",
  "info_service_port": 6024,
  "base_versions": {
    "Scrapy": "2.11.2",
    "lxml": "5.2.2.0",
    "libxml2": "2.12.6",
    "cssselect": "1.2.0",
    "parsel": "1.9.1",
    "w3lib": "2.2.1",
    "Twisted": "24.3.0",
    "Python": "3.12.4 (main, Jun 12 2024, 19:06:53) [GCC 13.2.0]",
    "pyOpenSSL": "24.1.0 (OpenSSL 3.2.2 4 Jun 2024)",
    "cryptography": "42.0.8",
    "Platform": "Linux-5.15.153.1-microsoft-standard-WSL2-x86_64-with-glibc2.38"
  },
  "available_resources": [
    {
      "name": "/info",
      "doc": "Root resource, only used for the /info/ endpoint, no other uses",
      "methods": [
        "GET"
      ]
    },
    {
      "name": "/info/engine",
      "doc": "Engine status resource, returns get_engine_status(curr_engine) imported from scrapy.utils.engine",
      "methods": [
        "GET"
      ]
    },
    {
      "name": "/info/stats",
      "doc": "Stats resource, returns crawler.stats.get_stats()",
      "methods": [
        "GET"
      ]
    },
    {
      "name": "/info/settings",
      "doc": "Settings resource, returns crawler.settings",
      "methods": [
        "GET"
      ]
    },
    {
      "name": "/info/slot",
      "doc": "Slot resource, returns engine's slot.inprogress request.to_dict()",
      "methods": [
        "GET"
      ]
    },
    {
      "name": "/info/general",
      "doc": "General data resource, returns the general data of the crawler. (You are currently here)",
      "methods": [
        "GET"
      ]
    }
  ]
}
```

`info/stats`: Spider stats (`crawler.stats.get_stats()`).

Example response:
```json
{
  "log_count/WARNING": 1,
  "log_count/DEBUG": 6,
  "log_count/INFO": 16,
  "start_time": "2024-08-18T19:33:17.895850+00:00",
  "memusage/startup": 76251136,
  "memusage/max": 78032896,
  "scheduler/enqueued/memory": 2,
  "scheduler/enqueued": 2,
  "scheduler/dequeued/memory": 2,
  "scheduler/dequeued": 2,
  "downloader/request_count": 2,
  "downloader/request_method_count/GET": 2,
  "downloader/request_bytes": 474,
  "downloader/response_count": 2,
  "downloader/response_status_count/200": 2,
  "downloader/response_bytes": 5052,
  "httpcompression/response_bytes": 24789,
  "httpcompression/response_count": 2,
  "response_received_count": 2
}
```

`info/slot`: list of in-progress requests.

Example response:
```json
{
  "in_progress_requests": [
    {
      "url": "http://quotes.toscrape.com/page/2/",
      "callback": null,
      "errback": null,
      "headers": {
        "Accept": [
          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        ],
        "Accept-Language": [
          "en"
        ],
        "User-Agent": [
          "Scrapy/2.11.2 (+https://scrapy.org)"
        ],
        "Accept-Encoding": [
          "gzip, deflate, br, zstd"
        ]
      },
      "method": "GET",
      "body": "",
      "cookies": {},
      "meta": {
        "download_timeout": 180,
        "download_slot": "quotes.toscrape.com",
        "download_latency": 0.4519026279449463,
        "depth": 0
      },
      "encoding": "utf-8",
      "priority": 0,
      "dont_filter": true,
      "flags": [],
      "cb_kwargs": {}
    },
    {
      "url": "http://quotes.toscrape.com/page/1/",
      "callback": null,
      "errback": null,
      "headers": {
        "Accept": [
          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        ],
        "Accept-Language": [
          "en"
        ],
        "User-Agent": [
          "Scrapy/2.11.2 (+https://scrapy.org)"
        ],
        "Accept-Encoding": [
          "gzip, deflate, br, zstd"
        ]
      },
      "method": "GET",
      "body": "",
      "cookies": {},
      "meta": {
        "download_timeout": 180,
        "download_slot": "quotes.toscrape.com",
        "download_latency": 0.4561948776245117,
        "depth": 0
      },
      "encoding": "utf-8",
      "priority": 0,
      "dont_filter": true,
      "flags": [],
      "cb_kwargs": {}
    }
  ]
}
```

`info/engine`: Info about execution engine.

Example response:
```json
{
  "time()-engine.start_time": 423.9953444004059,
  "len(engine.downloader.active)": 0,
  "engine.scraper.is_idle()": false,
  "engine.spider.name": "quote-spider",
  "engine.spider_is_idle()": false,
  "engine.slot.closing": null,
  "len(engine.slot.inprogress)": 2,
  "len(engine.slot.scheduler.dqs or [])": 0,
  "len(engine.slot.scheduler.mqs)": 0,
  "len(engine.scraper.slot.queue)": 0,
  "len(engine.scraper.slot.active)": 2,
  "engine.scraper.slot.active_size": 24789,
  "engine.scraper.slot.itemproc_size": 0,
  "engine.scraper.slot.needs_backout()": false
}
```

`info/settings`: Spider settings. When passing `"all=true"` as param, will return all the existing settings, when passing `"all=false"`, will return only non-default settings.

Example response:
```json
{
    "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
    "TELNETCONSOLE_ENABLED": false,
    "INFO_SERVICE_USERS": {
        "scrapy": "scrapy",
        "test": "test",
        "test2": "test2"
    },
    "VERY_SENSETIVE_INFO": "******",
    "SENSETIVE_INFO_1": "******",
    "SENSETIVE_INFO_2": "******",
    "SENSETIVE_INFO_3": "******",
    "INFO_SERVICE_SENSITIVE_KEYS": [
        "^.*SENSETIVE_INFO.*$"
    ]
}
```

## Tests 

Yes.
