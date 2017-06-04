import asyncio
import json
import os
import sys
import traceback
from collections import namedtuple

import aiohttp
import async_timeout
import discord

from ... import command_decorator
from ... import helpers

# A pokemon object, values will be "N/A" if no data was available
PoGoPokemon = namedtuple("PoGoPokemon", ("lat", "lng", "pkdex_id", "iv", "name", "cp", "lvl", "tl"))

# The most recent results from the PoGo api, an empty set
last_pokemons = set()

# The config dictionary that we get passed, this needs to be file-wide, since we have a background task that needs an updated config
bg_config = {}

# The config for which channels have what subscriptions to notifications
poke_config = {}


def store_persistent_poke_config():
    """Uses the json module to store the data in poke_config to disk,
    so we can recover voice state upon reboot of the bot."""
    global poke_config

    # We open and close the state file, and we use some tricks to get the filepath since it is above this file
    try:
        with open(os.path.join(os.path.dirname(__file__), "..", "..", "..", "persistent_state", "pokemon_state.json"),
                  mode="w") as poke_state_file:

            # The data we're going to store
            saved_data = {"pokemons": list(last_pokemons), "poke_config": poke_config}

            # We dump the persistent data to disk via json
            json.dump(saved_data, poke_state_file)

    except BaseException as e:
        print(traceback.format_exception(*sys.exc_info()))


def use_persistent_poke_dict(func):
    """This is meant to be used as a decorator to all functions
    that modify the last_pokemons or poke_config variables.
    It saves the state into a json file (/persistent_state/pokemon_state.json from the top of the bot)"""

    def decorated_func(*args, **kwargs):
        # We execute the function
        result = func(*args, **kwargs)

        # We store the persistent state to disk
        store_persistent_poke_config()

        return result

    # We return the decorated version of the function
    return decorated_func


def async_use_persistent_poke_dict(func):
    """This is meant to be used as a decorator to all functions
    that modify the last_pokemons or poke_config variables. This is for async functions.
    It saves the state of the dict into a json file (/persistent_state/pokemon_state.json from the top of the bot)"""

    async def decorated_func(*args, **kwargs):
        # We execute the function
        result = await func(*args, **kwargs)

        # We store the persistent state to disk
        store_persistent_poke_config()

        return result

    # We return the decorated version of the function
    return decorated_func


async def get_pokemon_data(timeout_seconds: int = 5):
    """Returns the union of all the sets of pokemon that the different apis discover. Returns all IVs."""
    barre = await get_pokemon_barrenechea_data(timeout_seconds)
    anime_hero = await get_anime_hero_data(timeout_seconds)
    return barre.union(anime_hero)


async def get_pokemon_barrenechea_data(timeout_seconds: int = 5):
    """Gets PoGo data from https://pogo.barrenechea.cl/0, which is data for all IVs. Raises asyncio.TimeoutError if the getting took more seconds than timeout_seconds.
    Raises ValueError if the data wasn't valid. Returns the split data as a set of PoGoPokemon Instances (namedtuples)."""
    # The url we get info from
    info_url = "https://pogo.barrenechea.cl/0"

    # The chars we split on
    split_on = ["\n", "\\n", ","]

    # We get the data
    try:
        # We use a timeout
        with async_timeout.timeout(timeout_seconds):
            async with aiohttp.ClientSession() as session:
                async with session.get(info_url) as response:
                    # We verify that everything went well
                    if response.status is not 200:
                        response_raw = ""
                    else:
                        # The text
                        response_raw = await response.text()

    except asyncio.TimeoutError as e:
        # We log
        helpers.log_info("Getting pokemon info from barrenechea failed, got timeout error.")
        return set()

    # We clean the data from the heading message, note that the emoji switches on loads
    head_message = "PayPal & BTC: http://bit.ly/donatepogo\n"
    head_message_index = response_raw.find(head_message)

    response_raw = response_raw[(head_message_index + len(head_message)):]

    # We split the data
    response_raw_split = response_raw
    for splitter in split_on[:-1]:
        response_raw_split = response_raw_split.replace(splitter, split_on[-1])
    split_response = response_raw_split.split(split_on[-1])

    # We create a list of the parts of the split data for each pokemon
    chunked_response = [split_response[i:i + 4] for i in range(0, len(split_response), 4)]

    if response_raw == "":
        return set()
    else:
        # We create the pokemon object list and return it
        pokemons = {PoGoPokemon(chunk[0].strip(), chunk[1].strip(), "N/A", chunk[3].strip()[len(" IV: "):-1].strip(),
                                chunk[2].strip(), *(["N/A"] * 3)) for chunk in
                    chunked_response if len(chunk) == 4}
        return pokemons


