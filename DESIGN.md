# Mini-Raft Design Document

## 1. Goals & Objectives

### Primary Goals
1. **Implement core Raft consensus**: Leader election, log replication, safety properties
2. **Production-ready code quality**: Tests, monitoring, documentation
3. **Educational value**: Clear code demonstrating Raft concepts
4. **Demonstrable**: Easy to run, visualize, and experiment with

### Non-Goals
- Byzantine fault tolerance (assumes honest nodes)
- Multi-datacenter optimization
- Production-scale performance (10K+ ops/sec)

## 2. System Architecture

### High-Level Design

```
┌───────────────────────────────────────────────────────┐
│                   Client Layer                        │
│  ┌─────────┐  ┌──────────┐  ┌───────────────┐       │
│  │   CLI   │  │ REST API │  │  Monitoring   │       │
│  └────┬────┘  └─────┬────┘  └───────┬───────┘       │
└───────┼─────────────┼───────────────┼───────────────┘
        │             │               │
┌───────▼─────────────▼───────────────▼───────────────┐
│              Raft Server (HTTP/RPC)                  │
│  ┌─────────────────────────────────────────────┐    │
│  │         Request Handlers                     │    │
│  │  • RequestVote    • AppendEntries           │    │
│  │  • ClientRequest  • Status                  │    │
│  └────────────────┬────────────────────────────┘    │
└───────────────────┼─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│                 Raft Node (Core)                     │
│  ┌──────────────────────────────────────────────┐   │
│  │          Persistent State                    │   │
│  │  • current_term  • voted_for  • log[]       │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │          Volatile State                      │   │
│  │  • commit_index  • last_applied  • state    │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │          Leader State (volatile)             │   │
│  │  • next_index[]  • match_index[]            │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │         Background Tasks                     │   │
│  │  • Election Timer  • Heartbeat Sender       │   │
│  └──────────────────────────────────────────────┘   │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│              State Machine (KV Store)                │
│  ┌──────────────────────────────────────────────┐   │
│  │  Operations: GET, SET, DELETE                │   │
│  │  Storage: In-memory dict                     │   │
│  └──────────────────────────────────────────────┘   │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│                Storage Layer                         │
│  ┌──────────────────────────────────────────────┐   │
│  │  • state.json      (persistent state)        │   │
│  │  • snapshot.json   (state machine snapshot)  │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### Component Details

#### 1. RaftNode (Core Logic)

**Responsibilities:**
- Implement Raft consensus protocol
- Manage state transitions (Follower → Candidate → Leader)
- Handle RPC requests (RequestVote, AppendEntries)
- Persist state to disk
- Apply committed entries to state machine

**Key Algorithms:**

```python
# Leader Election
def start_election():
    current_term += 1
    state = CANDIDATE
    voted_for = self.id
    votes = 1
    
    for peer in peers:
        response = peer.request_vote(
            term=current_term,
            candidate_id=self.id,
            last_log_index=last_log_index,
            last_log_term=last_log_term
        )
        if response.vote_granted:
            votes += 1
    
    if votes >= majority:
        become_leader()

# Log Replication
def replicate_log(peer):
    next_idx = next_index[peer]
    entries = log[next_idx:]
    
    response = peer.append_entries(
        term=current_term,
        prev_log_index=next_idx - 1,
        prev_log_term=log[next_idx - 1].term,
        entries=entries,
        leader_commit=commit_index
    )
    
    if response.success:
        next_index[peer] = next_idx + len(entries)
        match_index[peer] = next_idx + len(entries) - 1
        update_commit_index()
    else:
        next_index[peer] -= 1  # Backtrack
