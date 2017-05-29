import asyncio
import concurrent
import json
import os.path
import re
import sys
import traceback

import discord
import requests
import youtube_dl
from websockets.exceptions import ConnectionClosed

from ... import command_decorator
from ... import helpers

"""This file handles the voice command interactions, state, and commands."""

# The dict which describes the audio playing in a server, of form {"server id" : {"playlist_info" : {"is_playing" : Bool, "playlist_name" : str, "current_index" : int}, "channel_id": str, "queue" : [streamplayer, ...]}, ...}
# The current player for the playlist (if enabled) will be queue[0]
server_queue_info_dict = {}


def store_persistent_voice_state():
    """Uses the json module to store the data in server_queue_info_dict to disk,
    so we can recover voice state upon reboot of the bot."""
    global server_queue_info_dict

    # We open and close the state file, and we use some tricks to get the filepath since it is above this file
    try:
        with open(os.path.join(os.path.dirname(__file__), "..", "..", "..", "persistent_state", "voice_state.json"),
                  mode="w") as voice_state_file:

            # We store the data that is persistent (everything except the queue)
            saved_data = {}
            for key, val in server_queue_info_dict.items():
                saved_data[key] = {k: v for k, v in val.items() if k is not "queue"}
                # Note that we don't copy the queue and then empty it. This is because lists are mutable, and doing that would empty the list in server_queue_info_dict aswell
                saved_data[key]["queue"] = []
                saved_data[key]["volume"] = [player.volume for player in val["queue"]]
                saved_data[key]["paused"] = [not player.is_playing() for player in val["queue"]]

            # We dump the persistent data to disk via json
            json.dump(saved_data, voice_state_file)
            helpers.log_info("Stored voice state to disk.")

    except BaseException as e:
        print(traceback.format_exception(*sys.exc_info()))


def use_persistent_info_dict(func):
    """This is meant to be used as a decorator to all functions 
    that modify the server_queue_info_dict. 
    It saves the state of the dict into a json file (/persistent_state/voice_state.json from the top of the bot)"""

    def decorated_func(*args, **kwargs):
        # We execute the function
        result = func(*args, **kwargs)

        # We store the persistent state from the info dict to disk
        store_persistent_voice_state()

        return result

    # We return the decorated version of the function
    return decorated_func


def async_use_persistent_info_dict(func):
    """This is meant to be used as a decorator to all functions 
    that modify the server_queue_info_dict. This is for async functions.
    It saves the state of the dict into a json file (/persistent_state/voice_state.json from the top of the bot)"""

    async def decorated_func(*args, **kwargs):
        # We execute the function
        result = await func(*args, **kwargs)

        # We store the persistent state from the info dict to disk
        store_persistent_voice_state()

        return result

    # We return the decorated version of the function
    return decorated_func


def async_use_game_name_changer(func):
    """Wraps a function so it changes the name of the playing game if it should, after the function has returned."""

    # The function we return
    async def decorated_func(*args, **kwargs):
        result = await func(*args, **kwargs)
        # We execute the name changer
        handle_audio_title_game_name()
        return result

    # We return the decorated function
    return decorated_func

@command_decorator.command("voice join channel", "Joins the specified voice channel if anna can access it.",
                           cmd_special_params=[True, False, False])
@async_use_persistent_info_dict
async def cmd_join_voice_channel(message: discord.Message, client: discord.Client, config: dict,
                                 ignored_command_message_ids: list):
    """This command is issued to make anna join a voice channel if she has access to it on the server where this command was issued."""

    # We check if the issuing user has the proper permissions on this server
    if not await permission_checker(message, client, config):
        # We're done here
        return

    # Removing the anna-bot mention
    cleaned_message = helpers.remove_anna_mention(client, message)

    # The user is not an idiot, so we parse the message for the voice channel name, if there are two or more channels with the same name, we tell the user to choose between them using channel order numbers that we give to them depending on the channel IDs
    voice_channel_name = cleaned_message[len("voice join channel "):]

    # Checking how many voice channels in the server match the given name. If none match, we try to strip the name (the user might have been an idiot contrary to popular belief)
    num_matching_voice_channels = [
        (channel.type == discord.ChannelType.voice) and (channel.name == voice_channel_name) for channel in
        message.server.channels].count(True)

    # You can't be connected to multiple voice channels at the same time
    if not client.is_voice_connected(message.server):

        # We check to see if we have permissions to join the voice channel
        if not message.server.me.server_permissions.connect:
            # We don't have permissions to join a voice channel in this server, so we tell the user to fuck off
            await client.send_message(message.channel,
                                      message.author.mention + ", I don't have permission to join a voice channel on this server.")

            # We're done here
            return

        # We check if there exists at least 1 matching channel or not
        if num_matching_voice_channels > 0:

            # We check if there are more than 1 matching channel, because that means trouble
            if num_matching_voice_channels > 1:

                # We have some trouble on our hands
                # We make a list of tuples of all the channel candidates that the user could mean
                channel_candidates = [(channel, channel_number) for channel_number, channel in
                                      enumerate(message.server.channels) if
                                      (channel.name == voice_channel_name) and (
                                          channel.type == discord.ChannelType.voice)]

                # We print the alternatives to the user so they can message us back with the channel they want us to join
                await client.send_message(message.channel,
                                          message.author.mention + ", there are %i voice channels on this server with that name, please message me the number of the channel that you want me to join within 1 minute (e.g. \"%s 0\"):\n--------------------" % (
                                              len(
                                                  channel_candidates), message.server.me.mention) + "".join([(
                                              "\nNumber %s:\n\t%s users currently connected.\n--------------------" % (
                                                  str(
                                                      candidate[
                                                          1]),
                                                  str(
                                                      len(
                                                          candidate[
                                                              0].voice_members))))
                                              for
                                              candidate
                                              in
                                              channel_candidates]))

                response_message = await client.wait_for_message(timeout=60, author=message.author,
                                                                 channel=message.channel,
                                                                 check=lambda msg: helpers.is_message_command(msg,
                                                                                                              client))

                # We add the response message id to the ignored list of message ids
                ignored_command_message_ids.append(response_message.id)

                # We wait for the caller to send back a message to us so we can determine what channel we should join
                user_response = helpers.remove_anna_mention(client, response_message).strip()

                if user_response is not None:
                    # We know that the user sent us a message that @mentioned us, so we parse the rest of the message
                    if user_response.isdecimal():

                        # We can convert the user response into a number and then check if it is a valid choice or not
                        if int(user_response) in [x[1] for x in channel_candidates]:
                            # Converting the response into an int
                            user_response = int(user_response)

                            # Choosing the channel to join
                            voice_channel = [x[0] for x in channel_candidates if x[1] == int(user_response)][0]

                        else:
                            # The user tried to choose an invalid alternative
                            await client.send_message(message.channel,
                                                      message.author.mention + ", that's not an alternative.")

                            # We're done here
                            return


                    else:
                        # Invalid number / That's not a number
                        await client.send_message(message.channel,
                                                  message.author.mention + ", that's not a number.")

                        # We're done here
                        return

                else:
                    # The waiting timed out, so we message the user that they waited to long
                    await client.send_message(message.channel,
                                              message.author.mention + ", you waited to long with answering which channel you want me to connect to.")

                    # We're done here
                    return

            else:

                # Everything went well, we can safely try to join the voice channel
                # We get the channel from the channel name that the user specified
                voice_channel = discord.utils.get(message.server.channels, name=voice_channel_name,
                                                  type=discord.ChannelType.voice)


        else:

            # We couldn't find a match, so we try the same thing with a stripped version of the desired channel name
            voice_channel_name = voice_channel_name.strip()

            # Checking how many voice channels in the server match the given name
            num_matching_voice_channels = [
                (channel.type == discord.ChannelType.voice) and (channel.name == voice_channel_name) for channel in
                message.server.channels].count(True)

            # We check if we found any matching channels this time
            if num_matching_voice_channels > 0:

                # We have some trouble on our hands
                # We make a list of tuples of all the channel candidates that the user could mean
                channel_candidates = [(channel, channel_number) for channel_number, channel in
                                      enumerate(message.server.channels) if
                                      (channel.name == voice_channel_name) and (
                                          channel.type == discord.ChannelType.voice)]

                # We print the alternatives to the user so they can message us back with the channel they want us to join
                await client.send_message(message.channel,
                                          message.author.mention + ", there are %i voice channels on this server with that name, please message me the number of the channel that you want me to join within 1 minute (e.g. \"%s 0\"):\n--------------------" % (
                                              len(channel_candidates), message.server.me.mention) +
                                          "".join([(
                                              "\nNumber {0}:\n\t{1} users currently connected.\n--------------------".format(
                                                  str(candidate[1]),
                                                  str(len(candidate[0].voice_members)))) for candidate in
                                              channel_candidates]))

                response_message = await client.wait_for_message(timeout=60, author=message.author,
                                                                 channel=message.channel,
                                                                 check=lambda msg: helpers.is_message_command(msg,
                                                                                                              client))

                # We add the response message id to the ignored list of message ids
                ignored_command_message_ids.append(response_message.id)

                # We wait for the caller to send back a message to us so we can determine what channel we should join
                user_response = helpers.remove_anna_mention(client, response_message).strip()

                if user_response is not None:
                    # We know that the user sent us a message that @mentioned us, so we parse the rest of the message
                    if user_response.isdecimal():

                        # We can convert the user response into a number and then check if it is a valid choice or not
                        if int(user_response) in [x[1] for x in channel_candidates]:
                            # Converting the response into an int
                            user_response = int(user_response)

                            # Choosing the channel to join
                            voice_channel = [x[0] for x in channel_candidates if x[1] == int(user_response)][0]

                        else:
                            # The user tried to choose an invalid alternative
                            await client.send_message(message.channel,
                                                      message.author.mention + ", that's not an alternative.")

                            # We're done here
                            return


                    else:
                        # Invalid number / That's not a number
                        await client.send_message(message.channel,
                                                  message.author.mention + ", that's not a number.")

                        # We're done here
                        return

                else:
                    # The waiting timed out, so we message the user that they waited to long
                    await client.send_message(message.channel,
                                              message.author.mention + ", you waited too long with answering which channel you want me to connect to.")

                    # We're done here
                    return

            else:

                # We didn't find any matching channels, which means that the user is a fucking idiot
                await client.send_message(message.channel,
                                          message.author.mention + ", I couldn't find any voice channels called \"" + voice_channel_name + "\".")

                # We're done now
                return

    else:

        # We tell the user to check their IQ and try again (because the bot is already connected to a voice channel)
        await client.send_message(message.channel,
                                  message.author.mention + ", I can't join a voice channel when I'm already connected to one. Please use the voice leave command if you want me to join another channel.")

        # We're done now
        return

    # Everything should have exited if something went wrong by this stage, so we can safely assume that it's fine to connect to the voice channel that the user has specified
    # Telling the user that we found the channel and that we are joining right now
    await client.send_message(message.channel,
                              message.author.mention + ", ok, I'm joining \"%s\" right now." % voice_channel_name)

    # Joining the channel
    await client.join_voice_channel(voice_channel)

    # We add an entry for this server to the queue dict
    server_queue_info_dict[message.server.id] = {
        "playlist_info": {"is_playing": False, "playlist_name": "", "current_index": -1}, "queue": [],
        "channel_id": voice_channel.id}

    return ignored_command_message_ids


