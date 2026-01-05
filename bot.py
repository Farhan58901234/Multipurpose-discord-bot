# bot.py
import discord
from discord.ext import commands
import json
import os
import importlib
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import asyncio
from collections import deque
import warnings

warnings.filterwarnings("ignore", category=Warning)

# ----------------- load config -----------------
with open("config.json") as f:
    config = json.load(f)

TOKEN = config.get("token")
PREFIX = config.get("prefix", "!")
INTENTS = discord.Intents.all()

bot = commands.Bot(command_prefix=PREFIX, intents=INTENTS, help_command=None)

# ----------------- utils loader -----------------
utils = {}
def load_utils():
    utils_folder = "utils"
    if os.path.exists(utils_folder):
        for filename in os.listdir(utils_folder):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = filename[:-3]
                full_module = f"{utils_folder}.{module_name}"
                if full_module in utils:
                    importlib.reload(utils[full_module])
                    print(f"Reloaded helper {full_module}")
                else:
                    module = importlib.import_module(full_module)
                    utils[full_module] = module
                    print(f"Loaded helper {full_module}")

# ----------------- cogs loader -----------------
async def load_cogs(folder):
    if not os.path.exists(folder):
        return 0

    loaded_count = 0
    for root, dirs, files in os.walk(folder):
        for filename in files:
            if filename.endswith(".py") and not filename.startswith("__"):
                rel_path = os.path.relpath(os.path.join(root, filename), ".")
                module_name = rel_path.replace(os.sep, ".")[:-3]
                try:
                    if module_name in bot.extensions:
                        await bot.reload_extension(module_name)
                        print(f"Reloaded {module_name}")
                    else:
                        await bot.load_extension(module_name)
                        print(f"Loaded {module_name}")
                    loaded_count += 1
                except Exception as e:
                    print(f"Failed to load {module_name}: {e}")

    return loaded_count

# ----------------- hot-reload queue -----------------
reload_queue = deque()

class ReloadHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(".py"):
            print(f"{event.src_path} changed, scheduling reload...")
            reload_queue.append(event.src_path)
            # immediately reload helpers in utils folder
            if "utils" in event.src_path.replace("\\", "/").split("/"):
                load_utils()

async def reload_worker(bot):
    while True:
        if reload_queue:
            path = reload_queue.popleft()
            if not path.endswith(".py"):
                continue

            rel_path = os.path.relpath(path, ".")
            module_name = rel_path.replace(os.sep, ".")[:-3]

            # skip utils, already reloaded directly
            if module_name.startswith("utils."):
                continue

            try:
                if module_name in bot.extensions:
                    await bot.reload_extension(module_name)
                    print(f"Reloaded {module_name}")
                else:
                    await bot.load_extension(module_name)
                    print(f"Loaded {module_name}")
            except Exception as e:
                print(f"Failed to reload {module_name}: {e}")

        await asyncio.sleep(1)

# ----------------- import DB init -----------------
from utils.db import init_db

# ----------------- on_ready -----------------
@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")

    # set status & activity
    status_str = config.get("status", "online").lower()
    activity_config = config.get("activity", {"type": "playing", "name": "Discord.py"})

    status_map = {
        "online": discord.Status.online,
        "idle": discord.Status.idle,
        "dnd": discord.Status.dnd,
        "invisible": discord.Status.invisible
    }
    status = status_map.get(status_str, discord.Status.online)

    activity_type_map = {
        "playing": discord.ActivityType.playing,
        "watching": discord.ActivityType.watching,
        "listening": discord.ActivityType.listening,
        "competing": discord.ActivityType.competing
    }
    activity_type = activity_type_map.get(activity_config.get("type", "playing").lower(), discord.ActivityType.playing)
    activity_name = activity_config.get("name", "Discord.py")

    await bot.change_presence(
        status=status,
        activity=discord.Activity(type=activity_type, name=activity_name)
    )

# ----------------- main -----------------
async def main():
    # initialize DB first
    await init_db()

    # load utils
    load_utils()

    # load cogs/extensions
    commands_loaded = await load_cogs("commands")
    events_loaded = await load_cogs("events")

    print(f"Loaded {commands_loaded} command files!")
    print(f"Loaded {events_loaded} event files!")

    # start reload worker
    asyncio.create_task(reload_worker(bot))

    # start watchdog observer
    observer = Observer()
    handler = ReloadHandler()
    for folder in ["commands", "events", "utils"]:
        observer.schedule(handler, path=folder, recursive=True)
    observer.start()

    try:
        await bot.start(TOKEN)
    finally:
        observer.stop()
        observer.join()

# ----------------- run bot -----------------
asyncio.run(main())
