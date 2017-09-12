import quetzal_parser as qzl
import asyncio
import aiohttp
from io import BytesIO

async def main():
    print("ok.")
    async with aiohttp.ClientSession() as s, s.get('https://cdn.discordapp.com/attachments/132632676225122304/357105968011542529/save-zork1.qzl') as r:
        res = await r.read()

    print('got em')

    a = qzl.parse_quetzal(BytesIO(res))

    print(a)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())