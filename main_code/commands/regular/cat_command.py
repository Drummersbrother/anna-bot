import discord
import aiohttp
import async_timeout
import json

from ... import command_decorator
from ... import helpers

@command_decorator.command("cat",
                           "Sends a picture of a cute cat. Powered by https://random.cat .")
async def cat_cmd(message: discord.Message, client: discord.Client, config: dict):
    """Pulls a url from the random.cat api at random.cat/meow, decodes it and then sends that picture in an embed."""
    
    try:
        # We create an aiohttp.Client, and fetch the json from the meow api
        with async_timeout.timeout(5):
            async with aiohttp.ClientSession(loop=client.loop) as session:
                async with session.get("http://random.cat/meow") as response:
                    cat_url_text = await response.text()
                    cat_url = json.loads(cat_url_text)["file"]
    except (aiohttp.TimeoutError, json.JSONDecodeError, KeyError):
        # We didn't succeed with loading the url
        helpers.log_info("Wasn't able to load random.cat url.")
        await client.send_message(message.channel, "I wasn't able to load a cat url.")
        
        return
    
    # We create and send an embed with the url as a picture
    cat_embed = discord.Embed(title="Cat").set_image(url=cat_url)
    
    # We send the embed
    await client.send_message(message.channel, "Here's a cute cat!", embed=cat_embed)
    