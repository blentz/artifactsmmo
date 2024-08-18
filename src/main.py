#!/usr/bin/env python3


from lib.log import safely_start_logger
from lib.controller import GameController

import asyncio
import logging

MAX_THREADS = 1

CHARACTER_NAME = "wakko"


async def task():
    logging.info("SimpleCharacterAI started")
    controller = GameController(character=CHARACTER_NAME)
    logging.info("SimpleCharacterAI finished")


# main coroutine
async def main():
    await safely_start_logger()
    logging.info("Execution starting...")

    async with asyncio.TaskGroup() as group:
        for i in range(MAX_THREADS):
            _ = group.create_task(task())

    # log a message
    logging.info("Execution complete.")


if "__main__" in __name__:
    # start the event loop
    asyncio.run(main())
