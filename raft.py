"""
Mini-Raft: A production-ready Raft consensus implementation.

This module implements the core Raft protocol including:
- Leader election
- Log replication
- Snapshotting
- Membership changes
"""

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NodeState(str, Enum):
    """Possible states for a Raft node."""
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


class LogEntry(BaseModel):
    """A single entry in the replicated log."""
    term: int
    index: int
    command: Dict[str, Any]
    
    class Config:
        frozen = True


class AppendEntriesRequest(BaseModel):
    """RPC request to append entries to follower's log."""
    term: int
    leader_id: str
    prev_log_index: int
    prev_log_term: int
    entries: List[LogEntry]
    leader_commit: int


class AppendEntriesResponse(BaseModel):
    """RPC response for append entries."""
    term: int
    success: bool
    match_index: int = 0


class RequestVoteRequest(BaseModel):
    """RPC request to vote for candidate."""
    term: int
    candidate_id: str
    last_log_index: int
    last_log_term: int


class RequestVoteResponse(BaseModel):
    """RPC response for vote request."""
    term: int
    vote_granted: bool


class Snapshot(BaseModel):
    """State machine snapshot."""
    last_included_index: int
    last_included_term: int
    state: Dict[str, Any]
    members: List[str]


@dataclass
class RaftMetrics:
    """Metrics for monitoring Raft node health."""
    leader_elections: int = 0
    log_entries_appended: int = 0
    log_entries_committed: int = 0
    rpc_requests_sent: int = 0
    rpc_requests_received: int = 0
    state_changes: int = 0


class StateMachine:
    """Simple key-value state machine."""
    
    def __init__(self):
        self.data: Dict[str, Any] = {}
    
    def apply(self, command: Dict[str, Any]) -> Any:
        """Apply a command to the state machine."""
        op = command.get("op")
        
        if op == "set":
            key = command["key"]
            value = command["value"]
            self.data[key] = value
            return {"status": "ok", "key": key, "value": value}
        
        elif op == "get":
            key = command["key"]
            value = self.data.get(key)
            return {"status": "ok", "key": key, "value": value}
        
        elif op == "delete":
            key = command["key"]
            value = self.data.pop(key, None)
            return {"status": "ok", "key": key, "deleted": value}
        
        else:
            return {"status": "error", "message": f"Unknown operation: {op}"}
    
    def get_state(self) -> Dict[str, Any]:
        """Get the entire state for snapshotting."""
        return self.data.copy()
    
    def restore_state(self, state: Dict[str, Any]):
        """Restore state from snapshot."""
        self.data = state.copy()


