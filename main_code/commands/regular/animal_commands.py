import asyncio
import json

import aiohttp
import async_timeout
import discord

from ... import command_decorator
from ... import helpers


@command_decorator.command("cat",
                           "Sends a cute cat. Powered by https://random.cat .")
async def cat_cmd(message: discord.Message, client: discord.Client, config: dict):
    """Pulls a url from the random.cat api at random.cat/meow, decodes it and then sends that picture in an embed."""

    try:
        # We create an aiohttp.Client, and fetch the json from the meow api
        with async_timeout.timeout(5):
            async with aiohttp.ClientSession(loop=client.loop) as session:
                async with session.get("http://random.cat/meow") as response:
                    cat_url_text = await response.text()
                    cat_url = json.loads(cat_url_text)["file"]
    except (asyncio.TimeoutError, json.JSONDecodeError, KeyError):
        # We didn't succeed with loading the url
        helpers.log_info("Wasn't able to load random.cat url.")
        await client.send_message(message.channel, "I wasn't able to load a cat url.")

        return

    # We create and send an embed with the url as a picture
    cat_embed = discord.Embed(title="Cat").set_image(url=cat_url)

    # We send the embed
    await client.send_message(message.channel, "Here's a cute cat!", embed=cat_embed)


@command_decorator.command("dog",
                           "Sends a cute dog. Powered by https://random.dog .")
async def dog_cmd(message: discord.Message, client: discord.Client, config: dict):
    """Pulls a url from the random.dog api at random.dog/woof.json, decodes it and then sends that picture in an embed."""

    try:
        # We create an aiohttp.Client, and fetch the json from the meow api
        with async_timeout.timeout(5):
            async with aiohttp.ClientSession(loop=client.loop) as session:
                async with session.get("http://random.dog/woof.json") as response:
                    dog_url_text = await response.text()
                    dog_url = json.loads(dog_url_text)["url"]
    except (asyncio.TimeoutError, json.JSONDecodeError, KeyError):
        # We didn't succeed with loading the url
        helpers.log_info("Wasn't able to load random.dog url.")
        await client.send_message(message.channel, "I wasn't able to load a dog url.")

        return

    # We create and send an embed with the url as a picture
    dog_embed = discord.Embed(title="Dog").set_image(url=dog_url)

    # We send the embed
    await client.send_message(message.channel, "Here's a cute dog!", embed=dog_embed)