```

#### 2. RaftServer (RPC Layer)

**Responsibilities:**
- HTTP server for inter-node communication
- Serialize/deserialize RPC messages
- Route requests to RaftNode handlers
- Manage network connections

**Design Decisions:**

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| HTTP/REST | Universal, easy debugging | gRPC (better performance) |
| aiohttp | Async I/O, mature library | Tornado, FastAPI |
| JSON serialization | Human-readable, standard | Protobuf (more efficient) |

#### 3. Storage Layer

**Files:**

1. **state.json** - Persistent state
```json
{
  "current_term": 5,
  "voted_for": "node-1",
  "log": [
    {"term": 1, "index": 1, "command": {...}},
    {"term": 2, "index": 2, "command": {...}}
  ],
  "last_snapshot_index": 0,
  "last_snapshot_term": 0
}
```

2. **snapshot.json** - State machine snapshot
```json
{
  "last_included_index": 100,
  "last_included_term": 5,
  "state": {"key1": "value1", "key2": "value2"},
  "members": ["node-0", "node-1", "node-2"]
}
```

**Write Path:**
1. Update in-memory state
2. Synchronously write to disk
3. fsync() for durability
4. Return success

**Read Path:**
1. Load from disk on startup
2. Validate JSON structure
3. Restore in-memory state

## 3. Key Design Decisions

### 3.1 Election Timeout Randomization

**Decision:** Random timeout between 150-300ms

**Rationale:**
- Prevents split votes
- Based on Raft paper recommendations
- Short enough for fast failover
- Long enough to avoid spurious elections

**Analysis:**
```
Probability of split vote with N nodes:
P(split) ≈ (1/N)^(N-1) with random timeouts

For 5 nodes:
- Without randomization: ~30% split votes
- With randomization: <5% split votes
```

### 3.2 Heartbeat Frequency

**Decision:** 50ms heartbeat interval

**Rationale:**
- 3x heartbeats per minimum election timeout
- Ensures timely failure detection
- Low network overhead

**Tradeoffs:**
- Faster (25ms): More network traffic, better failure detection
- Slower (100ms): Less traffic, slower detection

### 3.3 Snapshot Threshold

**Decision:** Snapshot every 100 entries

**Rationale:**
- Prevents unbounded log growth
- Low snapshot overhead
- Fast recovery times

**Memory Analysis:**
```
Without snapshots:
- 1000 entries/sec × 86400 sec/day = 86M entries
- 1KB/entry × 86M = 86GB/day

With snapshots (100 entries):
- Max log size: ~100 entries = 100KB
- Snapshot overhead: O(state_size) every 100 commits
```

### 3.4 State Machine Choice

**Decision:** Simple key-value store

**Rationale:**
- Easy to understand
- Demonstrates state machine concept
- Sufficient for testing

**Extension Points:**
```python
class StateMachine:
    def apply(self, command):
        # Override for different state machines
        pass
    
    def get_state(self):
        # Snapshot support
        pass
    
    def restore_state(self, state):
        # Recovery support
        pass
```

## 4. Failure Modes & Handling

### 4.1 Node Failures

| Failure | Detection | Recovery | Time |
|---------|-----------|----------|------|
| Leader crash | Election timeout | New election | 150-300ms |
| Follower crash | AppendEntries RPC fails | Continue with majority | N/A |
| Majority crash | No quorum | System stalls | Manual intervention |

### 4.2 Network Failures

| Failure | Detection | Recovery | Notes |
|---------|-----------|----------|-------|
| Network partition | RPC timeout | Wait for heal | Majority side continues |
| Message loss | RPC timeout | Retry | Idempotent RPCs |
| High latency | Timeout | Adjust timeouts | May cause false elections |

### 4.3 Disk Failures

| Failure | Detection | Recovery | Data Loss |
|---------|-----------|----------|-----------|
| Disk full | Write error | Alert operator | None if caught |
| Corruption | Read error | Restore from peers | Depends on last snapshot |
| Total loss | Boot failure | Reformat, rejoin cluster | All local data |

## 5. Performance Characteristics

### 5.1 Throughput

**Expected:**
- Single node: ~1000 writes/sec (Python)
- 5-node cluster: ~500-700 writes/sec (limited by replication)

**Bottlenecks:**
1. Network RTT (50ms) → Max 20 ops/sec per RTT
2. Disk fsync (~1-10ms) → Max 100-1000 ops/sec
3. JSON serialization (~0.1ms/entry) → Max 10K ops/sec

### 5.2 Latency

**Write latency:**
```
Leader receives request:        0ms
├─ Append to local log:        1ms  (disk write)
├─ Send AppendEntries RPC:     5ms  (network RTT)
├─ Followers append:           1ms  (disk write)
└─ Leader commits:             5ms  (network RTT)
Total:                        ~12ms (typical)
```

**Read latency:**
- From leader: ~1ms (memory lookup)
- Linearizable read: ~12ms (requires quorum)

### 5.3 Scalability

**Cluster size:**
- Tested: 3-7 nodes
- Recommended: 3-5 nodes (odd number)
- Maximum: 7-9 nodes (write quorum increases)

**Scaling limits:**
```
With N nodes:
- Quorum size: (N+1)/2
- Max failures: (N-1)/2
- Network connections: N*(N-1) = O(N²)

