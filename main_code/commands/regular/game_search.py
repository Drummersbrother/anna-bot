import discord

from ... import command_decorator
from ... import helpers

from overwatch_api import *


"""This file handles all searches for people in different games"""

@command_decorator.command("game search", "Searches different games for the name given and returns matching accounts. Currently supports Overwatch.")
async def game_searchall_player(message: discord.Message, client: discord.Client, config: dict):
    """Searches all supported games for a player."""
    
    # We parse the name that we should search for
    search_name = helpers.remove_anna_mention(client, message.content.strip())[len("game search "):].strip()
    
    # We check if the name is more than 4 chars or more
    if not 100 > len(search_name) > 3:
        # We tell the user that they need to supply a longer name
        await client.send_message(message.channel, message.author.mention + ", please give a name that's 4 or more characters long.")
        return
    
    # We tell the user that we're searching the games
    await client.send_message(message.channel, message.author.mention + ", searching for **{0}**.".format(helpers.remove_discord_formatting(search_name)[0]))
    
    # The results of the searchers
    results = {}
    
    # We give the search names to the supported searchers
    for platform, searcher in player_searchers:
        results[platform] = searcher(search_name)
        
    # We remove game entries that are empty
    results = {platform: result for (platform, result) in results if result != {"PC": None, "XB": None, "PS": None}}}
    
    # We create an embed for the results
    game_embed = discord.Embed(title="Gaming accounts called **{0}**".format(
        helpers.remove_discord_formatting(search_name)[0]), colour=discord.Colour.dark_grey())

    # We add an author field, looks good
    game_embed.set_author(name="{0}.".format(helpers.remove_discord_formatting(search_name)[0]))

    # We add fields for all the games
    for platform, result in results:
        # We add a field for the platform with different regions and platforms that the user has accounts for
        game_embed.add_field(name=platform, value="**{0}** exists on these regions and platforms:\n".format(helpers.remove_discord_formatting(search_name)[0]) + ", ".join([
            *["PC-{0}".format(region) for region in result["PC"]],
            *["XB1-{0}".format(region) for region in result["XB"]],
            *["PS4-{0}".format(region) for region in result["PS"]]
            ]))
    
    # We send back the message with user info embed
    await client.send_message(message.channel, message.author.mention + ", here are the search results **{0}**".format(
        elpers.remove_discord_formatting(search_name)[0]), embed=game_embed)

    # We log it
    helpers.log_info("Sent game account info about {0} to {1} ({2}).".format(
        search_name, message.author.name, message.author.id))    

def overwatch_player_search(battletag: str):
    """Searches for a name with the overwatch api and returns a {"PC", "XB", "PS"} dict, 
    with some keys being None if there wasn't a player with that name"""

    ow_client = OverwatchAPI()
    
    # The result from the OW API
    api_result = ow_client.get_profile("pc", "global", battletag)
    
    # We parse the results and return in a well formed result dict
    cleaned_result_pc = [result_dict["region"] for result_dict in api_result["profile"] if result_dict["hasAccount"] and result_dict["platform"] == "pc"]
    cleaned_result_xb1 = [result_dict["region"] for result_dict in api_result["profile"] if result_dict["hasAccount"] and result_dict["platform"] == "xb1"]
    cleaned_result_ps4 = [result_dict["region"] for result_dict in api_result["profile"] if result_dict["hasAccount"] and result_dict["platform"] == "psn"]

    # We turn the empty lists into Nones
    return {"PC": cleaned_result_pc if cleaned_result_pc != [] else None, "XB": cleaned_result_xb1 if cleaned_result_xb1 != [] else None, "PS": cleaned_result_ps4 if cleaned_result_ps4 != [] else None}

# The searchers for playernames of different games / platforms
player_searchers = {"Overwatch": overwatch_player_search}
