# Copernicus and Gromacs on CoreOS

This is a work in progress. The eventual goal is to have a simple AWS cloudformation with a single small server, and an auto-scaling group of larger workers.

The next steps are to craft user-data to bring up the single node scenario, then a cloudformation to script the single node-scenario, and then a multi-node setup with EFS as a backing store and scaling policies to reduce the worker pool to 0 on idle.

The `cpcc` command could be extended to add a new `cloud` subcommand which can drive the following operations:

1. `new-cluster` - create a new cluster
1. `status` - show cluster status (number/size of server/workers)
1. `scale` - scale workers to desired number
1. `download` - download all data from cluster
1. `shutdown` - scale workers to 0 and shut master down
1. `revive` - start up master
1. `terminate` - terminate entire cluster, destroying all resources

## Status

Milestone one is almost complete.

## Proposed Milestones

### One

- Cloudformation with single-node and cooperating cpc-server and cpc-worker.
- Drive with shell/python script

### Two

- Cloudformation with small master and ASG with workers.
- Allow specification of gromacs/cpc versions
- implement `new-cluster`, `set-cluster`, `status`, `terminate` using boto

### Three

- Add persistent storage and scale-down on idle (pre-requisite: EFS in GA)
- implement `scale`, `shutdown`, `revive`

### Unscheduled

- `download`??
- GPU support
- gromacs release docker builds using jenkins
- detect cpu optimizations to choose best gromacs image

## Use it

### Create a cluster in AWS

The create-cluster.py script (which has dummy variables) will create a cluster in AWS (us-east-1 for now) consisting of a single node which runs the server and a worker. The script will output its IP address which you can use to login via `cpcc`.

You will need to have your AWS credentials in the file used by boto (python AWS library): http://boto.readthedocs.org/en/latest/boto_config_tut.html

This essentially fulfills the first milestone.

### Run the server/worker

Bring up a CoreOS host, and add the `cpc-server.service` and `cpc-worker.service` to `/etc/systemd/system` and run `sudo systemctl daemon-reload`. Then start them with `sudo systemctl start cpc-server cpc-worker`.

### Run the client (on the same host)

- docker run --rm -ti --net=host --volumes-from soellman/gromacs copernicus bash
- cpcc add-server -n test localhost
- cpcc use-server test
- cpcc login cpc-admin

## Strategies

### cluster upgrades

- Don't support them. Really. One cluster has one version of Copernicus and one version of gromacs.
- Maybe a simple cpc/gromacs version update on an EMPTY cluster.

### gromacs versions

- one tag set per version
- e.g. 5.1-intel-avx-gpu, 5.1-intel-sse-gpu, 5.1-amd-avx-gpu
- we need some util to detect right version so copernicus can create the right gromacs volume container
