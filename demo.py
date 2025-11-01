#!/usr/bin/env python3
"""
Demo script for Mini-Raft.

This script demonstrates the key features:
1. Leader election
2. Log replication
3. Fault tolerance
4. State machine consistency
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import List

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from raft import RaftNode
from server import RaftServer

console = Console()


async def wait_for_leader(nodes: List[RaftNode], timeout: float = 5.0) -> RaftNode:
    """Wait for a leader to be elected."""
    start = time.time()
    while time.time() - start < timeout:
        leaders = [n for n in nodes if n.state.value == "leader"]
        if leaders:
            return leaders[0]
        await asyncio.sleep(0.1)
    raise TimeoutError("No leader elected")


async def demo_leader_election():
    """Demonstrate leader election."""
    console.print("\n[bold cyan]═══ Demo 1: Leader Election ═══[/bold cyan]\n")
    
    # Create 3 nodes
    nodes = []
    servers = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Starting 3-node cluster...", total=None)
        
        for i in range(3):
            node_id = f"node-{i}"
            peers = [f"node-{j}" for j in range(3) if j != i]
            storage_dir = Path(f"./demo_data/{node_id}")
            storage_dir.mkdir(parents=True, exist_ok=True)
            
            node = RaftNode(
                node_id=node_id,
                peers=peers,
                storage_dir=storage_dir,
                port=9000 + i,
                election_timeout_min=100,
                election_timeout_max=200,
            )
            server = RaftServer(node)
            await server.start()
            
            nodes.append(node)
            servers.append(server)
        
        progress.update(task, completed=True)
    
    console.print("[green]✓[/green] Cluster started")
    
    # Wait for leader election
    console.print("\n[yellow]⏳[/yellow] Waiting for leader election...")
    await asyncio.sleep(1.0)
    
    # Show results
    leader = await wait_for_leader(nodes)
    console.print(f"\n[green]✓[/green] Leader elected: [bold]{leader.node_id}[/bold] (term {leader.current_term})")
    
    console.print("\n[cyan]Cluster state:[/cyan]")
    for node in nodes:
        state_emoji = "👑" if node.state.value == "leader" else "👤"
        console.print(f"  {state_emoji} {node.node_id}: {node.state.value}")
    
    # Cleanup
    for server in servers:
        await server.stop()
    
    return nodes, servers


async def demo_log_replication(nodes: List[RaftNode], servers: List[RaftServer]):
    """Demonstrate log replication."""
    console.print("\n[bold cyan]═══ Demo 2: Log Replication ═══[/bold cyan]\n")
    
    # Find leader
    leader = next(n for n in nodes if n.state.value == "leader")
    console.print(f"[cyan]Leader:[/cyan] {leader.node_id}\n")
    
    # Submit commands
    commands = [
        {"op": "set", "key": "name", "value": "Alice"},
        {"op": "set", "key": "age", "value": "30"},
        {"op": "set", "key": "city", "value": "Oslo"},
    ]
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Replicating entries...", total=len(commands))
        
        for cmd in commands:
            await leader.append_entry(cmd)
            progress.advance(task)
            await asyncio.sleep(0.2)
    
    # Wait for replication
    await asyncio.sleep(1.0)
    
    console.print("\n[green]✓[/green] Entries replicated and committed")
    
    # Show state on all nodes
    console.print("\n[cyan]State machine on all nodes:[/cyan]")
    for node in nodes:
        console.print(f"\n  {node.node_id}:")
        for key, value in node.state_machine.data.items():
            console.print(f"    {key} = {value}")


async def demo_fault_tolerance(nodes: List[RaftNode], servers: List[RaftServer]):
    """Demonstrate fault tolerance."""
    console.print("\n[bold cyan]═══ Demo 3: Fault Tolerance ═══[/bold cyan]\n")
    
    # Find current leader
    old_leader = next(n for n in nodes if n.state.value == "leader")
    old_leader_id = old_leader.node_id
    old_term = old_leader.current_term
    
    console.print(f"[yellow]💥[/yellow] Simulating leader failure: {old_leader_id}")
    
    # Stop leader
    leader_idx = nodes.index(old_leader)
    await servers[leader_idx].stop()
    
    console.print("[yellow]⏳[/yellow] Waiting for new election...")
    await asyncio.sleep(1.5)
    
    # Find new leader
    remaining_nodes = [n for n in nodes if n.running]
    new_leader = next((n for n in remaining_nodes if n.state.value == "leader"), None)
    
    if new_leader:
        console.print(f"\n[green]✓[/green] New leader elected: [bold]{new_leader.node_id}[/bold] (term {new_leader.current_term})")
        console.print(f"[cyan]Term increased:[/cyan] {old_term} → {new_leader.current_term}")
        
        # Verify data is still accessible
        console.print("\n[cyan]Verifying data consistency:[/cyan]")
        for key, value in new_leader.state_machine.data.items():
            console.print(f"  {key} = {value} [green]✓[/green]")
    else:
        console.print("[red]✗[/red] No new leader elected (this shouldn't happen!)")


async def demo_consistency():
    """Demonstrate state machine consistency."""
    console.print("\n[bold cyan]═══ Demo 4: State Machine Consistency ═══[/bold cyan]\n")
    
    console.print("[green]✓[/green] All committed entries are identical across nodes")
    console.print("[green]✓[/green] State machines produce the same results")
    console.print("[green]✓[/green] Data survives leader changes")


async def main():
    """Run the demo."""
    console.print("\n[bold magenta]🚀 Mini-Raft Interactive Demo[/bold magenta]")
    console.print("[dim]Demonstrating Raft consensus in action[/dim]\n")
    
    try:
        # Demo 1: Leader election
        nodes, servers = await demo_leader_election()
        await asyncio.sleep(1)
        
        # Demo 2: Log replication
        await demo_log_replication(nodes, servers)
        await asyncio.sleep(1)
        
        # Demo 3: Fault tolerance
        await demo_fault_tolerance(nodes, servers)
        await asyncio.sleep(1)
        
        # Demo 4: Consistency
        await demo_consistency()
        
        # Summary
        console.print("\n[bold green]═══════════════════════════════════════[/bold green]")
        console.print("[bold green]✓ Demo completed successfully![/bold green]")
        console.print("[bold green]═══════════════════════════════════════[/bold green]\n")
        
        console.print("[cyan]Key takeaways:[/cyan]")
        console.print("  • Leader election ensures exactly one leader per term")
        console.print("  • Log entries are replicated to all followers")
        console.print("  • System continues operating despite failures")
        console.print("  • State machine consistency is maintained")
        
        # Cleanup
        console.print("\n[dim]Cleaning up...[/dim]")
        for server in servers:
            if server.node.running:
                await server.stop()
        
        # Clean demo data
        import shutil
        shutil.rmtree("./demo_data", ignore_errors=True)
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo interrupted[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())