@command_decorator.command("voice joinme", "Joins the voice channel you are connected to if anna can access it.")
@async_use_persistent_info_dict
async def cmd_join_self_voice_channel(message: discord.Message, client: discord.Client, config: dict):
    """This method makes anna-bot join the voice channel of the member who called the command."""

    # We check if the issuing user has the proper permissions on this server
    if not await permission_checker(message, client, config):
        # We're done here
        return

    # We check if the user is connected to a valid voice channel
    if (message.author.voice.voice_channel is None) or (
                message.author.voice.voice_channel.type != discord.ChannelType.voice) or (
                message.author.voice.voice_channel.server.id != message.server.id):
        # We tell the user that they aren't connected to a voice channel
        await client.send_message(message.channel,
                                  message.author.mention + ", you aren't connected to a voice channel on this server, so I can't join you.")

        # We're done here
        return

    # We check if we are connected to a voice channel already on this server, as we can't be connected to more than 1 channel at a time
    if client.is_voice_connected(message.server):
        # We tell the user that we're already connected
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm already connected to a voice channel on this server, so I can't join you.")

    # We check to see if we have permissions to join the voice channel
    if not message.author.voice.voice_channel.permissions_for(message.server.me).connect:
        # We don't have permissions to their voice channel on this server, so we tell the user that
        await client.send_message(message.channel,
                                  message.author.mention + ", I don't have permission to your voice channel on this server.")

        # We're done here
        return

    # The channel the user is connected to
    member_channel = message.author.voice.voice_channel

    # Telling the user that we are joining right now
    await client.send_message(message.channel,
                              message.author.mention + ", ok, I'm joining \"{0}\" right now.".format(
                                  member_channel.name))

    # Joining the channel
    await client.join_voice_channel(member_channel)

    # We add an entry for this server to the queue dict
    server_queue_info_dict[message.server.id] = {
        "playlist_info": {"is_playing": False, "playlist_name": "", "current_index": -1}, "queue": [],
        "channel_id": member_channel.id}


@command_decorator.command("voice leave", "Leaves the voice channel anna is connected to")
@async_use_persistent_info_dict
@async_use_game_name_changer
async def cmd_leave_voice_channel(message: discord.Message, client: discord.Client, config: dict):
    """This command is issued to make anna leave a voice channel if she is connected to it on the server where this command was issued."""

    # We check if the issuing user has the proper permissions on this server
    if not await permission_checker(message, client, config):
        # We're done here
        return

    # We check if we were connected to a voice channel on the server where this command was issued
    if client.is_voice_connected(message.server):
        # We tell the issuing user that we've left the server
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm leaving the \"%s\" voice channel right now." % client.voice_client_in(
                                      message.server).channel.name)

        # We check if there are any stream players currently playing on that voice channel
        for stream in server_queue_info_dict[message.server.id]["queue"]:
            # We stop the player, but we also set the volume to 0 to prevent the queuehandler from making weird noises
            stream.volume = 0
            stream.stop()

        # We remove the stopped server's voice info
        del server_queue_info_dict[message.server.id]

        # We leave the voice channel that we're connected to on that server
        await client.voice_client_in(message.server).disconnect()

    else:
        # We aren't connected to a voice channel on the current server, the user is just being an idiot
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm not connected to a voice channel on this server, if you want me to connect to one, please use the \"{0} voice join channel CHANNELNAME\" command.".format(
                                      message.server.me.mention))


@command_decorator.command("voice play link",
                           "Adds the audio of the given link to the voice queue. The only platform that is guaranteed to work is youtube but it should work with all the sites listed here: https://rg3.github.io/youtube-dl/supportedsites.html , but I give no guarantees.")
@async_use_persistent_info_dict
@async_use_game_name_changer
async def cmd_voice_play_link(message: discord.Message, client: discord.Client, config: dict):
    """This command is used to queue up the audio of a youtube video at the given link, to the server's queue."""

    # We check if the issuing user has the proper permissions on this server
    if not await permission_checker(message, client, config):
        # We're done here
        return

    # We parse the url from the command message
    youtube_url = helpers.remove_anna_mention(client, message).strip()[len("voice play link "):]

    # We get the voice client on the server in which the command was issued
    voice = client.voice_client_in(message.server)

    # We check if we're connected to a voice channel in the server where the command was issued
    if voice is None:

        # We are not connected to a voice channel, so we tell the user to fuck off
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm not connected to any voice channels on this server, so I can't play any audio.")

    else:

        # We need to catch some errors
        try:
            # We're connected to a voice channel, so we try to create the ytdl stream player
            # I found these ytdl options here: https://github.com/rg3/youtube-dl/blob/master/youtube_dl/YoutubeDL.py https://github.com/rg3/youtube-dl/blob/e7ac722d6276198c8b88986f06a4e3c55366cb58/README.md
            youtube_player = await voice.create_ytdl_player(youtube_url, ytdl_options={"noplaylist": True},
                                                            after=queue_handler)
        except youtube_dl.DownloadError:
            # The URL failed to load, it's probably invalid
            await client.send_message(message.channel,
                                      message.author.mention + ", that URL failed to load, is it valid?")

            # We're done here
            return

        except ConnectionClosed:
            # This can happen with code 1000 "No reason"...

            # The URL failed to load, it's probably invalid
            await client.send_message(message.channel,
                                      message.author.mention + ", that URL failed to load, is it valid?")

            # We're done here
            return

        except:
            # Unknown error
            await client.send_message(message.channel,
                                      message.author.mention + ", I got an unrecognised error while loading.")

            # We reraise
            raise

        # We append the streamplayer to the server's queue
        server_queue_info_dict[message.server.id]["queue"].append(youtube_player)

        # If the server doesn't have any currently playing stream players, we start the new stream player
        if len(server_queue_info_dict[message.server.id]["queue"]) == 1:
            youtube_player.start()

            # Telling the user that we're playing the video
            await client.send_message(message.channel,
                                      message.author.mention + (
                                          ", I added to queue and started playing, audio with title: *{0}*, uploaded by: *{1}*. (Use **\"" + client.user.mention + " queue list\"** to see the current queue)").format(
                                          *helpers.remove_discord_formatting(youtube_player.title, (
                                              "N/A" if youtube_player.uploader is None else youtube_player.uploader))))

            # We log what video title and uploader the played audio has
            helpers.log_info(
                "Added to queue and started playing, audio with title: \"{0}\", uploaded by: \"{1}\", in voice channel: \"{2}\" on server: \"{3}\"".format(
                    youtube_player.title, ("N/A" if youtube_player.uploader is None else youtube_player.uploader),
                    voice.channel.name, voice.server.name))

        else:

            # Telling the user that we've added the audio to the queue
            await client.send_message(message.channel,
                                      message.author.mention + (
                                          ", I added audio with title: *{0}*, uploaded by: *{1}* to the queue. (Use **\"" + client.user.mention + " queue list\"** to see the current queue)").format(
                                          *helpers.remove_discord_formatting(youtube_player.title,
                                                                             youtube_player.uploader)))

            # We log what video title and uploader the played audio has
            helpers.log_info(
                "Added audio with title: \"{0}\", uploaded by: \"{1}\", to queue in voice channel: \"{2}\" on server: \"{3}\"".format(
                    youtube_player.title, youtube_player.uploader, voice.channel.name, voice.server.name))


