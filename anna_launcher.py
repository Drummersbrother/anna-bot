#! /usr/bin/env python3.5
import argparse
import sys
import os
import subprocess

from sys import platform as _platform
from importlib.util import find_spec

# The modules that have to be available for anna-bot to be able to run
required_modules = {"discord", "youtube_dl", "aiohttp", "aiodns"}

if _platform == "win32":
	# We're running on windows
	WINDOWS = True
else:
	WINDOWS = False

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
			print("Requirement {0} not found.".format(required))
			return False

	return True


def start_anna_bot(auto_restart: bool):
	"""We start anna-bot by importing and launching bot_main.start_bot."""
	
	# We verify that all required modules
	if not verify_requirements():
		print("You do not have all requirements installed, please see the readme.")
	
	# We import the anna-bot file
	import bot_main
	
	# The main loop
	while True:
		try:
			print("Starting anna-bot.")
			bot_main.start_anna()
		except Exception as e:
			# We only catch error that are supposed to be catchable, otherwise we would've used BaseException
			print("Anna-bot exited with exception {0}.\nTraceback: {1}".format(str(e), str(e.Traceback)))
			if auto_restart:
				print("Restarting anna-bot since you used the --restart flag.")
				continue
			
			print("Exiting the launcher since anna-bot exited and you didn't use the --restart flag.")
			break
		except:
			# We got an exception that isn't supposed to be catched, so we raise it
			print("Anna-bot exited with an un-handlable exception. Exiting launcher.")
			raise
	

def start_anna_bot_subpr(auto_restart: bool):
	interpreter = sys.executable

	if interpreter is None: # This should never happen
		raise RuntimeError("Was not able to find a python interpreter.")

	# We verify that all required modules
	if not verify_requirements():
		print("You do not have all requirements installed, please see the readme.")

	# The arguments of the subprocess command we have to use to run anna-bot
	cmd = (interpreter, "bot_main.py")

	while True:
		try: # POPEN?
			code = subprocess.call(cmd)
		except KeyboardInterrupt:
			# CTRL-C Should stop the launcher
			code = 0
			print("Anna-bot launcher got a CTRL-C.")
			break
		else: # This is executed if everything went fine and the bot process exited without and error status code
			if code == 0:
				break
			elif code == 1:
				print("Restarting anna-bot...")
				continue
			else:
				if not auto_restart:
					break

	print("Anna-bot exited with code {0}.".format(code))


def clear_screen():
	"""This is to have a arch-independent clearing of the terminal"""
	if WINDOWS:
		os.system("cls")
	else:
		os.system("clear")


def user_input():
	"""Taking user input."""
	return input("Anna-bot> ").lower().strip()


def input_y_n():
	"""A simple yes or no input method."""
	choice = None
	yes = ("yes", "y")
	no = ("no", "n")
	while choice not in yes and choice not in no:
		choice = input("Yes/No > ").lower().strip()
	return choice in yes


# The command line args passed to the launcher
args = parse_cli_arguments()

if __name__ == '__main__':
	abspath = os.path.abspath(__file__)
	dirname = os.path.dirname(abspath)
	# Sets current directory to the launcher's
	os.chdir(dirname)
	if args.start:
		print("Anna-bot launcher initiated with flags: " + ", ".join([(pair[0]) for pair in vars(args) if pair[1]]))
		print("Starting anna-bot...")
		try:
			start_anna_bot(auto_restart=args.auto_restart)
		except:
			pass
		finally:
			print("Anna-bot launcher is now exiting.")
	else:
		print("Launcher invoked without the start (-s) flag. What did you think would happen? (Use --help for info about the different flags.)")
		