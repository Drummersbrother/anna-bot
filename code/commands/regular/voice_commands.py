import discord

from ... import helpers

"""This file handles the voice channel interactions, state, and commands."""

# The list of tuples of voice stream players and server ids
server_and_stream_players = []


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

        # Everything should have exited if something went wrong by this stage, so we can safely assume that it's fine to connect to the voice channel that the user has programmed
        # Telling the user that we found the channel and that we are joining right now
        await client.send_message(message.channel,
                                  message.author.mention + ", ok, I'm joining \"%s\" right now." % voice_channel_name)

        # Joining the channel
        await client.join_voice_channel(voice_channel)


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
            for server_stream_pair in server_and_stream_players:

                # Checking if the server id matches the issuing user's server's id
                if server_stream_pair[0] == message.server.id:
                    # We stop the player
                    server_stream_pair[1].stop()

            # We remove the stopped entries in the list of players
            server_and_stream_players[:] = [x for x in server_and_stream_players if not x[1].is_done()]

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
    """This command is used to play the audio of a youtube video at the given link."""

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

            # We check if there already exists a stream player for this server, if so, we terminate it and start playing the given video
            for server_stream_pair in server_and_stream_players:

                # Checking if the server id matches the issuing user's server's id
                if server_stream_pair[0] == message.server.id:
                    # We stop the player
                    server_stream_pair[1].stop()

            # We remove the stopped entries in the list of players
            server_and_stream_players[:] = [x for x in server_and_stream_players if not x[1].is_done()]

            # We're connected to a voice channel, so we try to create the ytdl stream player
            youtube_player = await voice.create_ytdl_player(youtube_url)

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

            found_stream_player = False

            # We check if we have a stream player playing something on the server
            for server_stream_pair in server_and_stream_players:

                # Checking if the server id matches the issuing user's server's id
                if server_stream_pair[0] == message.server.id:
                    # We note that we found atleast one stream player playing something
                    found_stream_player = True

            # We check if we found any stream players
            if found_stream_player:

                # We parse the command and check if the specified volume is a valid non-negative integer
                clean_argument = helpers.remove_anna_mention(client, message)[13:].strip()

                if clean_argument.isdigit():

                    # We create an int from the string and clamp it between 0-2 (inclusive on both ends)
                    volume = min(max(int(clean_argument), 0), 200) / 100

                    # We set the volume of all stream players on the server to be the desired volume
                    for server_stream_pair in server_and_stream_players:

                        # Checking if the server id matches the issuing user's server's id
                        if server_stream_pair[0] == message.server.id:
                            # Setting the volume of the stream player
                            server_stream_pair[1].volume = volume

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
    """This method is used to toggle playing (pausing and unpausing) the current playing stream players in that server (if there are any)."""

    # We check if the command was issued in a PM
    if not message.channel.is_private:

        # The command was issued in a regular channel
        # We check if there we are connected to a voice channel on this server
        if client.voice_client_in(message.server) is not None:

            found_stream_player = False

            # We check if we have a stream player playing something on the server
            for server_stream_pair in server_and_stream_players:

                # Checking if the server id matches the issuing user's server's id
                if server_stream_pair[0] == message.server.id:
                    # We note that we found atleast one stream player playing something
                    found_stream_player = True

            # We check if we found any stream players
            if found_stream_player:

                # We loop through the stream players and toggle all of them
                for server_stream_pair in server_and_stream_players:

                    # Checking if the server id matches the issuing user's server's id
                    if server_stream_pair[0] == message.server.id:

                        # We toggle the playing status
                        if server_stream_pair[1].is_playing():
                            # The player is not paused, so we pause it
                            server_stream_pair[1].pause()
                        else:
                            # The player is paused, so we unpause it
                            server_stream_pair[1].resume()

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
    """This method is used to stop all audio from anna in a server."""

    # We check if the command was issued in a PM
    if not message.channel.is_private:

        # The command was issued in a regular channel
        # We check if there we are connected to a voice channel on this server
        if client.voice_client_in(message.server) is not None:

            found_stream_player = False

            # We check if we have a stream player playing something on the server
            for server_stream_pair in server_and_stream_players:

                # Checking if the server id matches the issuing user's server's id
                if server_stream_pair[0] == message.server.id:
                    # We note that we found atleast one stream player playing something
                    found_stream_player = True

            # We check if we found any stream players
            if found_stream_player:

                # We loop through the stream players and toggle all of them
                for server_stream_pair in server_and_stream_players:

                    # Checking if the server id matches the issuing user's server's id
                    if server_stream_pair[0] == message.server.id:
                        # We stop the player
                        server_stream_pair[1].stop()

                    # We remove all stopped players from the player list
                    server_and_stream_players[:] = [x for x in server_and_stream_players if not x[1].is_done()]

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
