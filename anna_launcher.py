#! /usr/bin/env python3.5
import argparse
import asyncio
import os
import sys
import time
import traceback
from importlib import reload
from importlib.util import find_spec
from sys import platform as _platform

import discord

# The modules that have to be available for anna-bot to be able to run
required_modules = {"discord", "youtube_dl", "aiohttp", "aiodns", "asyncio", "overwatch_api"}

if _platform == "win32":
	# We're running on windows
	WINDOWS = True
else:
	WINDOWS = False

def ratelimit_decorator(maxPerSecond):
	"""Shamelessly taken from http://blog.gregburek.com/2011/12/05/Rate-limiting-with-decorators/"""
	minInterval = 1.0 / float(maxPerSecond)
	def decorate(func):
		lastTimeCalled = [-minInterval]
		def rateLimitedFunction(*args,**kargs):
			elapsed = time.clock() - lastTimeCalled[0]
			leftToWait = minInterval - elapsed
			if leftToWait>0:
				print("Ratelimiting by waiting for {1} seconds to ensure more than {0} seconds between each launch.".format(1 / maxPerSecond, leftToWait))
				time.sleep(leftToWait)
			ret = func(*args,**kargs)
			lastTimeCalled[0] = time.clock()
			return ret
		return rateLimitedFunction
	return decorate


def parse_cli_arguments():
	parser = argparse.ArgumentParser(description="The anna-bot launcher")
	parser.add_argument("--start", "-s",
						help="Starts anna-bot",
						action="store_true")
	parser.add_argument("--auto-restart", "-r",
						help="Autorestarts anna-bot if it stops",
						action="store_true")
	return parser.parse_args()


def verify_requirements():
	"""Returns True if all requirements in required_modules exist / can be imported. Else returns False."""

	for required in required_modules:
		if find_spec(required) is None:
			# We missed a requirement
			launcher_log("Requirement {0} not found.".format(required))
			return False

	return True


def start_anna_bot(auto_restart: bool):
	"""We start anna-bot by importing and launching bot_main.start_bot."""

	# We verify that all required modules
	if not verify_requirements():
		launcher_log("You do not have all requirements installed, please see the readme.")
		return
	@ratelimit_decorator(1 / 60)
	def _start_anna(functon, *args, **kwargs):
		functon()

	import bot_main

	# The main loop
	while True:
		# We don't want to DOS our host machine
		# During this sleep the user of anna-bot can send a CTRL+C and it won't be caught in the try-except statement
		time.sleep(0.5)

		try:
			launcher_log("Starting anna-bot file.")
			_start_anna(bot_main.start_anna)
		except Exception as e:
			# We only catch error that are supposed to be catchable, otherwise we would've used BaseException
			e_type, e, e_traceback = sys.exc_info()
			launcher_log("Anna-bot exited with exception. Traceback: \n{0}".format(
				str("".join(traceback.format_exception(e_type, e, e_traceback)))))

			# We check if we should restart
			if auto_restart:
				launcher_log("Restarting anna-bot since you used the --restart flag.")
				continue

			launcher_log("Exiting the launcher since anna-bot exited and you didn't use the --restart flag.")
			break
		except BaseException:
			# We got an exception that isn't supposed to be catched, so we break
			launcher_log("Anna-bot exited with an un-handlable exception. Exiting launcher.")
			break

		# We check if we should continue running anna-bot
		if not auto_restart:
			launcher_log("Stopping anna-bot since you didn't use the --restart flag.")
			break

		# Giving the user info about why the bot is relaunching
		launcher_log("Restarting anna-bot since you used the --restart flag.")
		launcher_log("Updating event loop...")

		# We create and use a new event loop for the next iteration of anna-bot
		asyncio.get_event_loop().close()
		asyncio.set_event_loop(asyncio.new_event_loop())

		# We replace the old event loop with a new one, that's the only way to "reopen" loops I was able to find
		bot_main.helpers.actual_client.loop = asyncio.get_event_loop()

		# We need to refresh the client session to not get session closed errors
		bot_main.helpers.actual_client = discord.Client(cache_auth=False)

		# We import the anna-bot file (actually we reload it, as we are running a new instance of anna)
		reload(bot_main)

		launcher_log("Done updating event loop.")


def launcher_log(*args):
	"""Prints a message from anna_launcher instead of regular print."""
	print("Anna_launcher: ", *args)


# The command line args passed to the launcher
args = parse_cli_arguments()

if __name__ == '__main__':
	abspath = os.path.abspath(__file__)
	dirname = os.path.dirname(abspath)
	# Sets current directory to the launcher's
	os.chdir(dirname)
	if args.start:
		launcher_log(
			"Anna-bot launcher initiated with flags: " + ", ".join([pair for pair in vars(args) if vars(args)[pair]]))
		launcher_log("Starting anna-bot...")
		try:
			start_anna_bot(auto_restart=args.auto_restart)
		except BaseException:
			e_type, e, e_traceback = sys.exc_info()
			launcher_log("Got exception from anna-bot, will exit. Here is the traceback: \n{0}".format(
				str("".join(traceback.format_exception(e_type, e, e_traceback)))))
		finally:
			launcher_log("Anna-bot launcher is now exiting.")
	else:
		launcher_log(
			"Launcher invoked without the start (-s) flag. What did you think would happen? (Use --help for info about the different flags.)")
