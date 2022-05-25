Here are two URLs representing the "perf188" directory object of an unpacked tar ball.  The "old" is the existing v0.69 Pbench Server way of exposing the unpacked tar ball contents, the "new" is an example the proposal.  See below for more concrete examples.

{*}Old{*}: {{/incoming/perf102.perf.lab.eng.bos.redhat.com/trafficgen_config0_2021-12-01T07:01:45/1-none-bidirectional-64B-128flows-0.002pct_drop/sample2/tools-default/perf188}}

{*}New{*}: {{/api/vi/inventory/trafficgen_config0_2021-12-01T07:01:45/1-none-bidirectional-64B-128flows-0.002pct_drop/sample2/tools-default/perf188}}

Components of new API URI {{{}/api/v1/inventory/<{*}dataset{*}>{}}}[ {{<{*}path{*}>}} ]:
 * {{{}*dataset*{}}}: E.g. {{trafficgen_config0_2021-12-01T07:01:45}}
 * {{*path*}} (optional): E.g.{{{}/1-none-bidirectional-64B-128flows-0.002pct_drop/sample2/tools-default/perf188{}}}
 ** Note that the {{*path*}} must contain a leading slash ("{{{}/{}}}"), which represents the "root" directory of the tar ball contents
 * {{*HEAD*}} or {{*GET*}} on API URI {{/api/v1/inventory/<{*}dataset{*}>}} (no path specified)
 ** If dataset does not exist, returns 404
 ** If dataset is not in inventory, but exists (i.e. the tar ball exists, but is not unpacked)
 *** returns 307 to indicate dataset is being loaded, URI returned is a dataset load operation object (TBD) where HEAD on that object returns a 201 when it is loaded, and 307 to itself indicating still loading
 ** If dataset is in inventory, returns 200
 * {{*HEAD*}} on API URI {{/api/v1/inventory/<{*}dataset{*}><{*}path{*}>}} (path _*IS*_ specified)
 ** Returns a 400 if the {{*dataset*}} does not exist
 ** Returns a 404 if the {{*path*}} does not exist
 ** When {{*path*}} exists, returns a status 200, headers contain metadata about the object
 * {{*GET*}} on API URI {{/api/v1/inventory/<{*}dataset{*}><{*}path{*}>}} (path _*IS*_ specified)
 ** Returns a 400 if the {{*dataset*}} does not exist
 ** Returns a 404 if the {{*path*}} does not exist
 ** When {{*path*}} exists, headers contain metadata about the object
 *** If symlink, status 302 with payload a URL to symlinked object
 *** If directory, status 200, returns payload of directory contents as a JSON object
 *** If file, status 200, returns payload of file contents