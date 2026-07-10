from utils import *
from configs import *
from upgrader import Upgrader
from attacker import Attacker

class CoC_Bot:
    def __init__(self):
        BlueStacks_Manager.init()
        assert ADB_Manager.connect(60), "Failed to connect to ADB"
        self.upgrader = Upgrader()
        self.attacker = Attacker()
    
    # ============================================================
    # ⏱️ Task Execution
    # ============================================================
    
    def run(self):
        import time
        
        while True:
            try:
                if not running():
                    time.sleep(1)
                    continue
                
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
                    time.sleep(2)
                    continue

                if start_coc(force=False):
                    import random
                    # Random pauses between features so the activity rhythm
                    # never looks machine-regular
                    pause = lambda: time.sleep(random.uniform(1.5, 6.0))

                    update_status("now")

                    # Check home base
                    if not skip_home_base_upgrades or not exclude_home_attacks:
                        to_home_base(ref_cache=True)

                    if not skip_home_base_upgrades:
                        self.upgrader.run_home_base(exclude_home_base, exclude_home_lab)
                        pause()
                    if not exclude_home_attacks:
                        self.attacker.run_home_base(restart=True)
                        pause()

                    # Check builder base
                    if not skip_builder_base_upgrades or not exclude_builder_attacks:
                        to_builder_base(ref_cache=True)

                    if not skip_builder_base_upgrades:
                        self.upgrader.collect_builder_attack_elixir()
                        self.upgrader.run_builder_base(exclude_builder_base, exclude_builder_lab)
                        pause()
                    if not exclude_builder_attacks:
                        self.attacker.run_builder_base(restart=True)

                    # End of active cycle: do NOT stop CoC, just loop immediately back to check if toggles are still ON
                    update_status(time.time())

                # Varied idle between cycles (never a fixed heartbeat)
                import random
                time.sleep(random.uniform(2.5, 9.0))
            
            except (KeyboardInterrupt, SystemExit): raise
            except Exception as e:
                import traceback
                traceback.print_exc()
                stop_coc()
                update_status("error")
