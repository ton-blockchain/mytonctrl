from __future__ import annotations

from mypyconsole.mypyconsole import MyPyConsole
from mypylib import MyPyClass

from mytoncore.utils import get_package_resource_path
from mytoncore.mytoncore import MyTonCore
from mytonctrl.warnings import WarningChecker


class MyTonCtrl:
    def __init__(self, local: MyPyClass, ton: MyTonCore, console_engine: MyPyConsole):
        self.local = local
        self.ton = ton
        self._warning_checker = WarningChecker(local, ton)
        self._console_engine = console_engine

    def _add_console_commands(self):
        from modules.general import GeneralModule

        module = GeneralModule(self.ton, self.local)
        module.add_console_commands(self._console_engine)

        from modules.backups import BackupModule

        module = BackupModule(self.ton, self.local)
        module.add_console_commands(self._console_engine)

        from modules.custom_overlays import CustomOverlayModule

        module = CustomOverlayModule(self.ton, self.local)
        module.add_console_commands(self._console_engine)

        from modules.btc_teleport import BtcTeleportModule

        module = BtcTeleportModule(self.ton, self.local)
        module.add_console_commands(self._console_engine)

        if self.ton.using_validator():
            from modules.validator import ValidatorModule

            module = ValidatorModule(self.ton, self.local)
            module.add_console_commands(self._console_engine)

            from modules.wallet import WalletModule

            module = WalletModule(self.ton, self.local)
            module.add_console_commands(self._console_engine)

            from modules.utilities import UtilitiesModule

            module = UtilitiesModule(self.ton, self.local)
            module.add_console_commands(self._console_engine)

            if (
                self.ton.using_pool()
            ):  # add basic pool functions (pools_list, delete_pool, import_pool)
                from modules.pool import PoolModule

                module = PoolModule(self.ton, self.local)
                module.add_console_commands(self._console_engine)

            if self.ton.using_nominator_pool():
                from modules.nominator_pool import NominatorPoolModule

                module = NominatorPoolModule(self.ton, self.local)
                module.add_console_commands(self._console_engine)

            if self.ton.using_single_nominator():
                from modules.single_pool import SingleNominatorModule

                module = SingleNominatorModule(self.ton, self.local)
                module.add_console_commands(self._console_engine)

            if self.ton.using_liquid_staking():
                from modules.controller import ControllerModule

                module = ControllerModule(self.ton, self.local)
                module.add_console_commands(self._console_engine)

        if self.ton.using_validator() or self.ton.using_collator():
            from modules.collator_config import CollatorConfigModule

            module = CollatorConfigModule(self.ton, self.local)
            module.add_console_commands(self._console_engine)

        if self.ton.using_collator():
            from modules.collator import CollatorModule

            module = CollatorModule(self.ton, self.local)
            module.add_console_commands(self._console_engine)

        if self.ton.using_alert_bot():
            from modules.alert_bot import AlertBotModule

            module = AlertBotModule(self.ton, self.local)
            module.add_console_commands(self._console_engine)

    def _pre_up(self):
        try:
            self.local.try_function(self._warning_checker.check_mytonctrl_update)
            self.local.try_function(self._warning_checker.check_installer_user)
            self.local.try_function(self._warning_checker.check_vport)
            self._warning_checker.run_warnings()
        except Exception as e:
            self.local.add_log(f"PreUp error: {e}", "error")

    def run(
        self,
        skip_startup_checks: bool = False,
        cmd: str | None = None,
    ):
        with get_package_resource_path(
            "mytonctrl", "resources/translate.json"
        ) as translate_path:
            self.local.init_translator(str(translate_path))

        self._add_console_commands()

        self.local.db.config.isLocaldbSaving = False
        self.local.run()

        if not skip_startup_checks:
            self._pre_up()

        if cmd is not None:
            if not self._console_engine.run_cmd(cmd):
                raise SystemExit(1)
            return

        self._console_engine.run()
