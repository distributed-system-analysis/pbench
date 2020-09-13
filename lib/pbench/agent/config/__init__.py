import os
import pwd
import shutil

class ConfigMixIn:
    def config_activate(self):
        pbench_cfg = self.pbench_install_dir / "config"
        try:
            shutil.copy(self.config.pbench_conf, pbench_cfg)
        except shutil.Error:
            return 1
        except Exception:
            return 1
        
        return 0

class SSHMixIn:
    def ssh(self):
        ssh_key = self.pbench_install_dir / "id_rsa"

        try:
            shutil.copy(self.context.ssh_key, ssh_key)
        except shutil.Error:
            return 0
        except Exception:
            return 0
        finally:
            try:
                uid = pwd.getpwnam(self.config.user).pw_uid
                gid = pwd.getpwnam(self.config.group).pw_gid
            except KeyError:
                return 0
            else:
                if ssh_key.exists():
                    os.chown(ssh_key, uid, gid)
                    os.chmod(ssh_key, 0o600)
        
        return 1