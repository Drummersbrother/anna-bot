import asyncio
import json
from io import BytesIO

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
        await client.send_message(message.channel, "I wasn't able to load a cat.")
        
        return

    # We create and send an embed with the url as a picture
    await send_animal_embed(client, message.channel, cat_url, "Here's a cute cat!", "Cat")


@command_decorator.command("kitten", "Sends a cute kitten.")
async def kitten_cmd(message: discord.Message, client: discord.Client, config: dict):
    """Uses the mashape api here: https://market.mashape.com/nijikokun/kitten-placeholder to get a picture of a kitten"""

    # A function to get a kitten img url
    async def get_kitten_img_url():
        # We get the url
        try:
            return (await helpers.mashape_json_api_request(config,
                                                           endpoint="https://nijikokun-random-cats.p.mashape.com/random"))[
                "source"]
        except (asyncio.TimeoutError, json.JSONDecodeError, KeyError) as e:
            raise

    # A function to verify that a url has a kitten
    async def verify_kitten_url(url):
        # We try to verify that there is something at the end of the url
        with async_timeout.timeout(4):
            async with aiohttp.ClientSession(loop=client.loop) as session:
                async with session.get(url,
                                       headers={"accept": "image/x-png, image/gif, image/jpeg"}) as response:
                    # We make sure the url returns a 200
                    if response.status == 200:
                        return url

        # If we haven't returned by this point, we return None
        return

    # The list of tries we do
    url_coros = tuple([get_kitten_img_url() for _ in range(5)])
    # The list of verifies we do
    url_verify_coros = []

    # We use a for loop to get a url until the url is actually valid
    for result in await asyncio.gather(*url_coros, return_exceptions=True):
        if isinstance(result, str):
            url_verify_coros.append(verify_kitten_url(result))

    # We convert it into a tuple so we can gather it
    url_verify_coros = tuple(url_verify_coros)

    # We check the verified urls
    for result in await asyncio.gather(*url_verify_coros, return_exceptions=True):
        if isinstance(result, str):
            kitten_img_url = result
            break
    else:
        helpers.log_info("Was not able to load an image of a kitten for channel {0} ({1}).".format(
            message.channel.name, message.channel.id))

        # We tell the issuing user that we weren't able to get a picture
        await client.send_message(message.channel, "{0}I wasn't able to load a kitten image.".format(
            (client.mention + ", ") if not message.channel.is_private else ""))
        return

    helpers.log_info("Sending kitten image with url {0} to {1} ({2}).".format(kitten_img_url, message.author.name,
                                                                              message.author.id))

    # We create an embed and send it
    await send_animal_embed(client, message.channel, kitten_img_url, "Here's a cute kitten!", "Kitten")


@command_decorator.command("dog",
                           "Sends a cute dog. Powered by https://random.dog .")
async def dog_cmd(message: discord.Message, client: discord.Client, config: dict):
    """Pulls a url from the random.dog api at random.dog/woof.json, decodes it and then sends that picture in an embed."""

    helpers.log_info("Fetching dog url.")

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
        await client.send_message(message.channel, "I wasn't able to load a dog.")
        return

    helpers.log_info("Done fetching dog url, got {0}.".format(dog_url))

    # We check if we should handle gif or mp4
    if dog_url.endswith(".mp4") or dog_url.endswith(".gif"):
        # We download the mp4/file
        try:
            # We create an aiohttp.Client, and fetch the file
            with async_timeout.timeout(5):
                async with aiohttp.ClientSession(loop=client.loop) as session:
                    async with session.get(dog_url) as response:
                        helpers.log_info("Did not get picture dog, trying to load data instead.")
                        dog_file_data = await response.read()
                        dog_file_io = BytesIO(dog_file_data)
        except asyncio.TimeoutError:
            # We didn't succeed with loading the url
            helpers.log_info("Wasn't able to load random.dog file.")
            await client.send_message(message.channel, "I wasn't able to load a dog.")
            return

        # We send the file
        await client.send_file(message.channel, fp=dog_file_io, filename="doggo.{0}".format(dog_url[-3:]),
                               content="Here's a cute dog! (It's a doggo video 😉)")

        return

    # We create and send an embed with the url as a picture
    await send_animal_embed(client, message.channel, dog_url, "Here's a cute dog!", "Dog")


async def send_animal_embed(client: discord.Client, channel: discord.Channel, url: str, message: str, animal: str):
    """Sends a properly formatted embed to a channel, optimised for image urls for animal images."""

    helpers.log_info("Sent {0} image with url {1} to channel with id {2}.".format(animal, url, channel.id))

    # We create and send an embed with the url as a picture
    animal_embed = discord.Embed(title=animal).set_image(url=url)

    # We send the embed
    await client.send_message(channel, message, embed=animal_embed)
