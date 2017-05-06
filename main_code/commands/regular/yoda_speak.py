import asyncio
import urllib.parse

import discord

from ... import helpers


# TODO Check if this is going to work anytime soon in the future, it's down atm
# @command_decorator.command("yoda", "Infuses your text with midichlorians.")
async def yoda_speak(message: discord.Message, client: discord.Client, config: dict):
    """Uses the mashape api here: https://market.mashape.com/ismaelc/yoda-speak to convert the inputted text to yoda-speak."""

    # We get the input text
    if message.channel.is_private:
        query = message.content[len("yoda "):].strip()
    else:
        query = helpers.remove_anna_mention(client, message)[len("yoda "):].strip()

    # We try to get the results from the yoda api
    try:
        yodafied = await helpers.mashape_json_api_request(config, endpoint="https://yoda.p.mashape.com/yoda",
                                                          return_json=False, params={
                "sentence": urllib.parse.quote(query, safe="", errors="ignore")})
    except asyncio.TimeoutError as e:
        await client.send_message(message.channel, "{0}I wasn't able to infuse that with midichlorians.".format(
            (client.mention + ", ") if not message.channel.is_private else ""))
        return

    # We send back the yodafied text
    await client.send_message(message.channel, "{0}As Yoda himself would say: {1}".format(
        (client.mention + ", ") if not message.channel.is_private else "", yodafied))
