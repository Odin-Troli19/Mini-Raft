# 🚀 Mini-Raft: Production-Ready Raft Consensus Implementation

A complete, production-quality implementation of the Raft consensus algorithm with leader election, log replication, snapshotting, and comprehensive observability.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 🎯 Features

### Core Features
- ✅ **Leader Election** with randomized timeouts
- ✅ **Log Replication** with append entries RPC
- ✅ **Persistent Storage** with crash recovery
- ✅ **State Machine Replication** (key-value store)
- ✅ **Snapshotting** for log compaction
- ✅ **Membership Changes** (configuration changes)

### Stretch Features
- 🔥 **Real-time Monitoring CLI** with Rich UI
- 🔥 **Comprehensive Metrics** (Prometheus-compatible)
- 🔥 **Chaos Testing Framework** for fault injection
- 🔥 **HTTP RPC** with proper timeout handling
- 🔥 **Extensive Test Suite** (unit + integration + chaos)

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────┐
│                  Raft Cluster                       │
│                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    │
│  │  Node 1  │◄──►│  Node 2  │◄──►│  Node 3  │    │
│  │ (Leader) │    │(Follower)│    │(Follower)│    │
│  └────┬─────┘    └──────────┘    └──────────┘    │
│       │                                            │
│       │ Client Requests                            │
│       ▼                                            │
│  ┌──────────────────────────────┐                 │
│  │    State Machine (KV Store)  │                 │
│  └──────────────────────────────┘                 │
└─────────────────────────────────────────────────────┘
```

### Component Breakdown

1. **RaftNode** (`raft.py`)
   - Core consensus logic
   - Leader election mechanism
   - Log replication
   - State machine integration
   - Snapshot management

2. **RaftServer** (`server.py`)
   - HTTP API for RPC communication
   - Client request handling
   - Health checks and status endpoints

3. **CLI** (`cli.py`)
   - Cluster management
   - Real-time monitoring
   - Chaos testing
   - Client operations

4. **State Machine** (`raft.py`)
   - Key-value store implementation
   - Command application
   - Snapshot/restore support

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd mini-raft

# Install dependencies
pip install -r requirements.txt
```

### Start a 5-Node Cluster

```bash
# Generate cluster configuration
python cli.py start --nodes 5 --base-port 8000

# Start the cluster
./start_cluster.sh
```

### Monitor the Cluster

```bash
# Real-time monitoring with Rich UI
python cli.py watch --base-port 8000 --nodes 5
```

### Send Client Requests

```bash
# Set a value
python cli.py request --port 8000 --op set --key name --value "Alice"

# Get a value
python cli.py request --port 8000 --op get --key name

# Delete a value
python cli.py request --port 8000 --op delete --key name
```

### Run Tests

```bash
# Run all tests
pytest test_raft.py -v

# Run specific test category
pytest test_raft.py::TestLeaderElection -v

# Run with coverage
pytest test_raft.py --cov=raft --cov-report=html
```

## 📊 Monitoring & Observability

### Real-Time Dashboard

The CLI provides a beautiful real-time dashboard:

```bash
python cli.py watch --base-port 8000 --nodes 5 --refresh 1
```

Shows:
- Current node states (Leader/Follower/Candidate)
- Term numbers
- Commit indices
- Log sizes
- Election counts
- Committed entries

### Status Endpoint

Get JSON status from any node:

```bash
curl http://localhost:8000/status
```

Response:
```json
{
  "node_id": "node-0",
  "state": "leader",
  "term": 5,
  "commit_index": 42,
  "last_applied": 42,
  "log_size": 42,
  "metrics": {
    "leader_elections": 2,
    "log_entries_appended": 50,
    "log_entries_committed": 42,
    "state_changes": 3
  }
}
```

## 🧪 Testing Strategy

### Test Coverage

1. **Leader Election Tests**
   - Initial election
   - Re-election after leader failure
   - Term progression

2. **Log Replication Tests**
   - Entry replication to followers
   - Commit index advancement
   - State machine application

3. **Safety Property Tests**
   - Election safety (≤1 leader per term)
   - Log matching property
   - State machine safety

4. **Persistence Tests**
   - State recovery after crash
   - Snapshot creation and loading
   - Log compaction

5. **Network Partition Tests**
   - Majority partition operation
   - Split-brain prevention
   - Recovery after healing

6. **Chaos Tests**
   - Random node failures
   - Network latency injection
   - Partition scenarios

### Running Tests

```bash
# All tests
pytest test_raft.py -v -s

# Specific test class
pytest test_raft.py::TestLeaderElection -v

# With timeout
pytest test_raft.py --timeout=10

# With coverage report
pytest test_raft.py --cov=raft --cov-report=term-missing
```

## 🔥 Chaos Testing

Run chaos tests to validate fault tolerance:

```bash
# Run 100 random chaos operations
python cli.py chaos --operations 100

# Custom settings
python cli.py chaos --base-port 8000 --nodes 5 --operations 50
```

Chaos operations include:
- Random node failures
- Network latency injection
- Network partitions
- Message drops

## 🎓 Design Decisions

### 1. Language Choice: Python

**Why Python?**
- Rapid development and clear code
- Excellent async/await support
- Rich ecosystem (aiohttp, pytest)
- Easy to understand for learning

**Production Note:** For high-performance systems, consider Rust or Go

### 2. Storage: JSON Files

**Why JSON?**
- Simple, human-readable format
- Easy debugging and inspection
- No external database dependencies

