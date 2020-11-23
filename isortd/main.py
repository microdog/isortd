import base64
import logging
from concurrent import futures
from typing import Mapping

import aiohttp_cors
import click
from aiohttp import web
from isort import api, settings
from isort.exceptions import ISortError, ProfileDoesNotExist

from isortd import __version__ as ver


@click.command(context_settings={"help_option_names": ["-h --help"]})
@click.option("--host", type=str, help="App host", default="localhost")
@click.option("--port", type=int, help="App port", default=47393)
def main(host, port):
    logging.basicConfig(level=logging.INFO)
    with futures.ProcessPoolExecutor() as executor:
        app = factory(executor)
        app.logger.info(f"isortd version {ver} istening on {host} port {port}")
        web.run_app(app, host=host, port=port, handle_signals=True) or 0
    return 0


def factory(executor: futures.ProcessPoolExecutor) -> web.Application:
    app = web.Application()
    cors = aiohttp_cors.setup(app)
    handler = Handler(executor)
    sort_resource = cors.add(app.router.add_resource("/"))
    cors.add(
        sort_resource.add_route("POST", handler.handle),
        {
            "*": aiohttp_cors.ResourceOptions(
                expose_headers="*", allow_headers=("Content-Type", "X-*")
            ),
        },
    )

    ping_resource = cors.add(app.router.add_resource("/ping"))
    cors.add(
        ping_resource.add_route("GET", pong),
        {
            "*": aiohttp_cors.ResourceOptions(
                allow_methods=["GET"],
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            ),
        },
    )
    return app


async def pong(*_):
    return web.Response(text=f"pong", status=200)


class Handler:
    def __init__(self, executor: futures.ProcessPoolExecutor):
        self.executor = executor

    async def handle(self, request: web.Request):
        in_ = await request.text()
        try:
            config = self._parse(request.headers)
        except ISortError as e:
            return web.Response(f"Failed to parse config: {e}", status=400)
        out = api.sort_code_string(in_, config=config)
        if out:
            return web.Response(
                text=out, content_type=request.content_type, charset=request.charset
            )
        return web.Response(status=201)

    def _parse(self, headers: Mapping) -> settings.Config:
        parsed_kv = {
            key.lower().replace("x-", ""): value
            for key, value in headers.items()
            if key.startswith("X-")
        }
        cfg = settings.Config(**parsed_kv)
        return cfg
