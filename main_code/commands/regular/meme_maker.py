import asyncio
import json
from io import BytesIO

import Levenshtein
import aiohttp
import async_timeout
import discord

from ... import command_decorator
from ... import helpers


async def get_meme_list(passed_config: dict):
    """Returns the list of available images to use for meme generating. 
    Propagates asyncio.Timeouterror and json.JSONDecodeError if they're returned by the underlying Mashape api function."""
    return await helpers.mashape_json_api_request(passed_config,
                                                  endpoint="https://ronreiter-meme-generator.p.mashape.com/images",
                                                  return_json=True)


async def send_meme_in_channel(meme: str, top_text: str, bottom_text: str, msg_text: str, recipient: discord.Member,
                               passed_client: discord.Client, passed_channel: discord.Channel, passed_config: dict):
    """Sends a meme with the specified top and bottom texts to the specified channel and recipient, with the specified message."""

    # We try to fetch the meme
    try:
        helpers.log_info(
            "Loading meme \"{0}\", with top text \"{1}\", and bottom text \"{2}\" from the meme generator mashape api...".format(
                meme, top_text, bottom_text))

        # We get the image with the proper texts, and send it in the chat.
        meme_data, meme_resp = await helpers.mashape_json_api_request(passed_config,
                                                                      endpoint="https://ronreiter-meme-generator.p.mashape.com/meme",
                                                                      return_raw_response=True, return_data_aswell=True,
                                                                      params={"meme": meme, "top": top_text,
                                                                              "bottom": bottom_text})
        helpers.log_info("Done loading meme.")

    except asyncio.TimeoutError:
        await passed_client.send_message(passed_channel,
                                         "{0}I wasn't able to get the meme because of network timeout.".format(
                                             "" if passed_channel.is_private else recipient.mention + ", "))

        # We're done here
        return

    # We make sure the returned content type is not text/html, as that is the returned content type for an error msg
    if meme_resp.content_type.startswith("text/html"):
        # We failed to load the meme
        await passed_client.send_message(passed_channel,
                                         "{0}I wasn't able to load that meme with those parameters.".format(
                                             "" if passed_channel.is_private else recipient.mention + ", "))

        # We're done here
        return

    helpers.log_info("Sending meme to {0}.".format(helpers.log_ob(recipient)))

    # We download the meme into a BytesIO
    meme_data_io = BytesIO(meme_data)

    # We send the meme data
    await passed_client.send_file(passed_channel, fp=meme_data_io,
                                  filename="meme." + meme_resp.content_type[len("image/"):],
                                  content="{0}{2}\nThis is the *{1}* meme.".format(
                                      "" if passed_channel.is_private else recipient.mention + ", ", meme, msg_text))


@command_decorator.command("meme list", "Gives you a list of all the memes you can use.")
async def cmd_meme_list(message: discord.Message, client: discord.Client, config: dict):
    """Uses the mashape api here: https://market.mashape.com/ronreiter/meme-generator
    To return the list of available images to use for meme generating."""

    # We get the list
    try:
        helpers.log_info("Trying to load the meme image list from the meme generator mashape api...")
        meme_list = await get_meme_list(config)
        helpers.log_info("Successfully loaded the meme image list.")

    except (asyncio.TimeoutError, json.JSONDecodeError) as e:
        # We tell the issuing user that we weren't able to load the list
        await client.send_message(message.channel, "{0}I wasn't able to load the list because of an API error.".format(
            "" if message.channel.is_private else message.author.mention + ", "))
        return

    # We create a bytesio from the image list and send it as a file
    meme_list_io = BytesIO(bytearray(",\n".join(meme_list), encoding="utf-8"))

    # We send the file
    helpers.log_info("Sending the meme image list...")
    await client.send_file(message.channel, fp=meme_list_io, filename="memes.txt",
                           content="{0}Here are the memes!".format(
                               "" if message.channel.is_private else message.author.mention + ", "))


@command_decorator.command("meme search", "Shows the closest memes to a search request.")
async def cmd_meme_list(message: discord.Message, client: discord.Client, config: dict):
    """Uses the mashape api here: https://market.mashape.com/ronreiter/meme-generator
    To return the list of most closely matching memes"""

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

    # We parse the input
    if not message.channel.is_private:
        cleaned_raw_content = helpers.remove_anna_mention(client, message)[len("meme search "):].lower()
    else:
        cleaned_raw_content = message.content[len("meme search "):].lower()

    # The input has to be atleast 1 char
    if not (100 > len(cleaned_raw_content) > 1):
        await client.send_message(message.channel,
                                  "{0}You have to specify a search term longer than 1 character.".format(
                                      "" if message.channel.is_private else message.author.mention + ", "))
        return

    # We use levenshtein distance and match the 3 most closely matching images, and send them
    # basically, lowercase all memes, and make a list of the levenshtein distance between them and the query
    lower_case_memes = tuple(map(lambda s: s.lower(), meme_list))
    levenshtein_dists = tuple(zip(map(lambda s: Levenshtein.distance(cleaned_raw_content, s), lower_case_memes),
                                  range(len(lower_case_memes))))

    # We return the show_num memes with the lowest distance
    show_num = 3

    # We get the closest memes and send them all
    least_dists = sorted(levenshtein_dists, key=lambda d: d[0])[:show_num]

    # We loop through the dist, index, pairs in levenshtein dists, and send them
    for inx, dist in enumerate(least_dists):
        helpers.log_info("Sending meme search result {0} to {1}.".format(inx + 1, helpers.log_ob(message.author)))
        await send_meme_in_channel(meme_list[dist[1]], "", "", "This is search result **{0}**!".format(inx + 1),
                                   message.author, client, message.channel, config)
        helpers.log_info("Done sending meme search result.")


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

    # We send the meme
    await send_meme_in_channel(meme, top_text, bottom_text, "Here you go!", message.author, client, message.channel,
                               config)


