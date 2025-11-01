# Mini-Raft Project Structure

```
mini-raft/
├── README.md                    # Main documentation
├── DESIGN.md                   # Detailed design document
├── QUICKSTART.md               # Quick start guide
├── requirements.txt            # Python dependencies
├── Makefile                    # Development commands
├── Dockerfile                  # Container image definition
├── docker-compose.yml          # Multi-node deployment
│
├── Core Implementation
│   ├── raft.py                # Main Raft protocol implementation
│   ├── server.py              # HTTP RPC server
│   └── run_node.py            # Node runner script
│
├── Tools & CLI
│   ├── cli.py                 # Command-line interface
│   └── demo.py                # Interactive demo script
│
├── Testing
│   └── test_raft.py           # Comprehensive test suite
│
└── Generated at Runtime
    ├── data/                   # Node data directories
    │   ├── node-0/
    │   │   ├── state.json      # Persistent state
    │   │   └── snapshot.json   # State machine snapshot
    │   ├── node-1/
    │   └── ...
    └── start_cluster.sh        # Generated cluster start script
```

## File Descriptions

### Core Files

**raft.py** (800+ lines)
- `RaftNode` class: Core consensus implementation
- `StateMachine` class: Key-value store
- `LogEntry`, `Snapshot`: Data structures
- Leader election, log replication, snapshotting

**server.py** (200+ lines)
- `RaftServer` class: HTTP server wrapper
- RPC handlers (RequestVote, AppendEntries)
- Client request handling
- Network communication

**run_node.py** (100+ lines)
- Node startup script
- Configuration parsing
- Graceful shutdown handling

### CLI & Tools

**cli.py** (400+ lines)
- `ClusterMonitor`: Real-time status display
- `ChaosTest`: Fault injection
- Commands: start, watch, status, request, chaos
- Rich UI with tables and live updates

**demo.py** (200+ lines)
- Automated demonstration
- Leader election demo
- Log replication demo
- Fault tolerance demo
- Interactive and visual

### Testing

**test_raft.py** (400+ lines)
- Leader election tests
- Log replication tests
- Safety property tests
- Persistence tests
- Network partition tests
- Chaos tests
- Property-based tests

### Documentation

**README.md** (600+ lines)
- Feature overview
- Architecture diagrams
- Installation & usage
- Testing strategy
- Design decisions
- Performance characteristics
- Production considerations

**DESIGN.md** (600+ lines)
- System architecture
- Component breakdown
- Key design decisions
- Failure mode analysis
- Performance analysis
- Security considerations
- Future enhancements

**QUICKSTART.md** (200+ lines)
- 5-minute getting started
- Example commands
- Common issues
- Learning path

### Configuration

**requirements.txt**
- aiohttp: Async HTTP
- pydantic: Data validation
- click: CLI framework
- rich: Terminal UI
- pytest: Testing
- prometheus-client: Metrics

**Makefile**
- `make install`: Install dependencies
- `make test`: Run tests
- `make start`: Generate cluster config
- `make watch`: Monitor cluster
- `make clean`: Clean up

**docker-compose.yml**
- 5-node cluster definition
- Network configuration
- Volume mounts
- Health checks

## Key Components

### 1. Raft Protocol (raft.py)

```python
RaftNode
├── State Management
│   ├── current_term
│   ├── voted_for
│   ├── log[]
│   └── state (Leader/Follower/Candidate)
├── Leader Election
│   ├── _start_election()
│   ├── _request_vote()
│   └── handle_request_vote()
├── Log Replication
│   ├── append_entry()
│   ├── _replicate_to_peer()
│   └── handle_append_entries()
├── Persistence
│   ├── _persist_state()
│   └── _load_state()
└── Snapshotting
    ├── _create_snapshot()
    └── _load_snapshot()
```

### 2. RPC Layer (server.py)

```python
RaftServer
├── HTTP Endpoints
│   ├── POST /raft/request_vote
│   ├── POST /raft/append_entries
│   ├── POST /client/request
│   └── GET /status
├── RPC Client
│   └── send_rpc()
└── Server Lifecycle
    ├── start()
    └── stop()
```

### 3. CLI Tools (cli.py)

```python
CLI Commands
├── start     # Generate cluster config
├── watch     # Real-time monitoring
├── status    # Current cluster state
├── request   # Send client request
└── chaos     # Chaos testing
```

