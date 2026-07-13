######################
# == User Configs == #
######################

# OPTIONAL: Web app (enter empty string to disable)
WEB_APP_URL = "" # (e.g. 12.34.567.890:1234)
PA_USERNAME, PA_PASSWORD = "", "" # only if using pythonanywhere to auto extend hosting

# OPTIONAL: Telegram notifications (enter empty string to disable)
TELEGRAM_BOT_TOKEN = "" # (e.g. 123456789:ABCdefGHIjkl-MNO_pqrSTUvwxYZ)

# OPTIONAL: Groq API key for faster/more accurate OCR (enter empty string to disable)
GROQ_API_KEY = ""

# REQUIRED: Instance Settings
INSTANCE_IDS = ["main"]
ADB_ADDRESSES = ["127.0.0.1:5555"] # Bluestacks ADB addresses in order of instance IDs
DEFAULT_INSTANCE_ID = INSTANCE_IDS[0]

# REQUIRED: General Settings
LOCAL_GUI = True # web app not required
CHECK_INTERVAL = 5 # minutes

# REQUIRED: Upgrade settings
MAX_UPGRADES_PER_CHECK = 10 # applies to both home and builder base
START_FROM_MENU_TOP = True

#   Home base upgrade settings
OPEN_HOME_BUILDERS = 0 # number of home base builders to keep open (not upgrading), suggested to be 0 for maximum efficiency

UPGRADE_HEROES = True # can be overridden on desktop or web app
WALL_FOCUS = False # keep 1 builder idle and dump spare loot into walls whenever affordable (can be overridden on desktop or web app)
WALL_FOCUS_MIN_STORAGE_PCT = 50 # only start wall upgrades when a storage bar is at least this % full (alternates farming and walls)
MIN_LOOT_GOLD = 0 # skip enemy bases with less available gold than this ("Next" until found); 0 = disabled
MIN_LOOT_ELIXIR = 0 # skip enemy bases with less available elixir than this ("Next" until found); 0 = disabled
UPGRADE_HOME_BASE = True # can be overridden on desktop or web app
UPGRADE_HOME_LAB = True # can be overridden on desktop or web app
ASSIGN_LAB_ASSISTANT = True # can be overridden on desktop or web app
ASSIGN_BUILDER_APPRENTICE = True # can be overridden on desktop or web app

PRIORITY_HOME_BASE_UPGRADES = True # if false, will upgrade in random order regardless of priority settings (can be overridden on desktop or web app)
PRIORITY_HOME_LAB_UPGRADES = True # if false, will upgrade in random order regardless of priority settings (can be overridden on desktop or web app)

#   Every row is a priority level, with the first row being the highest priority
#   Within each row, upgrades are of equal priority and will be randomly chosen between
#   If no listed upgrades are available, will default to random upgrades
#   IMPORTANT: Capitalization and spacing must match exactly with in-game text
#   TIP: It is recommended to minimize the number of priority levels to keep check time reasonable (all upgrades in the same priority are checked in parallel)
HOME_BASE_UPGRADE_PRIORITY = [
    [
        "Laboratory",
        "Blacksmith",
        "Hero Hall",
        "Barbarian King",
        "Archer Queen",
        "Minion Prince",
        "Grand Warden",
        "Royal Champion",
        "Dragon Duke",
    ],
    [
        "Army Camp",
        "Barracks",
        "Dark Barracks",
        "Spell Factory",
        "Dark Spell Factory",
        "Workshop",
        "Clan Castle",
    ],
    [
        "Wall",
    ],
]
HOME_LAB_UPGRADE_PRIORITY = [
    [
        "Balloon",
        "Dragon",
        "Lightning Spell",
        "Rage Spell",
        "Freeze Spell",
        "Poison Spell",
        "Earthquake Spell",
    ],
]

#   Builder base upgrade settings
OPEN_BUILDER_BUILDERS = 0 # number of builder base builders to keep open (not upgrading), suggested to be 0 for maximum efficiency

UPGRADE_BUILDER_BASE = True # can be overridden on desktop or web app
UPGRADE_BUILDER_LAB = True # can be overridden on desktop or web app