**Production Alternative:** Use RocksDB or LevelDB for better performance

### 3. RPC: HTTP/REST

**Why HTTP?**
- Universal protocol
- Easy debugging with curl
- No special client libraries needed

**Production Alternative:** gRPC for better performance and type safety

### 4. Election Timeout: Randomized

**Implementation:**
- Min: 150ms, Max: 300ms
- Reduces split votes
- Based on Raft paper recommendations

**Tuning:** Adjust based on network latency (higher for WAN)

### 5. Heartbeat Interval: 50ms

**Why 50ms?**
- Fast enough for quick failure detection
- Not too aggressive for network traffic
- ~3x heartbeats per min election timeout

### 6. Snapshot Threshold: 100 entries

**Why 100?**
- Balances memory usage vs. snapshot overhead
- Prevents unbounded log growth
- Configurable per deployment needs

## 🔍 Implementation Details

### Leader Election

1. **Start as Follower**
   - Random election timeout (150-300ms)
   - Reset on heartbeat from leader

2. **Become Candidate**
   - Increment term
   - Vote for self
   - Request votes from peers

3. **Become Leader**
   - Receive majority votes
   - Start sending heartbeats
   - Initialize next_index/match_index

### Log Replication

1. **Client Request**
   - Only leader accepts requests
   - Append to local log
   - Return index to client

2. **Replication**
   - Send AppendEntries to all followers
   - Include previous log entry info
   - Followers check consistency

3. **Commitment**
   - Leader waits for majority replication
   - Advances commit_index
   - Applies to state machine

### Snapshotting

1. **Trigger**: Every 100 committed entries
2. **Process**:
   - Serialize state machine
   - Save last included index/term
   - Trim log entries before snapshot
   - Persist snapshot to disk

3. **Recovery**:
   - Load snapshot on startup
   - Restore state machine
   - Replay remaining log entries

## 🐛 Debugging Tips

### Check Node State

```bash
# View all nodes
python cli.py status --base-port 8000 --nodes 5

# Check specific node
curl http://localhost:8000/status | jq
```

### View Logs

Logs are written to stdout with timestamps:

```bash
# View node logs
tail -f /var/log/raft/node-0.log

# Filter for errors
grep ERROR /var/log/raft/*.log
```

### Common Issues

1. **No Leader Elected**
   - Check network connectivity
   - Verify election timeouts
   - Look for split votes in logs

2. **Entries Not Committing**
   - Verify majority of nodes running
   - Check log replication in status
   - Look for match_index progression

3. **High Latency**
   - Check network latency between nodes
   - Increase heartbeat interval
   - Reduce snapshot frequency

## 📈 Performance Tuning

### Network Tuning

```python
# Increase timeouts for WAN deployments
RaftNode(
    election_timeout_min=300,  # 300ms
    election_timeout_max=600,  # 600ms
    heartbeat_interval=100,    # 100ms
)
```

### Storage Tuning

```python
# Adjust snapshot frequency
if self.last_applied - self.last_snapshot_index >= 1000:  # More entries
    self._create_snapshot()
```

### Batch Operations

Send multiple operations in a single request for better throughput.

## 🚧 Production Considerations

### Security

- [ ] Add TLS for RPC communication
- [ ] Implement authentication/authorization
- [ ] Validate all RPC inputs
- [ ] Rate limit client requests

### Reliability

- [ ] Add retry logic with exponential backoff
- [ ] Implement circuit breakers
- [ ] Add request deduplication
- [ ] Health check improvements

### Scalability

- [ ] Implement read-only replicas
- [ ] Add batching for log entries
- [ ] Optimize snapshot transfer
- [ ] Add compression for RPC

### Observability

- [ ] Export Prometheus metrics
- [ ] Add distributed tracing
- [ ] Structured logging with correlation IDs
- [ ] Alerting rules for common failures

## 📚 References

- [Raft Paper](https://raft.github.io/raft.pdf) - "In Search of an Understandable Consensus Algorithm"
- [Raft Website](https://raft.github.io/) - Visualizations and resources
- [Raft PhD Dissertation](https://github.com/ongardie/dissertation) - Comprehensive coverage

## 🤝 Contributing

Contributions welcome! Areas for improvement:

1. **Performance**
   - Benchmark against etcd/Consul
   - Optimize RPC serialization
   - Add connection pooling

2. **Features**
   - Membership changes (joint consensus)
   - Pre-vote optimization
   - Leadership transfer

3. **Testing**
   - Add property-based tests
   - Jepsen-style consistency tests
   - Performance regression tests

4. **Documentation**
   - Architecture diagrams
   - Failure mode analysis
   - Deployment guide

## 📝 License

MIT License - see LICENSE file for details

## 🎯 Learning Resources

### Understanding Raft

1. Watch the [Raft visualization](http://thesecretlivesofdata.com/raft/)
2. Read the [Raft paper](https://raft.github.io/raft.pdf) (Section 5)
3. Try the [interactive demo](https://raft.github.io/)

### Next Steps

After mastering this implementation:

1. **Study Production Systems**
   - etcd (Go)
   - Consul (Go)
   - LogCabin (C++)

2. **Advanced Topics**
   - Paxos comparison
   - Byzantine fault tolerance
   - Distributed transactions

3. **Build On Top**
   - Distributed key-value store
   - Distributed lock service
   - Replicated state machines

---

Built with ❤️ for learning distributed systems
