from utils import *
from configs import *
from upgrader import Upgrader
from attacker import Attacker

class CoC_Bot:
    def __init__(self):
        assert ADB_Manager.connect(60), "Failed to connect to ADB"
        # Take ownership of BlueStacks (shut it down on exit) only once we're
        # connected — registering first meant a failed connect (BlueStacks
        # still booting, ADB offline) force-killed the user's emulator on exit
        BlueStacks_Manager.init()
        Pause_Handler.start()
        # CoC closed some other way (by hand, BlueStacks restarting) left the
        # cache that turns Supercell ID black in the next CoC: start clean
        if not coc_running(): clear_coc_cache()
        self.upgrader = Upgrader()
        self.attacker = Attacker()

    # ============================================================
    # ⏱️ Task Execution
    # ============================================================

    def run(self):
        while True:
            try:
                self.run_cycle()
            # Pause in the app: every touch raised Bot_Paused, whatever was
            # running stopped right there, and the next cycle starts over
            except Bot_Paused:
                self.wait_while_paused()
            except (KeyboardInterrupt, SystemExit): raise
            except Exception as e:
                import traceback
                traceback.print_exc()
                try:
                    stop_coc()
                    update_status("error")
                except Bot_Paused:
                    self.wait_while_paused()

    def wait_while_paused(self):
        import time
        print("⏸️ Paused from the app: the bot keeps its hands off the game")
        update_status("paused")
        while not running(): time.sleep(0.25)
        print("▶️ Resumed: starting over from the beginning")

    def run_cycle(self):
        import time, random

        Pause_Handler.check()
        Task_Handler.get_exclusions()
        exclude_home_base = Task_Handler.home_base_excluded(use_cached=True)
        exclude_home_lab = Task_Handler.home_lab_excluded(use_cached=True)
        wall_focus = not Task_Handler.wall_focus_excluded(use_cached=True)
        # Wall focus keeps run_home_base alive even when regular upgrades are off
        skip_home_base_upgrades = exclude_home_base and exclude_home_lab and not wall_focus
        exclude_home_attacks = Task_Handler.home_attacks_excluded(use_cached=True)

        exclude_builder_base = Task_Handler.builder_base_excluded(use_cached=True)
        exclude_builder_lab = Task_Handler.builder_lab_excluded(use_cached=True)
        skip_builder_base_upgrades = exclude_builder_base and exclude_builder_lab
        exclude_builder_attacks = Task_Handler.builder_attacks_excluded(use_cached=True)

        if skip_home_base_upgrades and exclude_home_attacks and skip_builder_base_upgrades and exclude_builder_attacks:
            # Standby mode: if everything is OFF, just sleep briefly and check again without opening CoC
            update_status("idle")
            Pause_Handler.sleep(2)
            return

        if start_coc(force=False):
            # Random pauses between features so the activity rhythm
            # never looks machine-regular
            pause = lambda: Pause_Handler.sleep(random.uniform(1.5, 6.0))

            update_status("now")
            worked = False   # did this round fight a battle or start any upgrade?

            # Check home base
            if not skip_home_base_upgrades or not exclude_home_attacks:
                to_home_base(ref_cache=True)

            if not skip_home_base_upgrades:
                worked |= bool(self.upgrader.run_home_base(exclude_home_base, exclude_home_lab))
                pause()
            if not exclude_home_attacks:
                worked |= bool(self.attacker.run_home_base(restart=True))
                pause()

            # Check builder base
            if not skip_builder_base_upgrades or not exclude_builder_attacks:
                to_builder_base(ref_cache=True)
                worked = True   # its flows don't report back yet: never rest on them

            if not skip_builder_base_upgrades:
                self.upgrader.collect_builder_attack_elixir()
                self.upgrader.run_builder_base(exclude_builder_base, exclude_builder_lab)
                pause()
            if not exclude_builder_attacks:
                self.attacker.run_builder_base(restart=True)

            update_status(time.time())

            # Busy rounds follow each other right away, CoC kept open. A round
            # with nothing to do (storages full, builders and lab busy) closes
            # CoC and rests: BlueStacks drawing the open game nonstop is what
            # keeps the Mac hot (~75% CPU vs ~2% with CoC closed)
            if not worked and not Task_Handler.rest_when_idle_excluded():
                self.rest()
                return

        # Varied idle between cycles (never a fixed heartbeat)
        Pause_Handler.sleep(random.uniform(2.5, 9.0))

    def rest(self):
        """Close CoC and wait the rest time (±15%), waking early when a
        switch changes in the app (Pause still works as everywhere)."""
        import time, random
        minutes = Task_Handler.setting("rest_minutes", getattr(configs, "CHECK_INTERVAL", 5))
        until = time.time() + max(1, minutes) * 60 * random.uniform(0.85, 1.15)
        print(f"😴 Nothing to do this round: CoC closes until {time.strftime('%H:%M', time.localtime(until))} so the Mac stays cool")
        stop_coc()
        update_status("resting", until=until)

        def switches():
            try: return set(Task_Handler.get_exclusions())
            except (KeyboardInterrupt, SystemExit): raise
            except Exception: return None   # no app reachable: just rest
        before = switches()
        while (left := until - time.time()) > 0:
            Pause_Handler.sleep(min(3, left))
            now = switches()
            if before is None: before = now
            elif now is not None and now != before:
                print("⏰ A switch changed in the app: checking right away")
                return