PRIORITY_BUILDER_BASE_UPGRADES = True # if false, will upgrade in random order regardless of priority settings (can be overridden on desktop or web app)
PRIORITY_BUILDER_LAB_UPGRADES = True # if false, will upgrade in random order regardless of priority settings (can be overridden on desktop or web app)

#   Every row is a priority level, with the first row being the highest priority
#   Within each row, upgrades are of equal priority and will be randomly chosen between
#   If no listed upgrades are available, will default to random upgrades
#   IMPORTANT: Capitalization and spacing must match exactly with in-game text
#   TIP: It is recommended to minimize the number of priority levels to keep check time reasonable (all upgrades in the same priority are checked in parallel)
BUILDER_BASE_UPGRADE_PRIORITY = [
    [
        "Builder Hall",
        "Multi Mortar",
        "Archer Tower",
        "Double Cannon",
        "Builder Barracks",
        "Battle Machine",
        "Battle Copter",
        "Star Laboratory",
    ],
    [
        "Gold Storage",
        "Elixir Storage",
        "Double Cannon",
        "Archer Tower",
    ],
]
BUILDER_LAB_UPGRADE_PRIORITY = [
    [
        "Boxer Giant",
        "Night Witch",
    ],
    [
        "Baby Dragon",
        "Power P.E.K.K.A",
    ],
]

# REQUIRED: Attack Settings
TROOP_DEPLOY_TIME = 2 # seconds
ATTACK_SLOT_RANGE = (0, 100) # inclusive, first slot is index 0
EXCLUDE_CLAN_TROOPS = True
ATTACK_HOME_BASE = True # can be overridden on desktop or web app
ATTACK_BUILDER_BASE = True # can be overridden on desktop or web app

# Smart Attack Settings (ported from MyBot.run/ClashAttack)
SMART_ATTACK = True          # Enable smart side detection & wave-based deployment
AI_ATTACK = False            # Use the Groq vision model to pick the attack side(s); falls back to the loot heuristic on failure (needs GROQ_API_KEY, can be overridden on desktop or web app)
DEPLOY_SPREAD_POINTS = 5     # Number of spread points per side for troop deployment
SMART_ATTACK_INSIDE_PCT = 60 # % of resources inside the base to force a single-side attack (MyBot.run "Inside Percentage")
SMART_ATTACK_OUTSIDE_PCT = 50 # % of resources near the border to attack every side holding loot (MyBot.run "Outside Percentage")
TANK_SLOTS = [] # army slot indices (0-based, matching barracks order) to deploy first as tanks; empty = auto (troops with the smallest counts lead)

# Spam Event Attack (single-troop two-finger hold-drag spam for challenge/farm events)
SPAM_EVENT = False               # when ON, home attacks bring ONE troop type and spam it with TWO fingers held at once (one per side, never released mid-card): the two presses are staggered (random side first + a pause so it isn't read as pinch/pan), then both fingers sweep their side with a randomized walk; then spread rage spells; when OFF, normal/smart attack runs (can be overridden on desktop or web app)
SPAM_EVENT_HOLD_MS = 400         # hold-still after the FIRST finger lands, before the second (ms, ±20%) — long enough that the game locks into deploy mode, not a pinch/pan
SPAM_EVENT_SIDE_PAUSE_MS = 350   # extra stagger pause after the SECOND finger lands, before sweeping (ms, ±20%)
SPAM_EVENT_MOVE_INTERVAL_MS = 60 # base ms between finger move steps during the sweep (randomized ±, lower = faster)
SPAM_EVENT_POINTS_PER_LINE = 10  # random-walk steps per lap per side (higher = longer sweep before re-checking the card)
SPAM_EVENT_MAX_PASSES = 30       # safety cap on laps per troop card (stops even if the card never reads as empty)
SPAM_EVENT_RAGE_SPACING = 0.13   # minimum normalized gap between rage-spell drops so their areas don't overlap

########################
# == System Configs == #
########################
DEBUG = False
DISABLE_DEVICE_SLEEP = True
WINDOW_DIMS = (1920, 1080) # width, height
ADB_ABS_DIR = "" # absolute path to dir with adb executable, leave empty to use system PATH
BLUESTACKS_BIN_PATH = "" # absolute path to Bluestacks executable, leave empty to use system defaults
