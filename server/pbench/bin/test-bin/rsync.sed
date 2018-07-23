#  Total file size: 0 bytes
#  Total transferred file size: 0 bytes
s/(Total (transferred )?file size:) [0-9,]+ (bytes)/\1 # \3/
#  Literal data: 0 bytes
#  Matched data: 0 bytes
s/((Literal|Matched) data:) [0-9,]+ (bytes)/\1 # \3/
#  File list size: 40
s/(File list size:) [0-9,]+/\1 #/
#  File list generation time: 0.001 seconds
#  File list transfer time: 0.000 seconds
s/(File list (generation|transfer) time:) [0-9,]+\.[0-9]+ (seconds)/\1 #.### \3/
#  Total bytes sent: 52
s/(Total bytes sent:) [0-9,]+/\1 #/
#  Total bytes received: 15
s/(Total bytes received:) [0-9,]+/\1 #/
#  sent ### bytes  received ### bytes  ###.## bytes/sec
s;(sent) [0-9,]+ (bytes  received) [0-9,]+ (bytes)  [0-9,]+\.[0-9]+ (bytes/sec);\1 # \2 # \3  #.### \4;
#  total size is 0  speedup is 0.00
s/(total size is) [0-9,]+  (speedup is) [0-9,]+\.[0-9]+/\1 #  \2 #.##/
#  Number of regular files transferred: 0
s/(Number of) (regular )?(files transferred: [0-9,]+)/\1 \3/
# Number of created files: 0
# Number of deleted files: 0
/Number of (created|deleted) files: /d 
#  Number of files: 0 (dir: 1, reg: 3)
s/(Number of files:) ([0-9,]+)( .+)?/\1 \2/