async def get_anime_hero_data(timeout_seconds: int = 5):
    """Gets PoGo data from http://animehero.io/coords/0-0, which is data for all IVs. Raises asyncio.TimeoutError if the getting took more seconds than timeout_seconds.
    Raises ValueError if the data wasn't valid. Returns the split data as a set of PoGoPokemon Instances (namedtuples)."""

    # The url we get info from
    info_url = "http://animehero.io/coords/0-0"

    # The chars we split on
    split_on = ["\n", " ", ","]

    # We get the data
    try:
        # We use a timeout
        with async_timeout.timeout(timeout_seconds):
            async with aiohttp.ClientSession() as session:
                async with session.get(info_url) as response:
                    # We verify that everything went well
                    if response.status is not 200:
                        return set()
                    else:
                        # The text
                        response_raw = await response.text()

    except asyncio.TimeoutError as e:
        # We log
        helpers.log_info("Getting pokemon info from animehero failed, got timeout error.")
        return set()

    # We split the data
    response_raw_split = response_raw
    for splitter in split_on[:-1]:
        response_raw_split = response_raw_split.replace(splitter, split_on[-1])
    split_response = response_raw_split.split(split_on[-1])
    split_response = [part.replace("\n", "") for part in split_response]
    split_response = [part for part in split_response if part != ""]

    # We chunk the response
    chunked_response = [[]]
    for part in split_response:
        if part == "IV100":
            continue
        if part[0] == "(" and part[-1] == ")":
            continue
        if len(chunked_response[-1]) < 8:
            chunked_response[-1].append(part)
        else:
            if part == "-CP:":
                chunked_response[-1].append(part)
            elif chunked_response[-1][-1] == "-CP:":
                chunked_response[-1].append(part)
            else:
                chunked_response.append([part])

    # We create the pokemon objects
    pokemons = []
    for chunk in chunked_response:
        if len(chunk) > 0:
            processed_chunk = [part for part in chunk if part not in ("-IV:", "IV100", "-TL:", "-CP:")]
            # We check if there is a CP value
            if len(processed_chunk) == 6:
                # There isn't one
                pokemons.append(PoGoPokemon(*processed_chunk[:2], "N/A", processed_chunk[4], processed_chunk[3], "N/A",
                                            processed_chunk[2], processed_chunk[5]))
            elif len(processed_chunk) == 7:
                # There is one
                pokemons.append(
                    PoGoPokemon(*processed_chunk[:2], "N/A", processed_chunk[4], processed_chunk[3], processed_chunk[6],
                                processed_chunk[2], processed_chunk[5]))

    return set(pokemons)


async def notification_handler_loop(passed_config: dict):
    """A background task for checking for new pokemon go pokemons, and delivering notifications about them to configured servers."""

    global last_pokemons, bg_config, poke_config

    # We update the background config
    bg_config = passed_config

    # We run this forever, but it works since async sleep is async
    while True:
        # We need the proper loop and being logged in properly
        await helpers.actual_client.wait_until_ready()

        # We do a notifications handling
        try:
            await handle_notifications()
        except:
            print(traceback.format_exc())

        # We wait until the time we should be called
        await asyncio.sleep(30)


