#!/usr/bin/python

__author__ = 'jonathan'

import sys
import os
import unittest
import subprocess
import tempfile
from pprint import pprint

TESTS = [
    [ 'env_create', 'east', 'dev', 'example' ],
    [ 'unit_create', 'east', 'dev', 'example' ],
    [ 'unit_add', 'east', 'dev', 'example' ],
]

test_root = os.path.abspath(os.path.dirname(sys.argv[0]))
china_repo_root = os.path.abspath(test_root + "/..")
ec2_stubs = test_root + "/ec2stubs"
china_bin = china_repo_root + "/bin"

if 'PYTHONPATH' in os.environ:
    china_env = {"PYTHONPATH": china_bin + ":" + os.environ['PYTHONPATH']}
else:
    china_env = {"PYTHONPATH": china_bin}

china_env['HOME'] = os.environ['HOME']
china_env['PATH'] = china_bin + ":" + ec2_stubs + ":" + os.environ['PATH']
china_env['EC2_STUBS'] = ec2_stubs
china_env['unit_domain'] = 'unit.example.com'

china_env['CHINA_BLUEPRINT_DIR'] =  test_root + "/blueprints"

def cleanup_line_endings(output):
    clean = ""
    for line in output.split('\n'):
        if line.strip().startswith("#"):
            continue
        clean += line.strip()+"\n"
    return clean

class TestChina(unittest.TestCase):

    def run_china_process(self, args, china_env):
        print "running: " + ' '.join(args)
        child = subprocess.Popen(args, shell=False, stdout=subprocess.PIPE, cwd=china_bin, env=china_env)
        output = child.communicate()
        stdout = output[0]
        return stdout

    def run_china_env_create(self, region, env, unit, test_log):
        args = [ 'china_env_create',
                 "-r", region,
                 "-e", env,
                 "-u", unit ]
        # Executed commands will log their call order and arguments here
        china_env['CHINA_TEST_LOG'] = test_log.name
        return self.run_china_process(args, china_env)

    def run_china_unit_create(self, region, env, unit, role, test_log):
        args = [ 'china_unit_create',
                 "-r", region,
                 "-e", env,
                 "-u", unit,
                 "-l", role ]
        # Executed commands will log their call order and arguments here
        china_env['CHINA_TEST_LOG'] = test_log.name
        china_env['ACTIVE_UNIT'] = unit
        return self.run_china_process(args, china_env)

    def run_china_unit_add(self, region, env, unit, role, test_log):
        args = [ 'china_unit_add',
                 "-r", region,
                 "-e", env,
                 "-u", unit,
                 "-l", role ]
        # Executed commands will log their call order and arguments here
        china_env['CHINA_TEST_LOG'] = test_log.name
        china_env['ACTIVE_UNIT'] = unit
        return self.run_china_process(args, china_env)

    def test_china(self):
        failed_tests = []
        for test in TESTS:
            command = test[0]
            region = test[1]
            env = test[2]
            unit = test[3]
            prefix = command+"_"+region+"_"+env+"_"+unit
            # print "running test: "+prefix
            china_log = tempfile.NamedTemporaryFile(prefix='test_cn_'+prefix, delete=False)

            if command == "env_create":
                self.run_china_env_create(region, env, unit, china_log)
            elif command == "unit_create":
                self.run_china_unit_create(region, env, unit, unit, china_log)
            elif command == "unit_add":
                self.run_china_unit_add(region, env, unit, unit, china_log)
            else:
                raise Exception("unknown command: "+command)

            with open(china_log.name) as data:
                actual_output = data.read()

            with open(test_root+"/expected/" + prefix +"_output.txt") as data:
                expected_output = data.read().strip()

            actual_output = actual_output.replace(ec2_stubs+"/", '').strip()
            actual_output = cleanup_line_endings(actual_output)
            expected_output = cleanup_line_endings(expected_output)
            expected_output = expected_output.replace("{{HOME}}", os.environ['HOME'])

            if (actual_output != expected_output):
                china_log.write(actual_output)
                failure = "(c=" + command + ",r=" + region + ",e=" + env + ",u=" + unit + "): " + china_log.name
                failed_tests += failure
                print "failed: "+ failure + ", \nactual=\n"+actual_output+"\n\nexpected=\n"+expected_output+"\n"
                sys.exit(0)
            else:
                print "success ------ actual="+actual_output

        self.assertFalse(failed_tests, "test failures: "+"\n".join(failed_tests))

if __name__ == '__main__':
    unittest.main()
