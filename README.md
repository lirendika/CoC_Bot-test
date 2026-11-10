<h1 align="center">Clash of Clans Bot</h1>
<p align="center">
    <a href="https://youtu.be/RTaFCiD5v3o">
        <img src="media/Cover_Image.png" alt="Cover Image" width="25%">
    </a>
    <br>
    <a href="https://youtu.be/RTaFCiD5v3o">Click for Demo Video</a>
</p>

## Automated Features (Both Villages)
* Resource collection 💰
* Hero upgrades 👑
* Building upgrades 🧱
* Laboratory upgrades 🔬
* Assistant assignment ⏩️
* Normal attacks ⚔️
* Full upgrade priority control 🚦
* Multiple accounts 👥

## Quality of Life Features
* View bot status on desktop or web app 🚦
* Pause from the desktop or web app stops every bot touch at once, so you can play yourself; Resume starts the bot over ⏯️
* Rest When Idle: a round with nothing to do (storages full, builders and lab busy) closes CoC for the rest time, so the computer stays cool 😴
* iPhone shortcut to auto resume / pause bot when CoC is opened by user ⏯️
* Telegram and web app notifications 🔔
* Automatic CoC app updates 🔼

## Dependencies
1. Install python packages with [setup.py](setup.py)
2. [Android Debug Bridge](https://developer.android.com/tools/releases/platform-tools)
    * Add to system path
        * Verify with: `adb --version`
3. [BlueStacks](https://www.bluestacks.com/)
    * Device profile: Samsung Galaxy S22 Ultra
    * Display resolution: 1920 x 1080
    * Frame rate: 30 (60 also works but keeps the computer hotter; after changing it, `python scripts/touch_check.py` checks on the live game that every tap, swipe and pinch still lands)
    * Performance: 2 CPU cores and 3 GB memory are enough for CoC and keep the computer cooler
    * Enable Android Debug Bridge
    * In Multi-Instance Manager, rename instances to match instance IDs in `configs.py` (the default ID is main, see steps 2 and 5 in [Setup Instructions](#setup-instructions) for more details)
    * Install Clash of Clans from Google Play
        * Default troop deployment size
        * Standard or XL scenery
4. [minitouch](https://app.unpkg.com/minitouch-prebuilt-support10@1.2.0/files/prebuilt) 
(__OPTIONAL__: pyminitouch should automate this)
    * Download prebuilt binary
        * Run `adb shell getprop ro.product.cpu.abi` to determine appropriate architecture
    * Open BlueStacks
    * Connect to Android Debug Bridge: `adb connect 127.0.0.1:5555`
    * Push the binary to BlueStacks:
        ```bash
        adb push <path-to-minitouch> /data/local/tmp/
        adb shell chmod 755 /data/local/tmp/minitouch
        ```
        * Verify with: `adb shell /data/local/tmp/minitouch`

## Setup Instructions
1. Install and configure dependencies listed above

2. Enter user configurations in `configs.py`
    > ❗️ __Important__: [setup.py](setup.py) creates `configs.py` from [configs.template.py](src/configs.template.py)

    > ❗️ __Important__: By default, all capabilities are enabled. Many configurations can be overridden in real time if using the desktop or web app.

    > __Note__: If using priority upgrades, instructions for defining upgrade priorities can be found in `configs.py`.

    > __Note__: To configure Telegram notifications, first set up a [Telegram bot](https://marketplace.creatio.com/sites/marketplace/files/app-guide/Instructions._Telegram_bot_1.pdf?utm_source=chatgpt.com) and send `/start`. Enter the API token generated during the setup process for `TELEGRAM_BOT_TOKEN`.

    > __Note__: If local OCR is too slow, you can offload it to [groq](https://console.groq.com). Just make an account and set up an API key to use for `GROQ_API_KEY` in `configs.py`. The free tier will hit the token rate limit after a while after which the bot will fallback to local OCR.

3. Start web app: `python app/app.py`
    > 💡 __Tip__: It is recommended to host the web app on [pythonanywhere](https://www.pythonanywhere.com) using the provided [wsgi.py](app/wsgi.py) template and [this tutorial](https://medium.com/@cssjhnnamae/how-to-deploy-a-python-app-on-pythonanywhere-cf399f4bbc01). Free accounts can host a single web app for an extendable period of 1 month (the bot can automatically extend hosting). If you want to enable automatic pythonanywhere hosting extension, enter your pythonanywhere username and passowrd into `PA_USERNAME` and `PA_PASSWORD` respectively in `configs.py`.
    
    > ❗️ __Important__: If hosting from a personal device, configure port forwarding as necessary
    
    * Each bot instance can be accessed at `WEB_APP_URL/<instance_id>` (the default instance ID is `main`)
    * View a demo of the web app [here](https://youtu.be/6w2SRJFtSnM)

4. Setup iPhone shortcut:
    > ❗️ __Important__: iOS will terminate long running shortcuts after about 30-60 mins (there's no reported limit so times may vary). To ensure the bot is paused for longer, it is suggested to set the shortcut to "run after confirmation" so that the pause duration can be set arbitrarily high through the web app when desired.

    > __Note__: An [older version](<shortcut/CoC Bot Auto Pause Old.shortcut>) of the shortcut is provided that does not require Scriptable, but is incapable of handling request errors
    
    * Download [Scriptable](https://apps.apple.com/us/app/scriptable/id1405459188) and create a new script named "CoC Bot Script" with the contents of [CoC_Bot_Script.js](<shortcut/Scriptable.js>)
    * Open the [provided shortcut](<shortcut/CoC Bot Auto Pause.shortcut>)
    * Enter your `WEB_APP_URL` into the `url` item of the Dictionary
    * Add your instance ids to the `ids` array in the Dictionary (main is added by default)
    * Create an Automation task that runs when CoC opens and is set to run immediately

5. Start the bot: `python src/main.py`
    > __Note__: With `DISABLE_DEVICE_SLEEP = True` in `configs.py` the computer stays awake while the bot runs, no password needed (on MacOS through `caffeinate`; closing a laptop's lid still puts it to sleep)

    > 💡 __Tip__: The BlueStacks window can be minimized without disrupting the bot as all interactions are handled through Android Debug Bridge

    > 💡 __Tip__: If not using the bot for development purposes, it can be built into an executable or desktop app for convenience using [build.sh](scripts/build.sh). The desktop app GUI or command-line arguments can be used to specify the instance to run if using multiple bot instances. View a demo of the desktop app [here](https://youtube.com/shorts/zVZwBW8QIeY?feature=share).

    * To run bots for multiple accounts just create additional BlueStacks instances with BlueStacks' multi-instance manager (ensuring BlueStacks instance names match bot instance IDs), set up the instance as usual, and append new instance names and their Android Debug Bridge addresses to `INSTANCE_IDS` and `ADB_ADDRESSES` in `configs.py`. Specify the instance to run using the `--id` flag (e.g. `python src/main.py --id main`).

## After a Clash of Clans Update
Game updates move buttons and restyle screens. [tests/ui_frames](tests/ui_frames) keeps pixel-exact screenshots of each UI the bot was adapted to, and [manifest.json](tests/ui_frames/manifest.json) records what each one shows and what the bot must read from it.
* `python scripts/panel_eval.py` and `python scripts/loot_eval.py` check the bot's screen readers (upgrade panel, battle result, dialogs, loot) against those frames; exit code 0 means all agree
* `python scripts/storage_eval.py` checks that the gold, elixir and dark elixir counters are read digit for digit and each storage's fill within 1%, that a covered or dimmed counter reads as nothing, and that attacks stop only once gold and elixir are both 90% full
* `python scripts/ui_probe.py <screenshot> scan` scores every template on a screenshot, and `eval "<expression>"` runs any bot function on it
* `python scripts/capture_frame.py <folder/name>` saves the live BlueStacks screen as a new reference frame
* `python scripts/pause_eval.py` checks with a fake device that a Pause lets no tap, swipe, screenshot or app command through and that the bot then starts over
* `python scripts/rest_eval.py` checks offline that only a round with nothing to do closes CoC and rests, and that a switch flipped in the app or a Pause ends the rest
* `python scripts/update_eval.py` checks with a fake device that the automatic CoC update presses only CoC's and Google Play's Update button, stays quiet when there's no update, and lets a Pause stop it before any click
* `python scripts/touch_check.py` opens and closes the Build panel, switches its tabs, swipes its list and pinches the village on the live game (nothing bought), reporting every gesture the game missed: run it after changing BlueStacks' frame rate, cores or memory
* `python scripts/upgrade_dryrun.py` drives the real upgrade flows on the live game while blocking every tap that would spend resources (`upgrade_dryrun.py helpers` walks the Builder's Apprentice and Lab Assistant flows up to their blocked Confirm while both are idle)

## Troubleshooting
* Supercell ID screens (switch account, Open) stay black while the game itself shows fine: on BlueStacks Air every CoC session that starts on the cache an earlier session left behind draws them black. Before switching accounts, Pause the bot, close CoC, then in BlueStacks open Android Settings > Apps > Clash of Clans > Storage & cache, press __Clear cache__ and start CoC again: that session can switch. Your account stays logged in. Never press Clear storage, which logs you out, and logging back in goes through those same screens