@async_use_persistent_poke_dict
async def handle_notifications():
    """Does a singe polling and handling of pokemon go notifications."""

    global last_pokemons, bg_config, poke_config

    # We get data from the apis
    try:
        pokemons = await get_pokemon_data()
    except asyncio.TimeoutError:
        # We safely ignore this
        return
    except Exception as e:
        # Broad exception clause, since we don't get debug info if we don't have manual logging
        e_type, e, e_traceback = sys.exc_info()

        helpers.log_warning("Got unknown error when trying to load pokemon data. Info:\n{0}".format("".join(
            ["    " + entry for entry in traceback.format_exception(e_type, e, e_traceback)])))
        return

    try:
        # If the data is not identical to the old data, we update the last_pokemons, and handle notifications
        if pokemons.difference(last_pokemons) != set():

            # We check if there are new pokemon's or if there are just fewer pokemon
            if pokemons - last_pokemons != set():
                # Our client
                client = helpers.actual_client

                # The pokemons we need to create notifications for
                notif_pokemons = pokemons - last_pokemons

                # We create a dict of IVs to filter for, into lists of embeds to send to the corresponding channel,
                # note that the worst case for this is the naive per-channel filter implementations,
                # and the best case is O(n) where n is len(notif_pokemons)

                # We create a set of the different filters for the subscribing channels
                filters = []
                for val in poke_config.values():
                    if val not in filters:
                        filters.append(val)

                # The dict of msg lists
                msg_filter_lookup = {}

                # We create all the lists
                for filter_info in filters:

                    # We filter the pokemon
                    filtered_pokemons = [pokemon for pokemon in notif_pokemons if filter_pokemon(pokemon, filter_info)]

                    # The list of msgs for this iv filter
                    notif_msgs = []

                    # We add msgs for each pokemon
                    for pokemon in filtered_pokemons:
                        # The string for the field for the pokemon
                        poke_msg = "**{3}**, Lat: **{0}**, Long: **{1}**, IV: **{2}%**".format(
                            round(get_float(pokemon.lat, 0), 5), round(get_float(pokemon.lng, 0), 5),
                            (get_int(pokemon.iv, 0)), pokemon.name)

                        # If there is a CP or TL value, we add them
                        if pokemon.cp != "N/A":
                            poke_msg += ", CP: **{0}**".format(pokemon.cp)
                        if pokemon.tl != "N/A":
                            poke_msg += ", Time left: **{0}**".format(pokemon.tl)

                        notif_msgs.append(poke_msg)

                    # We add the list to the dict
                    for channel, info in poke_config.items():
                        if info == filter_info:
                            msg_filter_lookup[channel] = notif_msgs

                # We loop through the different channels that use notifications
                for channel_id, info in poke_config.items():

                    # We try to get the channel, if not possible, we remove it from the config
                    channel = client.get_channel(channel_id)

                    if channel is None:
                        # We remove the key
                        del poke_config[channel_id]
                        continue

                    # We have the channel, so we get the list of messages to send, and send them
                    send_msgs = msg_filter_lookup[channel_id]

                    # If the list is empty, we don't send anything for this channel
                    if len(send_msgs) == 0:
                        continue

                    helpers.log_info(
                        "Sending pokemon notifications to channel {0} on server {1}.".format(helpers.log_ob(channel),
                                                                                             helpers.log_ob(
                                                                                                 channel.server)))

                    # We send the messages
                    await helpers.send_long(client, send_msgs, channel)

        # We update the last_pokemon data
        last_pokemons = pokemons

    except BaseException as e:
        print("Got error in pokemon notification handling, more info:\n", traceback.format_exc())


@command_decorator.command("pogo sub", "Subscribes the channel to pokemon go notifications, "
                                       "which means it sends messages about pokemon it finds. \n"
                                       "Use `-only POKEMONNAME,POKEMONNAME,POKEMONNAME,...` to only get notifications about certain pokemon. \n"
                                       "Use `-miniv AMOUNT` or `-maxiv AMOUNT` to only get notifications about pokemon with a minimum or maximum (respectively) IV of `AMOUNT`. \n"
                                       "Use `-mincp AMOUNT` or `-maxcp AMOUNT` to only get notifications about pokemon with a minimum or maximum (respectively) CP of `AMOUNT`.")
