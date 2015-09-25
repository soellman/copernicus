#!/usr/bin/env python

import os
import re
import string
import sys
import time

import boto

# args
cluster_name = "test"
instance_type = "t2.micro"
access_cidr = "0.0.0.0/0"
password = "initial"

def key_exists_aws(name):
    keys = ec2.get_all_key_pairs()
    return name in [x.name for x in keys]

def key_exists_local(name):
    fname = os.path.join(key_dir, name+".pem")
    return os.path.isfile(fname)

def create_key(name):
    key = ec2.create_key_pair(name)
    try:
        key.save(key_dir)
        return os.path.join(key_dir, name+".pem")
    except:
        return ""

def get_cf_template():
    with open("copernicus-cf.json", "r") as cft:
        return cft.read()

# read a file to a string, indented 8 spaces
def service_from_file(filename):
    output = ""
    with open(filename, "r") as unitfile:
        for line in unitfile.readlines():
            output += "        "+line
    return output

# format a service for use in cloud-config
def start_service(service):
    return ("    - name: {}\n"
            "      command: start\n"
            "      content: |\n").format(service) + service_from_file(service) + "\n"

# construct the whole user data and template
def get_userdata(services, var_dict):
    data = userdata_base
    for service in services:
        data += start_service(service)
    return string.Template(data).safe_substitute(var_dict)

# escape double quotes
# transform to string which looks like a list of strings to json
# -> each line looks like '  "oldline\n"'
def format_userdata(data):
    lines = []
    for line in data.split("\n"):
        # neutralize "\" at end of line
        # that's a lot of backslashes!
        line = re.sub(r"\\$", "\\\\\\\\", line)
        # escape all double-quotes
        line = line.replace('\"', '\\"')
        # pretend this line is a slice of a json file
        line = '  \"{}\\n\"'.format(line)
        lines.append(line)
    return string.join(lines, ",\n")


# const
cpc_prefix = "cpc-cluster"
key_dir = os.path.join(os.path.expanduser("~"), ".ssh")
services = ["cpc-server.service", "cpc-worker.service"]
userdata_base = ("#cloud-config\n"
                 "coreos:\n"
                 "  update:\n"
                 "    reboot-strategy: off\n"
                 "  units:\n"
                 "    - name: etcd2.service\n"
                 "      command: start\n")

# vars
key_name = cpc_prefix + "-" + cluster_name
stack_name = cpc_prefix + "-" + cluster_name
var_dict = {
        "PASSWORD": password,
        "INSTANCE_TYPE": instance_type,
        "ACCESS_CIDR": access_cidr,
        "KEY_NAME": key_name,
}




# START
# check if cluster already exists
# do some local check to see if cpc already knows about the cluster

print "Creating key and cluster named \"{}\"".format(cluster_name)

iam = boto.connect_iam()
user = iam.get_user()
print "Using user: {}".format(user.get_user_response.get_user_result.user.arn)


ec2 = boto.connect_ec2()

# unless keys exist, create one
if key_exists_aws(key_name):
    print "Exiting: key \"{}\" already exists in AWS.".format(key_name)
    sys.exit(1)

if key_exists_local(key_name):
    print "Exiting: key \"{}\" already exists in your ssh directory.".format(key_name)
    sys.exit(1)

key = create_key(key_name)
if key == "":
    print "Exiting: unable to create key \"{}\"".format(key)
    sys.exit(1)
else:
    print "Saved key \"{}\".".format(key)



# let's do it
var_dict["USERDATA"] = format_userdata(get_userdata(services, var_dict))
cf = string.Template(get_cf_template()).safe_substitute(var_dict)
cloudformation = boto.connect_cloudformation()
cloudformation.validate_template(cf)
print "Estimated cost for stack: {}".format(cloudformation.estimate_template_cost(cf))

arn = cloudformation.create_stack(stack_name, template_body=cf)
print "ARN of new stack: {}".format(arn)


#
# store keyname and cf name with cluster-name
#

asg_name = ""
while asg_name == "":
      stack = cloudformation.describe_stacks(stack_name)
      if len(stack) == 1:
          stack = stack[0]
      else:
          print "Too many stacks!!"
      print "Stack {} has status {}".format(stack.stack_name, stack.stack_status)

      if stack.stack_status == "CREATE_COMPLETE":
          asg_name = next((output.value for output in stack.outputs if output.key == "ASGName"), "not found")
          print "Found ASG: {}".format(asg_name)
          break

      time.sleep(5)

autoscale = boto.connect_autoscale()
group = autoscale.get_all_groups([asg_name])
if len(group) == 1:
    group = group[0]
else:
    print "Too many groups!!"
instance_ids = [i.instance_id for i in group.instances]
reservations = ec2.get_all_instances(instance_ids)
instances = [i for r in reservations for i in r.instances]

print "Your cpc-server ({}) has address {}".format(instances[0].id, instances[0].ip_address)

