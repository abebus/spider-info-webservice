from __future__ import annotations

from typing import TYPE_CHECKING

from scrapy.utils.reactor import listen_tcp
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.portal import IRealm, Portal
from twisted.web import guard, resource, server
from zope.interface import implementer
from scrapy.settings import BaseSettings
from scrapy.utils.conf import get_config

if TYPE_CHECKING:
    from typing import Any

    from .resources import RootResource
    from twisted.internet.tcp import Port
    from twisted.web import resource

try:
    import orjson
except ImportError:
    import json

    def dumps_as_bytes(obj, **kwargs) -> bytes:
        return json.dumps(obj, **kwargs).encode()
else:

    def dumps_as_bytes(obj, **kwargs) -> bytes:
        return orjson.dumps(obj, **kwargs)

def get_project_name_from_config() -> str:
    config = dict(get_config())

    if settings := config.get("settings"):
        return settings.get("default", "").split(".")[0]
    
    if deploy := config.get("deploy"):
        return deploy.get("project", "")
    
    return "None. No project name found"

def create_port(
    users: dict[str, bytes], host, portrange, crawler
) -> tuple[resource.Resource, RootResource, Port]:
    from .resources import RootResource

    checkers = [InMemoryUsernamePasswordDatabaseDontUse(**users)]
    r = resource.Resource()
    root_resource = RootResource(crawler)
    r.putChild(b"info", root_resource)
    portal = Portal(SimpleRealm(r), checkers)
    r2 = guard.HTTPAuthSessionWrapper(portal, [guard.BasicCredentialFactory("auth")])

    return (
        r,
        root_resource,
        listen_tcp(
            portrange=portrange,
            host=host,
            factory=server.Site(r2),
        ),
    )


def settings_to_dict(settings: BaseSettings) -> dict[str, Any]:
    dictionary = {}
    for key, value in settings.items():
        if isinstance(key, bytes):
            key = key.decode()
        if isinstance(value, BaseSettings):
            value = settings_to_dict(value)
        elif isinstance(value, bytes):
            value = value.decode()
        dictionary[key] = value
    return dictionary


def convert_bytes_to_str_in_dict(dict_: dict):
    return {
        k.decode() if isinstance(k, bytes) else k: convert_bytes_to_str_in_dict(v)
        if isinstance(v, dict)
        else v
        for k, v in dict_.items()
    }


def get_child_resources(resource: resource.Resource, parent_name=""):
    children = []
    for child_name, r in resource.children.items():
        name = "/".join([parent_name, child_name.decode()])
        if not name.startswith("/"):
            name = "/" + name
        children.append({"name": name, "doc": r.__doc__, "methods": ["GET"]})
        children.extend(get_child_resources(r, child_name.decode()))
    return children


@implementer(IRealm)
class SimpleRealm:
    def __init__(self, resource: resource.Resource):
        self.resource = resource

    def requestAvatar(self, avatarId, mind, *interfaces):
        if resource.IResource in interfaces:
            return resource.IResource, self.resource, lambda: None
        raise NotImplementedError()
