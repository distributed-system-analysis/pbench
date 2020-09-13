import shutil

class ConfigMixIn:
    def config_activate(self):
        pbench_cfg = self.pbench_install_dir / "config"
        try:
            shutil.copy(self.config.pbench_conf, pbench_cfg)
        except shutil.Error as ex:
            return 1
        except Exception as ex:
            return 1
        
        return 0