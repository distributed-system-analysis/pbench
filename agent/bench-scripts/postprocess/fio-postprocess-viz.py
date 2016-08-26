#!/usr/bin/env python2.7
import os
join = os.path.join
try:
    from configparser import SafeConfigParser
except ImportError:
    from ConfigParser import SafeConfigParser

html = \
"""
<html>
<head>
<title>Latency</title>
<link rel="stylesheet" href="/static/css/v0.3/jschart.css"/>
</head>
<body>
<script src="/static/js/v0.3/d3.min.js" charset="utf-8"></script>
<script src="/static/js/v0.3/d3-queue.min.js" charset="utf-8"></script>
<script src="/static/js/v0.3/jschart.js" charset="utf-8"></script>
<script src="/static/js/v0.3/saveSvgAsPng.js" charset="utf-8"></script>
<div id='jschart_latency'>
  <script>
    create_graph(0, "%s", "jschart_latency", "Percentiles", "Time (s)", "Latency (s)",
        { plotfiles: [ "avg.log", "median.log", "p90.log",
                       "p99.log", "min.log", "max.log" ],
          sort_datasets: false, x_log_scale: false
        });
  </script>
</div>
<script>finish_page()</script>
</body>
</html>
"""

columns = ["samples", "min", "avg", "median", "p90", "p95", "p99", "max"]

def main(ctx):

  out_files = [open(join(ctx.DIR, "%s.log" % c), 'w') for c in columns]
  for i in range(len(columns)):
    out_files[i].write("#LABEL:%s\n" % columns[i])

  with open(join(ctx.DIR, 'hist.csv'), 'r') as csv:
    csv.readline()
    for line in csv:
      vs = line.split(', ')
      for i in range(len(columns)):
        out_files[i].write("%d %s\n" % (int(vs[0]), vs[i+1].rstrip()))

  chart_type = "xy"
  cp = SafeConfigParser(allow_no_value=True)
  cp.read(ctx.job_file)
  for s in cp.sections():
    try:
      epoch = cp.get(s, 'log_unix_epoch')
      chart_type = "timeseries"
    except:
      pass
  print ("Chart Type: %s" % chart_type)
  with open(join(ctx.DIR, 'results.html'), 'w') as fp:
    fp.write(html % (chart_type,))

if __name__ == '__main__':
  import argparse
  p = argparse.ArgumentParser()
  arg = p.add_argument
  arg('-j', '--job-file', help='fio job file')
  arg('DIR', help='results directory')
  main(p.parse_args())