@command_decorator.command("voice play search youtube",
                           "Adds the audio of the first youtube search result from given query to the voice queue.")
@async_use_persistent_info_dict
@async_use_game_name_changer
async def cmd_voice_play_youtube_search(message: discord.Message, client: discord.Client, config: dict):
    """This method is used to add a youtube video to the server queue by picking the top search result from youtube on the specified query."""

    # We check if the issuing user has the proper permissions on this server
    if not await permission_checker(message, client, config):
        # We're done here
        return

    # We parse the url from the command message
    user_query = helpers.remove_anna_mention(client, message).strip()[len("voice play search youtube "):]

    # We get the voice client on the server in which the command was issued
    voice = client.voice_client_in(message.server)

    # We check if we're connected to a voice channel in the server where the command was issued
    if voice is None:

        # We are not connected to a voice channel, so we tell the user to fuck off
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm not connected to any voice channels on this server, so I can't play any audio.")

    else:

        # We make sure that the search query is atleast 4 chars long
        if len(user_query) < 4:
            # We tell the user that the query is too short
            await client.send_message(message.channel,
                                      message.author.mention + ", the search query needs to be atleast 4 characters long.")
            # We're done here
            return

        # We search for the video
        html_content = requests.get("http://www.youtube.com/results", {"search_query": user_query})
        search_results = re.findall("href=\"\/watch\?v=(.{11})", html_content.text)
        helpers.log_info(
            "Searched youtube for {0} and got result http://www.youtube.com/watch?v={1} to add to queue on channel {2} ({3}) on server {4} ({5}).".format(
                user_query, search_results[0], voice.channel.name, voice.channel.id, message.server.name,
                message.server.id))

        # We need to catch some errors
        try:
            # We're connected to a voice channel, so we try to create the ytdl stream player with the search result we got
            youtube_player = await voice.create_ytdl_player(
                "http://www.youtube.com/watch?v={0}".format(search_results[0]), ytdl_options={"noplaylist": True},
                after=queue_handler)
        except youtube_dl.utils.ExtractorError:
            # The URL failed to load, it's probably invalid
            await client.send_message(message.channel,
                                      message.author.mention + ", that URL failed to load, is it valid?")

            # We're done here
            return

        # We append the streamplayer to the server's queue
        server_queue_info_dict[message.server.id]["queue"].append(youtube_player)

        # If the server doesn't have any currently playing stream players, we start the new stream player
        if len(server_queue_info_dict[message.server.id]["queue"]) == 1:
            youtube_player.start()

            # Telling the user that we're playing the video
            await client.send_message(message.channel,
                                      message.author.mention + (
                                          ", I added and started playing, youtube video with title: *{0}*, uploaded by: *{1}* to the queue. (Use **\"" + client.user.mention + " queue list\"** to see the current queue)").format(
                                          *helpers.remove_discord_formatting(youtube_player.title,
                                                                             youtube_player.uploader)))

            # We log what video title and uploader the played video has
            helpers.log_info(
                "Added youtube and started playing, video with title: \"{0}\", uploaded by: \"{1}\", to queue in voice channel: \"{2}\" on server: \"{3}\"".format(
                    youtube_player.title, youtube_player.uploader, voice.channel.name, voice.server.name))

        else:

            # Telling the user that we've added the video to the queue
            await client.send_message(message.channel,
                                      message.author.mention + (
                                          ", I added youtube video with title: *{0}*, uploaded by: *{1}* to the queue. (Use **\"" + client.user.mention + " queue list\"** to see the current queue)").format(
                                          *helpers.remove_discord_formatting(youtube_player.title,
                                                                             youtube_player.uploader)))

            # We log what video title and uploader the played video has
            helpers.log_info(
                "Added youtube video with title: \"{0}\", uploaded by: \"{1}\", to queue in voice channel: \"{2}\" on server: \"{3}\"".format(
                    youtube_player.title, youtube_player.uploader, voice.channel.name, voice.server.name))


# TODO remake
async def cmd_voice_sound_effect(message: discord.Message, client: discord.Client, config: dict):
    """This method is used to play a sound effect in the voice channel anna is connected to on the issuing server."""

    # We check if the issuing user has the proper permissions on this server
    if not await permission_checker(message, client, config):
        # We're done here
        return

    # We parse the sound effect name from the command TODO
    sound_effect_name = helpers.remove_anna_mention(client, message).strip()

    # We get the voice client on the server in which the command was issued
    voice = client.voice_client_in(message.server)

    # We check if we're connected to a voice channel in the server where the command was issued
    if voice is None:

        # We are not connected to a voice channel, so we tell the user to fuck off
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm not connected to any voice channels on this server, so I can't play any audio.")

    else:

        # We're connected to a voice channel, so we check if the specified sound effect exists TODO

        # We create the stream player with the specified file name TODO

        # We append the stream and server id pair to the stream list
        server_and_stream_players.append((message.server.id, youtube_player))

        # We start the stream player
        youtube_player.start()

        # Telling the user that we're playing the video
        await client.send_message(message.channel,
                                  message.author.mention + ", now playing youtube video with title: \"%s\", uploaded by: \"%s\"." % (
                                      youtube_player.title, youtube_player.uploader))

        # We log what video title and uploader the played video has
        helpers.log_info(
            "Playing youtube video with title: \"%s\", uploaded by: \"%s\" in voice channel: \"%s\" on server: \"%s\"" % (
                youtube_player.title, youtube_player.uploader, voice.channel.name, voice.server.name))


@command_decorator.command("voice playlist play",
                           "Starts playing a playlist, and puts the playlist at the front of the queue.")
@async_use_persistent_info_dict
@async_use_game_name_changer
async def cmd_voice_playlist_play(message: discord.Message, client: discord.Client, config: dict):
    """This command plays the specified playlist file if it exists."""

    # We check if the user is allowed to use voice commands
    if not await permission_checker(message, client, config):
        # They're not allowed to use voice commands
        return

    # We check if we're connected to a voice channel / if we've setup a voice info entry for the server
    if not client.is_voice_connected(message.server):
        # We tell the user that we aren't connected to a voice channel in that server
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm not connected to a voice channel on this server, if you want me to connect to one, please use the \"{0} voice join channel CHANNELNAME\" command.".format(
                                      message.server.me.mention))
        # We're done here
        return

    # We check if the server is using playlists
    if server_queue_info_dict[message.server.id]["playlist_info"]["is_playing"]:
        # We tell the user that they need to disable the playlist before they start playing another one
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm already playing a playlist on this server, use \"{0} voice playlist stop\" to stop playing that playlist.".format(
                                      message.server.me.mention))

        # We're done here
        return

    # We parse the user input / specified playlist
    user_playlist = helpers.remove_anna_mention(client, message)[len("voice playlist play "):]
    # We remove unsafe chars from the user specified playlist filename
    # Note that we don't allow dots/full stops in the file name, this is so we don't need to use regular expressions to remove multiple dots in a row (try ../../../../kek.txt)
    user_playlist = "".join(c for c in user_playlist if c.isalnum() or c in (' ', '_')).rstrip()

    # We check if we can read the playlist file
    try:
        with open(os.path.join("playlists", user_playlist), mode="r", encoding="utf-8") as playlist_file:
            # We can read the file, so we store the current volume of the first thing in the queue
            last_volume = 1 if len(server_queue_info_dict[message.server.id]["queue"]) == 0 else \
                server_queue_info_dict[message.server.id]["queue"][0].volume

            # We get the voice client in the issuing server
            voice = client.voice_client_in(message.server)

            # We try to create a ytdl player with the link in the playlist file
            # We need to catch some errors
            try:
                # We're connected to a voice channel, so we try to create the ytdl stream player
                # I found these ytdl options here: https://github.com/rg3/youtube-dl/blob/master/youtube_dl/YoutubeDL.py https://github.com/rg3/youtube-dl/blob/e7ac722d6276198c8b88986f06a4e3c55366cb58/README.md
                youtube_player = await voice.create_ytdl_player(playlist_file.readline().strip(),
                                                                ytdl_options={"noplaylist": True},
                                                                after=queue_handler)
            except youtube_dl.DownloadError:
                # The URL failed to load, it's probably invalid
                await client.send_message(message.channel,
                                          message.author.mention + ", I wasn't able to load the first URL in the playlist, is it valid?")

                # We're done here
                return

            except ConnectionClosed:
                # This can happen with code 1000 "No reason"...

                # The URL failed to load, it's probably invalid
                await client.send_message(message.channel,
                                          message.author.mention + ", that URL failed to load, is it valid?")

                # We're done here
                return

            except:
                # Unknown error
                await client.send_message(message.channel,
                                          message.author.mention + ", I got an unrecognised error while loading the first URL in the playlist.")

                # We reraise
                raise

            # We set the volume of the new player
            youtube_player.volume = last_volume

            # We pause the current player in the queue (if there is one)
            if len(server_queue_info_dict[message.server.id]["queue"]) > 0:
                server_queue_info_dict[message.server.id]["queue"][0].pause()

            # We insert the streamplayer in the front of the queue
            server_queue_info_dict[message.server.id]["queue"].insert(0, youtube_player)

            # We update the server info dict for using playlists
            server_queue_info_dict[message.server.id]["playlist_info"]["is_playing"] = True
            server_queue_info_dict[message.server.id]["playlist_info"]["playlist_name"] = user_playlist
            server_queue_info_dict[message.server.id]["playlist_info"]["current_index"] = 0

            # We start the player
            youtube_player.start()

            # Telling the user that we're playing the video
            await client.send_message(message.channel,
                                      message.author.mention + (
                                          ", I added to queue and started playing, audio with title: *{0}*, uploaded by: *{1}*. (Use **\"" + client.user.mention + " queue list\"** to see the current queue)").format(
                                          *helpers.remove_discord_formatting(youtube_player.title, (
                                              "N/A" if youtube_player.uploader is None else youtube_player.uploader))))

            # We log what video title and uploader the played audio has
            helpers.log_info(
                "Added to queue and started playing, audio with title: \"{0}\", uploaded by: \"{1}\", in voice channel: \"{2}\" on server: \"{3}\"".format(
                    youtube_player.title, ("N/A" if youtube_player.uploader is None else youtube_player.uploader),
                    voice.channel.name, voice.server.name))

            # We handle the game name
            handle_audio_title_game_name()


    except IOError as e:
        # The file either doesn't exist, or we don't have permission to open it, but we assume that it doesn't exist
        await client.send_message(message.channel,
                                  message.author.mention + ", I wasn't able to open that file, are you sure that you specified a valid playlist name?")


