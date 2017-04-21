import discord

import owapi_overwatch_api.overwatch_api_async as owapi
from ... import command_decorator
from ... import helpers


@command_decorator.command("overwatch", "Displays info about an overwatch battletag.")
async def game_searchall_player(message: discord.Message, client: discord.Client, config: dict):
    """We fetch and display info about one or multiple overwatch accounts."""

    # We parse the battletag to search for from the issuing message
    # We parse the name that we should search for
    if message.channel.is_private:
        search_name = message.content.strip()[len("overwatch "):].strip()
    else:
        search_name = helpers.remove_anna_mention(client, message.content.strip())[len("overwatch "):].strip()

    # We check if the name is more than 4 chars or more
    if not 100 > len(search_name) > 3:
        # We tell the user that they need to supply a longer name
        await client.send_message(message.channel,
                                  message.author.mention + ", please give a battletag that's 4 or more characters long.")
        return

    # We tell the user that we're searching the games
    await client.send_message(message.channel, message.author.mention + ", searching for **{0}**.".format(
        helpers.remove_discord_formatting(search_name)[0]))

    # We create an overwatch api client
    ow_client = owapi.async_owapi_api()

    # The dict to store the gathered profiles
    profiles = {}

    # We log that we're going to search
    helpers.log_info("Searching for {0} with the overwatch_api...".format(search_name))

    # We loop through the platforms and search on them
    for platform in (owapi.PC, owapi.XBOX, owapi.PLAYSTATION):
        try:
            profiles[platform] = await ow_client.get_profile(search_name, platform=platform)
        except (owapi.RatelimitError, owapi.ProfileNotFoundError):
            pass

        helpers.log_info("Done searching on platform {0}.".format(platform))

    # We log that we're going to search
    helpers.log_info("Done searching for {0} with the overwatch_api.".format(search_name))

    # We tell the user that we're done searching
    await client.send_message(message.channel,
                              "Done searching for **{0}**.".format(helpers.remove_discord_formatting(search_name)[0]))

    # We check that there are profiles with the matching tag
    if profiles == {owapi.PC: {}, owapi.XBOX: {}, owapi.PLAYSTATION: {}}:
        await client.send_message(message.channel,
                                  message.author.mention + ", I couldn't find any game accounts for **{0}**.".format(
                                      helpers.remove_discord_formatting(search_name)[0]))
        return

    # We create some data from the profiles
    profile_cleaned = {}
    for platform, regions in profiles.items():
        for region, val in regions.items():
            profile_cleaned[platform.upper() + "-" + region.upper() + " -> " + search_name] = val

    # The dict that stores the data
    # This data is top played heroes, rank and SR, top SR in current season,
    profile_data = {key: [] for key, val in profile_cleaned.items()}

    for acc, val in profile_cleaned.items():
        # We add stats for quickplat and competitive
        c_stats = val["stats"]["competitive"]
        profile_data[acc].append(("Competitive",
                                  "Wins: **{0}**\nLosses: **{1}**\nWin rate: **{2}%**\nLevel: **{3}**\nRank: **{4}**\nK/D ratio: **{5}**\nTime played: **{6} hours**".format(
                                      c_stats["overall_stats"]["wins"],
                                      c_stats["overall_stats"]["losses"],
                                      c_stats["overall_stats"]["win_rate"],
                                      c_stats["overall_stats"]["level"] + (100 * c_stats["overall_stats"]["prestige"]),
                                      c_stats["overall_stats"]["comprank"],
                                      c_stats["game_stats"]["kpd"],
                                      c_stats["game_stats"]["time_played"]
                                  )))
        q_stats = val["stats"]["quickplay"]
        profile_data[acc].append(("Quickplay",
                                  "Wins: **{0}**\nLosses: **{1}**\nWin rate: **{2}%**\nLevel: **{3}**\nRank: **{4}**\nK/D ratio: **{5}**\nTime played: **{6} hours**".format(
                                      q_stats["overall_stats"]["wins"],
                                      q_stats["overall_stats"].get("losses", "N/A"),
                                      q_stats["overall_stats"]["win_rate"],
                                      q_stats["overall_stats"]["level"] + (100 * q_stats["overall_stats"]["prestige"]),
                                      q_stats["overall_stats"]["comprank"],
                                      q_stats["game_stats"]["kpd"],
                                      q_stats["game_stats"]["time_played"]
                                  )))

        heroes = val["heroes"]["playtime"]
        c_heroes = [{hero: playtime} for hero, playtime in heroes["competitive"].items()]
        q_heroes = [{hero: playtime} for hero, playtime in heroes["quickplay"].items()]

        # We create a list of heroes and sort it by their playtime, largest last
        c_sorted_heroes_playtime = sorted(c_heroes, key=lambda h: heroes["competitive"][list(h.keys())[0]])
        q_sorted_heroes_playtime = sorted(q_heroes, key=lambda h: heroes["quickplay"][list(h.keys())[0]])

        # We add the top 3 played heroes to the info
        profile_data[acc].append(("Top Competitive Heroes", "**1**. \t*{2}\n**2**. \t*{1}\n**3**. \t*{0}".format(
            *[(list(hero_info.keys())[0][:1].upper() + list(hero_info.keys())[0][1:] + "*, *{0}* hours.".format(
                list(hero_info.values())[0])) for hero_info in c_sorted_heroes_playtime[-3:]]
        )))
        profile_data[acc].append(("Top Quickplay Heroes", "**1**. \t*{2}\n**2**. \t*{1}\n**3**. \t*{0}".format(
            *[(list(hero_info.keys())[0][:1].upper() + list(hero_info.keys())[0][1:] + "*, *{0}* hours.".format(
                list(hero_info.values())[0])) for hero_info in
              q_sorted_heroes_playtime[-3:]]
        )))

    # We create an embed with the data
    data_embed = discord.Embed(title="Overwatch Stats.", color=discord.Color(16293146)).set_thumbnail(
        url="http://i.imgur.com/YZ4w2ey.png")

    # We add fields for all the profile data
    for prof_name, prof in profile_data.items():
        for field in prof:
            data_embed.add_field(name=prof_name + " " + field[0] + ":", value=field[1])

    # We send the data embed
    await client.send_message(message.channel, message.author.mention + ", here is some info about **{0}**".format(
        helpers.remove_discord_formatting(search_name)[0]), embed=data_embed)
