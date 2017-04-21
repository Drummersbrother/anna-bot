import aiohttp
import discord

import owapi_overwatch_api.overwatch_api_async as owapi
from ... import command_decorator
from ... import helpers

"""This file handles all searches for people in different games"""


@command_decorator.command("game search",
                           "Searches different games for the name given and returns matching accounts. Currently supports Overwatch.")
async def game_searchall_player(message: discord.Message, client: discord.Client, config: dict):
    """Searches all supported games for a player."""

    # The searchers for playernames of different games / platforms
    player_searchers = {"Overwatch": overwatch_player_search}

    # We parse the name that we should search for
    if message.channel.is_private:
        search_name = message.content.strip()[len("game search "):].strip()
    else:
        search_name = helpers.remove_anna_mention(client, message.content.strip())[len("game search "):].strip()

    # We check if the name is more than 4 chars or more
    if not 100 > len(search_name) > 3:
        # We tell the user that they need to supply a longer name
        await client.send_message(message.channel,
                                  message.author.mention + ", please give a name that's 4 or more characters long.")
        return

    # We tell the user that we're searching the games
    await client.send_message(message.channel, message.author.mention + ", searching for **{0}**.".format(
        helpers.remove_discord_formatting(search_name)[0]))

    # The results of the searchers
    results = {}

    # We give the search names to the supported searchers
    for platform, searcher in player_searchers.items():
        await client.send_message(message.channel, "Searching **{0}**...".format(platform))
        results[platform] = await searcher(search_name)
        await client.send_message(message.channel, "Done searching **{0}**...".format(platform))

    # We remove game entries that are empty
    results = {platform: result for platform, result in results.items() if
               result != {"PC": [], "XB": [], "PS": []}}

    # We create an embed for the results
    game_embed = discord.Embed(title="Gaming accounts called **{0}**".format(
        helpers.remove_discord_formatting(search_name)[0]), colour=discord.Colour.dark_grey())

    # We add an author field, looks good
    game_embed.set_author(name="Game search.".format(helpers.remove_discord_formatting(search_name)[0]))

    # We add fields for all the games
    for platform, result in results.items():
        # We add a field for the platform with different regions and platforms that the user has accounts for
        game_embed.add_field(name=platform, value="**{0}** exists on these region(s) and platform(s):\n\t".format(
            helpers.remove_discord_formatting(search_name)[0]) + ", ".join([
            *["PC-{0}".format(region).upper() for region in result["PC"]],
            *["XB1-{0}".format(region).upper() for region in result["XB"]],
            *["PS4-{0}".format(region).upper() for region in result["PS"]]
        ]))

    if results == {}:
        await client.send_message(message.channel,
                                  message.author.mention + ", I couldn't find any game accounts for **{0}**.".format(
                                      helpers.remove_discord_formatting(search_name)[0]))
        return

    # We send back the message with user info embed
    await client.send_message(message.channel, message.author.mention + ", here are the search results **{0}**".format(
        helpers.remove_discord_formatting(search_name)[0]), embed=game_embed)

    # We log it
    helpers.log_info("Sent game account info about {0} to {1} ({2}).".format(
        search_name, message.author.name, message.author.id))


async def overwatch_player_search(battletag: str):
    """Searches for a name with the overwatch api and returns a {"PC", "XB", "PS"} dict, 
    with some keys being None if there wasn't a player with that name"""
    ow_client = owapi.async_owapi_api(server_url="http://owapi.net")

    # Platforms we search on
    search_platforms = [owapi.PC, owapi.XBOX, owapi.PLAYSTATION]

    # The results we return
    result_dict = {"PC": [], "XB": [], "PS": []}

    # We log that we're searching with the overwatch api
    helpers.log_info("Searching with the overwatch api for battletag {0}.".format(battletag))
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
        for platform in search_platforms:
            # We search for the platform-region pair
            try:
                # The result from the OW API
                api_result = await ow_client.get_profile(battletag, session=session, platform=platform)
            except (owapi.RatelimitError, owapi.ProfileNotFoundError):
                # Error in the response (non-200 status code or other connection error)
                continue

            # We add the result (which we know is valid) to the result dict
            if platform == owapi.PC:
                result_dict["PC"].extend(api_result.keys())
            elif platform == owapi.XBOX:
                result_dict["XB"].extend(api_result.keys())
            elif platform == owapi.PLAYSTATION:
                result_dict["PS"].extend(api_result.keys())

    # We turn the empty lists into Nones
    return result_dict
