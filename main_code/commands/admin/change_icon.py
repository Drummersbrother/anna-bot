import discord
import requests

from ... import command_decorator
from ... import helpers


@command_decorator.command("change icon",
                           "Changes the anna-bot's profile icon to an image that the user attaches to the command message.",
                           admin=True)
async def cmd_admin_change_icon(message: discord.Message, client: discord.Client, config: dict):
    """This admin command is used to change the icon of the bot user to a specified image."""

    # Checking if the message has an attachment
    if message.attachments:

        # Looping through the attachments until we find a valid one to use for an icon
        for attachment in message.attachments:

            # Checking if the message has a valid image attachment (just checking if the height and width dict keys exist)
            if ("width" in attachment) and ("height" in attachment):
                # We tell the user that we're changing the icon
                await client.send_message(message.channel,
                                          "Ok {0:s}, now changing the icon to the image you sent!".format(
                                              message.author.mention))

                # We break out of the for loop as we are done
                # Note that as python does not change the last value of a for loop "counter" (in this case attachment) after the for loop has been exited,
                # and that neither for loops nor if statements create new namespaces, the last value of that variable is still a regular variable after the for loop has been executed.
                break

        # This is an else statement for the for loop (no pun intended), which executes after a for loop if the for loop doesn't stop because of a break statement
        else:

            # We tell the user that they didn't attach a valid icon image to their command message
            await client.send_message(message.channel,
                                      "I can't do that {0:s} because you didn't attach an image for me to set my icon to.".format(
                                          message.author.mention))

            # We're done here now
            return

    # The command message didn't have any attachments
    else:

        # We tell the user that they didn't attach a valid icon image to their command message
        await client.send_message(message.channel,
                                  "I can't do that {0:s} because you didn't attach an image for me to set my icon to.".format(
                                      message.author.mention))

        # We're done here now
        return

    # Logging that we're going to change the icon of the bot account
    helpers.log_info(
        "Changing {0:s}'s icon to {1:s} because admin {2:s} ({3:s}) triggered the change icon command.".format(
            client.user.name, attachment["url"], message.author.name, message.author.mention))

    # We download the image and upload it to the discord command simultaneously
    await client.edit_profile(avatar=requests.get(attachment["url"]).content)

    # Logging and telling the user that we're done changing the icon
    helpers.log_info("Now done changing the icon.")
    await client.send_message(message.channel, "Now done changing the icon.")