@async_use_persistent_poke_dict
async def subscribe_pogo_notification_channel(message: discord.Message, client: discord.Client, config: dict):
    """Adds a server to the channels that have subscribed to pokemon go notifications."""

    # This command needs to be used in a regular channel
    if message.channel.is_private:
        await client.send_message(message.channel, "This command can only be used in regular server channels, not PMs.")
        return

    # The raw parameter text, split with spaces and all empty strings removed. All strings are also transformed to lowercase
    split_query = helpers.remove_anna_mention(client, message)[len(" pogo sub"):].split(" ")
    split_query = [part.lower() for part in split_query if part != ""]

    # We make sure each type of flag is not used more than once
    if max(sum([True for part in split_query if (part == "-miniv") or (part == "-maxiv")]),
           sum([True for part in split_query if (part == "-mincp") or (part == "-maxcp")]),
           sum([True for part in split_query if part == "-only"])) > 1:
        # The user has specified more than 1 of each type of flag
        await client.send_message(message.channel,
                                  "You can only have 1 flag (`-miniv` or similar) for each type of filter (pokemon, iv, and cp). "
                                  "This channel is not subscribed to pogo notifications because of invalid parameters")
        return

    # We parse the options
    parse_iv = (("min" if "-miniv" in split_query else "max") if
                (("-miniv" in split_query) or ("-maxiv" in split_query)) else None)
    # "min" | "max" | None, where None means no info -> no filter
    # The index in split_query where the iv flag was used, None if the flag wasn't used
    iv_index = None if parse_iv is None else split_query.index("-miniv" if parse_iv == "min" else "-maxiv")

    parse_cp = (("min" if "-mincp" in split_query else "max") if
                (("-mincp" in split_query) or ("-maxcp" in split_query)) else None)
    # "min" | "max" | None, where None means no info -> no filter
    # The index in split_query where the cp flag was used, None if the flag wasn't used
    cp_index = None if parse_cp is None else split_query.index("-mincp" if parse_cp == "min" else "-maxcp")

    parse_pokemon = "-only" in split_query
    # The index in split_query where the -only flag was used, None if the flag wasn't used
    pokemon_index = None if not parse_pokemon else split_query.index("-only")

    # Each flag has one corresponding parameter, so we make sure that that parameter exists for all the used flags
    if len(split_query) != 2 * (
        sum([True for val in [parse_iv, parse_cp] if val is not None]) + (1 if parse_pokemon else 0)):
        # The user has not specified a value for each flag
        await client.send_message(message.channel,
                                  "You need to specify a value for each flag. "
                                  "This channel is not subscribed to pogo notifications because of invalid parameters")
        return

    # We make sure that the flags and arguments alternate
    for inx, part in enumerate(split_query):
        # If the index is even, then the part should be a flag, otherwise it should be a value
        if inx % 2 == 0:
            if not part in ("-only", "-maxiv", "-maxcp", "-miniv", "-mincp"):
                # The user did not specify a valid order of flags
                await client.send_message(message.channel,
                                          "You need to specify a flag and then a value, not any other order. "
                                          "This channel is not subscribed to pogo notifications because of invalid parameters.")
                return

    # We try to parse iv and cp, and then pokemon
    # If the parsing fails, we tell the user and don't actually sub them
    iv_filter_value = 0
    if parse_iv is not None:
        # We make sure there is a following value
        if iv_index + 1 == len(split_query):
            await client.send_message(message.channel, "You did not specify a value for iv filtering. "
                                                       "This channel is not subscribed to pogo notifications because of invalid parameters")
            return
        # We try to parse the following value
        iv_filter_value = get_int(split_query[iv_index + 1])

        # We make sure the value was valid
        if iv_filter_value is None:
            await client.send_message(message.channel, "You did not specify a valid value for iv filtering. "
                                                       "This channel is not subscribed to pogo notifications because of invalid parameters.")
            return

    # We parse cp filtering
    cp_filter_value = 0
    if parse_cp is not None:
        # We make sure there is a following value
        if cp_index + 1 == len(split_query):
            await client.send_message(message.channel, "You did not specify a value for cp filtering. "
                                                       "This channel is not subscribed to pogo notifications because of invalid parameters")
            return
        # We try to parse the following value
        cp_filter_value = get_int(split_query[cp_index + 1])

        # We make sure the value was valid
        if cp_filter_value is None:
            await client.send_message(message.channel, "You did not specify a valid value for cp filtering. "
                                                       "This channel is not subscribed to pogo notifications because of invalid parameters.")
            return

    # We parse pokemon filtering
    pokemon_filter_value = 0
    if parse_pokemon:
        # We make sure there is a following value
        if pokemon_index + 1 == len(split_query):
            await client.send_message(message.channel, "You did not specify a value for pokemon filtering. "
                                                       "This channel is not subscribed to pogo notifications because of invalid parameters")
            return
        # We try to parse the following value
        pokemon_filter_value = split_query[pokemon_index + 1].split(",")

        # We remove empty entries
        pokemon_filter_value = [pokemon.lower() for pokemon in pokemon_filter_value if pokemon != ""]

        # If there are no pokemon to filter for, we tell the user and don't sub
        if len(pokemon_filter_value) == 0:
            await client.send_message(message.channel, "You did not specify a value for pokemon filtering. "
                                                       "This channel is not subscribed to pogo notifications because of invalid parameters.")
            return

        # We make sure the value was valid
        if pokemon_filter_value is None:
            await client.send_message(message.channel, "You did not specify a valid value for pokemon filtering. "
                                                       "This channel is not subscribed to pogo notifications because of invalid parameters.")
            return

    # We add the sub to the config dict
    poke_config[message.channel.id] = {"filter_iv": parse_iv is not None,
                                       "filter_iv_type": ("below" if parse_iv == "max" else "above"),
                                       "iv_value": iv_filter_value,
                                       "filter_cp": parse_cp is not None,
                                       "filter_cp_type": ("below" if parse_cp == "max" else "above"),
                                       "cp_value": cp_filter_value,
                                       "filter_pokemon": parse_pokemon, "pokemons": pokemon_filter_value}

    # We tell the user we've subscribed
    await client.send_message(message.channel,
                              "This channel is now subscribed to pokemon go notifications with _{4}_, an IV of _{1}_ **{0}%**, and a CP of _{3}_ **{2}**.".format(
                                  iv_filter_value, ("at most" if parse_iv == "max" else "at least"),
                                  cp_filter_value, ("at most" if parse_cp == "max" else "at least"),
                                  ", ".join(pokemon_filter_value) if parse_pokemon else "all pokemon"))


