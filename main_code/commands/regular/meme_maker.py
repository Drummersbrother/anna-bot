import asyncio
import json
from io import BytesIO

import Levenshtein
import discord

from ... import command_decorator
from ... import helpers


async def get_meme_list(passed_config: dict):
    """Returns the list of available images to use for meme generating. 
    Propagates asyncio.Timeouterror and json.JSONDecodeError if they're returned by the underlying Mashape api function."""
    return await helpers.mashape_json_api_request(passed_config,
                                                  endpoint="https://ronreiter-meme-generator.p.mashape.com/images",
                                                  return_json=True)


@command_decorator.command("meme list", "Gives you a list of all the memes you can use.")
async def cmd_meme_list(message: discord.Message, client: discord.Client, config: dict):
    """Uses the mashape api here: https://market.mashape.com/ronreiter/meme-generator
    To return the list of available images to use for meme generating."""

    # We get the list
    try:
        helpers.log_info("Trying to load the meme image list from the meme generator mashape api...")
        meme_list = await get_meme_list()
        helpers.log_info("Successfully loaded the meme image list.")

    except (asyncio.TimeoutError, json.JSONDecodeError) as e:
        # We tell the issuing user that we weren't able to load the list
        await client.send_message(message.channel, "{0}I wasn't able to load the list because of an API error.".format(
            "" if message.channel.is_private else message.author.mention + ", "))
        return

    # We create a bytesio from the image list and send it as a file
    meme_list_io = BytesIO(bytearray("\n,".join(meme_list), encoding="utf-8"))

    # We send the file
    helpers.log_info("Sending the meme image list...")
    await client.send_file(message.channel, fp=meme_list_io, filename="memes.txt",
                           content="{0}Here are the memes!".format(
                               "" if message.channel.is_private else message.author.mention + ", "))


@command_decorator.command("meme make", "Creates a meme with the specified meme and bottom and top text. "
                                        "Use `meme make \"MEME_NAME\" \"TOP_TEXT\" \"BOTTOM_TEXT\"` "
                                        "to specify what image and texts you want. "
                                        "An example is `meme make \"Condescending Wonka\" \"AYLMAO\" \"M8\"`")
async def cmd_make_meme(message: discord.Message, client: discord.Client, config: dict):
    """Creates a meme with he specified image, bottom and top text.
    Memes are not case sensitive, as we do a levenshtein minimisation."""

    # We parse the input
    if not message.channel.is_private:
        cleaned_raw_content = helpers.remove_anna_mention(client, message)[len("meme make"):]
    else:
        cleaned_raw_content = message.content[len("meme make"):]

    # The content HAS TO BE in the format
    # "IMAGE" WHITESPACE "TOP" WHITESPACE "BOTTOM"
    # We do all validation in a try-except, so we can just exit once
    try:
        # We begin by stripping the content, and then we do various checks
        cleaned_raw_content = cleaned_raw_content.strip()

        # Assert it isn't empty
        assert len(cleaned_raw_content) > len(" " "" "")
        # Assert it isn't too long
        assert len(cleaned_raw_content) < 500

        # We split the content into 3 parts, one for everything enclosed in ""
        query_parameters = helpers.parse_quote_parameters(cleaned_raw_content, 3)

        # We assert that the image name isn't empty and isn't too long
        assert 150 > len(query_parameters[0]) > 1

    except AssertionError:
        # We got an invalid query
        await client.send_message(message.channel, "{0}I wasn't able to understand what kind of meme you wanted, "
                                                   "please check that you specified everything within quotes, had spaces between the fields, "
                                                   "and didn't leave the image empty".format(
            "" if message.channel.is_private else message.author.mention + ", "))

        # We're done here
        return

    # We get the list of memes
    try:
        helpers.log_info("Trying to load the meme image list from the meme generator mashape api...")
        meme_list = await get_meme_list(config)
        helpers.log_info("Successfully loaded the meme image list.")

    except (asyncio.TimeoutError, json.JSONDecodeError) as e:
        # We tell the issuing user that we weren't able to load the list
        await client.send_message(message.channel,
                                  "{0}I wasn't able to load the meme list because of an API error.".format(
                                      "" if message.channel.is_private else message.author.mention + ", "))
        return

    # We search the meme list for the meme we want to use
    if not query_parameters[0] in meme_list:
        # We do a levenshtein distance calculation on all the images to the query. Then we check that the distance is under a threshold, and then use the minimum distance meme
        query_parameters[0] = query_parameters[0].lower()

        # A list that is the index in the meme list that has the minimum levenshtein distance, and the distance it has
        min_dist_meme = [-1, 999]

        # We search for the minimum distance, this goes quite quickly, about 5us per meme, and max 20 ms for the whole list
        for inx, meme in enumerate([val.lower() for val in meme_list]):
            dist = Levenshtein.distance(query_parameters[0], meme)
            if dist < min_dist_meme[1]:
                min_dist_meme = [inx, dist]

        # We make sure the distance is not too big
        if min_dist_meme[1] > 10:
            await client.send_message(message.channel,
                                      "{0}I wasn't able to find a meme that's close enough to that name.".format(
                                          "" if message.channel.is_private else message.author.mention + ", "))

            # We're done here
            return

        query_parameters[0] = meme_list[min_dist_meme[0]]

    # The name of the meme the user selected
    meme = query_parameters[0]
    # The top text the user wants
    top_text = query_parameters[1]
    # The bottom text the user wants
    bottom_text = query_parameters[2]

    # We try to fetch the meme
    try:
        helpers.log_info(
            "Loading meme \"{0}\", with top text \"{1}\", and bottom text \"{2}\" from the meme generator mashape api...".format(
                meme, top_text, bottom_text))

        # We get the image with the proper texts, and send it in the chat.
        meme_data, meme_resp = await helpers.mashape_json_api_request(config,
                                                                      endpoint="https://ronreiter-meme-generator.p.mashape.com/meme",
                                                                      return_raw_response=True, return_data_aswell=True,
                                                                      params={"meme": meme, "top": top_text,
                                                                              "bottom": bottom_text})
        helpers.log_info("Done loading meme.")

    except asyncio.TimeoutError:
        await client.send_message(message.channel,
                                  "{0}I wasn't able to get the meme because of network timeout.".format(
                                      "" if message.channel.is_private else message.author.mention + ", "))

        # We're done here
        return

    # We make sure the returned content type is not text/html, as that is the returned content type for an error msg
    if meme_resp.content_type.startswith("text/html"):
        # We failed to load the meme
        await client.send_message(message.channel,
                                  "{0}I wasn't able to load that meme with those parameters.".format(
                                      "" if message.channel.is_private else message.author.mention + ", "))

        # We're done here
        return

    helpers.log_info("Sending meme to {0}.".format(helpers.log_ob(message.author)))

    # We download the meme into a BytesIO
    meme_data_io = BytesIO(meme_data)

    # We send the meme data
    await client.send_file(message.channel, fp=meme_data_io, filename="meme." + meme_resp.content_type[len("image/"):],
                           content="{0}Here you go!\nThis is the {1} meme.".format(
                               "" if message.channel.is_private else message.author.mention + ", ", meme))
