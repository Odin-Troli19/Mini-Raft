# 🚀 Quick Start Guide

Get Mini-Raft up and running in 5 minutes!

## Prerequisites

- Python 3.8 or higher
- pip package manager

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Option 1: Interactive Demo (Easiest)

Run the automated demo to see Raft in action:

```bash
python demo.py
```

This will show you:
- Leader election
- Log replication
- Fault tolerance
- State machine consistency

## Option 2: Manual Cluster (For Testing)

### 1. Start a Cluster

```bash
# Generate configuration for 5 nodes
python cli.py start --nodes 5 --base-port 8000

# Start the cluster
./start_cluster.sh
```

### 2. Monitor in Real-Time

In a new terminal:

```bash
python cli.py watch --base-port 8000 --nodes 5
```

You'll see a beautiful dashboard showing:
- Node states (Leader/Follower/Candidate)
- Current terms
- Commit indices
- Metrics

### 3. Send Commands

In another terminal:

```bash
# Set a value
python -c "
import asyncio
from cli import request
asyncio.run(request(8000, 'greeting', 'Hello Raft!', 'set'))
"

# Get the value back
python -c "
import asyncio
from cli import request
asyncio.run(request(8000, 'greeting', None, 'get'))
"
```

### 4. Test Fault Tolerance

Kill the leader and watch a new election:

```bash
# Find the leader's port from the watch command
# Then kill it
kill <leader-pid>

# Watch the election happen in the monitor!
```

## Option 3: Docker (Production-Like)

```bash
# Build and start
docker-compose up -d

# Watch logs
docker-compose logs -f node-0

# Stop
docker-compose down
```

## Quick Commands (Using Makefile)

```bash
# See all available commands
make help

# Start 5-node cluster
make start-5

# Watch cluster
make watch

# Run tests
make test

# Run chaos tests
make chaos

# Clean everything
make clean
```

## Next Steps

1. **Read the Design Doc**: `DESIGN.md` for architecture details
2. **Run Tests**: `make test` to see comprehensive testing
3. **Experiment**: Try killing nodes, partitioning network, etc.
4. **Learn More**: Check out the Raft paper at https://raft.github.io

## Common Issues

### "Address already in use"

Another process is using the port. Either kill it or use different ports:

```bash
python cli.py start --nodes 5 --base-port 9000
```

### "No leader elected"

Network issues or too many nodes down. Ensure:
- At least 3 nodes running (for 5-node cluster)
- No firewall blocking localhost
- Election timeout not too short

### Tests failing

Make sure no cluster is running:

```bash
make stop
make clean
make test
```

## Example Session

```bash
# Terminal 1: Start cluster
make clean
make start-5
./start_cluster.sh

# Terminal 2: Watch
make watch

# Terminal 3: Send requests
python demo.py  # Or manual commands

# When done
make stop
make clean
```

## What to Try

1. **Basic Operations**
   - Set, get, delete keys
   - Watch values replicate

2. **Failure Scenarios**
   - Kill the leader (watch re-election)
   - Kill a follower (watch system continue)
   - Kill 2 followers (watch system stall)

3. **Performance**
   - Send 100 requests, measure latency
   - Run chaos tests

4. **Code Exploration**
   - Read `raft.py` to understand the protocol
   - Check `test_raft.py` for test scenarios
   - Explore `cli.py` for monitoring tools

## Learning Path

1. ✅ Run the demo
2. ✅ Start a cluster manually
3. ✅ Send some commands
4. ✅ Kill a node, watch election
5. ⬜ Read the design doc
6. ⬜ Read the Raft paper
7. ⬜ Explore the code
8. ⬜ Run all tests
9. ⬜ Try chaos testing
10. ⬜ Modify and experiment!

## Getting Help

- Check the main `README.md` for detailed docs
- Read `DESIGN.md` for architecture
- Look at test cases in `test_raft.py`
- Read the Raft paper: https://raft.github.io/raft.pdf

## Contributing

Found a bug? Want to add a feature?

1. Check `DESIGN.md` for architecture
2. Write tests first
3. Make your changes
4. Run `make test` and `make quality`
5. Submit a PR!

---

Happy learning! 🎓🚀