@command_decorator.command("pogo unsub", "Unsubscribes the channel from pokemon go notifications.")
@async_use_persistent_poke_dict
async def unsubscribe_pogo_notification_channel(message: discord.Message, client: discord.Client, config: dict):
    """Removes a server from the channels that have subscribed to pokemon go notifications."""

    # This command needs to be used in a regular channel
    if message.channel.is_private:
        await client.send_message(message.channel, "This command can only be used in regular server channels, not PMs.")
        return

    # We check if the channel is subscribed
    if message.channel.id in poke_config.keys():
        # This channel is subscribed

        del poke_config[message.channel.id]
        await client.send_message(message.channel, "This channel is now unsubscribed from all pokemon go notifications")

    else:
        # This channel wasn't subscribed
        await client.send_message(message.channel,
                                  "This channel isn't subscribed to pokemon notifications, and can therefore not be unsubscribed from them.")


def filter_pokemon(pokemon: PoGoPokemon, info: dict):
    """Returns true if the given pokemon is allowed through the filter specified by info. Info has the form of
    {"filter_cp": bool, "filter_cp_type": "below"|"above", "cp_value": int,
    "filter_iv": bool, "filter_iv_type": "below"|"above", "iv_value": int,
    "filter_pokemon": bool, "pokemons": list <- empty means all}"""

    iv = get_int(pokemon.iv, 0) if pokemon.iv is not "N/A" else 0
    cp = get_int(pokemon.cp, 0) if pokemon.cp is not "N/A" else 0
    name = pokemon.name

    if info["filter_cp"]:
        # We filter by cp
        # We check what type of filter
        if info["filter_cp_type"] == "below":
            if cp > info["cp_value"]:
                return False
        else:
            if cp < info["cp_value"]:
                return False

    if info["filter_iv"]:
        # We filter by iv
        # We check what type of filter
        if info["filter_iv_type"] == "below":
            if iv > info["iv_value"]:
                return False
        else:
            if iv < info["iv_value"]:
                return False

    if info["filter_pokemon"]:
        # We filter by what pokemon are allowed
        if name.lower() not in info["pokemons"] and len(info["pokemons"]) > 0:
            return False

    return True


def get_int(obj, default=None):
    """Returns an int from a value if a conversion was possible, returns default (default None) otherwise."""
    try:
        return int(obj)
    except ValueError:
        return default


def get_float(obj, default=None):
    """Returns a float from a value if a conversion was possible, returns default (default None) otherwise."""
    try:
        return float(obj)
    except ValueError:
        return default
