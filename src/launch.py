def alert_unreachable():
    """Tell the user why the bot stopped — without it the dashboard just sat
    there looking idle, with the failure buried in a log file."""
    import sys, subprocess
    from utils import ADB_Manager
    if ADB_Manager.last_error == "adb executable not found":
        msg = ("The adb program was not found on this computer.\n\n"
               "Install Android platform-tools (Terminal: brew install android-platform-tools) "
               "or set ADB_ABS_DIR in src/configs.py, then start CoC Bot again.")
    else:
        msg = ("Can't reach BlueStacks over ADB.\n\n"
               "Open BlueStacks, wait until it has fully booted to the home screen, "
               "check Settings > Advanced > Android Debug Bridge is ON, "
               "then close this CoC Bot window and start it again.")
    if sys.platform == "darwin":
        subprocess.Popen(["osascript", "-e", f'display alert "CoC Bot" message "{msg}" as warning'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "CoC Bot", 0x30)

def launch_proc(args):
    from log import enable_logging
    from utils import parse_args, init_instance
    from coc_bot import CoC_Bot

    parse_args(args.debug, args.id, args.gui, args.gui_port)
    init_instance(args.id)
    enable_logging(args.id)
    try:
        bot = CoC_Bot()
    except AssertionError as e:
        if "ADB" in str(e): alert_unreachable()
        raise
    bot.run()

def cmd_launch(args):
    import utils
    if utils.DISABLE_DEVICE_SLEEP: utils.disable_sleep()
    launch_proc(args)

def gui_launch(args):
    from multiprocessing import Process
    import utils
    from gui import init_gui, get_gui
    from copy import deepcopy
    
    procs = {}
    pipe = init_gui(args.id)
    args.gui_port = get_gui().server_port
    
    # In this process, not a child one: the Mac stays awake for as long as
    # the process that asked lives, and a child Process ended right away
    if utils.DISABLE_DEVICE_SLEEP: utils.disable_sleep()

    if args.id is not None:
        p = Process(target=launch_proc, args=(args,))
        p.start()
        procs[args.id] = p
    try:
        while True:
            data = pipe.recv()
            if data == -1: raise SystemExit
            action, id = data.get("action"), data.get("id")
            if action == "start":
                args_copy = deepcopy(args)
                args_copy.id = data.get("id")
                p = Process(target=launch_proc, args=(args_copy,))
                p.start()
                procs[id] = p
            elif action == "stop":
                p = procs.pop(id, None)
                if p and p.is_alive():
                    p.terminate()
                    p.join()
    except (EOFError, KeyboardInterrupt, SystemExit):
        get_gui().stop()
        pipe.close()
        for p in procs.values():
            if p and p.is_alive():
                p.terminate()
                p.join()

def launch():
    import utils
    args = utils.parse_args()
    if args.gui: gui_launch(args)
    else: cmd_launch(args)
