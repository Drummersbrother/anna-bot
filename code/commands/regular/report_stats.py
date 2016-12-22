import json
import os.path
import time
from os import sep as dir_sep

import discord

from ... import helpers


async def cmd_report_stats(message: discord.Message, client: discord.Client, config: dict):
    """This method is used to handle reporting stats about the bot to the user who used the anna stats command."""

    # Creating the formatted string about how long the bot has been up for this "session"
    uptime_string = helpers.get_formatted_duration_fromtime(
        (time.time() - config["stats"]["volatile"]["start_time"]) // 1)

    # Loading the config file so we can use the stats that exists in it
    with open(os.path.dirname(__file__) + dir_sep + str(".." + dir_sep) * 3 + "config.json", mode="r",
              encoding="utf-8") as config_file:
        current_config = json.load(config_file)

    # Reporting the stats back into the chat where the command was issued
    await client.send_message(message.channel,
                              "Some stats about **anna-bot**:\n\tIt has been up for **{0}**. \n\tIt has sent **{1}** message(s). \n\tIt has received **{2}** command(s).".format(
                                  uptime_string, current_config["stats"]["messages_sent"],
                                  current_config["stats"]["commands_received"])
                              )
