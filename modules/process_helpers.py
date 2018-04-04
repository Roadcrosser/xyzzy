import asyncio

async def handle_process_output(process, looper, after):
    buffer = b""

    while process.returncode is None:
        try:
            output = await asyncio.wait_for(process.stdout.read(1), 0.5)
            buffer += output
        except asyncio.TimeoutError:
            await looper(buffer)

            buffer = b""

    last = await process.stdout.read()

    await after(last)