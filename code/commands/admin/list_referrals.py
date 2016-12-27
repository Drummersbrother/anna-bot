import os.path
from os import sep as dir_sep

import discord

from ... import command_decorator


@command_decorator.command("list referrals", "Sends a copy of the referrals file.", admin=True)
async def cmd_admin_list_referrals(message: discord.Message, client: discord.Client, config: dict):
    """This function is used to send back the contents of the referrals file to the issuing admin. Mostly for debug purposes."""

    # We tell the user that we're sending the file in a PM
    await client.send_message(message.channel, "Ok! You'll see the file in our PMs.")

    # We open the file and send it
    with open(os.path.dirname(__file__) + dir_sep + str(".." + dir_sep) * 3 + "referrals.json",
              mode="rb") as referrals_file:
        # We send the file
        await client.send_file(message.author, referrals_file, content="Here you go!")
