import discord


async def invite_link(message: discord.Message, client: discord.Client, config: dict):
    """This method is called to handle someone typing the message '!invite'.
    Note that this doesn't use the regular command decorator, because it uses config-based formatting in the helptext."""

    # Telling the user that we're working on it
    await client.send_message(message.channel,
                              "Sure thing " + message.author.mention + ", you'll see the link in our PMs :smile:")

    # Checking if the bot and the user has permissions to generate an invite link
    if message.author.permissions_in(message.channel).create_instant_invite and message.server.me.permissions_in(
            message.channel).create_instant_invite:
        # Generating a join/invite link (for the channel in which the message was sent) and doing some formatting on a message so we can be more human
        invite_url = await client.create_invite(message.channel,
                                                max_age=60 * config["invite_cmd"]["invite_valid_time_min"],
                                                max_uses=config["invite_cmd"]["invite_max_uses"], temporary=False)
        invite_url = invite_url.url

        # Make a message with proper formatting and put it in the chat where the invite link was requested, also mention the person who requested the link
        await client.send_message(message.author, "Ok, here's an invite link :smile: " + invite_url +
                                  " (valid for " + str(config["invite_cmd"]["invite_valid_time_min"]) + "min and "
                                  + str(config["invite_cmd"]["invite_max_uses"]) + " use[s])")

    else:
        # Checking whether it is the bot or the user who doesn't have permissions
        if not message.author.permissions_in(message.channel).create_instant_invite:
            # Telling the user who wanted the invite link that they don't have permissions to create invites
            await client.send_message(message.author,
                                      "Sorry, I can't do that for you since you don't have permissions to create invite links in that channel.")

        else:
            # Telling the user who wanted the invite link that they don't have permissions to create invites
            await client.send_message(message.author,
                                      "Sorry, I can't do that for you since I don't have permissions to create invite links in that channel.")
