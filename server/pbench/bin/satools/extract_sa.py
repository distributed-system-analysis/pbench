#!/usr/bin/env python3

import os
import re
import sys
import subprocess
import configparser
from satools import oscode
from distutils.spawn import find_executable
from optparse import OptionParser, make_option

try:
    from configparser import SafeConfigParser, NoSectionError, NoOptionError
except:
    from ConfigParser import SafeConfigParser, NoSectionError, NoOptionError

    
nodename_pattern = re.compile(r'nodename=".*"')
BASE_DIR = os.path.abspath(os.path.dirname('__file__'))
DEFAULT_SADF_PATH = find_executable('sadf')

# TODO:
# check if DEFAULT_SADF_PATH is empty (covered under process_binary())

# check 'sadf -H <file path>' to get magic / sysstat version
# sadf from lower versions of sysstat (< 11.1.1) can't convert binaries [2]
# Have to explicity check versions [2] and then deal with
# absence/presence/compatiblity of default sadf package [1].
# Can't just trigger a convert_binary() if it isn't a feature on
# that machine's sysstat package.

# check support in sysstat.py for 0x2173 [1]

# refs:
# 1. https://travis-ci.org/distributed-system-analysis/pbench/jobs/223449263#L876
# 2. http://mcs.une.edu.au/doc/sysstat/FAQ


class ConfigFileNotSpecified(Exception):
    pass

class ConfigFileError(Exception):
    pass


def extract_xml(sa_file_path='/tmp/sa01',
                sadf_script_path=DEFAULT_SADF_PATH):
    CMD_CONVERT = ['-x', "--", "-A"]
    CMD_CONVERT.insert(0, sadf_script_path)
    CMD_CONVERT.insert(-2, sa_file_path)
    
    target = os.path.dirname(sa_file_path)
    filename = os.path.basename(sa_file_path)    
    p1 = subprocess.Popen(
        CMD_CONVERT,
        env={'LC_ALL': 'C', 'TZ': 'UTC'},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1
    )

    XML_DATA = ''
    with p1.stdout:
        for line in iter(p1.stdout.readline, b''): 
            XML_DATA+=line.decode('utf-8')
    rc = p1.wait()
    err = p1.stderr
    err = err.read().decode()
    if rc == 0:
        print(err, file=sys.stdout)
        NODENAME = nodename_pattern.findall(XML_DATA)[0]\
                                   .replace("nodename=","").replace('"','')
        return (True, rc, NODENAME, XML_DATA)
    else:
        print(err, file=sys.stderr)
        del XML_DATA
        possible_error_patterns = [
            "sysstat version",
            "cannot read the format",
            "can no longer read the format",
            "sar/sadc",
        ]
        if any(pattern in err for pattern in possible_error_patterns):
            return (True, rc, None, None)
        else:
            print("ERROR: Supplied path doesn't yield an SA binary file. Check your input!", file=sys.stderr)
            # sys.exit(rc)
            return (False, rc, None, None)
        

def convert_binary(sa_file_path='/tmp/sa01',
                   sadf_script_path=DEFAULT_SADF_PATH):
    """
    From sadf man page:
    
    >> Convert an old system activity  binary  datafile  
    >> (version  9.1.6  and later) to current up-to-date format. 
    >> Use the following syntax:
    >>     $ sadf -c old_datafile > new_datafile
    """
    SA_FILEPATH_CONV = "%s_conv" % sa_file_path
    CMD_CONVERT = [sadf_script_path, '-c', sa_file_path]
    p2 = subprocess.Popen(CMD_CONVERT, stdout=open(SA_FILEPATH_CONV ,'w'),
                            stderr=subprocess.PIPE, env={'LC_ALL': 'C', 'TZ': 'UTC'})
    # p2.wait()
    err = p2.stderr
    if err:
        err = err.read().decode()
        print(err, file=sys.stderr)
        if "Cannot convert" in err:
            os.remove(SA_FILEPATH_CONV)
            return (False, '')

    print("converted binary to current version of sysstat..")
    print(p2.communicate()[0])

    return (True, SA_FILEPATH_CONV)


