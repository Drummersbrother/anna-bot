#! /usr/bin/env python3.5
import argparse
import os
import subprocess
import sys
import time
import traceback
from importlib.util import find_spec
from sys import platform as _platform

# The modules that have to be available for anna-bot to be able to run
required_modules = {"discord", "youtube_dl", "aiohttp", "aiodns", "asyncio", "overwatch_api"}

if _platform == "win32":
    # We're running on windows
    WINDOWS = True
else:
    WINDOWS = False

def ratelimit_decorator(maxPerSecond):
    """Shamelessly taken from http://blog.gregburek.com/2011/12/05/Rate-limiting-with-decorators/. 
    It is however, improved to actually work in my usecase."""
    minInterval = 1.0 / float(maxPerSecond)

    def decorate(func):
        lastTimeCalled = [time.time() - minInterval]

        def rateLimitedFunction(*args, **kWargs):
            elapsed = time.time() - lastTimeCalled[0]
            leftToWait = minInterval - elapsed
            if leftToWait > 0:
                launcher_log(
                    "Ratelimiting by waiting for {1} seconds to ensure more than {0} seconds between each launch.".format(
                        round(1 / maxPerSecond, 2), round(leftToWait, 2)))
                time.sleep(leftToWait)
            lastTimeCalled[0] = time.time()
            ret = func(*args, **kWargs)
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


def start_anna_bot_process(auto_restart: bool):
    # We verify that all required modules are installed
    if not verify_requirements():
        launcher_log("You do not have all requirements installed, please see the readme.")
        return

    @ratelimit_decorator(1 / 60)
    def _start_anna(functon, *args, **kwargs):
        return functon(*args, **kwargs)

    # We define some things
    interpreter = sys.executable
    start_cmd = (interpreter, "bot_main.py")

    # This shouldn't happen unless we're running in some kind of "safe" evalutaing function (practically impossible)
    if interpreter is None:
        launcher_log("Could not find interpreter, exiting.")
        return

    # The main loop
    while True:
        # We log and launch anna
        launcher_log("Launching anna-bot file...")
        print("-" * 25 + "Anna-Bot" + "-" * 25)
        try:
            # We redirect stderr to the log file
            with open("discord.log", encoding="utf-8", mode="a") as log_file:
                exited_process = _start_anna(subprocess.run, start_cmd, universal_newlines=True, stdin=subprocess.PIPE,
                                             stderr=subprocess.PIPE)
        except KeyboardInterrupt:
            print()
            launcher_log("Exiting because of CTRL+C.")
            break
        except:
            launcher_log("Exiting since launching anna-bot gave a python exception, here's the traceback:\n{0}".format(
                str("".join(traceback.format_exception(*sys.exc_info())))))
            break

        print("-" * 58)
        launcher_log("Anna-bot has exited with code {0}.".format(exited_process.returncode))

        # We analyze how anna was exited, and we relaunch if we're supposed to
        if exited_process.returncode == 0:
            # Everything is fine
            if auto_restart:
                launcher_log("Restarting anna-bot since you used the --restart flag.")
                continue
            else:
                launcher_log("Exiting since you didn't use the --restart flag")
                break
        elif exited_process.returncode < 0:
            # The process was exited by a POSIX signal, so we don't restart it, no matter what
            launcher_log(
                "Exiting since anna-bot exited by POSIX signal, with code {0}".format(exited_process.returncode))
            break
        else:
            # Anna-bot exited with an error code, but it wasn't by a POSIX signal, so we relaunch
            if auto_restart:
                launcher_log(
                    "Restarting anna-bot (even though we got an error exit code) since you used the --restart flag.")
                continue
            else:
                launcher_log("Exiting since you didn't use the --restart flag")
                break


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
            start_anna_bot_process(auto_restart=args.auto_restart)
        except BaseException:
            e_type, e, e_traceback = sys.exc_info()
            launcher_log("Got exception from anna-bot, will exit. Here is the traceback: \n{0}".format(
                str("".join(traceback.format_exception(e_type, e, e_traceback)))))
        finally:
            launcher_log("Anna-bot launcher is now exiting.")
    else:
        launcher_log(
            "Launcher invoked without the start (-s) flag. What did you think would happen? (Use --help for info about the different flags.)")