@command_decorator.command("voice playlist stop",
                           "Stops playing the current playlist, and starts playing the rest of the queue.")
@async_use_persistent_info_dict
@async_use_game_name_changer
async def cmd_voice_playlist_stop(message: discord.Message, client: discord.Client, config: dict):
    """This command stops playing a playlist and switches to the regular queue playing. It does this by invoking the queue handler."""

    # We check if the user is allowed to use voice commands
    if not await permission_checker(message, client, config):
        # They're not allowed to use voice commands
        return

    # We check if we're connected to a voice channel / if we've setup a voice info entry for the server
    if not client.is_voice_connected(message.server):
        # We tell the user that we aren't connected to a voice channel in that server
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm not connected to a voice channel on this server, if you want me to connect to one, please use the \"{0} voice join channel CHANNELNAME\" command.".format(
                                      message.server.me.mention))
        # We're done here
        return

    # We check if the server is using playlists
    if not server_queue_info_dict[message.server.id]["playlist_info"]["is_playing"]:
        # We tell the user that they need to disable the playlist before they start playing another one
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm not playing a playlist on this server, use \"{0} voice playlist play\" to start playing a playlist.".format(
                                      message.server.me.mention))

        # We're done here
        return

    # We're using playlists, so we just disable the playlist in playlist_info, and invoke the queue handler
    server_queue_info_dict[message.server.id]["playlist_info"]["is_playing"] = False
    server_queue_info_dict[message.server.id]["playlist_info"]["current_index"] = -1
    server_queue_info_dict[message.server.id]["playlist_info"]["playlist_name"] = ""

    # We stop the current player, and therefore invoke the queue handler
    server_queue_info_dict[message.server.id]["queue"][0].stop()

    # We tell the user that we've stopped playing the playlist
    await client.send_message(message.channel, message.author.mention + ", I've now stopped playing the playlist.")


@command_decorator.command("voice playlist add",
                           "Uploads the attached file as a playlist file. Filenames cannot contain dots. Use with caution. Format for playlist files is \"LINK\\nLINK\\nLINK\\n...\".",
                           admin=True)
async def cmd_voice_playlist_add(message: discord.Message, client: discord.Client, config: dict):
    """This command lets an anna-bot admin upload a new playlist file to the bot. This doesn't allow regular users to do it because of DoS and space concerns."""

    # This command can be used anywhere, the only requirement is that the message has attached a playlist file (one link per line, unix file endings), and that the file does not share it's name with one of the already existing playlists

    # We check if the user attached a file or not
    if not message.attachments:
        # The user needs to give us a file to upload
        await client.send_message(message.channel, message.author.mention + ", you need to attach a playlist file.")

        # We're done here
        return

    # We parse the filename and make it safe
    safe_filename = "".join(c for c in message.attachments[0]["filename"] if c.isalnum() or c in (' ', '_')).rstrip()

    # We create a list of the filenames in the playlist directory
    for root, dirs, playlist_files in os.walk("playlists"):
        # We only get top level files
        break

    # We check if the file already exists
    if safe_filename in playlist_files:
        # We tell the user that they need to specify a unique filename
        await client.send_message(message.channel,
                                  message.author.mention + ", you need to upload with a filename that doesn't already exist.")

        # We're done here
        return

    # We've validated the file, so we download it and store it in the playlists directory
    with open(os.path.join("playlists", safe_filename), mode="wb") as new_playlist_file:

        # We get the attached file from the url
        file_stream = requests.get(message.attachments[0]["url"], stream=True)

        # We write out chunks of the file to disk until it's done
        for chunk in file_stream.iter_content(chunk_size=1024):
            new_playlist_file.write(chunk)

    # We tell the user that we're done, and we log it
    await client.send_message(message.channel, message.author.mention + ", I've now stored that playlist.")
    helpers.log_info("Downloaded and stored playlist file {0}.".format(safe_filename))


@command_decorator.command("voice playlist remove",
                           "Removes an existing playlist file from anna-bot. Use with caution, as it will stop all playing of this playlist.",
                           admin=True)
async def cmd_voice_playlist_remove(message: discord.Message, client: discord.Client, config: dict):
    """This command lets an anna-bot admin remove an existing playlist file from the bot. This doesn't allow regular users to do it because of abuse concerns."""

    # This command can be used anywhere, the only requirement is that the user specifies a playlist file that exists
    # We parse the specified filename
    playlist_name = helpers.remove_anna_mention(client, message)[len("admin voice playlist remove "):].strip()

    # We check if it exists
    if not (os.path.isfile(os.path.join("playlists", playlist_name)) and not os.path.islink(
            os.path.join("playlists", playlist_name))):
        # The filename specified is not valid
        await client.send_message(message.channel, message.author.mention + ", that playlist doesn't exist.")

        # We're done here
        return

    # The file is not a symlink, and it's a file, so we remove it and tell the user
    try:
        # We remove the file
        os.remove(os.path.join("playlists", playlist_name))
    except (PermissionError, OSError) as e:
        # We tell the user that we weren't able to remove the file
        await client.send_message(message.channel,
                                  message.author.mention + ", I wasn't able to remove that playlist because of an error.")

        # We're done here
        return

    # We log it and tell the user that we've succeeded
    await client.send_message(message.channel, message.author.mention + ", I've now deleted that playlist")
    helpers.log_info("Deleted playlist {0}.".format(playlist_name))


@command_decorator.command("voice playlist list",
                           "Lists the available playlist files that anna-bot can play.")
async def cmd_voice_playlist_list(message: discord.Message, client: discord.Client, config: dict):
    """This command lets a regular user list the available playlist files on the bot."""

    # We check if the message was sent in a regular channel
    if not await pm_checker(message, client):
        # They can't execute the commands
        return False

    # We create a list of the filenames in the playlist directory
    playlist_files = []
    for root, dirs, playlist_files in os.walk("playlists"):
        # We only get top level files
        break

    # We check if we don't have any files.
    if playlist_files == []:
        await client.send_message(message.channel, message.author.mention + ", There are no playlist files available.")
        # We're done here
        return

    # The full message to send to the user
    list_message = message.author.mention + "These are the available playlist files:\n-------------------------"

    # We add an entry for each playlist file
    for name in playlist_files:
        list_message += "\n**{0}**\n-------------------------".format(name)

    # We send the message
    await helpers.send_long(client, list_message, message.channel)


@command_decorator.command("voice volume", "Change the volume of the audio that anna plays (0% -> 200%).")
@async_use_persistent_info_dict
async def cmd_voice_set_volume(message: discord.Message, client: discord.Client, config: dict):
    """This command is used to change the volume of the audio that anna plays."""

    # We check if the issuing user has the proper permissions on this server
    if not await permission_checker(message, client, config):
        # We're done here
        return

    # We check if there we are connected to a voice channel on this server
    if client.voice_client_in(message.server) is not None:

        # We check if we found any stream players
        if len(server_queue_info_dict[message.server.id]["queue"]) > 0:

            # We parse the command and check if the specified volume is a valid non-negative integer
            clean_argument = helpers.remove_anna_mention(client, message)[13:].strip()

            if clean_argument.isdigit():

                # We create an int from the string and clamp it between 0-2 (inclusive on both ends)
                volume = min(max(int(clean_argument), 0), 200) / 100

                # We set the volume of the currently playing player to be the desired volume
                # Setting the volume of the stream player
                server_queue_info_dict[message.server.id]["queue"][0].volume = volume

                # Telling the user that we've set the volume
                await client.send_message(message.channel,
                                          message.author.mention + ", I've changed the volume to %i%%." % int(
                                              volume * 100))

            else:
                # Invalid volume argument (wasn't a positive int)
                await client.send_message(message.channel,
                                          message.author.mention + ", that wasn't a valid volume level.")

        else:
            # We didn't find any stream players
            await client.send_message(message.channel,
                                      message.author.mention + ", I'm not playing any sound on this server.")

    else:
        # We aren't connected to any voice channel on this server
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm not connected to any voice channels on this server.")


