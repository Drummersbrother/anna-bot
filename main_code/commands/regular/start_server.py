import subprocess

import discord


async def start_server(message: discord.Message, client: discord.Client, config: dict):
    """This method is called to handle when someone wants to launch the server (a bat file).
    Note that this doesn't use the command decorator, because the command trigger is config based."""
    if message.content.lower().startswith(
            config["start_server_cmd"]["start_server_command"]) and (
                config["start_server_cmd"]["start_server_allowed_channel_and_server_pairs"] == [message.channel.name,
                                                                                                message.server.id]):
        # Telling the caller that we're on it
        await client.send_message(message.channel, message.author.mention + ", I'm on it!")

        # We have a try except clause so we can output errors to the chat
        try:
            server = subprocess.Popen(config["start_server_command"]["start_bat_filepath"],
                                      creationflags=subprocess.CREATE_NEW_CONSOLE)
            await client.send_message(message.channel,
                                      "All done! But please note that it might take up to a minute before the server can accept any players :smile:")
        except Exception as e:
            # We output the error to the chat
            await client.send_message(message.channel, str(e))
    else:
        # Telling the caller that they do not have the appropriate permissions
        await client.send_message(message.channel,
                                  message.author.mention + ", it seems that you do not have the appropriate permissions to start the server, try using the command in a known authorised channel...")
