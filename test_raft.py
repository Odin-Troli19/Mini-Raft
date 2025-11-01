"""
Comprehensive test suite for Mini-Raft.

Tests include:
- Leader election
- Log replication
- Safety properties
- Crash recovery
- Network partitions
"""

import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest

from raft import RaftNode, NodeState, LogEntry


@pytest.fixture
def temp_dir():
    """Create temporary directory for test data."""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir)


@pytest.fixture
async def three_node_cluster(temp_dir):
    """Create a 3-node cluster for testing."""
    nodes = []
    
    for i in range(3):
        node_id = f"node-{i}"
        peers = [f"node-{j}" for j in range(3) if j != i]
        storage_dir = temp_dir / node_id
        
        node = RaftNode(
            node_id=node_id,
            peers=peers,
            storage_dir=storage_dir,
            port=8000 + i,
            election_timeout_min=100,
            election_timeout_max=200,
            heartbeat_interval=25,
        )
        nodes.append(node)
    
    # Start all nodes
    for node in nodes:
        await node.start()
    
    yield nodes
    
    # Stop all nodes
    for node in nodes:
        await node.stop()


@pytest.fixture
async def five_node_cluster(temp_dir):
    """Create a 5-node cluster for testing."""
    nodes = []
    
    for i in range(5):
        node_id = f"node-{i}"
        peers = [f"node-{j}" for j in range(5) if j != i]
        storage_dir = temp_dir / node_id
        
        node = RaftNode(
            node_id=node_id,
            peers=peers,
            storage_dir=storage_dir,
            port=8000 + i,
            election_timeout_min=100,
            election_timeout_max=200,
            heartbeat_interval=25,
        )
        nodes.append(node)
    
    # Start all nodes
    for node in nodes:
        await node.start()
    
    yield nodes
    
    # Stop all nodes
    for node in nodes:
        await node.stop()


class TestLeaderElection:
    """Test leader election mechanism."""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_initial_election(self, three_node_cluster):
        """Test that a leader is elected initially."""
        nodes = three_node_cluster
        
        # Wait for election
        await asyncio.sleep(1.0)
        
        # Check that exactly one leader exists
        leaders = [n for n in nodes if n.state == NodeState.LEADER]
        assert len(leaders) == 1, f"Expected 1 leader, found {len(leaders)}"
        
        # Check that other nodes are followers
        followers = [n for n in nodes if n.state == NodeState.FOLLOWER]
        assert len(followers) == 2, f"Expected 2 followers, found {len(followers)}"
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_reelection_after_leader_failure(self, three_node_cluster):
        """Test that a new leader is elected after current leader fails."""
        nodes = three_node_cluster
        
        # Wait for initial election
        await asyncio.sleep(1.0)
        
        # Find and stop the leader
        leader = next(n for n in nodes if n.state == NodeState.LEADER)
        await leader.stop()
        
        # Wait for new election
        await asyncio.sleep(1.0)
        
        # Check that remaining nodes elected a new leader
        remaining = [n for n in nodes if n.running]
        leaders = [n for n in remaining if n.state == NodeState.LEADER]
        assert len(leaders) == 1, "Should elect new leader after failure"
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_term_increases_on_election(self, three_node_cluster):
        """Test that term increases with each election."""
        nodes = three_node_cluster
        
        # Wait for initial election
        await asyncio.sleep(1.0)
        initial_term = max(n.current_term for n in nodes)
        
        # Force a new election by stopping leader
        leader = next(n for n in nodes if n.state == NodeState.LEADER)
        await leader.stop()
        
        # Wait for new election
        await asyncio.sleep(1.0)
        
        new_term = max(n.current_term for n in nodes if n.running)
        assert new_term > initial_term, "Term should increase after election"


