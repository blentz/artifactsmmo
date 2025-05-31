#!/usr/bin/env python3
""" main entrypoint """

import asyncio
import logging
import os

from artifactsmmo_api_client.client import AuthenticatedClient, Client

from game.globals import BASEURL
from lib.httpstatus import extend_http_status
from lib.log import safely_start_logger
from lib.test import test_me

MAX_THREADS = 1
RAISE_ON_UNEXPECTED_STATUS = True

async def task():
    """ async task """
    logging.info("task started")
    token = os.environ.get("TOKEN")
    client = None
    if token:
        client = AuthenticatedClient(base_url=BASEURL, token=token,
                                     raise_on_unexpected_status=RAISE_ON_UNEXPECTED_STATUS)
    else:
        logging.warning("TOKEN not in ENV. Client NOT authenticated!")
        client = Client(base_url=BASEURL, raise_on_unexpected_status=RAISE_ON_UNEXPECTED_STATUS)
    test_me(client=client)
    logging.info("task finished")

async def main():
    """ main coroutine """
    await safely_start_logger()
    logging.info("Execution starting.")

    extend_http_status() # patch ArtifactsMMO custom codes into http.HTTPStatus

    async with asyncio.TaskGroup() as group:
        for _ in range(MAX_THREADS):
            _ = group.create_task(task())

    logging.info("Execution complete.")

if "__main__" in __name__:
    asyncio.run(main())