@command_decorator.command("meme upload", "Uploads a new image to make available for the meme commands. "
                                          "Only image formats are supported. Filesize is limited to 6MB.")
async def cmd_upload_meme(message: discord.Message, client: discord.Client, config: dict):
    """Uses the mashape api here: https://market.mashape.com/ronreiter/meme-generator
    Uploads a meme to the meme api. Only image formats are supported. We also limit to 6MB."""

    # We check if the user attached a file to the issuing message
    if 10 > len(message.attachments) == 0 and (not max(map(lambda x: len(x.filename)), message.attachments) < 100):
        await client.send_message(message.channel,
                                  "{0}You need to provide an attachment to upload a meme. Only image formats are supported. Filesize is limited to 6MB.".format(
                                      "" if message.channel.is_private else message.author.mention + ", "))

        # We're done here
        return

    # We create a list of all the valid (image or video, I think...) attachments
    valid_attachments = []

    for attachment in message.attachments:
        if ("width" in attachment) and ("height" in attachment) and attachment["size"] < 6 * (2 ** 20):
            # It's a valid attachment
            valid_attachments.append(attachment)

            # We log
            helpers.log_info(
                "Got valid attachment with width {0}, height {1}, size {2} bytes, and filename {3} from {4}.".format(
                    attachment["width"], attachment["width"], attachment["size"], attachment["filename"],
                    helpers.log_ob(message.author)))
        else:
            # We send a message about an invalid file
            await client.send_message(message.channel,
                                      "{0}The file with name \"{1}\" wasn't valid for uploading as a meme.".format(
                                          "" if message.channel.is_private else message.author.mention + ", ",
                                          attachment["filename"]))
            await asyncio.sleep(0.5)

    # We check if the user attached a file to the issuing message
    if len(valid_attachments) == 0:
        await client.send_message(message.channel,
                                  "{0}All your provided attachments were invalid. Please try again with valid ones."
                                  "Only image formats are supported. Filesize is limited to 6MB."
                                  .format("" if message.channel.is_private else message.author.mention + ", "))

        # We're done here
        return

    # The string we send with info about how the meme uploading went
    uploaded_meme_info = "{0}Here are the memes I uploaded:\n".format(
        "" if message.channel.is_private else message.author.mention + ", ")

    # We loop through the valid attachments and upload them to the mashape api
    for attachment in valid_attachments:
        # We try to upload the attachment
        try:

            # We log
            helpers.log_info("Fetching from attachment and uploading to mashape meme api, attachment from {0}.".format(
                helpers.log_ob(message.author)))

            # We fetch the attachment into a BytesIO
            try:
                # Timeout the fetch
                with async_timeout.timeout(5):
                    async with aiohttp.ClientSession(loop=helpers.actual_client.loop) as session:
                        async with session.get(attachment["url"]) as response:
                            meme_img_data = BytesIO(await response.read())
            except asyncio.TimeoutError:
                # We didn't succeed with loading the url
                helpers.log_info("Wasn't able to load meme upload attachment url {0}.".format(attachment["url"]))
                raise

            helpers.log_info("Uploading attachment \"{1}\" from {0}...".format(helpers.log_ob(message.author),
                                                                               attachment["filename"]))

            # We upload the meme data to the mashape api
            uploaded_response = await helpers.mashape_json_api_request(config,
                                                                       endpoint="https://ronreiter-meme-generator.p.mashape.com/images",
                                                                       method="post",
                                                                       return_json=False, return_raw_response=True,
                                                                       data={"image": meme_img_data},
                                                                       chunked=(2 ** 10) * 16)

            helpers.log_info(
                "Uploaded attachment \"{1}\" from {0}.".format(helpers.log_ob(message.author), attachment["filename"]))

            # We check for a 200 response from the api, if not, the uploading failed
            if not uploaded_response.status == 200:
                print(repr(uploaded_response))
                raise asyncio.TimeoutError

            # We add the info about the uploaded attachment to the info string
            uploaded_meme_info += "Uploaded file `\"{0}\"` with width `{1}`, height `{2}` and size ~`{3}`KBs.\n\t".format(
                attachment["filename"], attachment["width"], attachment["height"], round(attachment["size"] / 1024, 2))

        except asyncio.TimeoutError:
            # We weren't able to upload the meme
            helpers.log_info(
                "I wasn't able to upload the meme attachment from {0}.".format(helpers.log_ob(message.author)))

            # We give some info in the upload info string
            uploaded_meme_info += "I wasn't able to upload the meme `\"{0}\"`, is that a valid image?\n\t".format(
                attachment["filename"])

    # We send the upload info to the user
    await helpers.send_long(client, uploaded_meme_info, message.channel)
