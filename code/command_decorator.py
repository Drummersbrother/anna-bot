public_commands = []
admin_commands = []


def command(command_trigger: str, cmd_helptext: str, cmd_special_params=(False, False), admin=False):
    """This function defines the decorator with arguments that we use to quite dynamically create the command dicts in the main file."""

    global public_commands
    global admin_commands

    # The actual decorator that gets used on the function
    # Decorators with arguments basically return a parametrised decorator that then gets to decorate the actual function
    def real_decorator(cmd_method):

        # We append a cmd entry to the command list
        if not admin:
            # The command is public so we append to the public command list
            public_commands.append(dict(command=command_trigger, method=cmd_method, helptext=cmd_helptext,
                                        special_params=cmd_special_params))
        else:
            # The command is an admin command, so we append to the admin command list
            admin_commands.append(dict(command=command_trigger, method=cmd_method, helptext=cmd_helptext,
                                       special_params=cmd_special_params))

        # We actually don't modify the cmd method itself, we just need to register it as a command
        return cmd_method

    return real_decorator


def get_command_lists():
    """Get the public and admin command lists"""
    return public_commands, admin_commands