@command_decorator.command("voice toggle", "Toggle (pause or unpause) the audio anna is currently playing.")
@async_use_persistent_info_dict
async def cmd_voice_play_toggle(message: discord.Message, client: discord.Client, config: dict):
    """This method is used to toggle playing (pausing and unpausing) the currently playing stream player in that server (if there is one)."""

    # We check if the issuing user has the proper permissions on this server
    if not await permission_checker(message, client, config):
        # We're done here
        return

    # The command was issued in a regular channel
    # We check if there we are connected to a voice channel on this server
    if client.voice_client_in(message.server) is not None:

        # We check if there are any player's in the current queue
        if len(server_queue_info_dict[message.server.id]["queue"]) > 0:

            # The player that is currently at the front of the queue
            current_player = server_queue_info_dict[message.server.id]["queue"][0]

            # We toggle the playing status
            if current_player.is_playing():
                # The player is not paused, so we pause it
                current_player.pause()
            else:
                # The player is paused, so we unpause it
                current_player.resume()

            # We tell the user that we've toggled the stream player
            await client.send_message(message.channel, message.author.mention + ", I've now toggled the audio.")

        else:
            # We didn't find any stream players
            await client.send_message(message.channel,
                                      message.author.mention + ", I'm not playing any sound on this server.")

    else:
        # We aren't connected to any voice channel on this server
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm not connected to any voice channels on this server.")


@command_decorator.command("voice stop", "Stop the audio that anna is currently playing.")
@async_use_game_name_changer
async def cmd_voice_play_stop(message: discord.Message, client: discord.Client, config: dict):
    """This method is used to stop and remove the currently playing audio from anna in a server. This basically does queue.pop()"""

    # We check if the issuing user has the proper permissions on this server
    if not await permission_checker(message, client, config):
        # We're done here
        return

    # The command was issued in a regular channel
    # We check if there we are connected to a voice channel on this server
    if client.voice_client_in(message.server) is not None:

        # We check if there are any currently playing players
        if len(server_queue_info_dict[message.server.id]["queue"]) > 0:

            # The commands issuer's server and its queue and currently playing player
            server_queue = server_queue_info_dict[message.server.id]["queue"]
            current_player = server_queue[0]

            # We log that we are handling the end of a player
            helpers.log_info(
                "Youtube video with title: \"{0}\", uploaded by: \"{1}\", duration: {2}, was stopped by the stop command, handling server queue.".format(
                    current_player.title, current_player.uploader, current_player.duration))

            # We stop the currently playing player
            current_player.stop()

            # We don't do any handling of the next player in queue, since the queue handler does that for us, and if we del a player, we will get a sigsev when trying to use the queue handler
            queue_handler(current_player)

            # We tell the user that we've toggled the stream player
            await client.send_message(message.channel, message.author.mention + ", I've now stopped the audio.")

        else:
            # We didn't find any stream players
            await client.send_message(message.channel,
                                      message.author.mention + ", I'm not playing any sound on this server.")

    else:
        # We aren't connected to any voice channel on this server
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm not connected to any voice channels on this server.")


@command_decorator.command("queue list", "Lists the current voice queue.")
async def cmd_voice_queue_list(message: discord.Message, client: discord.Client, config: dict):
    """This method shows the audio current queue for the server that it was called from."""

    # We check if the message was sent in a regular channel
    if not await pm_checker(message, client):
        # They can't execute the commands
        return False

    # We check if the message was sent in a server where we are connected to a voice channel
    if client.voice_client_in(message.server) is None:
        # There is no voice client for this server
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm not connected to any voice channels on this server, so I can't play any audio.")
        # We're done here
        return

    # The whole queue list message
    queue_message = ""

    # We check if the server has anything in its queue at all
    if (not message.server.id in server_queue_info_dict) or len(
            server_queue_info_dict[message.server.id]["queue"]) == 0:
        # Nothing in the queue
        await client.send_message(message.channel, message.author.mention + ", this server's queue is empty.")
        # We're done here
        return

    # If we're playing a playlist, we don't list the videos, so we check if we're playing a playlist
    if server_queue_info_dict[message.server.id]["playlist_info"]["is_playing"]:
        player = server_queue_info_dict[message.server.id]["queue"][0]
        fields = helpers.remove_discord_formatting(
            server_queue_info_dict[message.server.id]["playlist_info"]["playlist_name"], player.title, player.uploader,
            str(player.duration),
            player.description[:300].replace("://", ":// ") + " \u2026")
        fields.insert(3, player.url.replace("_", "\\_"))

        # We're playing a playlist on the server, so we tell the user that
        await helpers.send_long(client,
                                message.author.mention + ", I'm currently playing playlist *{0}*, "
                                                         "and the currently playing audio is: "
                                                         "*{1}* by *{2}* at url __{3}__\nDuration: **{4}** seconds.\nDescription:\n{5}".format(
                                    *fields
                                ), message.channel)

        # We're done here
        return

    # We loop through the queue
    for inx, player in enumerate(server_queue_info_dict[message.server.id]["queue"]):
        # We add the list message for this player
        # We clear the formatting of almost all the youtube info, but then we insert the player url in the proper slot since youtube urls can have underscored in them,
        # and underscores are discord formatting, so we don't want that field to get cleaned

        # Not all video sources have descriptions, titles, duration, or uploaders
        safe_title = player.title if player.title is not None else "N/A"
        safe_uploader = player.uploader if player.uploader is not None else "N/A"
        safe_duration = player.duration if player.duration is not None else "N/A"
        safe_description = player.description
        if safe_description is None:
            # There is no given description
            safe_description = "There is no provided description for this audio."

        fields = helpers.remove_discord_formatting(str(inx), safe_title, safe_uploader,
                                                   str(safe_duration),
                                                   safe_description[:300].replace("://",
                                                                                  ":// ") + " \u2026")  # Unicode horizontal ellipsis
        fields.insert(2, ("*. **Currently playing this**" if inx == 0 else "*"))
        fields.insert(4, player.url.replace("_", "\\_"))
        queue_message += "-------------------------\n\tNr. **{0}**, *{1}{2}\nBy *{3}* at URL __{4}__\nDuration: **{5}** seconds.\nDescription:\n{6}\n-------------------------\n".format(
            *fields)

    # We send the queue message
    await helpers.send_long(client, message.author.mention + ", here is the current queue:\n" + queue_message,
                            message.channel)


@command_decorator.command("queue remove",
                           "Removes the specified queue index from the queue, if the index is 0, it effectively acts as a skip command.")
@async_use_persistent_info_dict
@async_use_game_name_changer
async def cmd_voice_queue_remove(message: discord.Message, client: discord.Client, config: dict):
    """This method removes a specified stream from the current queue for the server that it was called from."""

    # We check if the issuing user has the proper permissions on this server
    if not await permission_checker(message, client, config):
        # We're done here
        return

    # We check if the message was sent in a server where we are connected to a voice channel
    if client.voice_client_in(message.server) is None:
        # There is no voice client for this server
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm not connected to any voice channels on this server, so there isn't any queue.")
        # We're done here
        return

    # We check if there are any stream players in the server
    if len(server_queue_info_dict[message.server.id]["queue"]) == 0:
        # There is no audio playing in this server
        await client.send_message(message.channel,
                                  message.author.mention + ", there isn't anything in the queue on this server, so you can't remove anything from it.")
        # We're done here
        return

    # We parse the command and check if the specified volume is a valid non-negative integer
    clean_argument = helpers.remove_anna_mention(client, message)[len("queue remove "):].strip()

    if clean_argument.isdigit():
        # We check if the requested id is valid
        if int(clean_argument) < len(server_queue_info_dict[message.server.id]["queue"]):

            # We check if the specified id is the front of the queue and we are using playlists
            if int(clean_argument) == 0 and (server_queue_info_dict[message.server.id]["playlist_info"]["is_playing"]):
                # We stop the player, and we call the queue handler on it
                server_queue_info_dict[message.server.id]["queue"][0].stop()

                # We tell the user that we've removed the player from the queue
                await client.send_message(message.channel,
                                          message.author.mention + ", I've now removed it from the queue, but the playlist will continue.")

            else:
                # We stop the player, and it will be removed by the queue handler
                server_queue_info_dict[message.server.id]["queue"][int(clean_argument)].stop()

                # We tell the user that we've removed the player from the queue
                await client.send_message(message.channel,
                                          message.author.mention + ", I've now removed it from the queue.")

            # We log that we've removed the player from the queue
            helpers.log_info("Removed player at index {0} from queue on server {1} ({2}).".format(int(clean_argument),
                                                                                                  message.server.name,
                                                                                                  message.server.id))

        else:
            # The passed argument wasn't a valid number
            await client.send_message(message.channel, message.author.mention + ", that isn't a valid number.")
            # We're done here
            return

    else:
        # The passed argument wasn't a valid number
        await client.send_message(message.channel, message.author.mention + ", that isn't a valid number.")
        # We're done here
        return