Examples:
N=3 → Quorum=2, Failures=1, Connections=6
N=5 → Quorum=3, Failures=2, Connections=20
N=7 → Quorum=4, Failures=3, Connections=42
```

## 6. Testing Strategy

### 6.1 Unit Tests

**Coverage:**
- State transitions
- RPC handlers
- Log operations
- Persistence

**Example:**
```python
def test_vote_granted():
    node = RaftNode(...)
    request = RequestVoteRequest(
        term=2,
        candidate_id="peer1",
        last_log_index=5,
        last_log_term=1
    )
    response = node.handle_request_vote(request)
    assert response.vote_granted == True
```

### 6.2 Integration Tests

**Scenarios:**
- Leader election in 3/5/7 node clusters
- Log replication across nodes
- Commit propagation
- Crash recovery

### 6.3 Chaos Tests

**Fault injection:**
- Random node kills
- Network partitions
- Message delays/drops
- Disk failures

**Invariants to check:**
- At most one leader per term
- All committed entries are durable
- State machine consistency

### 6.4 Property-Based Tests

**Properties:**
```python
@given(commands=st.lists(st.dictionaries(...)))
def test_linearizability(commands):
    # Apply commands to cluster
    # Verify: reads see writes in order
    pass
```

## 7. Monitoring & Observability

### 7.1 Metrics

**Node metrics:**
- State (Leader/Follower/Candidate)
- Current term
- Commit index
- Log size
- Vote counts

**Performance metrics:**
- RPC latency (p50, p95, p99)
- Throughput (ops/sec)
- Election duration
- Replication lag

**System metrics:**
- CPU usage
- Memory usage
- Disk I/O
- Network bandwidth

### 7.2 Logging

**Log levels:**
```python
DEBUG: RPC details, timer events
INFO:  State changes, elections, commits
WARN:  Timeouts, retries, slow operations
ERROR: Failures, crashes, corruptions
```

**Key events to log:**
- State transitions
- Elections (start, vote, win/lose)
- Log entries (append, commit)
- Snapshots (create, load)
- Failures (crash, network, disk)

## 8. Security Considerations

### 8.1 Threat Model

**Assumptions:**
- Nodes are not malicious (non-Byzantine)
- Network is untrusted (may drop/delay messages)
- Attackers cannot forge node identities

**Threats:**
- Eavesdropping on RPC traffic
- Man-in-the-middle attacks
- Unauthorized client requests
- DoS via excessive requests

### 8.2 Mitigations

**Current:**
- None (educational implementation)

**Production recommendations:**
```
1. TLS for all RPC communication
2. Mutual authentication (mTLS)
3. Authorization for client requests
4. Rate limiting
5. Input validation
```

## 9. Future Enhancements

### 9.1 Performance

- [ ] Batching: Group multiple client requests
- [ ] Pipelining: Don't wait for each RPC
- [ ] Compression: Reduce network bandwidth
- [ ] Read optimization: Serve reads from followers

### 9.2 Features

- [ ] Membership changes (§6 of Raft paper)
- [ ] Pre-vote (prevent disruptive elections)
- [ ] Leadership transfer (graceful handoff)
- [ ] Log cleaning (more efficient than snapshots)

### 9.3 Operations

- [ ] Automated backup/restore
- [ ] Rolling upgrades
- [ ] Metrics export (Prometheus)
- [ ] Distributed tracing (Jaeger)

## 10. References

### Papers
1. Ongaro & Ousterhout, "In Search of an Understandable Consensus Algorithm" (2014)
2. Lamport, "The Part-Time Parliament" (1998) - Original Paxos
3. Lamport, "Paxos Made Simple" (2001)

### Implementations
1. etcd (Go) - https://github.com/etcd-io/etcd
2. Consul (Go) - https://github.com/hashicorp/consul
3. LogCabin (C++) - https://github.com/logcabin/logcabin

### Tools
1. Jepsen - Distributed systems testing
2. Chaos Mesh - Chaos engineering platform
3. TLA+ - Formal specification language

---

**Document Version:** 1.0  
**Last Updated:** 2024-11  
**Authors:** Mini-Raft Team
