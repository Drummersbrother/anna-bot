import discord

from ... import command_decorator
from ... import helpers


@command_decorator.command("broadcast", "Broadcasts a message to all the channels that anna-bot has access to.",
                           admin=True)
async def cmd_admin_broadcast(message: discord.Message, client: discord.Client, config: dict):
    """This method is used to handle admins wanting to broadcast a message to all servers and channel that anna-bot is in."""

    # We know that the issuing user is an admin
    if not message.channel.is_private:
        # The message to send in all the channels, we do this by just stripping off the first characters (the command part of the issuing message)
        message_content = helpers.remove_anna_mention(client, message).strip()[16:]

    else:
        message_content = message.content

    # Logging that we're going to broadcast the message
    helpers.log_info(message.author.name + " issued a broadcast of the message \"" + message_content + "\"!")

    # Telling the issuing user that we're broadcasting
    await client.send_message(message.channel, "I'm on it!")

    # Looping through all the channels on all the servers we have access to
    for server in client.servers:
        for channel in server.channels:

            # Doing some sanity checking (you can't send a message in a voice client)
            if channel.type == discord.ChannelType.text:
                # Checking permissions for our bot user in the current channel
                if channel.permissions_for(server.me).send_messages:
                    # We can (probably, since there might be channel level overrides):
                    await client.send_message(channel, "Broadcast: " + message_content)

    # Logging that we're done doing the broadcasting
    helpers.log_info(message.author.name + "'s broadcast of the message \"" + message_content + "\" is now done.")

    # Telling the issuing user that we're done broadcasting
    await client.send_message(message.channel, "Ok I'm done broadcasting :smile:")
