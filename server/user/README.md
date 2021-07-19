Quick-n-Dirty installation of bit-rot detection in the `pbench` user's home
directory:

  1. mkdir -p /home/pbench/bin
  2. cp bitrot-detect /home/pbench/bin/bitrot-detect
  3. chmod 755 /home/pbench/bin/bitrot-detect
  4. # Modify bitrot-detect.service to reference archive hierarchy path
     # - either /srv/pbench/archive/fs-version-001 or the archive directory
     # - on the NFS volume. 
     # Modify bitrot-detect.timer to use the time and date to run the bit-rot
     # - detection periodically.
  5. cp bitrot-detect.timer bitrot-detect.service /home/pbench/.config/systemd/user/
  6. systemctl --user enable bitrot-detect.service
  7. systemctl --user enable bitrot-detect.timer