@command_decorator.command("queue skip", "Alias for **queue remove 0**.")
@async_use_persistent_info_dict
@async_use_game_name_changer
async def cmd_voice_queue_remove(message: discord.Message, client: discord.Client, config: dict):
    """This method is an alias for queue remove 0."""

    # We check if the issuing user has the proper permissions on this server
    if not await permission_checker(message, client, config):
        # We're done here
        return

    # We check if the message was sent in a server where we are connected to a voice channel
    if client.voice_client_in(message.server) is None:
        # There is no voice client for this server
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm not connected to any voice channels on this server, so there isn't any queue.")
        # We're done here
        return

    # We check if there are any stream players in the server
    if (not message.server.id in server_queue_info_dict) or len(
            server_queue_info_dict[message.server.id]["queue"]) == 0:
        # There is no audio playing in this server
        await client.send_message(message.channel,
                                  message.author.mention + ", there isn't anything in the queue on this server, so you can't skip anything in it.")
        # We're done here
        return

    # We check if the specified id is the front of the queue and we are using playlists
    if server_queue_info_dict[message.server.id]["playlist_info"]["is_playing"]:
        # We stop the player, and we call the queue handler on it
        server_queue_info_dict[message.server.id]["queue"][0].stop()

        # We tell the user that we've removed the player from the queue
        await client.send_message(message.channel,
                                  message.author.mention + ", I've now skipped an entry in the current playlist, but the playlist will continue.")

    else:
        # We stop the player, and it will be removed by the queue handler
        server_queue_info_dict[message.server.id]["queue"][0].stop()

        # We tell the user that we've removed the player from the queue
        await client.send_message(message.channel,
                                  message.author.mention + ", I've now skipped an entry in the queue.")

    # We log that we've removed the player from the queue
    helpers.log_info("Skipped entry in queue on server {0} ({1}).".format(message.server.name, message.server.id))


@command_decorator.command("queue clear", "Clears the current voice queue, and stops the currently playing audio.")
@async_use_persistent_info_dict
@async_use_game_name_changer
async def cmd_voice_queue_clear(message: discord.Message, client: discord.Client, config: dict):
    """This method clears/resets the current queue for the server that ít was called from."""

    # We check if the issuing user has the proper permissions on this server
    if not await permission_checker(message, client, config):
        # We're done here
        return

    # We check if the message was sent in a server where we are connected to a voice channel
    if client.voice_client_in(message.server) is None:
        # There is no voice client for this server
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm not connected to any voice channels on this server, so there isn't any queue.")
        # We're done here
        return

    # We check if there are any stream players in the server
    if len(server_queue_info_dict[message.server.id]["queue"]) == 0:
        # There is no voice client for this server
        await client.send_message(message.channel,
                                  message.author.mention + ", there isn't anything in the queue on this server, so you can't clear it.")
        # We're done here
        return

    # We make sure that the current player is paused, by pausing it :)
    server_queue_info_dict[message.server.id]["queue"][0].pause()

    # We set the playlist info to not playing a playlist
    server_queue_info_dict[message.server.id]["playlist_info"]["is_playing"] = False
    server_queue_info_dict[message.server.id]["playlist_info"]["playlist_name"] = ""
    server_queue_info_dict[message.server.id]["playlist_info"]["current_index"] = -1

    # We clear the queue, note that this removes ALL references to the players within
    del server_queue_info_dict[message.server.id]["queue"][:]

    # We tell the user that we've cleared the queue
    await client.send_message(message.channel, message.author.mention + ", I've now cleared the queue.")

    # We log that we've cleared the queue
    helpers.log_info("Cleared queue on server {0} ({1}).".format(message.server.name, message.server.id))


@command_decorator.command("queue forward",
                           "Pauses the currently playing audio, moves the specified queue index to the front, and starts playing that instead.")
@async_use_persistent_info_dict
@async_use_game_name_changer
async def cmd_voice_queue_forward(message: discord.Message, client: discord.Client, config: dict):
    """This method brings a specified stream in the current queue (for the server that it was called from) forward to the front of the queue.
    It does not remove the currently playing stream, that's what the stop command does."""

    # We check if the issuing user has the proper permissions on this server
    if not await permission_checker(message, client, config):
        # We're done here
        return

    # We check if the message was sent in a server where we are connected to a voice channel
    if client.voice_client_in(message.server) is None:
        # There is no voice client for this server
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm not connected to any voice channels on this server, so there isn't any queue.")
        # We're done here
        return

    # We check if there are any stream players in the server
    if len(server_queue_info_dict[message.server.id]["queue"]) < 2:
        # There is no voice client for this server
        await client.send_message(message.channel,
                                  message.author.mention + ", there are too few items in the queue on this server to be able to move anything in it.")
        # We're done here
        return

    # We check if the server is playing a playlist as, if so, they can't forward anything
    if server_queue_info_dict[message.server.id]["playlist_info"]["is_playing"]:
        # Playing a playlist
        await client.send_message(message.channel,
                                  message.author.mention + ", I'm playing a playlist on this server, so you can't forward songs until you've turned off the playlist.")

        # We're done here
        return

    # We parse the command and check if the specified volume is a valid non-negative integer
    clean_argument = helpers.remove_anna_mention(client, message)[len(" queue forward"):].strip()

    if clean_argument.isdigit():
        # We check if the requested id is valid
        if 0 < int(clean_argument) < len(server_queue_info_dict[message.server.id]["queue"]):

            # We pause the currently playing player
            server_queue_info_dict[message.server.id]["queue"][0].pause()

            # We save the volume of the currently playing player
            last_volume = server_queue_info_dict[message.server.id]["queue"][0].volume

            # We move the specified player to the front
            server_queue_info_dict[message.server.id]["queue"].insert(0, server_queue_info_dict[message.server.id][
                "queue"].pop(
                int(clean_argument)))

            # We set the volume of the newly forwarded player
            server_queue_info_dict[message.server.id]["queue"][0].volume = last_volume

            # We resume the player
            server_queue_info_dict[message.server.id]["queue"][0].resume()

            # We tell the user that we've forwarded the player in the queue
            await client.send_message(message.channel,
                                      message.author.mention + ", I've now forwarded it to the front of the queue.")

            # We log that we've removed the player from the queue
            helpers.log_info(
                "Forwarded player at index {0} from queue on server {1} ({2}) to front of the queue.".format(
                    int(clean_argument), message.server.name, message.server.id))

        else:
            # The passed argument wasn't a valid number
            await client.send_message(message.channel,
                                      message.author.mention + ", that isn't a valid number. The valid range is 1 -> {0}.".format(
                                          len(server_queue_info_dict[message.server.id]["queue"])))
            # We're done here
            return

    else:
        # The passed argument wasn't a valid number
        await client.send_message(message.channel, message.author.mention + ", that isn't a valid number.")
        # We're done here
        return


@command_decorator.command("voice roles list", "Lists the roles that are allowed to issue voice commands.",
                           cmd_special_params=[False, True, False])
async def cmd_voice_permissions_list_allowed(message: discord.Message, client: discord.Client, config: dict,
                                             config_nope: dict):
    """This command lists the current allowed voice roles. It takes 2 config parameters because it has special param index 1 enabled, this means it can change the global config object"""

    # We check if the message was sent in a regular channel
    if not await pm_checker(message, client):
        # They can't execute the commands
        return [config]

    # We check if the user has the administrator permission
    if (not message.author.server_permissions.administrator) and (
            not helpers.is_member_anna_admin(message.author, config)):
        # We tell the user that they don't have permission to use this command
        await client.send_message(message.channel,
                                  message.author.mention + ", you do not have permission to use voice administration commands on this server. You need to have the \"Administrator\" permission on the server to use this command.")
        # No permission
        return [config]

    # We make sure that the server has a valid voice command roles list
    if not message.server.id in config["voice_command_roles"]:
        # We create the list
        config["voice_command_roles"][message.server.id] = []

    # We create the list message
    list_message = message.author.mention + ", here are the allowed voice roles:\n"

    # The list of invalid role id indices
    invalid_indices = []

    # We loop through the role ids
    for inx, role_id in enumerate(config["voice_command_roles"][message.server.id]):
        # We append the role info
        list_message += (("Role name: **{0}**, role id: *{1}*\n".format(
            *helpers.remove_discord_formatting(discord.utils.get(message.server.roles, id=role_id).name, role_id))) if (
            discord.utils.get(message.server.roles, id=role_id) is not None) else "")
        # We check if the role exists
        if discord.utils.get(message.server.roles, id=role_id) is None:
            # The roles doesn't exist, so we add the index to the invalid list
            invalid_indices.append(inx)

    # We remove all invalid role ids and write the new config out to file so we can reload it later
    for index in sorted(invalid_indices, reverse=True):
        del config["voice_command_roles"][message.server.id][index]
    # We write out the config
    helpers.write_config(config)

    # We check if the server has any valid voice command roles
    if len(config["voice_command_roles"][message.server.id]) == 0:
        # There are none left :(
        await client.send_message(message.channel,
                                  message.author.mention + ", this server doesn't have any voice command roles, so everyone is able to use voice commands.")

        # We're done here
        return [config]

    # We send the list message to the issuing user
    await helpers.send_long(client, list_message, message.channel)

    return [config]


