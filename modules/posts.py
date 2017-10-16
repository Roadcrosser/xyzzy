import json
import asyncio

async def post_carbon(xyzzy):
    if xyzzy.carbon_key:
        url = "https://www.carbonitex.net/discord/data/botdata.php"
        data = {
            "key": xyzzy.carbon_key,
            "servercount": len(xyzzy.guilds)
        }

        print("\nPosting to Carbonitex...")

        async with xyzzy.session.post(url, data=data) as r:
            text = await r.text()

        print("[{}] {}".format(r.status, text))

async def post_dbots(xyzzy):
    if xyzzy.dbots_key:
        url = "https://bots.discord.pw/api/bots/{}/stats".format(xyzzy.user.id)
        data = json.dumps({"server_count": len(xyzzy.guilds)})
        headers = {
            "Authorization": xyzzy.dbots_key,
            "content-type": "application/json"
        }

        print("\nPosting to DBots...")

        async with xyzzy.session.post(url, data=data, headers=headers) as r:
            text = await r.text()

        print("[{}] {}".format(r.status, text))

async def post_gist(xyzzy):
    if xyzzy.gist_key and xyzzy.gist_id:
        url = "https://api.github.com/gists/" + xyzzy.gist_id
        data = {
            "server_count": len(xyzzy.guilds),
            "session_count": sum(1 for i in xyzzy.channels.values() if not i.game.debug),
            "token": "MTcxMjg4MjM4NjU5NjAwMzg0.Bqwo2M.YJGwHHKzHqRcqCI2oGRl-tlRpn"
        }

        if xyzzy.gist_data_cache != data:
            xyzzy.gist_data_cache = data
            data = json.dumps({
                "files": {
                    "xyzzy_data.json": {
                        "content": json.dumps(data)
                    }
                }
            })
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": "token " + xyzzy.gist_key
            }

            print("\nPosting to GitHub...")

            async with xyzzy.session.patch(url, data=data, headers=headers) as r:
                print("[{}]".format(r.status))
        else:
            print("\nGitHub posting skipped.")

async def post_all(xyzzy):
    await post_carbon(xyzzy)
    await post_dbots(xyzzy)
    await post_gist(xyzzy)

def task_loop(xyzzy):
    async def loopy_doodle():
        while True:
            await post_all(xyzzy)
            await asyncio.sleep(3600)

    return xyzzy.loop.create_task(loopy_doodle())