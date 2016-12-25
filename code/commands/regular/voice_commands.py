import re
import urllib.parse
import urllib.request

import discord

from ... import helpers

"""This file handles the voice channel interactions, state, and commands."""

# The dict of lists of stream players, where [0] is the currently playing, and the other ones are ordered correspondingly)
server_and_queue_dict = {}


async def cmd_join_voice_channel(message: discord.Message, client: discord.Client, config: dict,
                                 ignored_command_message_ids: list):
    """This command is issued to make anna join a voice channel if she has access to it on the server where this command was issued."""

    # We check if the command was issued in a PM or in a regular server, so we can tell user not to be an idiot
    if message.channel.is_private:

        # This message was sent in a private channel, and we can therefore deduce that the user is about as smart as Eva
        await client.send_message(message.author,
                                  "There aren't any voice channels in private messages you know, so I can't really join one.")
    else:

        # Removing the anna-bot mention
        cleaned_message = helpers.remove_anna_mention(client, message)

        # The user is not an idiot, so we parse the message for the voice channel name, if there are two or more channels with the same name, we tell the user to choose between them using channel order numbers that we give to them depending on the channel IDs
        voice_channel_name = cleaned_message[11:]

        # Checking how many voice channels in the server match the given name. If none match, we try to strip the name (the user might have been an idiot contrary to popular belief)
        num_matching_voice_channels = [
            (channel.type == discord.ChannelType.voice) and (channel.name == voice_channel_name) for channel in
            message.server.channels].count(True)

        # You can't be connected to multiple voice channels at the same time
        if not client.is_voice_connected(message.server):

            # We check to see if we have permissions to join the voice channel
            if not message.channel.permissions_for(message.server.me).connect:
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
                                              message.author.mention + ", there are %i voice channels on this server with that name, please message me the number of the channel that you want me to join within 1 minute (e.g. \"@anna-bot 0\"):\n--------------------" % len(
                                                  channel_candidates) + "".join([(
                                                                                     "\nNumber %s:\n\t%s users currently connected.\n--------------------" % (
                                                                                         str(candidate[1]), str(len(
                                                                                             candidate[
                                                                                                 0].voice_members))))
                                                                                 for candidate in
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
                                              message.author.mention + ", there are %i voice channels on this server with that name, please message me the number of the channel that you want me to join within 1 minute (e.g. \"@anna-bot 0\"):\n--------------------" % len(
                                                  channel_candidates) + "".join([(
                                                                                     "\nNumber %s:\n\t%s users currently connected.\n--------------------" % (
                                                                                         str(candidate[1]), str(len(
                                                                                             candidate[
                                                                                                 0].voice_members))))
                                                                                 for candidate in
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
        server_and_queue_dict[message.server.id] = []

        return ignored_command_message_ids


async def cmd_leave_voice_channel(message: discord.Message, client: discord.Client, config: dict):
    """This command is issued to make anna leave a voice channel if she is connected to it on the server where this command was issued."""

    # We check if the command was issued in a PM
    if not message.channel.is_private:
        # We check if we were connected to a voice channel on the server where this command was issued
        if client.is_voice_connected(message.server):
            # We tell the issuing user that we've left the server
            await client.send_message(message.channel,
                                      message.author.mention + ", I'm leaving the \"%s\" voice channel right now." % client.voice_client_in(
                                          message.server).channel.name)

            # We check if there are any stream players currently playing on that voice channel
            for stream in server_and_queue_dict[message.server.id]:
                # We stop the player, but we also set the volume to 0 to prevent the queuehandler to make wierd noises
                stream.volume = 0
                stream.stop()

            # We remove the stopped queue
            del server_and_queue_dict[message.server.id]

            # We leave the voice channel that we're connected to on that server
            await client.voice_client_in(message.server).disconnect()

        else:
            # We aren't connected to a voice channel on the current server, the user is just being an idiot
            await client.send_message(message.channel,
                                      message.author.mention + ", I'm not connected to a voice channel on this server, if you want me to connect to one, please use the \"@anna-bot voice join CHANNELNAME\" command.")
    else:
        # The command was issued in a PM
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels.")


async def cmd_voice_play_youtube(message: discord.Message, client: discord.Client, config: dict):
    """This command is used to queue up the audio of a youtube video at the given link, to the server's queue."""

    # We check if the command was issued in a PM
    if not message.channel.is_private:

        # We parse the url from the command message
        youtube_url = helpers.remove_anna_mention(client, message).strip()[19:]

        # We get the voice client on the server in which the command was issued
        voice = client.voice_client_in(message.server)

        # We check if we're connected to a voice channel in the server where the command was issued
        if voice is None:

            # We are not connected to a voice channel, so we tell the user to fuck off
            await client.send_message(message.channel,
                                      message.author.mention + ", I'm not connected to any voice channels on this server, so I can't play any audio.")

        else:

            # We're connected to a voice channel, so we try to create the ytdl stream player
            youtube_player = await voice.create_ytdl_player(youtube_url, after=queue_handler)

            # We append the streamplayer to the server's queue
            server_and_queue_dict[message.server.id].append(youtube_player)

            # If the server doesn't have any currently playing stream players, we start the new stream player
            if len(server_and_queue_dict[message.server.id]) == 1:
                youtube_player.start()

                # Telling the user that we're playing the video
                await client.send_message(message.channel,
                                          message.author.mention + ", I added and started playing, youtube video with title: \"%s\", uploaded by: \"%s\" to the queue. (User \"" + client.user.mention + " voice queue list\" to see the current queue)" % (
                                              youtube_player.title, youtube_player.uploader))

                # We log what video title and uploader the played video has
                helpers.log_info(
                    "Added youtube and started playing, video with title: \"%s\", uploaded by: \"%s\", to queue in voice channel: \"%s\" on server: \"%s\"" % (
                        youtube_player.title, youtube_player.uploader, voice.channel.name, voice.server.name))

                # We're done here
                return

            # Telling the user that we're playing the video
            await client.send_message(message.channel,
                                      message.author.mention + ", I added youtube video with title: \"%s\", uploaded by: \"%s\" to the queue. (User \"" + client.user.mention + " voice queue list\" to see the current queue)" % (
                                          youtube_player.title, youtube_player.uploader))

            # We log what video title and uploader the played video has
            helpers.log_info(
                "Added youtube video with title: \"%s\", uploaded by: \"%s\", to queue in voice channel: \"%s\" on server: \"%s\"" % (
                    youtube_player.title, youtube_player.uploader, voice.channel.name, voice.server.name))

    else:
        # The command was issued in a PM
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels.")


async def cmd_voice_play_youtube_search(message: discord.Message, client: discord.Client, config: dict):
    """This method is used to add a youtube video to the server queue by picking the top search result from youtube on the specified query."""

    # We check if the command was issued in a PM
    if not message.channel.is_private:

        # We parse the url from the command message
        user_query = helpers.remove_anna_mention(client, message).strip()[len(" voice play search "):]

        # We get the voice client on the server in which the command was issued
        voice = client.voice_client_in(message.server)

        # We check if we're connected to a voice channel in the server where the command was issued
        if voice is None:

            # We are not connected to a voice channel, so we tell the user to fuck off
            await client.send_message(message.channel,
                                      message.author.mention + ", I'm not connected to any voice channels on this server, so I can't play any audio.")

        else:

            # I got this code from https://www.codeproject.com/Articles/873060/Python-Search-Youtube-for-Video
            query_string = urllib.parse.urlencode({"search_query": user_query})
            html_content = urllib.request.urlopen("http://www.youtube.com/results?" + query_string)
            search_results = re.findall("href=\"\/watch\?v=(.{11})", html_content.read().decode())
            helpers.log_info(
                "Searched youtube for {0} and got result http://www.youtube.com/watch?v={1} to add to queue on channel {2} ({3}) on server {4} ({5}).".format(
                    user_query, search_results[0], voice.channel.name, voice.channel.id, message.server.name,
                    message.server.id))

            # We're connected to a voice channel, so we try to create the ytdl stream player with the search result we got
            youtube_player = await voice.create_ytdl_player(
                "http://www.youtube.com/watch?v={1}".format(search_results[0]), after=queue_handler)

            # We append the streamplayer to the server's queue
            server_and_queue_dict[message.server.id].append(youtube_player)

            # If the server doesn't have any currently playing stream players, we start the new stream player
            if len(server_and_queue_dict[message.server.id]) == 1:
                youtube_player.start()

    else:
        # The command was issued in a PM
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels.")

# TODO remake
async def cmd_voice_sound_effect(message: discord.Message, client: discord.Client, config: dict):
    """This method is used to play a sound effect in the voice channel anna is connected to on the issuing server."""

    # We check if the command was issued in a PM
    if not message.channel.is_private:

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

    else:
        # The command was issued in a PM
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels.")


async def cmd_voice_set_volume(message: discord.Message, client: discord.Client, config: dict):
    """This command is used to change the volume of the audio that anna plays."""

    # We first check if the command was issued in a PM channel
    if not message.channel.is_private:
        # We check if there we are connected to a voice channel on this server
        if client.voice_client_in(message.server) is not None:

            # We check if we found any stream players
            if len(server_and_queue_dict[message.server.id]) > 0:

                # We parse the command and check if the specified volume is a valid non-negative integer
                clean_argument = helpers.remove_anna_mention(client, message)[13:].strip()

                if clean_argument.isdigit():

                    # We create an int from the string and clamp it between 0-2 (inclusive on both ends)
                    volume = min(max(int(clean_argument), 0), 200) / 100

                    # We set the volume of the currently playing player to be the desired volume
                    # Setting the volume of the stream player
                    server_and_queue_dict[message.server.id][0].volume = volume

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

    else:
        # The command was issued in a PM channel, so we tell the user to fuck off
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels.")


async def cmd_voice_play_toggle(message: discord.Message, client: discord.Client, config: dict):
    """This method is used to toggle playing (pausing and unpausing) the currently playing stream player in that server (if there is one)."""

    # We check if the command was issued in a PM
    if not message.channel.is_private:

        # The command was issued in a regular channel
        # We check if there we are connected to a voice channel on this server
        if client.voice_client_in(message.server) is not None:

            # We check if there are any player's in the current queue
            if len(server_and_queue_dict[message.server.id]) > 0:

                # The player that is currently at the front of the queue
                current_player = server_and_queue_dict[message.server.id][0]

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

    else:
        # The command was issued in a PM
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels.")


async def cmd_voice_play_stop(message: discord.Message, client: discord.Client, config: dict):
    """This method is used to stop and remove the currently playing audio from anna in a server. This basically does queue.pop()"""

    # We check if the command was issued in a PM
    if not message.channel.is_private:

        # The command was issued in a regular channel
        # We check if there we are connected to a voice channel on this server
        if client.voice_client_in(message.server) is not None:

            # We check if there are any currently playing players
            if len(server_and_queue_dict[message.server.id]) > 0:

                # The commands issuer's server and its queue and currently playing player
                server_queue = server_and_queue_dict[message.server.id]
                current_player = server_queue[0]

                # We log that we are handling the end of a player
                helpers.log_info(
                    "Youtube video with title: \"{0}\", uploaded by: \"{1}\", duration: {2}, was stopped by the stop command, handling server queue.".format(
                        current_player.title, current_player.uploader, current_player.duration))

                # We store the volume of the player
                last_volume = current_player.volume

                # We stop the currently playing player
                current_player.stop()

                # We set the volume of the next player to the volume of the exited one
                server_queue[1].volume = last_volume

                # We start the new player, and remove the old one from the queue
                server_queue[1].start()
                del server_queue[0]

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

    else:
        # The command was issued in a PM
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels.")


async def cmd_voice_queue_list(message: discord.Message, client: discord.Client, config: dict):
    """This method shows the audio current queue for the server that it was called from."""

    # We check if the message was sent in a regular channel
    if message.channel.is_private:
        # There are no queues for pms
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels, and there can therefore not belong any queues to them.")
        # We're done here
        return

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
    if len(server_and_queue_dict[message.server.id]) == 0:
        # Nothing in the queue
        await client.send_message(message.channel, message.author.mention + ", this server's queue is empty.")
        # We're done here
        return

    # We loop through the queue
    for inx, player in enumerate(server_and_queue_dict[message.server.id]):
        queue_message += "-------------------------\n\tNr. **" + str(inx) + "**, *" + player.title + (
            "*. **Currently playing this**" if inx == 0 else "*") + "\nBy *" + player.uploader + "* at URL __" + player.url + "__\n" + \
                         "Duration: " + player.duration + " seconds.\nDescription:\n\t" + player.description + "-------------------------\n"

    # We send the queue message
    helpers.send_long(client, message.author.mention + ", here is the current queue:\n" + queue_message,
                      message.channel)


async def cmd_voice_queue_remove(message: discord.Message, client: discord.Client, config: dict):
    """This method removes a specified stream from the current queue for the server that it was called from."""

    # We check if the message was sent in a regular channel
    if message.channel.is_private:
        # There are no queues for pms
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels, and there can therefore not belong any queues to them.")
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
    if len(server_and_queue_dict[message.server.id]) == 0:
        # There is no voice client for this server
        await client.send_message(message.channel,
                                  message.author.mention + ", there isn't anything in the queue on this server, so you can't remove anything from it.")
        # We're done here
        return

    # We parse the command and check if the specified volume is a valid non-negative integer
    clean_argument = helpers.remove_anna_mention(client, message)[len(" voice queue remove "):].strip()

    if clean_argument.isdigit():
        # We check if the requested id is valid
        if int(clean_argument) < len(server_and_queue_dict[message.server.id]):

            # We check if the specified id is the front of the queue
            if int(clean_argument) == 0:
                # We check if the player is done
                if server_and_queue_dict[message.server.id][0].is_done():
                    # We delete the player
                    del server_and_queue_dict[message.server.id][0]
                else:
                    # We stop the player, and it will be removed by the queue handler
                    server_and_queue_dict[message.server.id][0].stop()

            else:
                # We delete the player
                del server_and_queue_dict[message.server.id][int(clean_argument)]

            # We tell the user that we've removed the player from the queue
            await client.send_message(message.channel, message.author.mention + ", I've now removed it from the queue.")

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


async def cmd_voice_queue_clear(message: discord.Message, client: discord.Client, config: dict):
    """This method clears/resets the current queue for the server that ít was called from."""

    # We check if the message was sent in a regular channel
    if message.channel.is_private:
        # There are no queues for pms
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels, and there can therefore not belong any queues to them.")
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
    if len(server_and_queue_dict[message.server.id]) == 0:
        # There is no voice client for this server
        await client.send_message(message.channel,
                                  message.author.mention + ", there isn't anything in the queue on this server, so you can't clear it.")
        # We're done here
        return

    # We make sure that the current player is paused, by pausing it :)
    server_and_queue_dict[message.server.id][0].pause()

    # We clear the queue, note that this removes ALL references to the players within
    del server_and_queue_dict[message.server.id]

    # We tell the user that we've cleared the queue
    await client.send_message(message.channel, message.author.mention + ", I've now cleared the queue.")

    # We log that we've cleared the queue
    helpers.log_info("Cleared queue on server {0} ({1}).".format(message.server.name, message.server.id))


async def cmd_voice_queue_forward(message: discord.Message, client: discord.Client, config: dict):
    """This method brings a specified stream in the current queue (for the server that it was called from) forward to the front of the queue.
    It does not remove the currently playing stream, that's what the stop command does."""

    # We check if the message was sent in a regular channel
    if message.channel.is_private:
        # There are no queues for pms
        await client.send_message(message.author,
                                  "This is a PM channel, there are no voice channels belonging to PM channels, and there can therefore not belong any queues to them.")
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
    if len(server_and_queue_dict[message.server.id]) < 2:
        # There is no voice client for this server
        await client.send_message(message.channel,
                                  message.author.mention + ", there isn't anything in the queue on this server, so you move anything in it.")
        # We're done here
        return

    # We parse the command and check if the specified volume is a valid non-negative integer
    clean_argument = helpers.remove_anna_mention(client, message)[len(" voice queue forward "):].strip()

    if clean_argument.isdigit():
        # We check if the requested id is valid
        if 0 < int(clean_argument) < len(server_and_queue_dict[message.server.id]):

            # We pause the currently playing player
            server_and_queue_dict[message.server.id][0].pause()

            # We save the volume of the currently playing player
            last_volume = server_and_queue_dict[message.server.id].volume

            # We move the specified player to the front
            server_and_queue_dict[message.server.id].insert(0, server_and_queue_dict[message.server.id].pop(
                int(clean_argument)))

            # We set the volume of the newly forwarded player
            server_and_queue_dict[0].volume = last_volume

            # We resume the player
            server_and_queue_dict[0].resume()

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
                                          len(server_and_queue_dict[message.server.id])))
            # We're done here
            return

    else:
        # The passed argument wasn't a valid number
        await client.send_message(message.channel, message.author.mention + ", that isn't a valid number.")
        # We're done here
        return


def queue_handler(current_player):
    """This method gets called after each streamplayer stops, with current_player being the player that exited.
    It handles removing the player from the server's queue, and starting playing the next in the queue"""

    # We save the volume of the exited stream
    last_volume = current_player.volume

    # If we found the stream player that we got passed (This will always be true, but this variable is used for signaling)
    found = True

    # We find the exited streamplayer in the server and queue pair list Since we have no info on which server the streamplayer is playing on, we have to use id()
    for server_id in server_and_queue_dict:
        for inx_player, player in enumerate(server_and_queue_dict[server_id]):
            if current_player is player:
                found = True
                break

        if found:
            break

    # We log that we are handling the end of a player
    helpers.log_info(
        "Youtube video with title: \"{0}\", uploaded by: \"{1}\", duration: {2}, exited, handling server queue.".format(
            current_player.title, current_player.uploader, current_player.duration))

    # We make sure the impossible doesn't happen
    if not found:
        # We didn't find the stream player that was passed to us, which should never happen
        helpers.log_error("Did not find the streamplayer that was passed to the queue function, report the bug?")
        return

    # We check if the server has any more players in the queue
    if len(server_and_queue_dict[server_id]) == 1:
        helpers.log_info(
            "Server on which youtube video with title: \"{0}\", uploaded by: \"{1}\", duration: {2}, played, has exhausted it's queue.".format(
                current_player.title, current_player.uploader, current_player.duration))
        # We're done here
        return

    # We delete the old stream player
    del server_and_queue_dict[server_id][inx_player]

    # We set the volume and start the new first player in the queue
    server_and_queue_dict[server_id][0].volume = last_volume
    server_and_queue_dict[server_id][0].start()

    # We log that the new player is playing, and that we're done with the queue handling
    helpers.log_info(
        "Now playing youtube video with title: \"{0}\", uploaded by: \"{1}\", duration: {2}, and done with handling server queue.".format(
            current_player.title, current_player.uploader, current_player.duration))