class TestLogReplication:
    """Test log replication mechanism."""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_log_replication_to_followers(self, three_node_cluster):
        """Test that log entries are replicated to followers."""
        nodes = three_node_cluster
        
        # Wait for leader election
        await asyncio.sleep(1.0)
        
        # Find leader
        leader = next(n for n in nodes if n.state == NodeState.LEADER)
        
        # Append entry
        command = {"op": "set", "key": "test", "value": "123"}
        await leader.append_entry(command)
        
        # Wait for replication
        await asyncio.sleep(0.5)
        
        # Check that all nodes have the entry
        for node in nodes:
            assert len(node.log) >= 1, f"Node {node.node_id} should have log entry"
            assert node.log[0].command == command
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_commit_index_advances(self, three_node_cluster):
        """Test that commit index advances after replication."""
        nodes = three_node_cluster
        
        # Wait for leader election
        await asyncio.sleep(1.0)
        
        # Find leader
        leader = next(n for n in nodes if n.state == NodeState.LEADER)
        
        # Append multiple entries
        for i in range(5):
            command = {"op": "set", "key": f"key-{i}", "value": f"val-{i}"}
            await leader.append_entry(command)
        
        # Wait for replication and commit
        await asyncio.sleep(1.0)
        
        # Check that entries are committed
        assert leader.commit_index >= 5, "Leader should commit entries"
        
        # Check followers commit as well
        followers = [n for n in nodes if n.state == NodeState.FOLLOWER]
        for follower in followers:
            assert follower.commit_index >= 5, f"Follower {follower.node_id} should commit"
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_state_machine_application(self, three_node_cluster):
        """Test that committed entries are applied to state machine."""
        nodes = three_node_cluster
        
        # Wait for leader election
        await asyncio.sleep(1.0)
        
        # Find leader
        leader = next(n for n in nodes if n.state == NodeState.LEADER)
        
        # Set some values
        commands = [
            {"op": "set", "key": "a", "value": "100"},
            {"op": "set", "key": "b", "value": "200"},
            {"op": "set", "key": "c", "value": "300"},
        ]
        
        for cmd in commands:
            await leader.append_entry(cmd)
        
        # Wait for application
        await asyncio.sleep(1.0)
        
        # Check state machine on all nodes
        for node in nodes:
            assert node.state_machine.data.get("a") == "100"
            assert node.state_machine.data.get("b") == "200"
            assert node.state_machine.data.get("c") == "300"


class TestSafetyProperties:
    """Test Raft safety properties."""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_election_safety(self, five_node_cluster):
        """Test that at most one leader per term."""
        nodes = five_node_cluster
        
        # Run for several election cycles
        for _ in range(5):
            await asyncio.sleep(0.5)
            
            # Group nodes by term
            term_leaders = {}
            for node in nodes:
                if node.state == NodeState.LEADER:
                    term = node.current_term
                    if term not in term_leaders:
                        term_leaders[term] = []
                    term_leaders[term].append(node.node_id)
            
            # Check at most one leader per term
            for term, leaders in term_leaders.items():
                assert len(leaders) <= 1, f"Multiple leaders in term {term}: {leaders}"
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_log_matching(self, three_node_cluster):
        """Test that logs match across nodes."""
        nodes = three_node_cluster
        
        # Wait for leader election
        await asyncio.sleep(1.0)
        
        # Find leader
        leader = next(n for n in nodes if n.state == NodeState.LEADER)
        
        # Append entries
        for i in range(10):
            command = {"op": "set", "key": f"k{i}", "value": f"v{i}"}
            await leader.append_entry(command)
        
        # Wait for replication
        await asyncio.sleep(1.0)
        
        # Check that committed entries match across nodes
        for i in range(1, min(n.commit_index for n in nodes) + 1):
            entries = [n._get_log_entry(i) for n in nodes]
            
            # All committed entries should be identical
            first_entry = entries[0]
            for entry in entries[1:]:
                if entry:
                    assert entry.term == first_entry.term
                    assert entry.command == first_entry.command


