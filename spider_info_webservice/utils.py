from __future__ import annotations

import inspect
import re
from typing import TYPE_CHECKING, Iterable, Sequence

from scrapy.settings import BaseSettings, iter_default_settings
from scrapy.utils.conf import get_config
from scrapy.utils.reactor import listen_tcp
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.portal import IRealm, Portal
from twisted.web import guard, resource, server
from zope.interface import implementer

if TYPE_CHECKING:
    from typing import Any

    from twisted.internet.tcp import Port
    from twisted.web import resource

    from .resources import RootResource

try:
    import orjson # type: ignore 
except ImportError:
    import json

    def dumps_as_bytes(obj, **kwargs) -> bytes:
        if default := kwargs.pop("default", None):
            default = default
        else:
            default = str
        return json.dumps(obj, **kwargs, default=default).encode()
else:

    def dumps_as_bytes(obj, **kwargs) -> bytes:
        if default := kwargs.pop("default", None):
            default = default
        else:
            default = str
        return orjson.dumps(obj, **kwargs, default=default)


def build_single_regexp_for_keys(keys: list[str]) -> re.Pattern:
    return re.compile("|".join(f"({key})" for key in keys))


def hide_sensitive_data(data: dict[str, Any], regerxp: re.Pattern) -> None:
    """Mutates dict. Hide sensitive data in the data dictionary."""
    for key, value in data.items():
        if regerxp.match(key):
            data[key] = "******"
        if isinstance(value, dict):
            hide_sensitive_data(value, regerxp)


def get_project_name_from_config() -> str:
    config = dict(get_config())

    if settings := config.get("settings"):
        return settings.get("default", "").split(".")[0]

    if deploy := config.get("deploy"):
        return deploy.get("project", "")

    return "None. No project name found"


def create(
    users: dict[str, bytes], host, portrange, crawler, resources, resources_child_prefix
) -> tuple[resource.Resource, RootResource, Port]:
    from .resources import RootResource

    checkers = [InMemoryUsernamePasswordDatabaseDontUse(**users)]
    r = resource.Resource()
    root_resource = RootResource(crawler, resources, resources_child_prefix)
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


def convert_value(value):
    if isinstance(value, (BaseSettings, dict)):
        value = prepare_for_serialisation(value)
    elif isinstance(value, bytes):
        value = value.decode()
    elif inspect.isclass(value) and not isinstance(value, str):
        value = str(value)
    elif isinstance(value, (list, tuple, set)):
        value = [convert_value(v) for v in value]
    return value


def prepare_for_serialisation(dict_: BaseSettings | dict) -> dict[str, Any]:
    dictionary = {}
    for key, value in dict_.items():
        if isinstance(key, bytes):
            key = key.decode()

        value = convert_value(value)

        dictionary[key] = value
    return dictionary


def not_default_settings(settings: BaseSettings) -> Iterable[tuple[str, Any]]:
    """Return an iterable of the settings that have been overridden"""
    defset = dict(iter_default_settings())
    for name, value in settings.items():
        if name not in defset or defset[name] != value:
            yield name, value


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
