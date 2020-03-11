#!/usr/bin/env python3

import sys
from os.path import join, basename
from configparser import ConfigParser

_prog = basename(sys.argv[0])

html = """<html>
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
        create_jschart(0, "{}", "jschart_latency", "Percentiles", "Time (msec)", "Latency (usec)",
            {{ plotfiles: [ {} ],
              sort_datasets: false, x_log_scale: false
            }});
      </script>
    </div>
    <script>finish_page()</script>
  </body>
</html>
"""

def main(ctx):
  columns = ["samples"]
  plot_files = ["samples.log"]
  for pct in ctx.percentiles:
    if pct == 0:
      col = "min"
    elif pct == 50.0:
      col = "median"
    elif pct == 100.0:
      col = "max"
    else:
      col = "p{:1.0f}".format(pct)
    columns.append(col)
    plot_files.append("{}.log".format(col))
  columns_l = len(columns)
  with open(join(ctx.DIR, 'hist.csv'), 'r') as csv:
    line = csv.readline()
    # FIXME: this check for the string "min, median" is a little fragile
    while line and not line.__contains__('min, median'):
      line = csv.readline()
    if not line:
      print('[{}] ERROR: hit end of file without seeing header'.format(
          _prog), file=sys.stderr)
      return 1
    out_files = [open(join(ctx.DIR, pf), 'w') for pf in plot_files]
    for i in range(columns_l):
      out_files[i].write("#LABEL:{}\n".format(columns[i]))
    for line in csv:
      vs = line.split(', ')
      for i in range(columns_l):
        out_files[i].write("{:d} {}\n".format(int(vs[0]), vs[i+1].rstrip()))
    for i in range(columns_l):
      out_files[i].close()
  chart_type = "xy"
  cp = ConfigParser(allow_no_value=True)
  cp.read(ctx.job_file)
  for s in cp.sections():
    try:
      cp.get(s, 'log_unix_epoch')
    except Exception:
      pass
    else:
      chart_type = "timeseries"
  result_file_name = join(ctx.DIR, 'results.html')
  print("[{}] Chart Type: {} ({})".format(
      _prog, chart_type, result_file_name))
  with open(result_file_name, 'w') as fp:
    list_of_plot_file_quoted_strings = [ "\"{}\"".format(pf) for pf in plot_files ]
    # Note we don't plot samples.log
    concatenated_plot_file_quoted_strings = ", ".join(list_of_plot_file_quoted_strings[1:])
    fp.write(html.format(chart_type, concatenated_plot_file_quoted_strings))
  return 0

if __name__ == '__main__':
  import argparse
  p = argparse.ArgumentParser(_prog)
  arg = p.add_argument
  arg('-j', '--job-file', help='fio job file')
  arg('-t', '--time-quantum', nargs=1, type=int, default='1',
      help='time quantum given to fio-histo-log-pctiles.py')
  arg('-p', '--percentiles', nargs='+', type=float,
      default=[ 0., 50., 95., 99., 100. ],
      help='percentiles given to fio-histo-log-pctiles.py')
  arg('DIR', help='results directory')
  ret_status = main(p.parse_args())
  sys.exit(ret_status)