## Data Flow

### Write Path

```
Client
  ↓ POST /client/request
Leader Node
  ↓ append_entry()
Local Log
  ↓ _persist_state()
Disk (state.json)
  ↓ _replicate_to_peer()
Follower Nodes
  ↓ handle_append_entries()
Follower Logs
  ↓ _update_commit_index()
Committed Entry
  ↓ _apply_committed_entries()
State Machine
  ↓ apply()
Result
```

### Read Path (Linearizable)

```
Client
  ↓ POST /client/request (op: get)
Leader Node
  ↓ Check if leader
State Machine
  ↓ get()
Result
  ↓ Response
Client
```

## Extension Points

### Custom State Machine

```python
class MyStateMachine(StateMachine):
    def apply(self, command):
        # Your logic here
        pass
```

### Custom Storage

```python
class RocksDBStorage:
    def persist(self, state):
        # Use RocksDB instead of JSON
        pass
```

### Custom RPC

```python
class GRPCServer(RaftServer):
    def send_rpc(self, peer, method, data):
        # Use gRPC instead of HTTP
        pass
```

## Metrics & Monitoring

### Built-in Metrics

```python
RaftMetrics
├── leader_elections          # Count
├── log_entries_appended      # Count
├── log_entries_committed     # Count
├── rpc_requests_sent         # Count
├── rpc_requests_received     # Count
└── state_changes             # Count
```

### Status Endpoint

```bash
curl http://localhost:8000/status
```

Returns:
- Node state
- Current term
- Commit index
- Log size
- Metrics

### Real-time Dashboard

```bash
python cli.py watch
```

Shows:
- All node states
- Leader identification
- Commit progress
- Metrics

## Development Workflow

### 1. Setup

```bash
make install
```

### 2. Development

```bash
# Make changes to raft.py, server.py, etc.
make format          # Format code
make lint            # Check quality
make typecheck       # Type checking
```

### 3. Testing

```bash
make test            # All tests
make test-coverage   # With coverage
make test-leader     # Specific tests
```

### 4. Demo

```bash
python demo.py       # Interactive demo
make demo            # Full demo workflow
```

### 5. Deployment

```bash
make start-5         # Generate config
./start_cluster.sh   # Start nodes
make watch           # Monitor
```

## Production Checklist

- [ ] Replace JSON storage with RocksDB
- [ ] Add TLS for RPC
- [ ] Implement authentication
- [ ] Add Prometheus metrics export
- [ ] Setup distributed tracing
- [ ] Add structured logging
- [ ] Implement pre-vote optimization
- [ ] Add leadership transfer
- [ ] Setup monitoring dashboards
- [ ] Create backup/restore procedures
- [ ] Write operational runbooks
- [ ] Add alerting rules

## Performance Tuning

### For Low Latency

```python
RaftNode(
    election_timeout_min=50,   # Faster
    election_timeout_max=100,
    heartbeat_interval=10,
)
```

### For High Throughput

```python
# Batch multiple entries
entries = [entry1, entry2, entry3]
for entry in entries:
    await leader.append_entry(entry)
```

### For WAN

```python
RaftNode(
    election_timeout_min=500,  # Longer
    election_timeout_max=1000,
    heartbeat_interval=200,
)
```

## Common Patterns

### Graceful Shutdown

```python
async def shutdown():
    await server.stop()  # Stops Raft node too
```

### Reading Cluster State

```python
status = node.get_status()
print(f"Leader: {status['state'] == 'leader'}")
print(f"Term: {status['term']}")
```

### Forcing Election

```python
# Stop current leader
await leader.stop()

# Wait for new election
await asyncio.sleep(0.5)
```

## Troubleshooting

### No Leader Elected

Check:
1. All nodes can communicate
2. Majority (quorum) is up
3. Election timeouts configured

### Entries Not Committing

Check:
1. Leader has majority followers
2. Log replication working (check match_index)
3. No network partitions

### Tests Failing

```bash
make clean
make test
```

### High CPU Usage

Check:
1. Heartbeat interval too low?
2. Too many elections?
3. Log too large (needs snapshot)?

---

This structure is designed for:
- **Learning**: Clear, well-documented code
- **Testing**: Comprehensive test coverage
- **Experimentation**: Easy to modify and extend
- **Production**: Can be hardened for real use

For questions or issues, see README.md or DESIGN.md.