@command_decorator.command("voice roles add",
                           "Adds a role to the list of roles that are allowed to issue voice commands.",
                           cmd_special_params=[False, True, False])
async def cmd_voice_permissions_add_allowed(message: discord.Message, client: discord.Client, config: dict,
                                            config_nope: dict):
    """This command adds a role to the current allowed voice roles, and writes it to the config."""

    # We check if the message was sent in a regular channel
    if not await pm_checker(message, client):
        # They can't execute the commands
        return [config]

    # We check if the user has the administrator permission
    if (not message.author.server_permissions.administrator) and (
            not helpers.is_member_anna_admin(message.author, config)):
        # We tell the user that they don't have permission to use this command
        await client.send_message(message.channel,
                                  message.author.mention + ", you do not have permission to use voice administration commands on this server. You need to have the \"Administrator\" permission on the server to use this command.")
        # No permission
        return [config]

    # We make sure that the server has a valid voice command roles list
    if not message.server.id in config["voice_command_roles"]:
        # We create the list
        config["voice_command_roles"][message.server.id] = []

    # We parse the user specified role, if it isn't valid, we tell the user and exit
    user_add_role = helpers.get_role_from_mention(message.author,
                                                  helpers.remove_anna_mention(client, message).strip()[
                                                  len("voice roles add "):])
    if user_add_role is None:
        # The role isn't valid
        await client.send_message(message.channel,
                                  message.author.mention + ", that isn't a valid role mention or doesn't exist on this server.")

        # We're done here
        return [config]

    # We check if the role already exists in the allowed command roles
    if user_add_role.id in config["voice_command_roles"][message.server.id]:
        # We tell the user that it's already in the list
        await client.send_message(message.channel,
                                  message.author.mention + ", that role is already configured as an allowed role.")

        # We're done here
        return [config]

    # We add the role to the config
    config["voice_command_roles"][message.server.id].append(user_add_role.id)

    # We write out the config to file, and tell the user that we're done
    helpers.write_config(config)

    await client.send_message(message.channel, message.author.mention + ", I've now added it to the allowed role list.")
    return [config]


@command_decorator.command("voice roles remove",
                           "Removes a role from the list of roles that are allowed to issue voice commands.",
                           cmd_special_params=[False, True, False])
async def cmd_voice_permissions_remove_allowed(message: discord.Message, client: discord.Client, config: dict,
                                               config_nope: dict):
    """This command removes a role to the current allowed voice roles, and writes it to the config."""

    # We check if the message was sent in a regular channel
    if not await pm_checker(message, client):
        # They can't execute the commands
        return [config]

    # We check if the user has the administrator permission
    if (not message.author.server_permissions.administrator) and (
            not helpers.is_member_anna_admin(message.author, config)):
        # We tell the user that they don't have permission to use this command
        await client.send_message(message.channel,
                                  message.author.mention + ", you do not have permission to use voice administration commands on this server. You need to have the \"Administrator\" permission on the server to use this command.")
        # No permission
        return [config]

    # We make sure that the server has a valid voice command roles list
    if not message.server.id in config["voice_command_roles"]:
        # We create the list
        config["voice_command_roles"][message.server.id] = []

    # We parse the user specified role, if it isn't valid, we tell the user and exit
    user_add_role = helpers.get_role_from_mention(message.author,
                                                  helpers.remove_anna_mention(client, message).strip()[
                                                  len("voice roles add "):])
    if user_add_role is None:
        # The role isn't valid
        await client.send_message(message.channel,
                                  message.author.mention + ", that isn't a valid role mention or doesn't exist on this server.")

        # We're done here
        return [config]

    # We check if the role doesn't exists in the allowed command roles
    if user_add_role.id not in config["voice_command_roles"][message.server.id]:
        # We tell the user that it's not in the list
        await client.send_message(message.channel,
                                  message.author.mention + ", that role is not configured as an allowed role.")

        # We're done here
        return [config]

    # We remove the role from the config
    config["voice_command_roles"][message.server.id].remove(user_add_role.id)

    # We write out the config to file, and tell the user that we're done
    helpers.write_config(config)

    await client.send_message(message.channel,
                              message.author.mention + ", I've now removed it from the allowed role list.")
    return [config]


async def permission_checker(message: discord.Message, client: discord.Client, config: dict):
    """This checks if the command issuer has the proper permissions on their server to use voice commands. It also makes sure that the command was not issued in a private channel.
    If the user is allowed to use commands, it returns true, otherwise, it returns false"""

    # We check if the message was sent in a regular channel
    if not await pm_checker(message, client):
        # They can't execute the commands
        return False

    # We check if the server has configured allowed voice roles
    if message.server.id in config["voice_command_roles"]:
        # We check if the issuing user has an allowed role
        if not any(i in config["voice_command_roles"][message.server.id] for i in [x.id for x in message.author.roles]):
            # We check if the server purposefully doesn't have any roles
            if len(config["voice_command_roles"][message.server.id]) > 0:
                # The user does not have permission to use the command
                await client.send_message(message.channel,
                                          message.author.mention + ", you do not have permission to use voice commands on this server.")
                # No permission
                return False

    # They can and are allowed to execute the commands
    return True


async def pm_checker(message: discord.Message, client: discord.Client):
    """This method checks if the passed message is in PM or not.
    Returns True if the message was not sent in a PM, else returns false."""

    # We check if the message was sent in a regular channel
    if message.channel.is_private:
        # There are no voice commands for pms
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels, and there can therefore not belong any queues to them.")
        # They can't execute the commands
        return False
    return True


def is_playing(server_id: str):
    """This method checks if we are have any active players on the passed server.
    Returns True if we are playing something (len(queue) >= 1).
    Returns False if we aren't (this includes not having setup a voice info object)."""
    if server_queue_info_dict.get(server_id) is not None:
        # We check if we're playing anything
        return len(server_queue_info_dict[server_id]["queue"]) >= 1
    else:
        return False


def find_stream_player(stream_player):
    """This method returns the server id and queue index of a stream player, returns (False, False, False) if they don't exist."""

    # If we found the stream player that we got passed (This will always be true, but this variable is used for signaling)
    found = True

    # We find the exited streamplayer in the server and info list Since we have no info on which server the streamplayer is playing on, we have to use id()
    for server_id in server_queue_info_dict:
        for inx_player, player in enumerate(server_queue_info_dict[server_id]["queue"]):
            if stream_player is player:
                found = True
                break

        if found:
            break

    # We make sure the impossible doesn't happen
    if not found:
        # We didn't find the stream player that was passed to us, which should never happen
        helpers.log_error("Did not find the streamplayer that was passed to the find function, report the bug?")
        return

    return server_id, inx_player


def handle_audio_title_game_name():
    """Checks if we should change our game title to the title of the currently playing audio, and does so if we should."""

    # Here we set our "Currently playing" message, but only if we're only playing 1 audio stream, otherwise we set it empty
    playing_servers_list = list(
        {server_id: info for server_id, info in server_queue_info_dict.items() if len(info["queue"]) > 0}.values())

    if len(playing_servers_list) == 1:
        helpers.playing_game_info = [True, playing_servers_list[0]["queue"][0].title]

    else:
        if not helpers.playing_game_info[1] == "":
            helpers.playing_game_info = [True, ""]

@use_persistent_info_dict
def queue_handler(current_player):
    """This method gets called after each streamplayer stops, with current_player being the player that exited.
    It handles removing the player from the server's queue, and starting playing the next in the queue, or if the server uses playlists, it starts the next audio feed in the playlist."""

    # We save the volume of the exited stream
    last_volume = current_player.volume

    # We find the stream player in the server voice info dict
    server_id, inx_player = find_stream_player(current_player)

    # We log that we are handling the end of a player
    helpers.log_info(
        "Audio feed with title: \"{0}\", uploaded by: \"{1}\", duration: {2}, exited, handling server queue.".format(
            current_player.title, current_player.uploader, current_player.duration))

    # We delete the old stream player
    del server_queue_info_dict[server_id]["queue"][inx_player]

    # Here we split the logic to handle playlists (not youtube-like playlists, I mean the file playlists)
    # We also check that the exhausted/stopped player causes a new player to become the first player, as if not, we shouldn't load a new playlist entry
    if server_queue_info_dict[server_id]["playlist_info"]["is_playing"] and inx_player == 0:

        # We do playlist logic, and check whether it succeeded
        if update_server_playlist(server_id, last_volume):
            # We're done here
            return
        else:
            # We weren't able to play the next playlist entry, so we disable playlists
            pass

    # We aren't using playlists if we get to this code, so we disable playlists, and play the next audio feed in the queue
    server_queue_info_dict[server_id]["playlist_info"]["is_playing"] = False
    server_queue_info_dict[server_id]["playlist_info"]["current_index"] = -1
    server_queue_info_dict[server_id]["playlist_info"]["playlist_name"] = ""

    # We aren't playing a playlist file
    # We check if the server has any more players in the queue
    if len(server_queue_info_dict[server_id]["queue"]) == 0:
        helpers.log_info(
            "Server on which audio feed with title: \"{0}\", uploaded by: \"{1}\", duration: {2}, played, has exhausted it's queue.".format(
                current_player.title, current_player.uploader, current_player.duration))
        # We're done here
        return

    # We check if there is a new first player in the server queue
    if inx_player == 0:
        # We set the volume and start the new first player in the queue
        server_queue_info_dict[server_id]["queue"][0].volume = last_volume
        server_queue_info_dict[server_id]["queue"][0].start()

        current_player = server_queue_info_dict[server_id]["queue"][0]

        # We log that the new player is playing, and that we're done with the queue handling
        helpers.log_info(
            "Now playing audio feed with title: \"{0}\", uploaded by: \"{1}\", duration: {2}, and done with handling server queue.".format(
                current_player.title, current_player.uploader, current_player.duration))

        # We handle the game name
        handle_audio_title_game_name()