class TestPersistence:
    """Test persistence and recovery."""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_state_persists_across_restart(self, temp_dir):
        """Test that node state persists across restarts."""
        node_id = "test-node"
        storage_dir = temp_dir / node_id
        
        # Create and start node
        node1 = RaftNode(
            node_id=node_id,
            peers=["peer1", "peer2"],
            storage_dir=storage_dir,
            port=8000,
        )
        await node1.start()
        
        # Append some entries
        for i in range(5):
            entry = LogEntry(
                term=1,
                index=i + 1,
                command={"op": "set", "key": f"k{i}", "value": f"v{i}"}
            )
            node1.log.append(entry)
        
        node1.current_term = 5
        node1.voted_for = "peer1"
        node1._persist_state()
        
        # Stop node
        await node1.stop()
        
        # Create new node with same storage
        node2 = RaftNode(
            node_id=node_id,
            peers=["peer1", "peer2"],
            storage_dir=storage_dir,
            port=8000,
        )
        
        # Check that state was loaded
        assert node2.current_term == 5
        assert node2.voted_for == "peer1"
        assert len(node2.log) == 5
        
        await node2.stop()
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_snapshot_creation(self, temp_dir):
        """Test that snapshots are created correctly."""
        node_id = "test-node"
        storage_dir = temp_dir / node_id
        
        node = RaftNode(
            node_id=node_id,
            peers=["peer1", "peer2"],
            storage_dir=storage_dir,
            port=8000,
        )
        await node.start()
        
        # Apply many entries to state machine
        for i in range(150):
            node.state_machine.apply({"op": "set", "key": f"k{i}", "value": f"v{i}"})
            node.last_applied = i + 1
            
            # Add to log
            entry = LogEntry(term=1, index=i + 1, command={})
            node.log.append(entry)
        
        # Create snapshot
        node._create_snapshot()
        
        # Check snapshot was created
        snapshot_file = storage_dir / "snapshot.json"
        assert snapshot_file.exists()
        
        # Check log was trimmed
        assert len(node.log) < 150
        
        await node.stop()


class TestNetworkPartitions:
    """Test behavior under network partitions."""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(15)
    async def test_majority_partition_continues(self, five_node_cluster):
        """Test that majority partition can continue operating."""
        nodes = five_node_cluster
        
        # Wait for leader election
        await asyncio.sleep(1.0)
        
        # Isolate 2 nodes (minority)
        await nodes[3].stop()
        await nodes[4].stop()
        
        # Wait for new leader if needed
        await asyncio.sleep(1.0)
        
        # Majority should still have a leader
        majority = nodes[:3]
        leaders = [n for n in majority if n.state == NodeState.LEADER]
        assert len(leaders) == 1, "Majority partition should have leader"
        
        # Should be able to commit entries
        leader = leaders[0]
        command = {"op": "set", "key": "test", "value": "partition"}
        await leader.append_entry(command)
        
        await asyncio.sleep(0.5)
        
        # Entry should be committed in majority
        assert leader.commit_index >= 1


class TestMetrics:
    """Test metrics collection."""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_metrics_tracking(self, three_node_cluster):
        """Test that metrics are tracked correctly."""
        nodes = three_node_cluster
        
        # Wait for leader election
        await asyncio.sleep(1.0)
        
        # Check that leader elections were counted
        total_elections = sum(n.metrics.leader_elections for n in nodes)
        assert total_elections >= 1, "Should count leader elections"
        
        # Find leader and append entries
        leader = next(n for n in nodes if n.state == NodeState.LEADER)
        
        for i in range(5):
            await leader.append_entry({"op": "set", "key": f"k{i}", "value": i})
        
        await asyncio.sleep(1.0)
        
        # Check log metrics
        assert leader.metrics.log_entries_appended >= 5
        assert leader.metrics.log_entries_committed >= 5


# Helper functions for running tests
def run_tests():
    """Run all tests."""
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_tests()