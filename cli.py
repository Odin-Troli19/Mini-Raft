"""
CLI for managing and monitoring Mini-Raft cluster.

Features:
- Start/stop cluster nodes
- Watch cluster state in real-time
- Submit client requests
- Chaos testing
"""

import asyncio
import json
import random
import sys
from pathlib import Path
from typing import List, Optional

import click
from aiohttp import ClientSession, ClientTimeout
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich import box

console = Console()


class ClusterMonitor:
    """Monitor and display cluster state."""
    
    def __init__(self, node_ports: List[int]):
        self.node_ports = node_ports
        self.base_url = "http://localhost"
    
    async def get_node_status(self, port: int) -> Optional[dict]:
        """Get status from a single node."""
        try:
            timeout = ClientTimeout(total=0.5)
            async with ClientSession() as session:
                async with session.get(
                    f"{self.base_url}:{port}/status",
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception:
            pass
        return None
    
    async def get_cluster_status(self) -> List[dict]:
        """Get status from all nodes."""
        tasks = [self.get_node_status(port) for port in self.node_ports]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        statuses = []
        for port, result in zip(self.node_ports, results):
            if isinstance(result, dict):
                statuses.append(result)
            else:
                statuses.append({
                    "node_id": f"node-{port}",
                    "state": "unreachable",
                    "term": 0,
                })
        
        return statuses
    
    def create_status_table(self, statuses: List[dict]) -> Table:
        """Create a rich table for cluster status."""
        table = Table(
            title="🚀 Mini-Raft Cluster Status",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan"
        )
        
        table.add_column("Node ID", style="yellow")
        table.add_column("State", style="bold")
        table.add_column("Term", justify="right")
        table.add_column("Commit Index", justify="right")
        table.add_column("Log Size", justify="right")
        table.add_column("Elections", justify="right")
        table.add_column("Committed", justify="right")
        
        for status in statuses:
            state = status.get("state", "unknown")
            
            # Color code states
            if state == "leader":
                state_display = f"[green bold]👑 {state.upper()}[/green bold]"
            elif state == "candidate":
                state_display = f"[yellow]🗳️  {state.upper()}[/yellow]"
            elif state == "follower":
                state_display = f"[blue]👤 {state.upper()}[/blue]"
            else:
                state_display = f"[red]❌ {state.upper()}[/red]"
            
            metrics = status.get("metrics", {})
            
            table.add_row(
                status.get("node_id", "unknown"),
                state_display,
                str(status.get("term", 0)),
                str(status.get("commit_index", 0)),
                str(status.get("log_size", 0)),
                str(metrics.get("leader_elections", 0)),
                str(metrics.get("log_entries_committed", 0)),
            )
        
        return table
    
    def create_cluster_info(self, statuses: List[dict]) -> Panel:
        """Create cluster summary panel."""
        leaders = sum(1 for s in statuses if s.get("state") == "leader")
        followers = sum(1 for s in statuses if s.get("state") == "follower")
        candidates = sum(1 for s in statuses if s.get("state") == "candidate")
        unreachable = sum(1 for s in statuses if s.get("state") == "unreachable")
        
        max_term = max((s.get("term", 0) for s in statuses), default=0)
        
        info = f"""
[cyan]Total Nodes:[/cyan] {len(statuses)}
[green]Leaders:[/green] {leaders}
[blue]Followers:[/blue] {followers}
[yellow]Candidates:[/yellow] {candidates}
[red]Unreachable:[/red] {unreachable}
[magenta]Current Term:[/magenta] {max_term}
        """
        
        return Panel(
            info.strip(),
            title="Cluster Overview",
            border_style="cyan"
        )
    
    async def watch(self, refresh_rate: float = 1.0):
        """Watch cluster status in real-time."""
        with Live(console=console, refresh_per_second=1/refresh_rate) as live:
            while True:
                statuses = await self.get_cluster_status()
                
                layout = Layout()
                layout.split_column(
                    Layout(self.create_cluster_info(statuses), size=10),
                    Layout(self.create_status_table(statuses))
                )
                
                live.update(layout)
                await asyncio.sleep(refresh_rate)


class ChaosTest:
    """Chaos testing utilities."""
    
    def __init__(self, node_ports: List[int]):
        self.node_ports = node_ports
        self.base_url = "http://localhost"
    
    async def kill_random_node(self) -> int:
        """Simulate killing a random node."""
        # In real implementation, this would stop the process
        # For now, we just log it
        port = random.choice(self.node_ports)
        console.print(f"[red]💀 Killing node on port {port}[/red]")
        return port
    
    async def partition_network(self, group1: List[int], group2: List[int]):
        """Simulate network partition."""
        console.print(f"[yellow]🔌 Creating network partition:[/yellow]")
        console.print(f"  Group 1: {group1}")
        console.print(f"  Group 2: {group2}")
    
    async def random_latency(self, min_ms: int = 50, max_ms: int = 500):
        """Add random network latency."""
        latency = random.randint(min_ms, max_ms)
        console.print(f"[yellow]⏱️  Adding {latency}ms network latency[/yellow]")
        await asyncio.sleep(latency / 1000.0)


@click.group()
def cli():
    """Mini-Raft cluster management CLI."""
    pass


@cli.command()
@click.option('--nodes', '-n', default=5, help='Number of nodes in cluster')
@click.option('--base-port', '-p', default=8000, help='Base port for first node')
@click.option('--data-dir', '-d', default='./data', help='Data directory')
def start(nodes: int, base_port: int, data_dir: str):
    """Start a Raft cluster."""
    console.print(f"[green]🚀 Starting Mini-Raft cluster with {nodes} nodes...[/green]")
    
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    
    # Generate node IDs
    node_ids = [f"node-{i}" for i in range(nodes)]
    
    # Create start script
    script_lines = ["#!/bin/bash", ""]
    
    for i, node_id in enumerate(node_ids):
        port = base_port + i
        peers = [nid for nid in node_ids if nid != node_id]
        peers_str = ",".join(peers)
        
        node_dir = data_path / node_id
        node_dir.mkdir(exist_ok=True)
        
        script_lines.append(
            f"python3 run_node.py --node-id {node_id} "
            f"--port {port} --peers {peers_str} "
            f"--storage-dir {node_dir} &"
        )
    
    script_lines.append("")
    script_lines.append("echo 'All nodes started'")
    script_lines.append("wait")
    
    script_path = Path("start_cluster.sh")
    script_path.write_text("\n".join(script_lines))
    script_path.chmod(0o755)
    
    console.print(f"[cyan]📝 Cluster configuration:[/cyan]")
    console.print(f"  Nodes: {nodes}")
    console.print(f"  Ports: {base_port} - {base_port + nodes - 1}")
    console.print(f"  Data directory: {data_path}")
    console.print(f"\n[yellow]Run: ./start_cluster.sh[/yellow]")


@cli.command()
@click.option('--base-port', '-p', default=8000, help='Base port for first node')
@click.option('--nodes', '-n', default=5, help='Number of nodes')
@click.option('--refresh', '-r', default=1.0, help='Refresh rate in seconds')
def watch(base_port: int, nodes: int, refresh: float):
    """Watch cluster status in real-time."""
    ports = [base_port + i for i in range(nodes)]
    monitor = ClusterMonitor(ports)
    
    try:
        asyncio.run(monitor.watch(refresh))
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped monitoring[/yellow]")


@cli.command()
@click.option('--port', '-p', default=8000, help='Node port to send request to')
@click.option('--key', '-k', required=True, help='Key')
@click.option('--value', '-v', help='Value (for set operation)')
@click.option('--op', type=click.Choice(['set', 'get', 'delete']), default='set')
async def request(port: int, key: str, value: Optional[str], op: str):
    """Send a client request to the cluster."""
    command = {"op": op, "key": key}
    if op == "set":
        if not value:
            console.print("[red]Error: --value required for set operation[/red]")
            sys.exit(1)
        command["value"] = value
    
    console.print(f"[cyan]Sending {op} request to port {port}...[/cyan]")
    
    try:
        timeout = ClientTimeout(total=5.0)
        async with ClientSession() as session:
            async with session.post(
                f"http://localhost:{port}/client/request",
                json=command,
                timeout=timeout
            ) as response:
                result = await response.json()
                
                if response.status == 200:
                    console.print(f"[green]✓ Success:[/green] {json.dumps(result, indent=2)}")
                else:
                    console.print(f"[red]✗ Error:[/red] {json.dumps(result, indent=2)}")
    
    except Exception as e:
        console.print(f"[red]✗ Request failed: {e}[/red]")


@cli.command()
@click.option('--base-port', '-p', default=8000, help='Base port')
@click.option('--nodes', '-n', default=5, help='Number of nodes')
@click.option('--operations', '-o', default=100, help='Number of operations')
def chaos(base_port: int, nodes: int, operations: int):
    """Run chaos tests on the cluster."""
    console.print(f"[red]☠️  Starting chaos test with {operations} operations...[/red]")
    
    ports = [base_port + i for i in range(nodes)]
    tester = ChaosTest(ports)
    
    async def run_chaos():
        for i in range(operations):
            # Random chaos operation
            action = random.choice(['kill', 'latency', 'partition'])
            
            if action == 'kill':
                await tester.kill_random_node()
            elif action == 'latency':
                await tester.random_latency()
            elif action == 'partition':
                mid = len(ports) // 2
                await tester.partition_network(ports[:mid], ports[mid:])
            
            await asyncio.sleep(random.uniform(0.5, 2.0))
        
        console.print("[green]✓ Chaos test completed[/green]")
    
    try:
        asyncio.run(run_chaos())
    except KeyboardInterrupt:
        console.print("\n[yellow]Chaos test interrupted[/yellow]")


@cli.command()
@click.option('--base-port', '-p', default=8000, help='Base port')
@click.option('--nodes', '-n', default=5, help='Number of nodes')
def status(base_port: int, nodes: int):
    """Get current cluster status."""
    ports = [base_port + i for i in range(nodes)]
    monitor = ClusterMonitor(ports)
    
    async def show_status():
        statuses = await monitor.get_cluster_status()
        console.print(monitor.create_cluster_info(statuses))
        console.print(monitor.create_status_table(statuses))
    
    asyncio.run(show_status())


if __name__ == '__main__':
    cli()