@use_persistent_info_dict
def insert_start_player_future_in_queue(player_future, server_id: str, target_volume: float, index: int):
    """This function is used as a add_done_callback callback for adding a streamplayer to a servers queue in a specified position."""
    # We try to get the streamplayer from the future, and we catch and report errors

    try:
        player = player_future.result()

    except youtube_dl.DownloadError:
        # The URL failed to load, it's probably invalid
        helpers.log_info(
            "Was not able to load playlist entry at index {0} in playlist {1} because of a youtube_dl.DownloadError. Trying next entry in the playlist.".format(
                index, server_queue_info_dict[server_id]["playlist_info"]["playlist_name"]))

        # We try again with the next entry in the playlist
        if update_server_playlist(server_id, target_volume):
            # We managed to create a new ytdl_player, or atleast try to do it
            helpers.log_info("New ytdl player is going to be created.")
        else:
            # We failed
            helpers.log_info("Was not able to create a new ytdl_player.")

        # We're done here
        return

    except ConnectionClosed:
        # This can happen with code 1000 "No reason"...

        # The URL failed to load, it's probably invalid
        helpers.log_info(
            "Was not able to load playlist entry at index {0} in playlist {1} because of a websockets.exceptions.ConnectionClosed error. Trying next entry in the playlist.".format(
                index, server_queue_info_dict[server_id]["playlist_info"]["playlist_name"]))

        # We try again with the next entry in the playlist
        if update_server_playlist(server_id, target_volume):
            # We managed to create a new ytdl_player, or atleast try to do it
            helpers.log_info("New ytdl player is going to be created.")
        else:
            # We failed
            helpers.log_info("Was not able to create a new ytdl_player.")

        # We're done here
        return

    except Exception as e:
        # Unknown error
        helpers.log_info(
            "Was not able to load playlist entry at index {0} in playlist {1} because of an unknown error. Stopping playlist. Info: {2}".format(
                index, server_queue_info_dict[server_id]["playlist_info"]["playlist_name"], str(e)))

        # If this was an error stemming from the event loop closing, this probably means that the bot was exited, so we just exit, and don't stop playing
        if isinstance(e, concurrent.futures.CancelledError):
            return

        # We aren't using playlists if we get to this code, so we disable playlists, and play the next audio feed in the queue
        server_queue_info_dict[server_id]["playlist_info"]["is_playing"] = False
        server_queue_info_dict[server_id]["playlist_info"]["current_index"] = -1
        server_queue_info_dict[server_id]["playlist_info"]["playlist_name"] = ""

        # We're done here, and we don't retry
        return

    # We catch exception from trying to insert into a queue on a server that doesn't have a voice info object anymore
    try:
        # We insert the streamplayer into the server's queue
        server_queue_info_dict[server_id]["queue"].insert(index, player)
    except KeyError as e:
        helpers.log_info(
            "Was not able to add audio feed to server with id {0} as there was no voice info for that server.".format(
                server_id))

        # We're done here
        return

    # We set the target volume, and if the player is at the beginning of the queue, we start it and pause the previous first
    player.volume = target_volume
    if index == 0:
        player.start()
        if len(server_queue_info_dict[server_id]["queue"]) > 1:
            server_queue_info_dict[server_id]["queue"][1].pause()

    # We log what video title and uploader the played audio has
    helpers.log_info(
        "Added to index {4} in queue, audio with title: \"{0}\", uploaded by: \"{1}\". This was entry {2} in playlist {3}.".format(
            player.title,
            ("N/A" if player.uploader is None else player.uploader),
            server_queue_info_dict[server_id]["playlist_info"]["current_index"],
            server_queue_info_dict[server_id]["playlist_info"]["playlist_name"], index))

    # We handle the game name
    handle_audio_title_game_name()

@use_persistent_info_dict
def update_server_playlist(server_id: str, target_volume: float):
    """This method is used to move to the next entry in a playlist on a server.
    It doesn't check if the current entry is playing.
    Returns False if it wasn't able to begin ytdl_player creation. Else returns False."""

    # We check if we can read the playlist file
    try:
        with open(os.path.join("playlists", server_queue_info_dict[server_id]["playlist_info"]["playlist_name"]),
                  mode="r", encoding="utf-8") as playlist_file:

            # Performance
            target_line = server_queue_info_dict[server_id]["playlist_info"]["current_index"] + 1
            # We loop back to the beginning of the playlist if we reached the end
            target_line = 0 if target_line == sum(1 for _ in playlist_file) else target_line

            # We seek back to the beginning of the file, so we can loop over it again, this took me like 1 hour to debug...
            playlist_file.seek(0)

            # We search through the file to the line on which the new link should exist
            for inx, line in enumerate(playlist_file):
                # We check if we're reached the target line (current index + 1)
                if inx == target_line:
                    # We reached the target line, so we create a new stream player (CTRL+C CTRL+V of voice play link)
                    # We need to catch some errors
                    # The client
                    client = helpers.actual_client

                    # The voice channel we're connected to, we check that it exists, as some playlists with broken links may trigger this code when the voice client for the server has been removed
                    voice = client.voice_client_in(client.get_server(server_id))

                    # We make sure we're connected to the right channel, by reconnecting to the right channel
                    # Do note that this does 2 things:
                    # If the bot is not connected to the server, but should be (which it should be at this stage in the code), it connects to the original channel it joined
                    # Otherwise, it DOES NOT move itself between channels, but simply does nothing
                    connection_coro = client.join_voice_channel(
                        client.get_channel(server_queue_info_dict[server_id]["channel_id"]))
                    connection_fut = asyncio.run_coroutine_threadsafe(connection_coro, client.loop)

                    # We check if we're connected to a voice channel
                    if voice is None:
                        try:
                            voice = connection_fut.result()

                            # We check that we're connected
                            if voice is None:
                                helpers.log_info(
                                    "Could not handle queue, as server ({0}) did not have a voice client.".format(
                                        server_id))
                                # We're done here
                                return False

                        except Exception:
                            # We don't accept errors
                            helpers.log_info(
                                "Could not handle queue, as we got an error when we tried to connect to channel {1} on server ({0})".format(
                                    server_id, server_queue_info_dict[server_id]["channel_id"]))
                            # We're done here
                            return False

                    # We have the correct line, so we try to create a ytdl player
                    # I found these ytdl options here: https://github.com/rg3/youtube-dl/blob/master/youtube_dl/YoutubeDL.py https://github.com/rg3/youtube-dl/blob/e7ac722d6276198c8b88986f06a4e3c55366cb58/README.md
                    youtube_player_future = asyncio.run_coroutine_threadsafe(
                        voice.create_ytdl_player(line.strip(), ytdl_options={"noplaylist": True},
                                                 after=queue_handler), client.loop)

                    # We register a callback to the future, so it adds the player to the first position in the queue when ytdl is done
                    youtube_player_future.add_done_callback(
                        lambda x: insert_start_player_future_in_queue(x, server_id, target_volume, 0))

                    # We update the playlist index
                    server_queue_info_dict[server_id]["playlist_info"]["current_index"] = target_line

                    # We succeeded in loading a new playlist entry, and we've logged it, so we're done
                    return True

    except IOError as e:
        # We weren't able to open the playlist file, so we go back to using the regular queue
        # But we log it

        # The voice channel we're connected to, we check that it exists, as some playlists with broken links may trigger this code when the voice client for the server has been removed
        voice = client.voice_client_in(client.get_server(server_id))

        # We check that it exists
        if voice is None:
            helpers.log_info(
                "Could not handle queue, as server ({0}) did not have a voice client.".format(
                    server_id))
            # We're done here
            return False

        helpers.log_info(
            "Wasn't able to load playlist file {0} to continue playing playlist on server {1} ({2}), because of an IOError.".format(
                os.path.join("playlists", server_queue_info_dict[server_id]["playlist_info"]["playlist_name"]),
                voice.server.name, voice.server.id))

        return False
