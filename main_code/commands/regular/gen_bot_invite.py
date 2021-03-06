import discord

from ... import command_decorator


@command_decorator.command("add-bot",
                           "Generate an invite link so you can add the bot to your own server, (with proper permissions of course).")
async def gen_bot_invite(message: discord.Message, client: discord.Client, config: dict):
    """This method is called to handle someone wanting to invite anna-bot to their own server"""

    # We check if this command is enabled
    if not config["add_bot_cmd"]["enabled"]:
        # The command is not enabled
        await client.send_message(message.channel,
                                  message.author.mention + ", you can't add this bot to another server.")

        # We're done here
        return

    # Creating the Permissions object so the bot gets proper permissions to work when it is invited to a server
    bot_permissions = discord.Permissions().none()

    # Actually modifying all the properties of the permissions objects so we get the permissions
    bot_permissions.create_instant_invite = True
    bot_permissions.read_messages = True
    bot_permissions.send_messages = True
    bot_permissions.embed_links = True
    bot_permissions.read_message_history = True
    bot_permissions.connect = True
    bot_permissions.speak = True

    # Creating the url with all the proper settings
    invite_url = discord.utils.oauth_url(config["credentials"]["app_client_id"], bot_permissions)

    # Giving the url back to the user with proper formatting
    await client.send_message(message.channel,
                              message.author.mention + ", here is the bot invite link :smile: " + invite_url + " (it has good permission defaults but you can, of course, change that on your own later.)")