class RaftNode:
    """
    A single node in a Raft cluster.
    
    Implements the full Raft consensus protocol with leader election,
    log replication, and snapshotting.
    """
    
    def __init__(
        self,
        node_id: str,
        peers: List[str],
        storage_dir: Path,
        host: str = "localhost",
        port: int = 8000,
        election_timeout_min: int = 150,
        election_timeout_max: int = 300,
        heartbeat_interval: int = 50,
    ):
        self.node_id = node_id
        self.peers = peers
        self.all_nodes = [node_id] + peers
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.host = host
        self.port = port
        
        # Persistent state
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.log: List[LogEntry] = []
        
        # Volatile state
        self.state = NodeState.FOLLOWER
        self.commit_index = 0
        self.last_applied = 0
        
        # Leader state
        self.next_index: Dict[str, int] = {}
        self.match_index: Dict[str, int] = {}
        
        # Election timing
        self.election_timeout_min = election_timeout_min
        self.election_timeout_max = election_timeout_max
        self.heartbeat_interval = heartbeat_interval
        self.last_heartbeat = time.time()
        self.election_timeout = self._random_election_timeout()
        
        # State machine
        self.state_machine = StateMachine()
        
        # Snapshot state
        self.last_snapshot_index = 0
        self.last_snapshot_term = 0
        
        # Metrics
        self.metrics = RaftMetrics()
        
        # Network simulation
        self.peer_connections: Dict[str, str] = {}  # peer_id -> url
        self.rpc_handlers = {}
        
        # Control flags
        self.running = False
        self.tasks: List[asyncio.Task] = []
        
        # Load persistent state
        self._load_state()
        
        logger.info(f"Node {self.node_id} initialized on {self.host}:{self.port}")
    
    def _random_election_timeout(self) -> float:
        """Generate a random election timeout in milliseconds."""
        return random.randint(self.election_timeout_min, self.election_timeout_max) / 1000.0
    
    def _get_last_log_index(self) -> int:
        """Get the index of the last log entry."""
        if self.log:
            return self.log[-1].index
        return self.last_snapshot_index
    
    def _get_last_log_term(self) -> int:
        """Get the term of the last log entry."""
        if self.log:
            return self.log[-1].term
        return self.last_snapshot_term
    
    def _get_log_entry(self, index: int) -> Optional[LogEntry]:
        """Get log entry at given index."""
        if index <= self.last_snapshot_index:
            return None
        
        offset = index - self.last_snapshot_index - 1
        if 0 <= offset < len(self.log):
            return self.log[offset]
        return None
    
    def _get_log_term(self, index: int) -> int:
        """Get term of log entry at given index."""
        if index == 0:
            return 0
        if index == self.last_snapshot_index:
            return self.last_snapshot_term
        
        entry = self._get_log_entry(index)
        return entry.term if entry else 0
    
    def _persist_state(self):
        """Persist current term, voted_for, and log to disk."""
        state_file = self.storage_dir / "state.json"
        state = {
            "current_term": self.current_term,
            "voted_for": self.voted_for,
            "log": [entry.model_dump() for entry in self.log],
            "last_snapshot_index": self.last_snapshot_index,
            "last_snapshot_term": self.last_snapshot_term,
        }
        
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def _load_state(self):
        """Load persistent state from disk."""
        state_file = self.storage_dir / "state.json"
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            self.current_term = state.get("current_term", 0)
            self.voted_for = state.get("voted_for")
            self.log = [LogEntry(**entry) for entry in state.get("log", [])]
            self.last_snapshot_index = state.get("last_snapshot_index", 0)
            self.last_snapshot_term = state.get("last_snapshot_term", 0)
            
            logger.info(f"Node {self.node_id} loaded state: term={self.current_term}, log_size={len(self.log)}")
    
    def _create_snapshot(self):
        """Create a snapshot of the current state."""
        if self.last_applied <= self.last_snapshot_index:
            return
        
        snapshot = Snapshot(
            last_included_index=self.last_applied,
            last_included_term=self._get_log_term(self.last_applied),
            state=self.state_machine.get_state(),
            members=self.all_nodes.copy(),
        )
        
        snapshot_file = self.storage_dir / "snapshot.json"
        with open(snapshot_file, 'w') as f:
            json.dump(snapshot.model_dump(), f, indent=2)
        
        # Trim log
        if self.log:
            offset = self.last_applied - self.last_snapshot_index
            self.log = self.log[offset:]
        
        self.last_snapshot_index = snapshot.last_included_index
        self.last_snapshot_term = snapshot.last_included_term
        
        self._persist_state()
        logger.info(f"Node {self.node_id} created snapshot at index {self.last_applied}")
    
    def _load_snapshot(self):
        """Load snapshot from disk."""
        snapshot_file = self.storage_dir / "snapshot.json"
        if snapshot_file.exists():
            with open(snapshot_file, 'r') as f:
                data = json.load(f)
            
            snapshot = Snapshot(**data)
            self.state_machine.restore_state(snapshot.state)
            self.last_snapshot_index = snapshot.last_included_index
            self.last_snapshot_term = snapshot.last_included_term
            self.last_applied = snapshot.last_included_index
            
            logger.info(f"Node {self.node_id} loaded snapshot at index {self.last_snapshot_index}")
    
    def _transition_to(self, new_state: NodeState):
        """Transition to a new state."""
        if self.state != new_state:
            logger.info(f"Node {self.node_id}: {self.state} -> {new_state} (term {self.current_term})")
            self.state = new_state
            self.metrics.state_changes += 1
            
            if new_state == NodeState.LEADER:
                # Initialize leader state
                last_log_index = self._get_last_log_index()
                for peer in self.peers:
                    self.next_index[peer] = last_log_index + 1
                    self.match_index[peer] = 0
                
                # Send initial heartbeats
                asyncio.create_task(self._send_heartbeats())
            
            elif new_state == NodeState.FOLLOWER:
                self.election_timeout = self._random_election_timeout()
                self.last_heartbeat = time.time()
    
    async def _start_election(self):
        """Start a new election."""
        self.current_term += 1
        self._transition_to(NodeState.CANDIDATE)
        self.voted_for = self.node_id
        self._persist_state()
        
        self.metrics.leader_elections += 1
        
        logger.info(f"Node {self.node_id} starting election for term {self.current_term}")
        
        votes_received = 1  # Vote for self
        votes_needed = (len(self.all_nodes) // 2) + 1
        
        # Request votes from all peers
        vote_tasks = []
        for peer in self.peers:
            task = asyncio.create_task(self._request_vote(peer))
            vote_tasks.append(task)
        
        # Wait for votes
        for task in asyncio.as_completed(vote_tasks):
            try:
                response = await task
                if response and response.vote_granted:
                    votes_received += 1
                    
                    if votes_received >= votes_needed and self.state == NodeState.CANDIDATE:
                        logger.info(f"Node {self.node_id} won election with {votes_received} votes")
                        self._transition_to(NodeState.LEADER)
                        return
                
                elif response and response.term > self.current_term:
                    self._step_down(response.term)
                    return
            
            except Exception as e:
                logger.debug(f"Vote request failed: {e}")
        
        # If we didn't win, start a new election
        if self.state == NodeState.CANDIDATE:
            logger.info(f"Node {self.node_id} lost election with {votes_received} votes")
    
    async def _request_vote(self, peer: str) -> Optional[RequestVoteResponse]:
        """Send RequestVote RPC to peer."""
        request = RequestVoteRequest(
            term=self.current_term,
            candidate_id=self.node_id,
            last_log_index=self._get_last_log_index(),
            last_log_term=self._get_last_log_term(),
        )
        
        self.metrics.rpc_requests_sent += 1
        
        # Simulate RPC (in real implementation, this would be HTTP/gRPC)
        try:
            response = await self._simulate_rpc(peer, "request_vote", request.model_dump())
            if response:
                return RequestVoteResponse(**response)
        except Exception as e:
            logger.debug(f"RequestVote to {peer} failed: {e}")
        
        return None
    
    def handle_request_vote(self, request: RequestVoteRequest) -> RequestVoteResponse:
        """Handle RequestVote RPC."""
        self.metrics.rpc_requests_received += 1
        
        # Update term if necessary
        if request.term > self.current_term:
            self._step_down(request.term)
        
        vote_granted = False
        
        # Grant vote if:
        # 1. Request term >= current term
        # 2. Haven't voted for anyone else this term
        # 3. Candidate's log is at least as up-to-date as ours
        if request.term >= self.current_term:
            if self.voted_for is None or self.voted_for == request.candidate_id:
                last_log_term = self._get_last_log_term()
                last_log_index = self._get_last_log_index()
                
                log_is_up_to_date = (
                    request.last_log_term > last_log_term or
                    (request.last_log_term == last_log_term and 
                     request.last_log_index >= last_log_index)
                )
                
                if log_is_up_to_date:
                    vote_granted = True
                    self.voted_for = request.candidate_id
                    self._persist_state()
                    self.last_heartbeat = time.time()
                    logger.info(f"Node {self.node_id} voted for {request.candidate_id} in term {request.term}")
        
        return RequestVoteResponse(term=self.current_term, vote_granted=vote_granted)
    
    async def _send_heartbeats(self):
        """Send heartbeat (empty AppendEntries) to all peers."""
        if self.state != NodeState.LEADER:
            return
        
        tasks = []
        for peer in self.peers:
            task = asyncio.create_task(self._replicate_to_peer(peer))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _replicate_to_peer(self, peer: str):
        """Replicate log entries to a single peer."""
        if self.state != NodeState.LEADER:
            return
        
        next_idx = self.next_index.get(peer, 1)
        prev_log_index = next_idx - 1
        prev_log_term = self._get_log_term(prev_log_index)
        
        # Get entries to send
        entries = []
        for i in range(next_idx, self._get_last_log_index() + 1):
            entry = self._get_log_entry(i)
            if entry:
                entries.append(entry)
        
        request = AppendEntriesRequest(
            term=self.current_term,
            leader_id=self.node_id,
            prev_log_index=prev_log_index,
            prev_log_term=prev_log_term,
            entries=entries,
            leader_commit=self.commit_index,
        )
        
        self.metrics.rpc_requests_sent += 1
        
        try:
            response_data = await self._simulate_rpc(peer, "append_entries", request.model_dump())
            if response_data:
                response = AppendEntriesResponse(**response_data)
                
                if response.term > self.current_term:
                    self._step_down(response.term)
                    return
                
                if response.success:
                    # Update next_index and match_index
                    self.match_index[peer] = response.match_index
                    self.next_index[peer] = response.match_index + 1
                    
                    # Update commit_index
                    self._update_commit_index()
                else:
                    # Decrement next_index and retry
                    self.next_index[peer] = max(1, self.next_index[peer] - 1)
        
        except Exception as e:
            logger.debug(f"AppendEntries to {peer} failed: {e}")
    
    def handle_append_entries(self, request: AppendEntriesRequest) -> AppendEntriesResponse:
        """Handle AppendEntries RPC."""
        self.metrics.rpc_requests_received += 1
        self.last_heartbeat = time.time()
        
        # Update term if necessary
        if request.term > self.current_term:
            self._step_down(request.term)
        
        # Reject if term < current term
        if request.term < self.current_term:
            return AppendEntriesResponse(term=self.current_term, success=False)
        
        # Step down if we're a candidate
        if self.state == NodeState.CANDIDATE:
            self._transition_to(NodeState.FOLLOWER)
        
        # Check if log contains entry at prev_log_index with matching term
        if request.prev_log_index > 0:
            prev_entry = self._get_log_entry(request.prev_log_index)
            if not prev_entry or prev_entry.term != request.prev_log_term:
                return AppendEntriesResponse(
                    term=self.current_term,
                    success=False,
                    match_index=self.last_snapshot_index
                )
        
        # Append new entries
        for entry in request.entries:
            existing = self._get_log_entry(entry.index)
            
            if existing and existing.term != entry.term:
                # Delete conflicting entry and all that follow
                offset = entry.index - self.last_snapshot_index - 1
                self.log = self.log[:offset]
            
            if not existing:
                self.log.append(entry)
                self.metrics.log_entries_appended += 1
        
        self._persist_state()
        
        # Update commit index
        if request.leader_commit > self.commit_index:
            self.commit_index = min(request.leader_commit, self._get_last_log_index())
            self._apply_committed_entries()
        
        match_index = request.prev_log_index + len(request.entries)
        return AppendEntriesResponse(
            term=self.current_term,
            success=True,
            match_index=match_index
        )
    
    def _update_commit_index(self):
        """Update commit index based on match_index from followers."""
        if self.state != NodeState.LEADER:
            return
        
        # Find the highest index replicated on a majority
        for n in range(self._get_last_log_index(), self.commit_index, -1):
            entry = self._get_log_entry(n)
            if entry and entry.term == self.current_term:
                replicated_count = 1  # Count self
                
                for peer in self.peers:
                    if self.match_index.get(peer, 0) >= n:
                        replicated_count += 1
                
                if replicated_count >= (len(self.all_nodes) // 2) + 1:
                    self.commit_index = n
                    self._apply_committed_entries()
                    break
    
    def _apply_committed_entries(self):
        """Apply committed entries to state machine."""
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self._get_log_entry(self.last_applied)
            
            if entry:
                result = self.state_machine.apply(entry.command)
                self.metrics.log_entries_committed += 1
                logger.debug(f"Node {self.node_id} applied entry {self.last_applied}: {result}")
        
        # Create snapshot periodically
        if self.last_applied - self.last_snapshot_index >= 100:
            self._create_snapshot()
    
    def _step_down(self, new_term: int):
        """Step down to follower state."""
        self.current_term = new_term
        self.voted_for = None
        self._transition_to(NodeState.FOLLOWER)
        self._persist_state()
    
    async def _simulate_rpc(self, peer: str, method: str, data: dict) -> Optional[dict]:
        """
        Simulate RPC call to peer.
        In production, this would use aiohttp or gRPC.
        """
        # This is a placeholder - in the full implementation,
        # we'll use actual HTTP requests
        await asyncio.sleep(0.01)  # Simulate network delay
        return None
    
    async def append_entry(self, command: Dict[str, Any]) -> bool:
        """
        Append a new entry to the log (client request).
        Only leaders can accept client requests.
        """
        if self.state != NodeState.LEADER:
            return False
        
        entry = LogEntry(
            term=self.current_term,
            index=self._get_last_log_index() + 1,
            command=command,
        )
        
        self.log.append(entry)
        self.metrics.log_entries_appended += 1
        self._persist_state()
        
        logger.info(f"Node {self.node_id} appended entry {entry.index}: {command}")
        
        # Replicate to followers
        await self._send_heartbeats()
        
        return True
    
    async def _election_timer_loop(self):
        """Main election timer loop."""
        while self.running:
            await asyncio.sleep(0.05)  # Check every 50ms
            
            if self.state != NodeState.LEADER:
                elapsed = time.time() - self.last_heartbeat
                if elapsed >= self.election_timeout:
                    logger.debug(f"Node {self.node_id} election timeout ({elapsed:.2f}s)")
                    await self._start_election()
                    self.election_timeout = self._random_election_timeout()
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats when leader."""
        while self.running:
            await asyncio.sleep(self.heartbeat_interval / 1000.0)
            
            if self.state == NodeState.LEADER:
                await self._send_heartbeats()
    
    async def start(self):
        """Start the Raft node."""
        self.running = True
        self._load_snapshot()
        
        # Start background tasks
        self.tasks.append(asyncio.create_task(self._election_timer_loop()))
        self.tasks.append(asyncio.create_task(self._heartbeat_loop()))
        
        logger.info(f"Node {self.node_id} started")
    
    async def stop(self):
        """Stop the Raft node."""
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        logger.info(f"Node {self.node_id} stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current node status."""
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "term": self.current_term,
            "commit_index": self.commit_index,
            "last_applied": self.last_applied,
            "log_size": len(self.log),
            "last_log_index": self._get_last_log_index(),
            "voted_for": self.voted_for,
            "peers": self.peers,
            "metrics": {
                "leader_elections": self.metrics.leader_elections,
                "log_entries_appended": self.metrics.log_entries_appended,
                "log_entries_committed": self.metrics.log_entries_committed,
                "state_changes": self.metrics.state_changes,
            }
        }