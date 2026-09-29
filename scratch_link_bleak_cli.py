"""Console entry point for the Scratch Link Bleak prototype."""
import asyncio
from scratch_link_bleak import main


def run():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