def check_sadf_compliance(sa_file_path='/tmp/sa01', cfg_name=None, path=None):
    """
    Attempt to determine os-code for a SA binary which failed to
    convert to XML in first go. If attempt fails, try to convert that
    binary to be compatible with a newer sysstat version using `sadf -c`.
    
    Returns: 
    - (True, path-to-new-sa-binary) if conversion happens
    - (False, os-code) if conversion failed and we now need OS specific 
      sadf binaries to process this SA file.
    """
    res = oscode.determine_version(file_path=sa_file_path)
    if res[0]:
        print("compatible OS version for this binary: %s" % res[1])
        script_path = os.path.join(path, "sadf-%s-64" % res[1])
        if os.path.exists(script_path):
                return extract_xml(sa_file_path=sa_file_path,
                                   sadf_script_path=script_path)
        else:
            msg = "Appropriate sadf-<type>-<arch> script necessary to process this file not found!\n"
            msg += "Please provide a path to folder containing sadf script corresponding to Red Hat OS: %s\n" % res[1] 
            msg += "Path should be configured under [SAR] section in %s" % cfg_name
            print(msg, file=sys.stderr)
            # sys.exit(1)
            return (False, 1, None, None)

    else:
        print("ERROR: [oscode/sysstat-version]::[file-magic] record for this binary not found.", file=sys.stderr)
        print("Please file a bug @ https://github.com/distributed-system-analysis/satools. Thanks!", file=sys.stderr)
        # sys.exit(1)
        return (False, 1, None, None)


def dump_xml(data='', sa_file_path=None):
    XML_DUMP_FILE = os.path.basename(sa_file_path) + ".xml"
    NEW_PATH = os.path.join(
        os.path.dirname(sa_file_path),
        XML_DUMP_FILE
    )
    with open(NEW_PATH, 'w') as f:
        f.write(data)

    return NEW_PATH


def process_binary(path=None, cfg=None, write_data_to_file=False):
    """
    main block responsible for handling SA binary file.

    Returns:
    - (status, nodename, path_to_dumped_xml_file) if write_data_to_file == True
    - (status, nodename, xml_data) if write_data_to_file == False
    """

    if not DEFAULT_SADF_PATH:
        print("No executable version of sysstat found. Aborting!", file=sys.stderr)
        return (False, None, None)
    
    try:
        config = SafeConfigParser()
        config.read(cfg)
        sadf_binaries_path = config.get('SAR', 'sadf_binaries_path')
        
        extraction_status, rc, nodename, data = extract_xml(sa_file_path=path)
        if extraction_status == True and rc != 0:
            # Couldn't extract in one go. So then, try to convert to latest sysstat version.
            conversion_status = convert_binary(sa_file_path=path)

            if conversion_status[0]:
                extraction_status, rc, nodename, data = extract_xml(sa_file_path=conversion_status[1])
                os.remove(conversion_status[1])        
                if extraction_status == True and rc != 0:
                    # Per se, extraction failed after conversion to latest sysstat version's format.
                    # So now, try to detect oscode and follow that path.
                    print("Failed to extract converted binary. Checking oscode..", file=sys.stderr)
                    extraction_status, rc, nodename, data = check_sadf_compliance(sa_file_path=path,
                                                                              cfg_name=cfg,
                                                                              path=sadf_binaries_path)
            else:
                # so to speak, failed to convert to latest sysstat's versioning.
                # Fall back to oscode detection route. 
                extraction_status, rc, nodename, data = check_sadf_compliance(sa_file_path=path,
                                                                          cfg_name=cfg,
                                                                          path=sadf_binaries_path)
        if write_data_to_file and extraction_status:
            xml_file_path = dump_xml(data=data, sa_file_path=path)
            del data
            return (extraction_status, nodename, xml_file_path)
        else:
            return (extraction_status, nodename, data)
                    
    except ConfigFileNotSpecified as e:
        print(e, file=sys.stderr)

    except ConfigFileError as e:
        print(e, file=sys.stderr)

    except Exception as e:
        print("Other error", e, file=sys.stderr)
        import traceback
        print(traceback.format_exc())
        

if __name__ == '__main__':

    usage = "Usage: extract_sa.py [--config <path-to-pbench-index.cfg>] <path-to-sa-binary>"
    parser = OptionParser(usage)
    o = make_option("-c", "--config", dest="cfg_name", help="Specify config file")
    parser.add_option(o)
    (options, args) = parser.parse_args()
    if not options.cfg_name:
        parser.error('Path to pbench-index.cfg required.')
    
    try:
        SA_FILEPATH = args[0]
        status, nodename, fp = process_binary(path=SA_FILEPATH,
                                                cfg=options.cfg_name,
                                                write_data_to_file=True)
        if status:
            print("Nodename: %s" % nodename)
            print("XML data saved to: %s" % fp)
        else:
            sys.exit(1)
            
    except IndexError as e:
        parser.error("No SA binary file supplied to script")
    except Exception as e:
        print("Other error", e, file=sys.stderr)
        import traceback
        print(traceback.format_exc())
